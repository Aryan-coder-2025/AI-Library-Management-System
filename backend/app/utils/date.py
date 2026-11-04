"""
Date and timezone utility functions.
Standardizes system-wide date evaluation against UTC to eliminate host-local timezone drift.
"""
from datetime import date, datetime, timedelta, timezone


def get_utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def get_utc_today() -> date:
    """
    Returns the current date evaluated strictly at UTC (calendar day at UTC).
    Standardizes overdue loan evaluation, fine calculations, and notification sweeps.
    """
    return datetime.now(timezone.utc).date()


def get_library_timezone(tz_name: str = "Asia/Kolkata") -> timezone:
    """
    Resolves a timezone object for the institutional timezone.
    Attempts IANA ZoneInfo lookup first, falling back to fixed UTC offset
    (e.g. UTC+05:30 for Asia/Kolkata / IST) on environments without tzdata.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        if tz_name in ("Asia/Kolkata", "IST"):
            return timezone(timedelta(hours=5, minutes=30))
        if tz_name == "UTC":
            return timezone.utc
        return timezone(timedelta(hours=5, minutes=30))

