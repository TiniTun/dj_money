from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import TestCase

from .dashboard.categories import CategoryTree
from .dashboard.currency import RateBook, available_currencies
from .dashboard.periods import Period, dashboard_today, month_to_date, previous_month_to_date, week_to_date
from .dashboard.spending import Total, recent, spending_transactions, total_for, totals_by_category
from .models import ExchangeRate, ExpenseCategory
from .testing import create_account, create_category, create_currency, create_transaction, create_user


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


class SpendingTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.aud = create_currency('AUD')
        self.account = create_account(self.user, self.aud)
        self.savings = create_account(self.user, self.aud, name='Savings')
        self.october = Period(date(2026, 10, 1), date(2026, 10, 31))
        self.book = RateBook(['AUD'], until=date(2026, 10, 31))

    def spending(self):
        return spending_transactions(self.user, CategoryTree(self.user))

    def total(self):
        return total_for(self.spending(), self.october, 'AUD', self.book)

    def totals_by_category(self):
        return totals_by_category(self.spending(), self.october, 'AUD', self.book, CategoryTree(self.user))

    def test_only_spending_expenses_are_counted(self):
        food = create_category(self.user, 'Продукты')
        transfers = create_category(self.user, 'Переводы между своими', is_spending=False)
        on = date(2026, 10, 20)
        create_transaction(self.account, Decimal('-100'), on, category=food)
        create_transaction(self.account, Decimal('-50'), on, category=create_category(self.user, 'Карта', parent=transfers))
        create_transaction(self.account, Decimal('500'), on, transaction_type='income')
        create_transaction(self.account, Decimal('-30'), on, transaction_type='transfer', to_account=self.savings)
        create_transaction(create_account(create_user('other'), self.aud), Decimal('-999'), on)
        self.assertEqual(self.total(), Total(amount=Decimal('100'), unconverted=0))

    def test_positive_expense_counts_as_spending(self):
        create_transaction(self.account, Decimal('30'), date(2026, 10, 20))
        self.assertEqual(self.total().amount, Decimal('30'))

    def test_unconverted_are_counted_not_summed(self):
        kzt_account = create_account(self.user, create_currency('KZT'), name='Kaspi')
        create_transaction(kzt_account, Decimal('-4500'), date(2026, 10, 20))  # нет курса USD→KZT
        create_transaction(self.account, Decimal('0'), date(2026, 10, 20))
        self.assertEqual(self.total(), Total(amount=Decimal('0'), unconverted=2))

    def test_period_bounds_are_inclusive(self):
        for day in (date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 24), date(2026, 10, 25)):
            create_transaction(self.account, Decimal('-10'), day)
        total = total_for(self.spending(), Period(date(2026, 10, 1), date(2026, 10, 24)), 'AUD', self.book)
        self.assertEqual(total.amount, Decimal('20'))

    def test_categories_roll_up_to_root_and_uncategorized_is_last(self):
        food = create_category(self.user, 'Еда')
        cafe = create_category(self.user, 'Кафе', parent=food)
        transport = create_category(self.user, 'Транспорт')
        on = date(2026, 10, 20)
        create_transaction(self.account, Decimal('-200'), on, category=cafe)
        create_transaction(self.account, Decimal('-50'), on, category=food)
        create_transaction(self.account, Decimal('-100'), on, category=transport)
        create_transaction(self.account, Decimal('-300'), on)
        names = [(c.name, c.amount) for c in self.totals_by_category()]
        self.assertEqual(names, [('Еда', Decimal('250')), ('Транспорт', Decimal('100')), ('Без категории', Decimal('300'))])

    def test_category_outside_users_tree_is_its_own_root(self):
        foreign = create_category(create_user('other'), 'Чужая')
        create_transaction(self.account, Decimal('-70'), date(2026, 10, 20), category=foreign)
        totals = self.totals_by_category()
        self.assertEqual([(c.category_id, c.name, c.amount) for c in totals], [(foreign.id, 'Чужая', Decimal('70'))])

    def test_recent_is_today_and_yesterday(self):
        for day in (22, 23, 24):
            create_transaction(self.account, Decimal('-10'), date(2026, 10, day))
        self.assertEqual([t.date for t in recent(self.spending(), date(2026, 10, 24))], [date(2026, 10, 24), date(2026, 10, 23)])
