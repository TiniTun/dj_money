from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from .dashboard.categories import CategoryTree
from .dashboard.currency import RateBook, available_currencies
from .dashboard.periods import Period, dashboard_today, month_to_date, previous_month_to_date, week_to_date
from .models import ExchangeRate, ExpenseCategory
from .testing import create_category, create_currency, create_user


class CategoryTreeTests(TestCase):
    def setUp(self):
        self.user = create_user()

    def test_children_of_not_spending_category_are_excluded(self):
        transfers = create_category(self.user, 'Переводы между своими', is_spending=False)
        child = create_category(self.user, 'Оплата карты', parent=transfers)
        create_category(self.user, 'Продукты')
        self.assertEqual(CategoryTree(self.user).excluded_ids(), {transfers.id, child.id})

    def test_root_of_walks_up_to_top_level(self):
        food = create_category(self.user, 'Еда')
        cafe = create_category(self.user, 'Кафе', parent=food)
        coffee = create_category(self.user, 'Кофе', parent=cafe)
        self.assertEqual(CategoryTree(self.user).root_of(coffee.id), food)

    def test_category_cycle_does_not_hang(self):
        a = create_category(self.user, 'A')
        b = create_category(self.user, 'B', parent=a)
        ExpenseCategory.objects.filter(pk=a.pk).update(parent_category=b)
        tree = CategoryTree(self.user)
        self.assertIn(tree.root_of(a.id), {a, b})
        self.assertEqual(tree.excluded_ids(), set())


class PeriodTests(TestCase):
    def test_dashboard_today_uses_brisbane_time(self):
        now = datetime(2026, 10, 23, 15, 0, tzinfo=timezone.utc)
        self.assertEqual(dashboard_today(now), date(2026, 10, 24))

    def test_week_starts_on_monday(self):
        self.assertEqual(week_to_date(date(2026, 10, 25)), Period(date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual(week_to_date(date(2026, 10, 19)), Period(date(2026, 10, 19), date(2026, 10, 19)))

    def test_month_to_date(self):
        self.assertEqual(month_to_date(date(2026, 10, 24)), Period(date(2026, 10, 1), date(2026, 10, 24)))

    def test_previous_month_to_date_clamps_and_wraps_year(self):
        self.assertEqual(previous_month_to_date(date(2026, 3, 31)), Period(date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(previous_month_to_date(date(2024, 3, 30)), Period(date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(previous_month_to_date(date(2026, 1, 15)), Period(date(2025, 12, 1), date(2025, 12, 15)))


class RateBookTests(TestCase):
    def setUp(self):
        usd, kzt, aud = create_currency('USD'), create_currency('KZT'), create_currency('AUD')
        ExchangeRate.objects.create(source_currency=usd, target_currency=kzt, exchange_rate=450, date=date(2026, 10, 16))
        ExchangeRate.objects.create(source_currency=usd, target_currency=aud, exchange_rate=Decimal('1.5'), date=date(2026, 10, 16))

    def test_cross_rate_uses_last_rate_on_or_before_date(self):
        book = RateBook(['KZT', 'AUD'], until=date(2026, 10, 18))
        self.assertEqual(book.convert(Decimal('-4500'), 'KZT', 'AUD', date(2026, 10, 18)), Decimal('-15'))

    def test_usd_has_rate_one(self):
        book = RateBook(['AUD'], until=date(2026, 10, 18))
        self.assertEqual(book.convert(Decimal('10'), 'USD', 'AUD', date(2026, 10, 18)), Decimal('15'))
        self.assertEqual(book.convert(Decimal('15'), 'AUD', 'USD', date(2026, 10, 18)), Decimal('10'))

    def test_same_currency_needs_no_rate(self):
        book = RateBook([], until=date(2026, 10, 18))
        self.assertEqual(book.convert(Decimal('7'), 'TRY', 'TRY', date(2020, 1, 1)), Decimal('7'))

    def test_missing_rate_returns_none(self):
        book = RateBook(['KZT', 'AUD'], until=date(2026, 10, 18))
        self.assertIsNone(book.convert(Decimal('100'), 'KZT', 'AUD', date(2026, 10, 15)))

    def test_available_currencies_are_usd_plus_quoted(self):
        self.assertEqual(available_currencies(), ['AUD', 'KZT', 'USD'])
