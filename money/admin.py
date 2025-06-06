from django.contrib import admin
from django import forms

from .widgets import HierarchicalSelect

from .models import IncomeCategory
from .models import ExpenseCategory
from .models import Currency
from .models import BankCard
from .models import AccountType
from .models import Account
from .models import Transaction
from .models import BankExportFiles
from .models import ExchangeRate
from .models import TransactionCashback


admin.site.register(Currency)
admin.site.register(BankCard)
admin.site.register(AccountType)
admin.site.register(Account)
admin.site.register(BankExportFiles)
admin.site.register(ExchangeRate)
admin.site.register(TransactionCashback)

class ExpenseCategoryInLine(admin.TabularInline):
    model = ExpenseCategory
        
def get_hierarchical_choices():
    def add_category(category, choices, level=0):
        choices.append((category.pk, "---" * level + category.name))
        for child_category in ExpenseCategory.objects.filter(parent_category=category):
            add_category(child_category, choices, level + 1)
            
    choices = []
    for root_category in ExpenseCategory.objects.filter(parent_category__isnull=True):
        add_category(root_category, choices)
    return choices

class TransactionAdminForm(forms.ModelForm):
    category = forms.ChoiceField(choices=[("", "---------")], widget=HierarchicalSelect(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].choices = [("", "---------")] + get_hierarchical_choices()


    def clean_category(self):
        category_id = self.cleaned_data.get('category')
        if not category_id:
            return None
        else:
            return ExpenseCategory.objects.get(pk=category_id)

    class Meta:
        model = Transaction
        fields = '__all__'

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'date_processing', 'transaction_type', 'category', 'income_category', 'amount', 'currency', 'original_amount', 'original_currency', 'account', 'to_account', 'comment')
    list_filter = ('date', 'transaction_type', 'category', 'income_category', 'account')
    form = TransactionAdminForm
    #raw_id_fields = ['category', ]

class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'user',)
    list_filter = ('name', 'parent_category')

class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'user',)
    list_filter = ('name', 'parent_category')

admin.site.register(Transaction, TransactionAdmin)
admin.site.register(IncomeCategory, IncomeCategoryAdmin)
admin.site.register(ExpenseCategory, ExpenseCategoryAdmin)