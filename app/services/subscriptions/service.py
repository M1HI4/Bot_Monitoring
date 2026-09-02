from __future__ import annotations

from app.models.common import MetricName
from app.models.config import SubscriptionsFile, TargetSubscription, UserSubscription
from app.services.config.service import ConfigService
from app.utils.time import to_iso8601, utc_now


class SubscriptionService:
    def __init__(self, config_service: ConfigService) -> None:
        self.config_service = config_service

    def get_all(self) -> SubscriptionsFile:
        return self.config_service.load_subscriptions()

    def get_user_subscription(self, user_id: int) -> UserSubscription | None:
        subscriptions_file = self.get_all()
        return next((item for item in subscriptions_file.subscriptions if item.user_id == user_id), None)

    def get_total_target_subscriptions(self) -> int:
        return sum(len(item.targets) for item in self.get_all().subscriptions)

    def upsert_target_metrics(self, user_id: int, target_id: str, metrics: list[MetricName]) -> UserSubscription:
        subscriptions_file = self.get_all()
        normalized_metrics = list(dict.fromkeys(metrics))
        user_subscription = next((item for item in subscriptions_file.subscriptions if item.user_id == user_id), None)
        if user_subscription is None:
            user_subscription = UserSubscription(user_id=user_id, targets=[])
            subscriptions_file.subscriptions.append(user_subscription)

        current = next((item for item in user_subscription.targets if item.target_id == target_id), None)
        if current is None:
            user_subscription.targets.append(
                TargetSubscription(
                    target_id=target_id,
                    metrics=normalized_metrics,
                    updated_at=to_iso8601(utc_now()),
                )
            )
        else:
            current.metrics = normalized_metrics
            current.updated_at = to_iso8601(utc_now())

        updated = SubscriptionsFile(version=subscriptions_file.version, subscriptions=subscriptions_file.subscriptions)
        self.config_service.save_subscriptions(updated)
        return next(item for item in updated.subscriptions if item.user_id == user_id)

    def upsert_many(self, user_id: int, mapping: dict[str, list[MetricName]]) -> UserSubscription:
        for target_id, metrics in mapping.items():
            self.upsert_target_metrics(user_id=user_id, target_id=target_id, metrics=metrics)
        return self.get_user_subscription(user_id) or UserSubscription(user_id=user_id, targets=[])

    def remove_target_subscription(self, user_id: int, target_id: str) -> bool:
        subscriptions_file = self.get_all()
        user_subscription = next((item for item in subscriptions_file.subscriptions if item.user_id == user_id), None)
        if user_subscription is None:
            return False
        new_targets = [item for item in user_subscription.targets if item.target_id != target_id]
        if len(new_targets) == len(user_subscription.targets):
            return False
        user_subscription.targets = new_targets
        subscriptions_file.subscriptions = [item for item in subscriptions_file.subscriptions if item.user_id != user_id]
        if new_targets:
            subscriptions_file.subscriptions.append(user_subscription)
        updated = SubscriptionsFile(version=subscriptions_file.version, subscriptions=subscriptions_file.subscriptions)
        self.config_service.save_subscriptions(updated)
        return True

    def clear_user(self, user_id: int) -> bool:
        subscriptions_file = self.get_all()
        filtered = [item for item in subscriptions_file.subscriptions if item.user_id != user_id]
        if len(filtered) == len(subscriptions_file.subscriptions):
            return False
        updated = SubscriptionsFile(version=subscriptions_file.version, subscriptions=filtered)
        self.config_service.save_subscriptions(updated)
        return True
