from django.shortcuts import render
from django.http import HttpResponse
from django.views import generic
import datetime
import time
import csv
from .models import Transaction, User, IncomeCategory, ExpenseCategory, Currency, Account
from .utils.halyk_parser import convert_pdf_to_csv, normalize_csv


class TransactionView(generic.ListView):
    template_name = 'money/tranlist.html'
    context_object_name = 'latest_transaction_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Transaction.objects.order_by('-date')[:10]

def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")

def halyk_converter(request):
    code = time.mktime(datetime.datetime.now().timetuple())
    #input_file = './money/files/input.pdf'
    input_file = f'./money/files/input.csv'
    output_file = f'./money/files/output_{code}.csv'

    #convert_pdf_to_csv(input_file, not_normalize_file)
    normalize_csv(input_file, output_file)

    res = []

    with open(output_file, 'r', newline='', encoding='utf-8') as f_in:
        reader = csv.reader(f_in)
        
        for row in reader:
            income_category = None
            expense_category = None
            transaction_type = ''
            original_amount = 0

            amount = float(row[3].replace(" ", "").replace(",", "."))

            if amount >= 0:
                income_category = IncomeCategory.objects.filter(name='Indeterminately').first()
                transaction_type = 'income'
                original_amount = float(row[5].replace(" ", "").replace(",", "."))
            elif amount < 0:
                expense_category = ExpenseCategory.objects.filter(name='Indeterminately').first()
                transaction_type = 'expense'
                original_amount = float(row[6].replace(" ", "").replace(",", "."))

            account = Account.objects.filter(account_number = row[8]).first()
            last_num_account = row[8][-4:]
            if not account:
                account = Account.objects.filter(bank_card__card_number_last = last_num_account, currency__code = row[4]).first()
                if not account:
                    account = Account.objects.filter(bank_card__card_number_last = last_num_account, default = True).first()

            new_transaction = Transaction()
            new_transaction.user = User.objects.get(username="Egor")
            new_transaction.category = expense_category
            new_transaction.income_category = income_category
            new_transaction.transaction_type = transaction_type
            new_transaction.amount = amount
            new_transaction.currency = Currency.objects.filter(code = row[4]).first()
            new_transaction.original_amount = original_amount
            new_transaction.exchange_rate = amount / float(original_amount)
            new_transaction.date = datetime.datetime.strptime(row[0], '%d.%m.%Y').date()
            new_transaction.date_processing = datetime.datetime.strptime(row[1], '%d.%m.%Y').date()
            new_transaction.comment = row[2]
            new_transaction.account = account
            new_transaction.save()

            res.append(new_transaction)

    return HttpResponse("All Ok!")

