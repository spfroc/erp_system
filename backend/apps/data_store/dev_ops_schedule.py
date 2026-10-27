"""下次运行时间计算。"""

from __future__ import annotations

from datetime import datetime, timedelta


def _match_cron_field(field: str, value: int) -> bool:
    field = (field or "*").strip()
    if field == "*":
        return True
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("*/"):
            try:
                step = int(part[2:])
            except ValueError:
                return False
            if step > 0 and value % step == 0:
                return True
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            try:
                start, end = int(start_s), int(end_s)
            except ValueError:
                return False
            if start <= value <= end:
                return True
            continue
        try:
            if int(part) == value:
                return True
        except ValueError:
            return False
    return False


def cron_matches(expr: str, when: datetime) -> bool:
    parts = (expr or "").split()
    if len(parts) != 5:
        return False
    minute, hour, day, month, weekday = parts
    # cron weekday: 0=Sun .. 6=Sat; Python weekday: 0=Mon .. 6=Sun
    cron_weekday = (when.weekday() + 1) % 7
    return (
        _match_cron_field(minute, when.minute)
        and _match_cron_field(hour, when.hour)
        and _match_cron_field(day, when.day)
        and _match_cron_field(month, when.month)
        and _match_cron_field(weekday, cron_weekday)
    )


def next_run_at(*, schedule_type: str, interval_seconds: int | None, cron_expr: str, now: datetime, last_run_at: datetime | None = None) -> datetime | None:
    if schedule_type == "manual":
        return None
    if schedule_type == "interval":
        seconds = int(interval_seconds or 0)
        if seconds <= 0:
            return None
        base = last_run_at or now
        candidate = base + timedelta(seconds=seconds)
        if candidate <= now:
            return now + timedelta(seconds=seconds)
        return candidate
    if schedule_type == "cron":
        cursor = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        for _ in range(60 * 24 * 8):
            if cron_matches(cron_expr, cursor):
                return cursor
            cursor += timedelta(minutes=1)
        return None
    return None
