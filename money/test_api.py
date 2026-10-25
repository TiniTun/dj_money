import json
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from .models import BankExportFiles, BankSource, ExchangeRate, Transaction
from .testing import create_account, create_category, create_currency, create_transaction, create_user

TODAY = date(2026, 10, 21)  # Wednesday
RATES_DATE = date(2026, 10, 18)


class DashboardApiTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client.force_login(self.user)
        usd, self.aud, self.kzt = create_currency('USD'), create_currency('AUD'), create_currency('KZT')
        ExchangeRate.objects.create(source_currency=usd, target_currency=self.kzt, exchange_rate=450, date=RATES_DATE)
        ExchangeRate.objects.create(source_currency=usd, target_currency=self.aud, exchange_rate='1.5', date=RATES_DATE)
        self.account = create_account(self.user, self.kzt)
        patcher = mock.patch('money.api.dashboard_today', return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_endpoints_require_login(self):
        self.client.logout()
        for url in ['/api/me', '/api/dashboard/summary', '/api/dashboard/categories',
                    '/api/dashboard/transactions/recent', '/api/dashboard/status']:
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_me_returns_default_currency(self):
        self.assertEqual(
            self.client.get('/api/me').json(),
            {'username': 'u', 'default_currency': 'AUD', 'currencies': ['AUD', 'KZT', 'USD']},
        )

    def test_me_falls_back_to_usd_when_default_currency_has_no_rates(self):
        ExchangeRate.objects.filter(target_currency=self.aud).delete()
        body = self.client.get('/api/me').json()
        self.assertEqual(body['default_currency'], 'USD')
        self.assertIn('USD', body['currencies'])

    def test_summary_for_user_without_transactions(self):
        body = self.client.get('/api/dashboard/summary').json()
        self.assertEqual((body['today'], body['month'], body['previous_month_to_date'], body['unconverted']),
                         (0, 0, 0, 0))
        self.assertEqual((body['currency'], body['as_of']), ('AUD', '2026-10-21'))

    def test_summary_converts_to_requested_currency(self):
        create_transaction(self.account, -4500, TODAY)
        self.assertEqual(self.client.get('/api/dashboard/summary?currency=AUD').json()['today'], 15.0)
        self.assertEqual(self.client.get('/api/dashboard/summary?currency=KZT').json()['today'], 4500.0)

    def test_summary_periods(self):
        create_transaction(self.account, -450, TODAY)
        create_transaction(self.account, -900, date(2026, 10, 19))  # Monday of this week
        create_transaction(self.account, -1350, date(2026, 10, 5))
        create_transaction(self.account, -4500, date(2026, 9, 10))  # inside previous month to date
        create_transaction(self.account, -9000, date(2026, 9, 25))  # after the 21st: not compared
        body = self.client.get('/api/dashboard/summary?currency=KZT').json()
        self.assertEqual(
            (body['today'], body['week'], body['month'], body['previous_month_to_date']),
            (450, 1350, 2700, 4500),
        )

    def test_summary_counts_unconverted(self):
        create_transaction(self.account, -450, TODAY)
        create_transaction(self.account, -10, TODAY, currency=create_currency('EUR'))  # no EUR rate
        body = self.client.get('/api/dashboard/summary?currency=KZT').json()
        self.assertEqual((body['today'], body['unconverted']), (450, 1))

    def test_unknown_currency_is_rejected(self):
        for url in ['/api/dashboard/summary', '/api/dashboard/categories', '/api/dashboard/transactions/recent']:
            response = self.client.get(f'{url}?currency=XXX')
            self.assertEqual(response.status_code, 400, url)
            self.assertEqual(response.json(), {'detail': 'Неизвестная валюта'})

    def test_categories_group_by_root_and_put_uncategorized_last(self):
        food = create_category(self.user, 'Еда')
        cafe = create_category(self.user, 'Кафе', parent=food)
        taxi = create_category(self.user, 'Такси')
        create_transaction(self.account, -450, TODAY, category=cafe)
        create_transaction(self.account, -900, TODAY, category=food)
        create_transaction(self.account, -2250, TODAY, category=taxi)
        create_transaction(self.account, -4500, TODAY)
        create_transaction(self.account, -450, date(2026, 10, 1), category=taxi)
        body = self.client.get('/api/dashboard/categories?currency=KZT&period=week').json()
        self.assertEqual((body['currency'], body['period'], body['start'], body['end']),
                         ('KZT', 'week', '2026-10-19', '2026-10-21'))
        self.assertEqual(body['items'], [
            {'id': taxi.id, 'name': 'Такси', 'amount': 2250.0},
            {'id': food.id, 'name': 'Еда', 'amount': 1350.0},
            {'id': None, 'name': 'Без категории', 'amount': 4500.0},
        ])
        month = self.client.get('/api/dashboard/categories?currency=KZT').json()
        self.assertEqual((month['period'], month['start']), ('month', '2026-10-01'))
        self.assertEqual(month['items'][0], {'id': taxi.id, 'name': 'Такси', 'amount': 2700.0})

    def test_categories_reject_unknown_period(self):
        self.assertEqual(self.client.get('/api/dashboard/categories?period=year').status_code, 422)

    def test_recent_transactions(self):
        food = create_category(self.user, 'Еда')
        create_transaction(self.account, -4500, TODAY, category=food, place='Кофейня')
        create_transaction(self.account, -450, TODAY - timedelta(days=1), place='')
        create_transaction(self.account, -450, TODAY - timedelta(days=2), place='old')
        create_transaction(self.account, 450, TODAY, transaction_type='income')
        body = self.client.get('/api/dashboard/transactions/recent?currency=AUD').json()
        self.assertEqual(body['currency'], 'AUD')
        self.assertEqual(len(body['items']), 2)
        first, second = body['items']
        self.assertEqual(first, {
            'id': first['id'], 'date': '2026-10-21', 'title': 'Кофейня', 'category': 'Еда',
            'amount': 15.0, 'original_amount': 4500.0, 'original_currency': 'KZT',
        })
        self.assertEqual((second['title'], second['category'], second['amount']), ('', None, 1.5))

    def test_recent_title_falls_back_to_comment_and_unconverted_amount_is_null(self):
        tx = create_transaction(self.account, -10, TODAY, currency=create_currency('EUR'), place='')
        tx.comment = 'Подарок'
        tx.save()
        item = self.client.get('/api/dashboard/transactions/recent').json()['items'][0]
        self.assertEqual((item['title'], item['amount'], item['original_amount'], item['original_currency']),
                         ('Подарок', None, 10.0, 'EUR'))

    def test_recent_transaction_without_currency(self):
        tx = create_transaction(self.account, -450, TODAY, place='Наличные')
        Transaction.objects.filter(pk=tx.pk).update(currency=None)
        response = self.client.get('/api/dashboard/transactions/recent')
        self.assertEqual(response.status_code, 200)
        item = response.json()['items'][0]
        self.assertEqual((item['title'], item['amount'], item['original_currency']), ('Наличные', None, None))

    def test_status(self):
        create_transaction(self.account, -450, TODAY - timedelta(days=5))
        create_transaction(self.account, -450, TODAY)  # uncategorized this month
        source = BankSource.objects.update_or_create(code='bcc', defaults={'name': 'BCC'})[0]
        BankExportFiles.objects.create(user=self.user, source=source, status=BankExportFiles.Status.FAILED)
        body = self.client.get('/api/dashboard/status').json()
        self.assertEqual(body['accounts'], [{'name': 'Card', 'last_date': '2026-10-21', 'days': 0, 'level': 'ok'}])
        self.assertEqual(body['rates'], {'last_date': '2026-10-18', 'level': 'ok'})
        self.assertEqual(body['uncategorized'], {'count': 2, 'level': 'warn'})
        self.assertEqual([item['source'] for item in body['failed_imports']], ['BCC'])
        self.assertEqual(body['stuck_pending'], 0)

    def test_status_without_problems(self):
        body = self.client.get('/api/dashboard/status').json()
        self.assertEqual(body['uncategorized'], {'count': 0, 'level': 'ok'})
        self.assertEqual((body['accounts'], body['failed_imports']), ([], []))

    def test_stuck_pending_uses_current_time(self):
        source = BankSource.objects.update_or_create(code='bcc', defaults={'name': 'BCC'})[0]
        file = BankExportFiles.objects.create(user=self.user, source=source, status=BankExportFiles.Status.PENDING)
        BankExportFiles.objects.filter(pk=file.pk).update(uploaded_at=datetime.now(timezone.utc) - timedelta(hours=2))
        self.assertEqual(self.client.get('/api/dashboard/status').json()['stuck_pending'], 1)

    def test_other_users_data_is_not_returned(self):
        other = create_user('other')
        other_account = create_account(other, self.kzt, name='Other')
        create_transaction(other_account, -4500, TODAY, place='Чужое')
        self.assertEqual(self.client.get('/api/dashboard/summary').json()['today'], 0)
        self.assertEqual(self.client.get('/api/dashboard/transactions/recent').json()['items'], [])
        self.assertEqual(self.client.get('/api/dashboard/categories').json()['items'], [])
        self.assertEqual(self.client.get('/api/dashboard/status').json()['accounts'], [])

    def test_openapi_schema_is_exported(self):
        out = StringIO()
        call_command('export_openapi_schema', api='money.api.api', indent=2, stdout=out)
        committed = json.loads((settings.BASE_DIR / 'frontend' / 'openapi.json').read_text())
        self.assertEqual(json.loads(out.getvalue()), committed, 'Run export_openapi_schema and npm run gen:api')


class FrontendRoutingTests(TestCase):
    def test_root_is_served_by_frontend_not_django(self):
        self.assertEqual(self.client.get('/').status_code, 404)
        self.assertEqual(self.client.get('/money/').status_code, 200)
