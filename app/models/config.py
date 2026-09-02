from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.common import AlertSeverity, MetricName, Role, TargetType


class TelegramConfig(BaseModel):
    token: str = Field(min_length=1)


class PrometheusConfig(BaseModel):
    base_url: str = Field(min_length=1)
    timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)


class AppPathConfig(BaseModel):
    targets_file: str = "configs/targets.yaml"
    users_file: str = "configs/users.yaml"
    alerts_file: str = "configs/alerts.yaml"
    subscriptions_file: str = "configs/subscriptions.yaml"
    alert_state_file: str = "runtime/alert_state.yaml"


class ApplicationConfig(BaseModel):
    name: str = "telegram-monitor-bot"
    environment: str = "production"
    log_level: str = "INFO"
    private_only: bool = True
    reload_configs_each_request: bool = True
    background_check_interval_seconds: int = Field(default=30, ge=5)
    default_alert_repeat_interval_seconds: int = Field(default=600, ge=30)
    timezone: str = "Europe/Moscow"


class RuntimeConfig(BaseModel):
    telegram: TelegramConfig
    prometheus: PrometheusConfig
    app: ApplicationConfig = Field(default_factory=ApplicationConfig)
    paths: AppPathConfig = Field(default_factory=AppPathConfig)


class TargetDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    type: TargetType
    description: str = Field(min_length=1)
    prometheus: dict[str, str]
    enabled: bool = True

    @field_validator("id", "name", "description")
    @classmethod
    def strip_string(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be empty.")
        return cleaned

    @field_validator("prometheus")
    @classmethod
    def validate_prometheus(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("Prometheus matcher map must not be empty.")
        return {str(key).strip(): str(item).strip() for key, item in value.items() if str(item).strip()}


class TargetsFile(BaseModel):
    version: int = 1
    targets: list[TargetDefinition] = Field(default_factory=list)

    @field_validator("targets")
    @classmethod
    def ensure_unique_targets(cls, value: list[TargetDefinition]) -> list[TargetDefinition]:
        target_ids = [target.id for target in value]
        duplicates = {item for item in target_ids if target_ids.count(item) > 1}
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate target ids found: {duplicate_list}")
        return value


class UserDefinition(BaseModel):
    user_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    username: str | None = None
    role: Role = Role.USER
    enabled: bool = True

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class UsersFile(BaseModel):
    version: int = 1
    users: list[UserDefinition] = Field(default_factory=list)

    @field_validator("users")
    @classmethod
    def ensure_unique_users(cls, value: list[UserDefinition]) -> list[UserDefinition]:
        user_ids = [user.user_id for user in value]
        duplicates = {item for item in user_ids if user_ids.count(item) > 1}
        if duplicates:
            duplicate_list = ", ".join(str(item) for item in sorted(duplicates))
            raise ValueError(f"Duplicate user ids found: {duplicate_list}")
        return value


class AvailabilityAlertConfig(BaseModel):
    enabled: bool = True
    severity: AlertSeverity = AlertSeverity.CRITICAL
    repeat_interval_seconds: int | None = Field(default=None, ge=30)


class AlertSettingsConfig(BaseModel):
    repeat_interval_seconds: int = Field(default=600, ge=30)
    availability_alerts: AvailabilityAlertConfig = Field(default_factory=AvailabilityAlertConfig)


class MetricAlertConfig(BaseModel):
    enabled: bool = True
    comparator: str = "gt"
    unit: str = Field(min_length=1)
    severity: AlertSeverity = AlertSeverity.WARNING
    repeat_interval_seconds: int | None = Field(default=None, ge=30)
    thresholds: dict[TargetType, float]

    @field_validator("comparator")
    @classmethod
    def validate_comparator(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"gt", "lt"}:
            raise ValueError("Comparator must be 'gt' or 'lt'.")
        return cleaned

    @model_validator(mode="after")
    def validate_thresholds(self) -> "MetricAlertConfig":
        if not self.thresholds:
            raise ValueError("Thresholds must not be empty.")
        return self


class AlertsFile(BaseModel):
    version: int = 1
    settings: AlertSettingsConfig = Field(default_factory=AlertSettingsConfig)
    metrics: dict[MetricName, MetricAlertConfig] = Field(default_factory=dict)


class TargetSubscription(BaseModel):
    target_id: str = Field(min_length=1)
    metrics: list[MetricName]
    updated_at: str | None = None

    @field_validator("metrics")
    @classmethod
    def normalize_metrics(cls, value: list[MetricName]) -> list[MetricName]:
        ordered_unique = list(dict.fromkeys(value))
        if not ordered_unique:
            raise ValueError("Target subscription must contain at least one metric.")
        return ordered_unique


class UserSubscription(BaseModel):
    user_id: int = Field(gt=0)
    targets: list[TargetSubscription] = Field(default_factory=list)

    @field_validator("targets")
    @classmethod
    def ensure_unique_target_ids(cls, value: list[TargetSubscription]) -> list[TargetSubscription]:
        target_ids = [target.target_id for target in value]
        duplicates = {item for item in target_ids if target_ids.count(item) > 1}
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"Duplicate target subscriptions found: {duplicate_list}")
        return value


class SubscriptionsFile(BaseModel):
    version: int = 1
    subscriptions: list[UserSubscription] = Field(default_factory=list)

    @field_validator("subscriptions")
    @classmethod
    def ensure_unique_subscription_users(cls, value: list[UserSubscription]) -> list[UserSubscription]:
        user_ids = [subscription.user_id for subscription in value]
        duplicates = {item for item in user_ids if user_ids.count(item) > 1}
        if duplicates:
            duplicate_list = ", ".join(str(item) for item in sorted(duplicates))
            raise ValueError(f"Duplicate subscription users found: {duplicate_list}")
        return value


class AlertStateRecord(BaseModel):
    user_id: int = Field(gt=0)
    target_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    active: bool = False
    deduplicated: bool = False
    first_triggered_at: str | None = None
    last_sent_at: str | None = None
    recovered_at: str | None = None
    last_value: float | None = None
    threshold: float | None = None
    severity: str | None = None
    last_message: str | None = None


class AlertStateFile(BaseModel):
    version: int = 1
    alerts: list[AlertStateRecord] = Field(default_factory=list)

    @field_validator("alerts")
    @classmethod
    def ensure_unique_records(cls, value: list[AlertStateRecord]) -> list[AlertStateRecord]:
        seen: set[tuple[int, str, str]] = set()
        for item in value:
            key = (item.user_id, item.target_id, item.metric)
            if key in seen:
                raise ValueError(f"Duplicate alert state entry found for key={key}.")
            seen.add(key)
        return value


def model_to_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)
