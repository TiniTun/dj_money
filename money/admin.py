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
admin.site.register(Transaction)
admin.site.register(BankExportFiles)
