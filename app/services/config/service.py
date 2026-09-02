from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.models.config import (
    AlertStateFile,
    AlertsFile,
    RuntimeConfig,
    SubscriptionsFile,
    TargetsFile,
    UsersFile,
    model_to_dict,
)
from app.storage.yaml_storage import YamlStorage
from app.utils.exceptions import ConfigValidationError

ModelType = TypeVar("ModelType", bound=BaseModel)


class ConfigService:
    _env_pattern = re.compile(r"^\$\{([A-Z0-9_]+)\}$")

    def __init__(self, project_root: Path, storage: YamlStorage) -> None:
        self.project_root = project_root
        self.storage = storage
        self.base_config_path = self.project_root / "configs" / "config.yaml"

    def load_runtime_config(self) -> RuntimeConfig:
        return self._load_model(self.base_config_path, RuntimeConfig, "config.yaml")

    def load_targets(self) -> TargetsFile:
        return self._load_model(self.resolve_path(self.load_runtime_config().paths.targets_file), TargetsFile, "targets.yaml")

    def load_users(self) -> UsersFile:
        return self._load_model(self.resolve_path(self.load_runtime_config().paths.users_file), UsersFile, "users.yaml")

    def load_alerts(self) -> AlertsFile:
        return self._load_model(self.resolve_path(self.load_runtime_config().paths.alerts_file), AlertsFile, "alerts.yaml")

    def load_subscriptions(self) -> SubscriptionsFile:
        return self._load_model(
            self.resolve_path(self.load_runtime_config().paths.subscriptions_file),
            SubscriptionsFile,
            "subscriptions.yaml",
        )

    def load_alert_state(self) -> AlertStateFile:
        return self._load_model(
            self.resolve_path(self.load_runtime_config().paths.alert_state_file),
            AlertStateFile,
            "alert_state.yaml",
        )

    def save_users(self, users: UsersFile) -> None:
        path = self.resolve_path(self.load_runtime_config().paths.users_file)
        self.storage.write_yaml_atomic(path, model_to_dict(users))

    def save_subscriptions(self, subscriptions: SubscriptionsFile) -> None:
        path = self.resolve_path(self.load_runtime_config().paths.subscriptions_file)
        self.storage.write_yaml_atomic(path, model_to_dict(subscriptions))

    def save_alert_state(self, alert_state: AlertStateFile) -> None:
        path = self.resolve_path(self.load_runtime_config().paths.alert_state_file)
        self.storage.write_yaml_atomic(path, model_to_dict(alert_state))

    def ensure_runtime_files(self) -> None:
        config = self.load_runtime_config()
        self.storage.ensure_yaml_file(self.resolve_path(config.paths.subscriptions_file), model_to_dict(SubscriptionsFile()))
        self.storage.ensure_yaml_file(self.resolve_path(config.paths.alert_state_file), model_to_dict(AlertStateFile()))

    def validate_all(self) -> dict[str, int]:
        runtime = self.load_runtime_config()
        targets = self.load_targets()
        users = self.load_users()
        alerts = self.load_alerts()
        subscriptions = self.load_subscriptions()
        self.load_alert_state()
        return {
            "targets": len(targets.targets),
            "users": len(users.users),
            "alert_metrics": len(alerts.metrics),
            "subscriptions": len(subscriptions.subscriptions),
            "background_interval_seconds": runtime.app.background_check_interval_seconds,
        }

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    def _load_model(self, path: Path, model_type: type[ModelType], label: str) -> ModelType:
        raw = self._read_yaml(path, label)
        resolved = self._resolve_env(raw)
        try:
            return model_type.model_validate(resolved or {})
        except ValidationError as exc:
            raise ConfigValidationError(f"Configuration validation failed for {label}: {exc}") from exc

    def _read_yaml(self, path: Path, label: str) -> dict[str, Any]:
        try:
            data = self.storage.read_yaml(path, default={})
        except Exception as exc:
            raise ConfigValidationError(f"Unable to read {label}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigValidationError(f"Configuration file {label} must contain a YAML mapping at top level.")
        return data

    def _resolve_env(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._resolve_env(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_env(item) for item in value]
        if isinstance(value, str):
            match = self._env_pattern.fullmatch(value.strip())
            if match:
                return os.getenv(match.group(1), "")
        return value
