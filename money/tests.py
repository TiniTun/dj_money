from datetime import date
from decimal import Decimal
from io import StringIO
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .forms import DateCurrencyExchangeForm
from .models import Account, AccountType, Currency, ExchangeRate, PlaceCategoryMapping, Transaction
from .tasks import update_exchange_rates_daily, upload_exchange_rates_task
from .testing import create_account, create_category, create_currency, create_transaction, create_user
from .utils import frankfurter_api
from .utils.exchange_rates import sync_exchange_rates


def api_response(rows):
    response = mock.Mock()
    response.json.return_value = rows
    response.raise_for_status.return_value = None
    return response


def http_error(status_code):
    return requests.HTTPError(response=mock.Mock(status_code=status_code))


class FrankfurterApiTests(TestCase):
    @mock.patch('money.utils.frankfurter_api.requests.get')
    def test_rates_groups_rows_by_date(self, get):
        get.return_value = api_response([
            {'date': '2026-10-16', 'base': 'USD', 'quote': 'KZT', 'rate': 452.64},
            {'date': '2026-10-16', 'base': 'USD', 'quote': 'RUB', 'rate': 81.5},
            {'date': '2026-10-19', 'base': 'USD', 'quote': 'KZT', 'rate': 452.62},
        ])

        result = frankfurter_api.rates(start_date=date(2026, 10, 16), end_date=date(2026, 10, 19), symbols=['USD', 'KZT', 'RUB'])

        self.assertEqual(result, {
            date(2026, 10, 16): {'KZT': 452.64, 'RUB': 81.5},
            date(2026, 10, 19): {'KZT': 452.62},
        })
        params = get.call_args.kwargs['params']
        self.assertEqual(params['quotes'], 'KZT,RUB')  # base is not requested as a quote
        self.assertEqual((params['from'], params['to']), ('2026-10-16', '2026-10-19'))

    @mock.patch('money.utils.frankfurter_api.requests.get')
    def test_supported_currencies(self, get):
        get.return_value = api_response([{'iso_code': 'KZT', 'name': 'Tenge'}, {'iso_code': 'USD', 'name': 'US Dollar'}])

        self.assertEqual(frankfurter_api.supported_currencies(), {'KZT', 'USD'})

    def test_only_network_errors_and_5xx_are_transient(self):
        self.assertTrue(frankfurter_api.is_transient_error(requests.ConnectionError()))
        self.assertTrue(frankfurter_api.is_transient_error(requests.Timeout()))
        self.assertTrue(frankfurter_api.is_transient_error(http_error(503)))
        self.assertFalse(frankfurter_api.is_transient_error(http_error(422)))
        self.assertFalse(frankfurter_api.is_transient_error(ValueError('bad date')))


class SyncExchangeRatesTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar')
        self.kzt = Currency.objects.create(code='KZT', name='Tenge')

    def sync(self, rate, overwrite):
        with mock.patch('money.utils.frankfurter_api.supported_currencies', return_value={'USD', 'KZT'}), \
                mock.patch('money.utils.frankfurter_api.requests.get') as get:
            get.return_value = api_response([{'date': '2026-10-16', 'base': 'USD', 'quote': 'KZT', 'rate': rate}])
            return sync_exchange_rates(date(2026, 10, 16), date(2026, 10, 16), overwrite=overwrite)

    def test_repeated_sync_does_not_duplicate_and_overwrites(self):
        self.sync(450, overwrite=True)
        self.sync(452.64, overwrite=True)

        rate = ExchangeRate.objects.get()
        self.assertEqual(rate.exchange_rate, Decimal('452.64'))

    def test_without_overwrite_existing_rate_is_kept(self):
        ExchangeRate.objects.create(source_currency=self.usd, target_currency=self.kzt, exchange_rate=440, date=date(2026, 10, 16))

        self.sync(452.64, overwrite=False)

        self.assertEqual(ExchangeRate.objects.get().exchange_rate, Decimal('440'))

    @mock.patch('money.utils.frankfurter_api.rates', return_value={})
    @mock.patch('money.utils.frankfurter_api.supported_currencies', return_value={'USD', 'KZT'})
    def test_currency_unknown_to_api_is_skipped(self, supported, rates):
        Currency.objects.create(code='XBT', name='Bitcoin')

        with self.assertLogs('money.utils.exchange_rates', 'WARNING') as logs:
            sync_exchange_rates(date(2026, 10, 16), date(2026, 10, 16))

        self.assertEqual(rates.call_args.kwargs['symbols'], ['KZT'])
        self.assertIn('XBT', logs.output[0])

    def test_missing_base_currency_raises_clear_error(self):
        self.usd.delete()

        with self.assertRaisesMessage(ValueError, 'Base currency USD is missing'):
            sync_exchange_rates(date(2026, 10, 16), date(2026, 10, 16))


class ExchangeRateTaskTests(TestCase):
    @mock.patch('money.tasks.sync_exchange_rates', return_value=8)
    def test_daily_task_refreshes_last_week(self, sync):
        update_exchange_rates_daily()

        start_date, end_date = sync.call_args.args
        self.assertEqual(end_date, date.today())
        self.assertEqual((end_date - start_date).days, 7)

    @mock.patch('money.tasks.sync_exchange_rates', side_effect=requests.ConnectionError())
    def test_network_error_is_retried(self, sync):
        with mock.patch.object(update_exchange_rates_daily, 'retry', side_effect=RuntimeError('retried')) as retry:
            with self.assertRaisesMessage(RuntimeError, 'retried'):
                update_exchange_rates_daily()
        retry.assert_called_once()

    @mock.patch('money.tasks.sync_exchange_rates', side_effect=http_error(422))
    def test_client_error_is_not_retried(self, sync):
        with mock.patch.object(upload_exchange_rates_task, 'retry') as retry:
            with self.assertRaises(requests.HTTPError):
                upload_exchange_rates_task('2026-10-16', '2026-10-16')
        retry.assert_not_called()


class TransactionExchangeRateTests(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar')
        self.kzt = Currency.objects.create(code='KZT', name='Tenge')
        self.user = User.objects.create(username='u')
        self.account = Account.objects.create(
            user=self.user, name='Kaspi', account_type=AccountType.objects.create(name='card'),
            currency=self.kzt, balance=0,
        )

    def create_transaction(self, on_date):
        return Transaction.objects.create(
            user=self.user, transaction_type='expense', amount=Decimal('4500'),
            currency=self.kzt, original_currency=self.usd, date=on_date, date_processing=on_date,
            account=self.account,
        )

    def test_weekend_transaction_uses_last_published_rate(self):
        ExchangeRate.objects.create(source_currency=self.usd, target_currency=self.kzt, exchange_rate=440, date=date(2026, 10, 15))
        ExchangeRate.objects.create(source_currency=self.usd, target_currency=self.kzt, exchange_rate=450, date=date(2026, 10, 16))
        ExchangeRate.objects.create(source_currency=self.usd, target_currency=self.kzt, exchange_rate=460, date=date(2026, 10, 19))

        tx = self.create_transaction(date(2026, 10, 18))  # Sunday

        self.assertEqual(Decimal(tx.exchange_rate), Decimal('450'))
        self.assertEqual(Decimal(tx.original_amount), Decimal('10'))

    def test_stale_rate_is_used_but_logged(self):
        ExchangeRate.objects.create(source_currency=self.usd, target_currency=self.kzt, exchange_rate=450, date=date(2026, 9, 1))

        with self.assertLogs('money.models', 'WARNING') as logs:
            tx = self.create_transaction('2026-10-18')  # imports pass dates as strings

        self.assertEqual(Decimal(tx.exchange_rate), Decimal('450'))
        self.assertIn('stale', logs.output[0])

    def test_missing_rate_is_logged(self):
        with self.assertLogs('money.models', 'WARNING') as logs:
            tx = self.create_transaction(date(2026, 10, 18))

        self.assertEqual(Decimal(tx.exchange_rate), Decimal('1'))
        self.assertIn('No exchange rate', logs.output[0])


class DateCurrencyExchangeFormTests(TestCase):
    def setUp(self):
        Currency.objects.create(code='KZT', name='Tenge')

    def form(self, extra_currency):
        return DateCurrencyExchangeForm(data={
            'start_date': '2026-10-16', 'end_date': '2026-10-16', 'extra_currency': extra_currency, 'only_extra': True,
        })

    def test_extra_currency_is_normalized(self):
        form = self.form(' kzt ')

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['extra_currency'], 'KZT')

    def test_unknown_extra_currency_is_rejected(self):
        form = self.form('xbt')

        self.assertFalse(form.is_valid())
        self.assertIn('extra_currency', form.errors)


class ApplyCategoryRulesCommandTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.account = create_account(self.user, create_currency('AUD'))
        self.transfers = create_category(self.user, 'Переводы между своими', is_spending=False)
        self.shops = create_category(self.user, 'Supermarkets')
        PlaceCategoryMapping.objects.create(user=self.user, place_keyword='Transfer to xx', category=self.transfers)
        PlaceCategoryMapping.objects.create(user=self.user, place_keyword='Woolworths', category=self.shops)

    def expense(self, place, category=None, transaction_type='expense'):
        # place is not part of the transaction's unique key, so each one needs its own amount
        amount = -10 - Transaction.objects.count()
        return create_transaction(self.account, amount, date(2026, 10, 20), place=place, category=category,
                                  transaction_type=transaction_type,
                                  to_account=self.account if transaction_type == 'transfer' else None)

    def run_command(self, *args):
        out = StringIO()
        call_command('apply_category_rules', *args, stdout=out)
        return out.getvalue()

    def category_of(self, transaction):
        transaction.refresh_from_db()
        return transaction.category

    def test_uncategorized_expense_gets_rule_category(self):
        tx = self.expense('Transfer to xx1234 CommBank app')

        self.run_command()

        self.assertEqual(self.category_of(tx), self.transfers)

    def test_dry_run_reports_change_without_saving(self):
        tx = self.expense('Transfer to xx1234 CommBank app')

        out = self.run_command('--dry-run')

        self.assertIsNone(self.category_of(tx))
        self.assertIn('Transfer to xx1234 CommBank app', out)
        self.assertIn('Переводы между своими', out)

    def test_existing_category_is_kept_without_overwrite(self):
        tx = self.expense('Woolworths Yeronga', category=self.transfers)

        out = self.run_command()
        self.assertEqual(self.category_of(tx), self.transfers)
        self.assertIn('1 expenses already have another category', out)

        self.run_command('--overwrite')
        self.assertEqual(self.category_of(tx), self.shops)

    def test_category_option_applies_only_that_categorys_rules(self):
        transfer = self.expense('Transfer to xx1234 CommBank app')
        shop = self.expense('Woolworths Yeronga')

        self.run_command('--category', 'переводы между своими')

        self.assertEqual(self.category_of(transfer), self.transfers)
        self.assertIsNone(self.category_of(shop))

    def test_unknown_category_is_an_error(self):
        with self.assertRaisesMessage(Exception, 'Nope'):
            self.run_command('--category', 'Nope')

    def test_income_transfers_and_other_users_rules_are_ignored(self):
        income = self.expense('Transfer to xx1234 CommBank app', transaction_type='income')
        transfer = self.expense('Transfer to xx1234 CommBank app', transaction_type='transfer')
        other = create_user('other')
        other_tx = create_transaction(create_account(other, self.account.currency), -10, date(2026, 10, 20),
                                      place='Transfer to xx9999 CommBank app')

        self.run_command()

        self.assertIsNone(self.category_of(income))
        self.assertIsNone(self.category_of(transfer))
        self.assertIsNone(self.category_of(other_tx))
