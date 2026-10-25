import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class Period:
    """A range of dates, both ends inclusive."""
    start: date
    end: date


def dashboard_today(now: datetime | None = None) -> date:
    """Today's date in the dashboard's time zone, not the server's."""
    now = now or timezone.now()
    return now.astimezone(ZoneInfo(settings.DASHBOARD_TIMEZONE)).date()


def week_to_date(today: date) -> Period:
    """From this week's Monday to today."""
    return Period(today - timedelta(days=today.weekday()), today)


def month_to_date(today: date) -> Period:
    return Period(today.replace(day=1), today)


def previous_month_to_date(today: date) -> Period:
    """The previous month from the 1st to the same day of the month, clamped to the month's length."""
    last_of_previous = today.replace(day=1) - timedelta(days=1)
    day = min(today.day, last_of_previous.day)
    return Period(last_of_previous.replace(day=1), last_of_previous.replace(day=day))
