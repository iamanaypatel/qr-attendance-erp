"""
Timezone utilities for Dr. Virendra Swarup Memorial Trust Group of Institutions (VSGOI)
Centralizes Asia/Kolkata (IST = UTC+05:30) timezone logic across backend, APIs, and reporting.
"""

from datetime import datetime, date, time
from zoneinfo import ZoneInfo

# Authoritative timezone for institutions in India
INSTITUTION_TIMEZONE_NAME = "Asia/Kolkata"
IST = ZoneInfo(INSTITUTION_TIMEZONE_NAME)

def get_current_ist_datetime() -> datetime:
    """
    Returns current datetime normalized to Asia/Kolkata (IST) timezone.
    """
    return datetime.now(IST)

def get_current_ist_date() -> date:
    """
    Returns today's date in Asia/Kolkata (IST).
    Prevents midnight UTC rollover bugs where local midnight attendance falls on wrong date.
    """
    return datetime.now(IST).date()

def get_current_ist_time() -> time:
    """
    Returns current time in Asia/Kolkata (IST).
    Truncated to seconds for consistency in database Time columns.
    """
    now_dt = datetime.now(IST)
    return now_dt.time().replace(microsecond=0)

def format_time_ist(t: time | datetime | None, format_str: str = "%I:%M %p") -> str:
    """
    Formats a time or datetime into human-readable 12-hour AM/PM string (e.g. '09:15 AM').
    """
    if not t:
        return "-"
    if isinstance(t, datetime):
        # If timezone-aware or UTC, convert to IST
        if t.tzinfo is not None:
            t = t.astimezone(IST)
        return t.strftime(format_str)
    elif isinstance(t, time):
        return t.strftime(format_str)
    return str(t)
