from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from app.models.common import MetricName, TargetType

MatcherMap = Mapping[str, str]

FILESYSTEM_EXCLUDE_REGEX = (
    "^(autofs|binfmt_misc|bpf|cgroup2?|configfs|debugfs|devpts|devtmpfs|fusectl|hugetlbfs|mqueue|"
    "nsfs|overlay|proc|pstore|rpc_pipefs|securityfs|selinuxfs|squashfs|sysfs|tmpfs|tracefs)$"
)


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    name: MetricName
    display_name: str
    emoji: str
    unit: str
    supported_target_types: tuple[TargetType, ...]
    description: str
    query_builder: Callable[[MatcherMap, TargetType], str]


def escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_label_matchers(matchers: MatcherMap, extra_equals: MatcherMap | None = None) -> str:
    merged: dict[str, str] = {}
    merged.update({key: value for key, value in matchers.items() if value})
    if extra_equals:
        merged.update({key: value for key, value in extra_equals.items() if value})
    return ",".join(f'{key}="{escape_label_value(value)}"' for key, value in merged.items())


def build_availability_query(matchers: MatcherMap, target_type: TargetType) -> str:
    if target_type == TargetType.CONTAINER:
        return f"max((time() - container_last_seen{{{build_label_matchers(matchers)}}}) < bool 120)"
    return f"max(up{{{build_label_matchers(matchers)}}})"


def build_cpu_query(matchers: MatcherMap, target_type: TargetType) -> str:
    if target_type == TargetType.CONTAINER:
        label_matchers = build_label_matchers(matchers)
        return f"sum(rate(container_cpu_usage_seconds_total{{{label_matchers}}}[5m])) * 100"
    label_matchers = build_label_matchers(matchers, {"mode": "idle"})
    return f"100 - (avg(rate(node_cpu_seconds_total{{{label_matchers}}}[5m])) * 100)"


def build_ram_query(matchers: MatcherMap, target_type: TargetType) -> str:
    if target_type == TargetType.CONTAINER:
        label_matchers = build_label_matchers(matchers)
        return (
            f"100 * (sum(container_memory_working_set_bytes{{{label_matchers}}}) / "
            f"clamp_min(sum(container_spec_memory_limit_bytes{{{label_matchers}}}), 1))"
        )
    label_matchers = build_label_matchers(matchers)
    return (
        f"(1 - (node_memory_MemAvailable_bytes{{{label_matchers}}} / "
        f"node_memory_MemTotal_bytes{{{label_matchers}}})) * 100"
    )


def build_disk_query(matchers: MatcherMap, target_type: TargetType) -> str:
    if target_type == TargetType.CONTAINER:
        label_matchers = build_label_matchers(matchers)
        return (
            f"100 * (sum(container_fs_usage_bytes{{{label_matchers}}}) / "
            f"clamp_min(sum(container_fs_limit_bytes{{{label_matchers}}}), 1))"
        )
    base_matchers = build_label_matchers(matchers)
    prefix = f"{base_matchers}," if base_matchers else ""
    return (
        "100 * (1 - ("
        f"sum(node_filesystem_avail_bytes{{{prefix}mountpoint=\"/\",fstype!~\"{FILESYSTEM_EXCLUDE_REGEX}\"}})"
        " / "
        f"sum(node_filesystem_size_bytes{{{prefix}mountpoint=\"/\",fstype!~\"{FILESYSTEM_EXCLUDE_REGEX}\"}})"
        "))"
    )


def build_temperature_query(matchers: MatcherMap, target_type: TargetType) -> str:
    return f"max(node_hwmon_temp_celsius{{{build_label_matchers(matchers)}}})"


METRIC_DEFINITIONS: dict[MetricName, MetricDefinition] = {
    MetricName.CPU: MetricDefinition(
        name=MetricName.CPU,
        display_name="CPU",
        emoji="⚙️",
        unit="percent",
        supported_target_types=(TargetType.PHYSICAL, TargetType.BLADE, TargetType.VM, TargetType.CONTAINER),
        description="Средняя загрузка CPU за последние 5 минут.",
        query_builder=build_cpu_query,
    ),
    MetricName.RAM: MetricDefinition(
        name=MetricName.RAM,
        display_name="RAM",
        emoji="🧠",
        unit="percent",
        supported_target_types=(TargetType.PHYSICAL, TargetType.BLADE, TargetType.VM, TargetType.CONTAINER),
        description="Использование оперативной памяти.",
        query_builder=build_ram_query,
    ),
    MetricName.DISK: MetricDefinition(
        name=MetricName.DISK,
        display_name="Disk",
        emoji="💽",
        unit="percent",
        supported_target_types=(TargetType.PHYSICAL, TargetType.BLADE, TargetType.VM, TargetType.CONTAINER),
        description="Использование корневой файловой системы.",
        query_builder=build_disk_query,
    ),
    MetricName.TEMPERATURE: MetricDefinition(
        name=MetricName.TEMPERATURE,
        display_name="Температура",
        emoji="🌡",
        unit="celsius",
        supported_target_types=(TargetType.PHYSICAL, TargetType.BLADE),
        description="Максимальная температура по метрике node_hwmon_temp_celsius.",
        query_builder=build_temperature_query,
    ),
}


def get_metric_definition(metric: MetricName) -> MetricDefinition:
    return METRIC_DEFINITIONS[metric]


def list_supported_metrics(target_type: TargetType) -> list[MetricDefinition]:
    return [definition for definition in METRIC_DEFINITIONS.values() if target_type in definition.supported_target_types]


def is_metric_supported(metric: MetricName, target_type: TargetType) -> bool:
    return target_type in METRIC_DEFINITIONS[metric].supported_target_types
