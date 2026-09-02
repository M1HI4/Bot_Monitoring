from __future__ import annotations

import asyncio

from app.models.common import MetricName, TargetType
from app.models.config import TargetDefinition
from app.models.telemetry import MetricSnapshot, TargetSnapshot
from app.services.config.service import ConfigService
from app.services.prometheus.client import PrometheusClient
from app.services.prometheus.queries import (
    build_availability_query,
    get_metric_definition,
    is_metric_supported,
    list_supported_metrics,
)
from app.utils.exceptions import MetricUnavailableError, PrometheusRequestError
from app.utils.time import utc_now


class MonitoringService:
    def __init__(self, config_service: ConfigService, prometheus_client: PrometheusClient) -> None:
        self.config_service = config_service
        self.prometheus_client = prometheus_client

    def get_enabled_targets(self) -> list[TargetDefinition]:
        return [target for target in self.config_service.load_targets().targets if target.enabled]

    def get_targets_map(self) -> dict[str, TargetDefinition]:
        return {target.id: target for target in self.get_enabled_targets()}

    def get_target_by_id(self, target_id: str) -> TargetDefinition | None:
        return self.get_targets_map().get(target_id)

    def get_supported_metric_names(self, target_type: TargetType) -> list[MetricName]:
        return [definition.name for definition in list_supported_metrics(target_type)]

    def validate_metric_selection(self, target: TargetDefinition, metrics: list[MetricName]) -> None:
        invalid = [metric.value for metric in metrics if not is_metric_supported(metric, target.type)]
        if invalid:
            invalid_text = ", ".join(invalid)
            raise MetricUnavailableError(
                f"Для таргета {target.id} типа {target.type.value} недоступны метрики: {invalid_text}"
            )

    async def get_target_snapshot(
        self,
        target: TargetDefinition,
        metrics: list[MetricName] | None = None,
    ) -> TargetSnapshot:
        selected_metrics = metrics or self.get_supported_metric_names(target.type)
        self.validate_metric_selection(target=target, metrics=selected_metrics)

        availability_query = build_availability_query(target.prometheus, target.type)
        collected_at = utc_now()
        try:
            availability_value = await self.prometheus_client.query_value(availability_query)
            availability = None if availability_value is None else availability_value >= 1
        except PrometheusRequestError as exc:
            return TargetSnapshot(
                target=target,
                available=None,
                availability_query=availability_query,
                collected_at=collected_at,
                error=str(exc),
            )

        metric_tasks = [self._fetch_metric_snapshot(target=target, metric=metric) for metric in selected_metrics]
        snapshots = await asyncio.gather(*metric_tasks)
        return TargetSnapshot(
            target=target,
            available=availability,
            availability_query=availability_query,
            collected_at=collected_at,
            metrics={snapshot.metric: snapshot for snapshot in snapshots},
        )

    async def get_many_target_snapshots(
        self,
        targets: list[TargetDefinition],
        metrics_map: dict[str, list[MetricName]] | None = None,
    ) -> dict[str, TargetSnapshot]:
        results = await asyncio.gather(
            *[
                self.get_target_snapshot(target, metrics=(metrics_map or {}).get(target.id))
                for target in targets
            ]
        )
        return {snapshot.target.id: snapshot for snapshot in results}

    async def get_prometheus_health(self) -> tuple[bool, str]:
        return await self.prometheus_client.check_health()

    async def _fetch_metric_snapshot(self, target: TargetDefinition, metric: MetricName) -> MetricSnapshot:
        definition = get_metric_definition(metric)
        query = definition.query_builder(target.prometheus, target.type)
        collected_at = utc_now()
        try:
            value = await self.prometheus_client.query_value(query)
            if value is None:
                return MetricSnapshot(
                    metric=metric,
                    display_name=definition.display_name,
                    emoji=definition.emoji,
                    value=None,
                    unit=definition.unit,
                    available=False,
                    query=query,
                    collected_at=collected_at,
                    error="метрика недоступна",
                )
            return MetricSnapshot(
                metric=metric,
                display_name=definition.display_name,
                emoji=definition.emoji,
                value=value,
                unit=definition.unit,
                available=True,
                query=query,
                collected_at=collected_at,
            )
        except PrometheusRequestError as exc:
            return MetricSnapshot(
                metric=metric,
                display_name=definition.display_name,
                emoji=definition.emoji,
                value=None,
                unit=definition.unit,
                available=False,
                query=query,
                collected_at=collected_at,
                error=str(exc),
            )
