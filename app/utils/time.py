from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso8601(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def format_datetime(value: datetime | str | None, timezone_name: str = "Europe/Moscow") -> str:
    if value is None:
        return "неизвестно"
    if isinstance(value, str):
        parsed = parse_iso8601(value)
        if parsed is None:
            return "неизвестно"
        value = parsed
    return value.astimezone(ZoneInfo(timezone_name)).strftime("%d.%m.%Y %H:%M:%S")
