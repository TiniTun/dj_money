from django.db import models
from django.contrib.auth.models import User


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    parent_category = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)


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

class Transaction(models.Model):
    TRANSACTION_TYPE = (
        ('expense', 'Расход'),
        ('income', 'Доход'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    income_category = models.ForeignKey(IncomeCategory, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.ForeignKey(Currency, default=1, on_delete=models.SET_NULL, null=True, blank=True)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    date = models.DateField()
    date_processing = models.DateField(default=None)
    comment = models.TextField(blank=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, default=1)

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.amount}"
