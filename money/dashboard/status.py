from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from django.contrib.auth.models import User
from django.db.models import Max, QuerySet

from money.models import STALE_RATE_AFTER, BankExportFiles, BankSource, ExchangeRate, Transaction

from .periods import Period

FRESH_DAYS = 3
STALE_DAYS = 10
ACTIVE_ACCOUNT_DAYS = 180
PENDING_STUCK_AFTER = timedelta(hours=1)

Level = Literal['ok', 'warn', 'bad']


@dataclass
class AccountFreshness:
    name: str
    last_date: date
    days: int
    level: Level


@dataclass
class RatesStatus:
    last_date: date | None
    level: Level


@dataclass
class FailedImport:
    source: str
    uploaded_at: datetime


def freshness_level(days: int) -> Level:
    if days <= FRESH_DAYS:
        return 'ok'
    if days <= STALE_DAYS:
        return 'warn'
    return 'bad'


def account_freshness(user: User, today: date) -> list[AccountFreshness]:
    """Days since the last transaction of any type, for accounts active in the last ACTIVE_ACCOUNT_DAYS."""
    accounts = (
        user.account_set.annotate(last_date=Max('transaction__date'))
        .filter(last_date__gte=today - timedelta(days=ACTIVE_ACCOUNT_DAYS))
        .order_by('name')
    )
    result = []
    for account in accounts:
        days = (today - account.last_date).days
        result.append(AccountFreshness(account.name, account.last_date, days, freshness_level(days)))
    return result


def rates_status(today: date) -> RatesStatus:
    last = ExchangeRate.objects.aggregate(last=Max('date'))['last']
    if last is None or today - last > STALE_RATE_AFTER:
        return RatesStatus(last, 'bad')
    return RatesStatus(last, 'ok')


def uncategorized_count(transactions: QuerySet[Transaction], month: Period) -> int:
    return transactions.filter(category__isnull=True, date__range=(month.start, month.end)).count()


def failed_imports(user: User) -> list[FailedImport]:
    """Sources whose latest statement of the user failed; a later successful upload clears it."""
    result = []
    for source in BankSource.objects.all():
        latest = (
            BankExportFiles.objects.filter(user=user, source=source).order_by('-uploaded_at', '-id').first()
        )
        if latest is not None and latest.status == BankExportFiles.Status.FAILED:
            result.append(FailedImport(source.name, latest.uploaded_at))
    return result


def stuck_pending_count(user: User, now: datetime) -> int:
    return BankExportFiles.objects.filter(
        user=user, status=BankExportFiles.Status.PENDING, uploaded_at__lt=now - PENDING_STUCK_AFTER,
    ).count()
