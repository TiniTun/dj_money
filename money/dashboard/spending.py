from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import QuerySet

from money.models import Transaction

from .categories import CategoryTree
from .currency import RateBook
from .periods import Period

UNCATEGORIZED = 'Без категории'


@dataclass
class Total:
    amount: Decimal
    unconverted: int  # transactions left out of the amount: zero sum or no exchange rate


@dataclass
class CategoryTotal:
    category_id: int | None
    name: str
    amount: Decimal


def spending_transactions(user: User, tree: CategoryTree) -> QuerySet[Transaction]:
    """The user's expenses outside the categories that are not spending; no category counts as spending."""
    return (
        Transaction.objects.filter(user=user, transaction_type='expense')
        .exclude(category_id__in=tree.excluded_ids())
        .select_related('currency', 'category')
    )


def spent(tx: Transaction, currency: str, book: RateBook) -> Decimal | None:
    """The size of a spending in the target currency; None if it cannot be counted."""
    if not tx.amount or tx.currency is None:
        return None
    return book.convert(abs(tx.amount), tx.currency.code, currency, tx.date)


def total_for(transactions: QuerySet[Transaction], period: Period, currency: str, book: RateBook) -> Total:
    amount, unconverted = Decimal(0), 0
    for tx in transactions.filter(date__range=(period.start, period.end)):
        value = spent(tx, currency, book)
        if value is None:
            unconverted += 1
        else:
            amount += value
    return Total(amount, unconverted)


def totals_by_category(transactions: QuerySet[Transaction], period: Period, currency: str, book: RateBook,
                       tree: CategoryTree) -> list[CategoryTotal]:
    """Spending per top-level category, largest first; uncategorized goes last. Uncounted transactions are skipped."""
    amounts = defaultdict(Decimal)
    roots = {}
    uncategorized = None
    for tx in transactions.filter(date__range=(period.start, period.end)):
        value = spent(tx, currency, book)
        if value is None:
            continue
        if tx.category is None:
            uncategorized = (uncategorized or Decimal(0)) + value
            continue
        # a category outside the user's tree (legacy data) is its own root
        root = tree.root_of(tx.category_id) if tx.category_id in tree.categories else tx.category
        roots[root.id] = root
        amounts[root.id] += value
    totals = [CategoryTotal(root_id, roots[root_id].name, amount) for root_id, amount in amounts.items()]
    totals.sort(key=lambda total: total.amount, reverse=True)
    if uncategorized is not None:
        totals.append(CategoryTotal(None, UNCATEGORIZED, uncategorized))
    return totals


def recent(transactions: QuerySet[Transaction], today: date) -> list[Transaction]:
    """Today's and yesterday's spending, newest first."""
    return list(transactions.filter(date__range=(today - timedelta(days=1), today)).order_by('-date', '-id'))
