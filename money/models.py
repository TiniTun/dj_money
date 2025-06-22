from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .validators import validate_file_extension


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent_category = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    for_categorized = models.BooleanField(default=True, help_text="Use this category for categorization of transactions")


    def __str__(self):
        return self.name

class IncomeCategory(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent_category = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)


    def __str__(self):
        return self.name
    
class Currency(models.Model):
    code = models.CharField(max_length=3)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name} ({self.code})"

class ExchangeRate(models.Model):
    source_currency = models.ForeignKey(Currency, related_name='source_currency', on_delete=models.CASCADE)
    target_currency = models.ForeignKey(Currency, related_name='target_currency', on_delete=models.CASCADE)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6)
    date = models.DateField()

    def __str__(self):
        return f"{self.date}: 1 {self.source_currency.code} = {self.exchange_rate} {self.target_currency.code}"

class BankCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card_number = models.CharField(max_length=19)  # XXXX-XXXX-XXXX-XXXX
    card_number_last = models.CharField(max_length=4)
    card_name = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.card_name} ({self.card_number})"



class AccountType(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    account_type = models.ForeignKey(AccountType, on_delete=models.CASCADE)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, default=1)
    bank_card = models.ForeignKey(BankCard, null=True, blank=True, on_delete=models.SET_NULL)
    default = models.BooleanField(default=False)
    account_number = models.CharField(max_length=255, default='')
    balance = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class BankExportFiles(models.Model):
    BANK_TYPE = (
        ('halyk', 'Halyk'),
        ('ziirat', 'Ziirat'),
        ('deniz', 'Deniz'),
        ('kaspikz', 'Kaspi.kz'),
        ('bcc', 'BCC.kz')
    )
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'В ожидании'
        PROCESSING = 'PROCESSING', 'В обработке'
        COMPLETED = 'COMPLETED', 'Завершено'
        FAILED = 'FAILED', 'Ошибка'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='statement_imports') 
    description = models.CharField(max_length=255, blank=True)
    document = models.FileField(upload_to='files/', validators=[validate_file_extension], null=True, blank=True)
    sourse = models.CharField(max_length=10, choices=BANK_TYPE, default='bcc', help_text="Source bank type")
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="Date and time of file upload")
    processed_at = models.DateTimeField(null=True, blank=True)
    s3_file_key = models.CharField(max_length=1024, help_text="Files key in S3", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, help_text="Notes or comments about the import process")

    class Meta:
        unique_together = ('user', 's3_file_key', 'sourse')
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Import {self.id} to {self.uploaded_at.strftime('%Y-%m-%d %H:%M')} - {self.status}"

class Transaction(models.Model):
    TRANSACTION_TYPE = (
        ('expense', 'Расход'),
        ('income', 'Доход'),
        ('transfer', 'Перевод'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    income_category = models.ForeignKey(IncomeCategory, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.ForeignKey(Currency, default=1, on_delete=models.SET_NULL, null=True, blank=True)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_currency = models.ForeignKey(Currency, default=1, on_delete=models.SET_NULL, related_name='%(class)s_original_currency', null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    date = models.DateField()
    date_processing = models.DateField(default=None)
    comment = models.TextField(blank=True)
    place = models.TextField(blank=True, null=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, default=1)
    to_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='%(class)s_to_account', null=True, blank=True)
    statement_import = models.ForeignKey(BankExportFiles, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    class Meta:
        # Этот уникальный индекс предотвратит создание дубликатов транзакций
        # при повторной загрузке одного и того же файла.
        unique_together = ('account', 'transaction_type', 'date', 'date_processing', 'original_amount', 'original_currency', 'comment')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if self.original_amount and self.amount:
            self.exchange_rate = abs(float(self.amount) / float(self.original_amount))
        elif self.exchange_rate:
            if self.original_currency.code == 'USD' and self.currency.code != 'USD':
                if self.amount:
                    self.original_amount = float(self.amount) / float(self.exchange_rate)
                else:
                    self.amount = float(self.original_amount) * float(self.exchange_rate)
            elif self.original_currency.code != 'USD' and self.currency.code == 'USD':
                if self.amount:
                    self.original_amount = float(self.amount) * float(self.exchange_rate)
                else:
                    self.amount = float(self.original_amount) / float(self.exchange_rate)
        if self.transaction_type == 'transfer':
            if not self.to_account:
                raise ValidationError(f'The beneficiary\'s account is required for the "Transfer" type. {self.amount}')
            
            #if self.amount <= 0:
            #    raise ValidationError('Transfer amount must be positive')
            
            #if self.account.balance < self.amount:
            #    raise ValidationError('Insufficient funds on the sender\'s account')
        
        super(Transaction, self).save(*args, **kwargs)

class TransactionCashback(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    real_amount = models.DecimalField(max_digits=10, decimal_places=2)
    cashback = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f'{self.transaction.date}: {self.transaction.amount} {self.transaction.currency.code}, {self.real_amount}, {self.cashback}'

#@receiver(post_save, sender=Transaction)
#def update_account_balance(sender, instance=None, created=False, **kwargs):
#    if created and instance.transaction_type == 'transfer':
#        with transaction.atomic():
#            instance.account.balance -= instance.amount
#            instance.account.save()
#            instance.to_account.balance += instance.amount
#            instance.to_account.save()

class GptLog(models.Model):
    """Model for logging requests to GPT models."""
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'В ожидании'
        SUCCESS = 'SUCCESS', 'Успешно'
        FAILED = 'FAILED', 'Ошибка'

    celery_task_id = models.CharField(max_length=255, unique=True, db_index=True, help_text="Celery task ID")
    model_name = models.CharField(max_length=100, help_text="The name of the model used")
    prompt = models.TextField(help_text="The full prompt sent to the model")
    result = models.TextField(blank=True, help_text="The full result received from the model")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Log for task {self.celery_task_id} - {self.status}"

class PlaceCategoryMapping(models.Model):
    """A dictionary to automatically map a place/keyword to a category."""
    class MatchType(models.TextChoices):
        EXACT = 'EXACT', 'Точное совпадение'
        CONTAINS = 'CONTAINS', 'Содержит'

    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="The user this rule belongs to.")
    place_keyword = models.CharField(max_length=255, db_index=True, help_text="Keyword to match in the transaction's place/comment.")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, help_text="The category to assign if a match is found.")
    match_type = models.CharField(max_length=10, choices=MatchType.choices, default=MatchType.CONTAINS)

    class Meta:
        unique_together = ('user', 'place_keyword', 'category')
        ordering = ['-id']

    def __str__(self):
        return f"'{self.place_keyword}' -> '{self.category.name}' for {self.user.username}"