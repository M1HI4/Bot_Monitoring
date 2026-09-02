from __future__ import annotations

from dataclasses import dataclass

from app.services.alerts.service import AlertStateService, AlertingService
from app.services.config.service import ConfigService
from app.services.prometheus.client import PrometheusClient
from app.services.prometheus.service import MonitoringService
from app.services.subscriptions.service import SubscriptionService
from app.services.users.service import UsersService
from app.storage.yaml_storage import YamlStorage


@dataclass(slots=True)
class AppServices:
    config: ConfigService
    users: UsersService
    subscriptions: SubscriptionService
    prometheus: PrometheusClient
    monitoring: MonitoringService
    alert_state: AlertStateService
    alerting: AlertingService


def build_services(project_root) -> AppServices:
    storage = YamlStorage()
    config_service = ConfigService(project_root=project_root, storage=storage)
    users_service = UsersService(config_service=config_service)
    subscription_service = SubscriptionService(config_service=config_service)
    prometheus_client = PrometheusClient(config_service=config_service)
    monitoring_service = MonitoringService(config_service=config_service, prometheus_client=prometheus_client)
    alert_state_service = AlertStateService(config_service=config_service)
    alerting_service = AlertingService(
        config_service=config_service,
        users_service=users_service,
        subscription_service=subscription_service,
        monitoring_service=monitoring_service,
        alert_state_service=alert_state_service,
    )
    return AppServices(
        config=config_service,
        users=users_service,
        subscriptions=subscription_service,
        prometheus=prometheus_client,
        monitoring=monitoring_service,
        alert_state=alert_state_service,
        alerting=alerting_service,
    )
