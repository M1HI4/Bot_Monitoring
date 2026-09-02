from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"


class TargetType(str, Enum):
    PHYSICAL = "physical"
    BLADE = "blade"
    VM = "vm"
    CONTAINER = "container"


class MetricName(str, Enum):
    CPU = "cpu"
    RAM = "ram"
    DISK = "disk"
    TEMPERATURE = "temperature"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


SYSTEM_AVAILABILITY_METRIC = "availability"
