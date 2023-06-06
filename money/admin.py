from django.contrib import admin

from .models import IncomeCategory
from .models import ExpenseCategory
from .models import Currency
from .models import BankCard
from .models import AccountType
from .models import Account
from .models import Transaction
from .models import BankExportFiles


admin.site.register(Currency)
admin.site.register(BankCard)
admin.site.register(AccountType)
admin.site.register(Account)
admin.site.register(BankExportFiles)


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'date_processing', 'transaction_type', 'category', 'income_category', 'amount', 'currency', 'original_amount', 'original_currency', 'account', 'to_account', 'comment')
    list_filter = ('date', 'transaction_type', 'category', 'income_category', 'account')

class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'user',)
    list_filter = ('name', 'parent_category')

class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'user',)
    list_filter = ('name', 'parent_category')

admin.site.register(Transaction, TransactionAdmin)
admin.site.register(IncomeCategory, IncomeCategoryAdmin)
admin.site.register(ExpenseCategory, ExpenseCategoryAdmin)