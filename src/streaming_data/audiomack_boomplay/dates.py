from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def dates_inclusive(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end date must not be before start date")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def latest_completed_week(now: datetime | None = None, timezone: str = "Africa/Lagos") -> tuple[date, date]:
    zone = ZoneInfo(timezone)
    local_now = now.astimezone(zone) if now and now.tzinfo else (now.replace(tzinfo=zone) if now else datetime.now(zone))
    # Thursday is weekday 3. Always choose the Thursday before the current Saturday run.
    days_since_thursday = (local_now.weekday() - 3) % 7
    if days_since_thursday == 0:
        days_since_thursday = 7
    end = local_now.date() - timedelta(days=days_since_thursday)
    return end - timedelta(days=6), end


def validate_reporting_week(start: date) -> tuple[date, date]:
    if start.weekday() != 4:
        raise ValueError("week_start_date must be a Friday")
    return start, start + timedelta(days=6)


def expected_filename(platform: str, play_date: date) -> str:
    stamp = play_date.strftime("%Y%m%d")
    if platform == "audiomack":
        return f"audiomack_streams_{stamp}.csv.asc"
    if platform == "boomplay":
        return f"Boomplay_NG_{stamp}.csv"
    raise ValueError(f"Unsupported platform: {platform}")
