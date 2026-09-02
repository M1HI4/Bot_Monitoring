from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from app.models.common import MetricName, SYSTEM_AVAILABILITY_METRIC
from app.models.config import AlertStateFile, AlertStateRecord, MetricAlertConfig, TargetDefinition, UserDefinition
from app.models.telemetry import MetricSnapshot, TargetSnapshot
from app.services.config.service import ConfigService
from app.services.prometheus.service import MonitoringService
from app.services.subscriptions.service import SubscriptionService
from app.services.users.service import UsersService
from app.utils.formatting import format_alert_message, format_recovery_message
from app.utils.time import parse_iso8601, to_iso8601, utc_now

logger = logging.getLogger(__name__)


class AlertStateService:
    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service

    def load(self) -> AlertStateFile:
        return self.config_service.load_alert_state()

    def save(self, alert_state: AlertStateFile) -> None:
        self.config_service.save_alert_state(alert_state)

    def get_or_create(
        self,
        alert_state: AlertStateFile,
        *,
        user_id: int,
        target_id: str,
        metric: str,
    ) -> AlertStateRecord:
        for item in alert_state.alerts:
            if item.user_id == user_id and item.target_id == target_id and item.metric == metric:
                return item
        record = AlertStateRecord(user_id=user_id, target_id=target_id, metric=metric)
        alert_state.alerts.append(record)
        return record


class AlertingService:
    def __init__(
        self,
        *,
        config_service: ConfigService,
        users_service: UsersService,
        subscription_service: SubscriptionService,
        monitoring_service: MonitoringService,
        alert_state_service: AlertStateService,
    ) -> None:
        self.config_service = config_service
        self.users_service = users_service
        self.subscription_service = subscription_service
        self.monitoring_service = monitoring_service
        self.alert_state_service = alert_state_service
        self._task: asyncio.Task | None = None

    def start(self, bot: Bot) -> asyncio.Task:
        self._task = asyncio.create_task(self._run(bot), name="alerting-worker")
        return self._task

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            logger.info("Alert worker cancelled.")
        self._task = None

    async def _run(self, bot: Bot) -> None:
        while True:
            interval = 30
            try:
                await self.process_cycle(bot)
                interval = self.config_service.load_runtime_config().app.background_check_interval_seconds
            except Exception as exc:
                logger.exception("Alert processing cycle failed: %s", exc)
                try:
                    interval = self.config_service.load_runtime_config().app.background_check_interval_seconds
                except Exception:
                    interval = 30
            await asyncio.sleep(interval)

    async def process_cycle(self, bot: Bot) -> None:
        runtime = self.config_service.load_runtime_config()
        targets = {target.id: target for target in self.monitoring_service.get_enabled_targets()}
        alerts_config = self.config_service.load_alerts()
        users = {user.user_id: user for user in self.users_service.list_users(enabled_only=True)}
        subscriptions = self.subscription_service.get_all()
        state_file = self.alert_state_service.load()

        snapshot_cache: dict[str, TargetSnapshot] = {}
        for user_subscription in subscriptions.subscriptions:
            user = users.get(user_subscription.user_id)
            if user is None:
                continue
            for target_subscription in user_subscription.targets:
                target = targets.get(target_subscription.target_id)
                if target is None:
                    continue
                if target.id not in snapshot_cache:
                    snapshot_cache[target.id] = await self.monitoring_service.get_target_snapshot(target)
                snapshot = snapshot_cache[target.id]

                if alerts_config.settings.availability_alerts.enabled:
                    await self._evaluate_availability(
                        bot=bot,
                        state_file=state_file,
                        user=user,
                        target=target,
                        snapshot=snapshot,
                        repeat_interval=alerts_config.settings.availability_alerts.repeat_interval_seconds
                        or alerts_config.settings.repeat_interval_seconds
                        or runtime.app.default_alert_repeat_interval_seconds,
                    )

                for metric in target_subscription.metrics:
                    metric_config = alerts_config.metrics.get(metric)
                    if metric_config is None or not metric_config.enabled:
                        continue
                    threshold = metric_config.thresholds.get(target.type)
                    if threshold is None:
                        continue
                    metric_snapshot = snapshot.metrics.get(metric)
                    await self._evaluate_metric_threshold(
                        bot=bot,
                        state_file=state_file,
                        user=user,
                        target=target,
                        metric=metric,
                        metric_config=metric_config,
                        metric_snapshot=metric_snapshot,
                        threshold=threshold,
                        repeat_interval=metric_config.repeat_interval_seconds
                        or alerts_config.settings.repeat_interval_seconds
                        or runtime.app.default_alert_repeat_interval_seconds,
                    )

        self.alert_state_service.save(state_file)

    async def _evaluate_availability(
        self,
        *,
        bot: Bot,
        state_file: AlertStateFile,
        user: UserDefinition,
        target: TargetDefinition,
        snapshot: TargetSnapshot,
        repeat_interval: int,
    ) -> None:
        if snapshot.available is None:
            return

        record = self.alert_state_service.get_or_create(
            state_file,
            user_id=user.user_id,
            target_id=target.id,
            metric=SYSTEM_AVAILABILITY_METRIC,
        )
        now = utc_now()
        if snapshot.available is False:
            was_active = record.active
            should_send = self._should_send(record, repeat_interval, now)
            record.active = True
            record.threshold = 1
            record.last_value = 0
            record.severity = "critical"
            record.deduplicated = not should_send
            record.recovered_at = None
            if should_send:
                message = format_alert_message(
                    target_name=target.name,
                    target_type=target.type.value,
                    metric_name=SYSTEM_AVAILABILITY_METRIC,
                    current_value="target down",
                    threshold="target up",
                    repeated=was_active and record.last_sent_at is not None,
                )
                await self._send_message(bot, user.chat_id, message)
                record.first_triggered_at = to_iso8601(now) if not was_active else (record.first_triggered_at or to_iso8601(now))
                record.last_sent_at = to_iso8601(now)
                record.last_message = message
            return

        if record.active:
            message = format_recovery_message(
                target_name=target.name,
                target_type=target.type.value,
                metric_name=SYSTEM_AVAILABILITY_METRIC,
                current_value="target up",
            )
            await self._send_message(bot, user.chat_id, message)
            record.active = False
            record.deduplicated = False
            record.recovered_at = to_iso8601(now)
            record.last_value = 1
            record.last_message = message

    async def _evaluate_metric_threshold(
        self,
        *,
        bot: Bot,
        state_file: AlertStateFile,
        user: UserDefinition,
        target: TargetDefinition,
        metric: MetricName,
        metric_config: MetricAlertConfig,
        metric_snapshot: MetricSnapshot | None,
        threshold: float,
        repeat_interval: int,
    ) -> None:
        if metric_snapshot is None or not metric_snapshot.available or metric_snapshot.value is None:
            return

        record = self.alert_state_service.get_or_create(
            state_file,
            user_id=user.user_id,
            target_id=target.id,
            metric=metric.value,
        )
        now = utc_now()
        breach = self._compare(metric_snapshot.value, threshold, metric_config.comparator)
        if breach:
            was_active = record.active
            should_send = self._should_send(record, repeat_interval, now)
            record.active = True
            record.threshold = threshold
            record.last_value = metric_snapshot.value
            record.severity = metric_config.severity.value
            record.deduplicated = not should_send
            record.recovered_at = None
            if should_send:
                message = format_alert_message(
                    target_name=target.name,
                    target_type=target.type.value,
                    metric_name=metric.value,
                    current_value=self._format_value(metric_snapshot.value, metric_snapshot.unit),
                    threshold=self._format_value(threshold, metric_snapshot.unit),
                    repeated=was_active and record.last_sent_at is not None,
                )
                await self._send_message(bot, user.chat_id, message)
                record.first_triggered_at = to_iso8601(now) if not was_active else (record.first_triggered_at or to_iso8601(now))
                record.last_sent_at = to_iso8601(now)
                record.last_message = message
            return

        if record.active:
            message = format_recovery_message(
                target_name=target.name,
                target_type=target.type.value,
                metric_name=metric.value,
                current_value=self._format_value(metric_snapshot.value, metric_snapshot.unit),
            )
            await self._send_message(bot, user.chat_id, message)
            record.active = False
            record.deduplicated = False
            record.recovered_at = to_iso8601(now)
            record.last_value = metric_snapshot.value
            record.last_message = message

    async def _send_message(self, bot: Bot, chat_id: int, text: str) -> None:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            logger.warning("Unable to send alert to chat_id=%s: %s", chat_id, exc)

    def _should_send(self, record: AlertStateRecord, repeat_interval: int, now) -> bool:
        if not record.active or not record.last_sent_at:
            return True
        last_sent = parse_iso8601(record.last_sent_at)
        if last_sent is None:
            return True
        return (now - last_sent).total_seconds() >= repeat_interval

    def _compare(self, value: float, threshold: float, comparator: str) -> bool:
        if comparator == "lt":
            return value < threshold
        return value > threshold

    def _format_value(self, value: float, unit: str) -> str:
        if unit == "percent":
            return f"{value:.1f} %"
        if unit == "celsius":
            return f"{value:.1f} °C"
        return f"{value:.1f} {unit}".strip()
