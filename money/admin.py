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
from .models import GptLog
from .models import PlaceCategoryMapping

admin.site.register(Currency)
admin.site.register(BankCard)
admin.site.register(AccountType)
admin.site.register(Account)
admin.site.register(BankExportFiles)
admin.site.register(ExchangeRate)
admin.site.register(TransactionCashback)

def get_hierarchical_choices():
    def add_category(category, choices, level=0):
        choices.append((category.pk, "---" * level + category.name))
        for child_category in ExpenseCategory.objects.filter(parent_category=category):
            add_category(child_category, choices, level + 1)
            
    choices = []
    for root_category in ExpenseCategory.objects.filter(parent_category__isnull=True):
        add_category(root_category, choices)
    return choices

class HierarchicalCategoryFormMixin(forms.ModelForm):
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

class TransactionAdminForm(HierarchicalCategoryFormMixin):
    class Meta:
        model = Transaction
        fields = '__all__'

class PlaceCategoryMappingAdminForm(HierarchicalCategoryFormMixin):
     class Meta:
         model = PlaceCategoryMapping
         fields = '__all__'

@admin.register(PlaceCategoryMapping)
class PlaceCategoryMappingAdmin(admin.ModelAdmin):
    list_display = ('place_keyword', 'category', 'match_type', 'user')
    list_filter = ('user', 'match_type', 'category')
    search_fields = ('place_keyword', 'category__name')
    list_editable = ('category', 'match_type')
    form = PlaceCategoryMappingAdminForm

@admin.register(GptLog)
class GptLogAdmin(admin.ModelAdmin):
    list_display = ('celery_task_id', 'model_name', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'model_name', 'created_at')
    search_fields = ('celery_task_id', 'prompt', 'result')
    readonly_fields = ('celery_task_id', 'model_name', 'prompt', 'result', 'status', 'error_message', 'created_at', 'updated_at')

class ExpenseCategoryInLine(admin.TabularInline):
    model = ExpenseCategory

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'date_processing', 'transaction_type', 'category', 'income_category', 'amount', 'currency', 'original_amount', 'original_currency', 'account', 'to_account', 'place', 'comment')
    list_filter = ('date', 'transaction_type', 'category', 'income_category', 'account')
    form = TransactionAdminForm
    #raw_id_fields = ['category', ]

class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'user',)
    list_filter = ('name', 'parent_category')

class ParentCategoryFilter(admin.SimpleListFilter):
    # Заголовок, который будет отображаться в админ-панели
    title = 'Is root category'
    # Параметр, который будет использоваться в URL
    parameter_name = 'is_root'

    def lookups(self, request, model_admin):
        # Варианты выбора для фильтра
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        # Логика фильтрации
        if self.value() == 'yes':
            return queryset.filter(parent_category__isnull=True)
        if self.value() == 'no':
            return queryset.filter(parent_category__isnull=False)

class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'user',)
    list_filter = (ParentCategoryFilter, 'user',)

admin.site.register(Transaction, TransactionAdmin)
admin.site.register(IncomeCategory, IncomeCategoryAdmin)
admin.site.register(ExpenseCategory, ExpenseCategoryAdmin)