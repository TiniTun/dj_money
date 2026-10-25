from datetime import date, datetime

from ninja import Schema

from money.dashboard.status import Level


class MeOut(Schema):
    username: str
    default_currency: str
    currencies: list[str]


class SummaryOut(Schema):
    currency: str
    as_of: date
    today: float
    week: float
    month: float
    previous_month_to_date: float
    unconverted: int


class CategoryOut(Schema):
    id: int | None
    name: str
    amount: float


class CategoriesOut(Schema):
    currency: str
    period: str
    start: date
    end: date
    items: list[CategoryOut]


class RecentTransactionOut(Schema):
    id: int
    date: date
    title: str
    category: str | None
    amount: float | None
    original_amount: float
    original_currency: str | None


class RecentOut(Schema):
    currency: str
    items: list[RecentTransactionOut]


class AccountStatusOut(Schema):
    name: str
    last_date: date
    days: int
    level: Level


class RatesOut(Schema):
    last_date: date | None
    level: Level


class UncategorizedOut(Schema):
    count: int
    level: Level


class FailedImportOut(Schema):
    source: str
    uploaded_at: datetime


class StatusOut(Schema):
    accounts: list[AccountStatusOut]
    rates: RatesOut
    uncategorized: UncategorizedOut
    failed_imports: list[FailedImportOut]
    stuck_pending: int
