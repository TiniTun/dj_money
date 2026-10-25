"""Factories for tests; not a test module itself."""
from django.contrib.auth.models import User

from .models import Account, AccountType, Currency, ExpenseCategory, Transaction


def create_user(username='u'):
    return User.objects.create(username=username)


def create_currency(code):
    return Currency.objects.create(code=code, name=code)


def create_account(user, currency, name='Card'):
    return Account.objects.create(
        user=user, name=name, currency=currency, balance=0,
        account_type=AccountType.objects.get_or_create(name='card')[0],
    )


def create_category(user, name, parent=None, is_spending=True):
    return ExpenseCategory.objects.create(user=user, name=name, parent_category=parent, is_spending=is_spending)


def create_transaction(account, amount, on, *, transaction_type='expense', category=None, currency=None,
                       place='', to_account=None):
    # original_amount is set so Transaction.save derives rate 1 instead of looking for an ExchangeRate
    return Transaction.objects.create(
        user=account.user, account=account, to_account=to_account, transaction_type=transaction_type,
        amount=amount, original_amount=amount, currency=currency or account.currency,
        original_currency=currency or account.currency,
        date=on, date_processing=on, category=category, place=place,
    )
