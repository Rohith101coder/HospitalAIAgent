from datetime import datetime, date, time
import pytz
from app.core.config import settings


def get_hospital_tz():
    """Retrieve hospital timezone object."""
    return pytz.timezone(settings.HOSPITAL_TIMEZONE)


def now_hospital() -> datetime:
    """Current datetime in hospital timezone."""
    tz = get_hospital_tz()
    return datetime.now(tz)


def now_utc() -> datetime:
    """Current UTC datetime."""
    return datetime.utcnow()


def to_hospital_tz(dt: datetime) -> datetime:
    """Convert any datetime (assumed UTC if naive) to hospital timezone."""
    tz = get_hospital_tz()
    if dt.tzinfo is None:
        # Naive datetime from DB stored as UTC
        dt = pytz.utc.localize(dt)
    return dt.astimezone(tz)


def hospital_to_utc(dt: datetime) -> datetime:
    """Convert hospital localized/naive datetime to naive UTC datetime for DB storage."""
    tz = get_hospital_tz()
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt.astimezone(pytz.utc).replace(tzinfo=None)


def format_slot_time(start_dt: datetime, end_dt: datetime) -> str:
    """Format slot datetime into human-friendly string in hospital timezone."""
    local_start = to_hospital_tz(start_dt)
    local_end = to_hospital_tz(end_dt)
    return f"{local_start.strftime('%I:%M %p')} - {local_end.strftime('%I:%M %p')}"


def format_date_str(dt: datetime) -> str:
    """Format date string YYYY-MM-DD in hospital timezone."""
    local_dt = to_hospital_tz(dt)
    return local_dt.strftime("%Y-%m-%d")

