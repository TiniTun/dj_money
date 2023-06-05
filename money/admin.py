from django.contrib import admin

from .models import IncomeCategory
from .models import ExpenseCategory
from .models import Currency
from .models import BankCard
from .models import AccountType
from .models import Account
from .models import Transaction
from .models import BankExportFiles



admin.site.register(IncomeCategory)
admin.site.register(ExpenseCategory)
admin.site.register(Currency)
admin.site.register(BankCard)
admin.site.register(AccountType)
admin.site.register(Account)
admin.site.register(BankExportFiles)


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'date_processing', 'transaction_type', 'amount', 'currency', 'original_amount', 'original_currency', 'account', 'to_account', 'comment')
    list_filter = ('date', 'transaction_type')

admin.site.register(Transaction, TransactionAdmin)

def display_currency():
    pass