from typing import Literal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.security import django_auth

from money.dashboard.categories import CategoryTree
from money.dashboard.currency import BASE_CODE, RateBook, available_currencies
from money.dashboard.periods import (
    Period, dashboard_today, month_to_date, previous_month_to_date, week_to_date,
)
from money.dashboard.spending import recent, spending_transactions, spent, total_for, totals_by_category
from money.dashboard.status import (
    account_freshness, failed_imports, rates_status, stuck_pending_count, uncategorized_count,
)
from money.schemas import (
    AccountStatusOut, CategoriesOut, CategoryOut, FailedImportOut, MeOut, RatesOut, RecentOut,
    RecentTransactionOut, StatusOut, SummaryOut, UncategorizedOut,
)

api = NinjaAPI(title='dj_money', auth=django_auth, docs_decorator=staff_member_required, urls_namespace='api')


def money(value) -> float:
    return round(float(value), 2)


def checked_currency(currency: str) -> str:
    if currency not in available_currencies():
        raise HttpError(400, 'Неизвестная валюта')
    return currency


def user_context(request):
    """What every dashboard endpoint starts from: today, the user's spending, and the rates."""
    today = dashboard_today()
    tree = CategoryTree(request.user)
    book = RateBook(available_currencies(), until=today)
    return today, tree, book, spending_transactions(request.user, tree)


@api.get('/me', response=MeOut)
def me(request):
    currencies = available_currencies()
    default = settings.DASHBOARD_DEFAULT_CURRENCY
    return {
        'username': request.user.get_username(),
        'default_currency': default if default in currencies else BASE_CODE,
        'currencies': currencies,
    }


@api.get('/dashboard/summary', response=SummaryOut)
def summary(request, currency: str = settings.DASHBOARD_DEFAULT_CURRENCY):
    currency = checked_currency(currency)
    today, tree, book, transactions = user_context(request)
    month = total_for(transactions, month_to_date(today), currency, book)
    return {
        'currency': currency,
        'as_of': today,
        'today': money(total_for(transactions, Period(today, today), currency, book).amount),
        'week': money(total_for(transactions, week_to_date(today), currency, book).amount),
        'month': money(month.amount),
        'previous_month_to_date': money(total_for(transactions, previous_month_to_date(today), currency, book).amount),
        'unconverted': month.unconverted,
    }


@api.get('/dashboard/categories', response=CategoriesOut)
def categories(request, currency: str = settings.DASHBOARD_DEFAULT_CURRENCY,
               period: Literal['week', 'month'] = 'month'):
    currency = checked_currency(currency)
    today, tree, book, transactions = user_context(request)
    bounds = week_to_date(today) if period == 'week' else month_to_date(today)
    totals = totals_by_category(transactions, bounds, currency, book, tree)
    return {
        'currency': currency,
        'period': period,
        'start': bounds.start,
        'end': bounds.end,
        'items': [CategoryOut(id=total.category_id, name=total.name, amount=money(total.amount)) for total in totals],
    }


@api.get('/dashboard/transactions/recent', response=RecentOut)
def recent_transactions(request, currency: str = settings.DASHBOARD_DEFAULT_CURRENCY):
    currency = checked_currency(currency)
    today, tree, book, transactions = user_context(request)
    items = []
    for tx in recent(transactions, today):
        converted = spent(tx, currency, book)
        items.append(RecentTransactionOut(
            id=tx.id,
            date=tx.date,
            title=tx.place or tx.comment,
            category=tx.category.name if tx.category else None,
            amount=None if converted is None else money(converted),
            original_amount=money(abs(tx.amount)),
            original_currency=tx.currency.code if tx.currency else None,
        ))
    return {'currency': currency, 'items': items}


@api.get('/dashboard/status', response=StatusOut)
def status(request):
    today = dashboard_today()
    transactions = spending_transactions(request.user, CategoryTree(request.user))
    rates = rates_status(today)
    uncategorized = uncategorized_count(transactions, month_to_date(today))
    return {
        'accounts': [AccountStatusOut(**vars(account)) for account in account_freshness(request.user, today)],
        'rates': RatesOut(last_date=rates.last_date, level=rates.level),
        'uncategorized': UncategorizedOut(count=uncategorized, level='warn' if uncategorized else 'ok'),
        'failed_imports': [FailedImportOut(**vars(item)) for item in failed_imports(request.user)],
        'stuck_pending': stuck_pending_count(request.user, timezone.now()),
    }
