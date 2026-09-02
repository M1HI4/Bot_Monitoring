from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models.common import MetricName
from app.models.config import TargetDefinition


@dataclass(slots=True)
class MetricSnapshot:
    metric: MetricName
    display_name: str
    emoji: str
    value: float | None
    unit: str
    available: bool
    query: str
    collected_at: datetime
    error: str | None = None


@dataclass(slots=True)
class TargetSnapshot:
    target: TargetDefinition
    available: bool | None
    availability_query: str
    collected_at: datetime
    metrics: dict[MetricName, MetricSnapshot] = field(default_factory=dict)
    error: str | None = None
