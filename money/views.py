from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.views import generic
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
import datetime
import time
import csv
import requests
from .models import Transaction, User, IncomeCategory, ExpenseCategory, Currency, Account, BankExportFiles, ExchangeRate
from .forms import BankExportFilesForm, DateCurrencyExchangeForm
from .utils.halyk_parser import normalize_halyk_csv
from .utils.fixed_api import fetch_exchange_rates_for_date, date_range


class TransactionView(LoginRequiredMixin, generic.ListView):
    template_name = 'money/tranlist.html'
    context_object_name = 'latest_transaction_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Transaction.objects.order_by('-date')[:10]

def index(request):
    return render(request, 'money/index.html')

@login_required
def upload_file(request):
    if request.method == 'POST':
        form = BankExportFilesForm(request.POST, request.FILES)
        if form.is_valid():
            # Если необходимо, выполните дополнительную валидацию файла
            form_sourse = form.cleaned_data['sourse']
            if form_sourse == 'ziirat':
                redirect = 'ziirat'
            elif form_sourse == 'halyk':
                redirect = 'halyk'
            elif form_sourse == 'deniz':
                redirect = 'deniz'
            else:
                redirect = 'upload'
            # Здесь можно сохранить файл
            form.save()
            request.session['form_data'] = form.instance.document.name
            return HttpResponseRedirect(f'/money/{redirect}/')
        else:
            return render(request, 'money/upload.html', {'form': form})

    else:
        form = BankExportFilesForm()
    return render(request, 'money/upload.html', {'form': form})

def handle_uploaded_file(f, name_file):
    with open(name_file, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

@login_required
def halyk_converter(request):
    
    code = time.mktime(datetime.datetime.now().timetuple())

    #wtf?
    input_file = f"{settings.MEDIA_ROOT}files/{request.session.get('form_data')}"
    #input_file = settings.MEDIA_ROOT + BankExportFiles.objects.latest('uploaded_at').document.name
    output_file = f'{settings.MEDIA_ROOT}files/output_{code}.csv'

    #convert_pdf_to_csv(input_file, not_normalize_file)
    normalize_halyk_csv(input_file, output_file)

    res = []

    with open(output_file, 'r', newline='', encoding='utf-8') as f_in:
        reader = csv.reader(f_in)
        
        for row in reader:
            income_category = None
            expense_category = None
            transaction_type = ''
            to_account = None
            original_amount = 0
            tax = 0

            user = User.objects.get(username="Egor")
            currency = Currency.objects.filter(code = row[4]).first()
            data_original = datetime.datetime.strptime(row[0], '%d.%m.%Y').date()
            date_processing = datetime.datetime.strptime(row[1], '%d.%m.%Y').date()
            comment = row[2]

            amount = float(row[3].replace(" ", "").replace(",", "."))
            credit = float(row[5].replace(" ", "").replace(",", "."))
            debit = float(row[6].replace(" ", "").replace(",", "."))

            account = Account.objects.filter(account_number = row[8]).first()
            last_num_account = row[8][-4:]
            if not account:
                account = Account.objects.filter(bank_card__card_number_last = last_num_account, 
                                                 currency__code = row[4], 
                                                 name__startswith = 'Halyk'
                                                 ).first()
                if not account:
                    account = Account.objects.filter(bank_card__card_number_last = last_num_account, default = True).first()

            if amount >= 0:
                if row[4] == 'USD' and row[9] == 'USD':
                    continue

                transaction_type = 'income'
                original_amount = credit
                original_currency = account.currency

                if comment == 'Client conversion in Homebank' and credit > 0:
                    transaction_type = 'transfer'
                    amount = amount*(-1)
                    to_account = account
                    account = Account.objects.filter(currency__code = row[4], name__startswith = 'Halyk').first()
                else:
                    income_category = IncomeCategory.objects.filter(name='Indeterminately').first()

            elif amount < 0:
                transaction_type = 'expense'
                original_amount = debit
                original_currency = account.currency

                if credit == 0 and comment == 'Autoconversion of additional amount on past transactions':
                    transaction_type = 'transfer'

                    original_amount = abs(amount)
                    amount = debit

                    currency_tmp = currency
                    currency = original_currency
                    original_currency = currency_tmp

                    to_account = Account.objects.filter(currency__code = row[4], name__startswith = 'Halyk').first()
                    if not to_account:
                        to_account = Account.objects.filter(name = 'Temporary', default = True).first()

                elif comment == 'Client conversion in Homebank' and credit == 0:
                    if row[4] == row[9]:
                        continue
                else:
                    expense_category = ExpenseCategory.objects.filter(name='Indeterminately').first()

            if amount < 0 and comment == 'Transfer to another card':
                tax = abs(original_amount) - abs(amount)
                original_amount = amount

            exchange_rate = abs(amount / float(original_amount))

            transaction_exists = Transaction.objects.filter(user = user, 
                                                            transaction_type = transaction_type, 
                                                            amount = amount, 
                                                            currency = currency, 
                                                            original_amount = original_amount,
                                                            original_currency = original_currency,
                                                            date = data_original,
                                                            date_processing = date_processing,
                                                            comment = comment,
                                                            account = account,
                                                            to_account = to_account
                                                            ).exists()
            if transaction_exists:
                continue

            new_transaction = Transaction()
            new_transaction.user = user
            new_transaction.category = expense_category
            new_transaction.income_category = income_category
            new_transaction.transaction_type = transaction_type
            new_transaction.amount = amount
            new_transaction.currency = currency
            new_transaction.original_amount = original_amount
            new_transaction.original_currency = original_currency
            new_transaction.exchange_rate = exchange_rate
            new_transaction.date = data_original
            new_transaction.date_processing = date_processing
            new_transaction.comment = comment
            new_transaction.account = account
            new_transaction.to_account = to_account
            new_transaction.save()

            if tax > 0:
                # add transaction commission
                tax_transaction = Transaction()
                tax_transaction.user = user
                tax_transaction.category = ExpenseCategory.objects.filter(name='Сommission').first()
                tax_transaction.income_category = income_category
                tax_transaction.transaction_type = transaction_type
                tax_transaction.amount = tax*(-1)
                tax_transaction.currency = currency
                tax_transaction.original_amount = tax*(-1)
                tax_transaction.original_currency = original_currency
                tax_transaction.exchange_rate = exchange_rate
                tax_transaction.date = data_original
                tax_transaction.date_processing = date_processing
                tax_transaction.comment = 'Сommission'
                tax_transaction.account = account
                tax_transaction.to_account = to_account
                tax_transaction.save()

            res.append(new_transaction)

    return HttpResponse("All Ok!")

@login_required
def ziirat_converter(request):

    code = time.mktime(datetime.datetime.now().timetuple())

    form_data = request.session.get('form_data')

    if form_data:
        input_file = f"{settings.MEDIA_ROOT}{form_data}"
    else:
        return HttpResponse("NO DATA!")
    
    with open(input_file, 'r', newline='', encoding='utf-8') as f_in:
        reader = csv.reader(f_in, delimiter=';')
        
        for row in reader:
            income_category = None
            expense_category = None
            to_account = None
            original_amount = 0
            exchange_rate = 0

            user = User.objects.get(username="Egor")
            currency = Currency.objects.filter(code = 'TRY').first()
            original_currency = Currency.objects.filter(code = 'USD').first()
            data_original = datetime.datetime.strptime(row[0], '%d.%m.%Y').date()
            date_processing = datetime.datetime.strptime(row[0], '%d.%m.%Y').date()
            transaction_type = row[6]
            comment = f'{row[2]} | {row[1]}'

            amount = float(row[3].replace(" ", "").replace(",", "."))

            account = Account.objects.filter(currency__code = 'TRY', name__startswith = 'Ziraat Egor').first()

            if transaction_type == 'expense':
                expense_category = ExpenseCategory.objects.filter(id = int(row[5].split('|')[0])).first()
                exchange_rate = ExchangeRate.objects.get(target_currency__code = 'TRY', date = data_original).exchange_rate
                #original_amount = abs(float(amount)) / abs(float(exchange_rate))
            elif transaction_type == 'transfer':
                transfer_amount = float(row[7].replace(" ", "").replace(",", "."))
                if transfer_amount < 0:
                    original_amount = amount
                    amount = transfer_amount

                    original_currency = currency
                    currency = Currency.objects.filter(code = row[8]).first()

                    to_account = account
                    account = Account.objects.filter(name = row[9]).first()
                elif transfer_amount >= 0:
                    original_amount = transfer_amount
                    original_currency = Currency.objects.filter(code = row[8]).first()
                    to_account = Account.objects.filter(name = row[9]).first()
            elif transaction_type == 'income':
                income_category = IncomeCategory.objects.filter(name='Indeterminately').first()
                original_amount = amount
                original_currency = currency
            
            transaction_exists = Transaction.objects.filter(user = user, 
                                                            transaction_type = transaction_type, 
                                                            amount = amount, 
                                                            currency = currency, 
                                                            #original_amount = original_amount,
                                                            #original_currency = original_currency,
                                                            date = data_original,
                                                            date_processing = date_processing,
                                                            comment = comment,
                                                            account = account,
                                                            to_account = to_account
                                                            ).exists()
            if transaction_exists:
                continue
            
            new_transaction = Transaction()
            new_transaction.user = user
            new_transaction.category = expense_category
            new_transaction.income_category = income_category
            new_transaction.transaction_type = transaction_type
            new_transaction.amount = amount
            new_transaction.currency = currency
            new_transaction.original_amount = original_amount
            new_transaction.original_currency = original_currency
            new_transaction.exchange_rate = exchange_rate
            new_transaction.date = data_original
            new_transaction.date_processing = date_processing
            new_transaction.comment = comment
            new_transaction.account = account
            new_transaction.to_account = to_account
            new_transaction.save()

    return HttpResponse("Ziraat")

@login_required
def deniz_converter(request):

    code = time.mktime(datetime.datetime.now().timetuple())

    form_data = request.session.get('form_data')

    if form_data:
        input_file = f"{settings.MEDIA_ROOT}{form_data}"
    else:
        return HttpResponse("NO DATA!")
    
    with open(input_file, 'r', newline='', encoding='utf-8') as f_in:
        reader = csv.reader(f_in, delimiter=';')
        
        for row in reader:
            income_category = None
            expense_category = None
            to_account = None
            original_amount = 0
            exchange_rate = 0

            user = User.objects.get(username="Egor")
            currency = Currency.objects.filter(code = 'TRY').first()
            original_currency = Currency.objects.filter(code = 'USD').first()
            data_original = datetime.datetime.strptime(row[0], '%d.%m.%Y %H:%M').date()
            date_processing = datetime.datetime.strptime(row[0], '%d.%m.%Y  %H:%M').date()
            transaction_type = row[8]
            comment = f'{row[2]} | {row[1]} | {row[3]} | {row[4]}'

            amount = float(row[5].replace(" ", "").replace(",", "."))

            account = Account.objects.filter(currency__code = 'TRY', name__startswith = 'Deniz').first()
            
            if transaction_type == 'expense':
                expense_category = ExpenseCategory.objects.filter(id = int(row[7].split('|')[0])).first()
                exchange_rate = ExchangeRate.objects.get(target_currency__code = 'TRY', date = data_original).exchange_rate
                #original_amount = abs(float(amount)) / abs(float(exchange_rate))
            elif transaction_type == 'transfer':
                transfer_amount = float(row[9].replace(" ", "").replace(",", "."))
                if transfer_amount < 0:
                    original_amount = amount
                    amount = transfer_amount

                    original_currency = currency
                    currency = Currency.objects.filter(code = row[10]).first()

                    to_account = account
                    account = Account.objects.filter(name = row[11]).first()
                elif transfer_amount >= 0:
                    original_amount = transfer_amount
                    original_currency = Currency.objects.filter(code = row[10]).first()
                    to_account = Account.objects.filter(name = row[11]).first()
            elif transaction_type == 'income':
                income_category = IncomeCategory.objects.filter(name='Indeterminately').first()
                original_amount = amount
                original_currency = currency

            transaction_exists = Transaction.objects.filter(user = user, 
                                                            transaction_type = transaction_type, 
                                                            amount = amount, 
                                                            currency = currency, 
                                                            #original_amount = original_amount,
                                                            #original_currency = original_currency,
                                                            date = data_original,
                                                            date_processing = date_processing,
                                                            comment = comment,
                                                            account = account,
                                                            to_account = to_account
                                                            ).exists()
            if transaction_exists:
                continue
            
            new_transaction = Transaction()
            new_transaction.user = user
            new_transaction.category = expense_category
            new_transaction.income_category = income_category
            new_transaction.transaction_type = transaction_type
            new_transaction.amount = amount
            new_transaction.currency = currency
            new_transaction.original_amount = original_amount
            new_transaction.original_currency = original_currency
            new_transaction.exchange_rate = exchange_rate
            new_transaction.date = data_original
            new_transaction.date_processing = date_processing
            new_transaction.comment = comment
            new_transaction.account = account
            new_transaction.to_account = to_account
            new_transaction.save()
            

    return HttpResponse("Deniz")

@login_required
def get_currency_exchange_rate(request):
    #fetch_historical_exchange_rates(datetime.datetime.strptime('2022-01-01','%Y-%m-%d'),datetime.datetime.strptime('2023-07-04','%Y-%m-%d'))
    
    if request.method == 'POST':
        form = DateCurrencyExchangeForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            for single_date in date_range(start_date, end_date):
                fetch_exchange_rates_for_date(single_date)
        else:
            return render(request, 'money/currency.html', {'form': form})
    else:
        form =DateCurrencyExchangeForm()
        return render(request, 'money/currency.html', {'form': form})

    return HttpResponse("All OK!")