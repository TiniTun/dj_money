from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import generic
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction as db_transaction
import os
import datetime
import time
import csv
import requests
import boto3
import json
import tempfile
from .models import Transaction, User, IncomeCategory, ExpenseCategory, Currency, Account, BankExportFiles, ExchangeRate, TransactionCashback
from .forms import BankExportFilesForm, DateCurrencyExchangeForm
from .decorators import token_required
from .utils.halyk_parser import normalize_halyk_csv
from .utils.s3_utils import get_s3_client
from .tasks import process_statement_import, categorize_transactions_batch, upload_files, fetch_exchange_rates_task


from .parsers.bcc_parser import BccStatementParser



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
            uploaded_file = request.FILES['document']
            source_instance = form.cleaned_data['source']

            # Ensure the shared temp directory exists inside the container
            os.makedirs(settings.SHARED_TMP_DIR, exist_ok=True)

            # Create a temporary file to pass its path to Celery.
            # The task will be responsible for deleting it.
            # Using a suffix helps in debugging if the file is not deleted.
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{uploaded_file.name}", dir=settings.SHARED_TMP_DIR
            ) as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                temp_file_path = tmp.name

            # Launch the background task
            task = upload_files.delay(
                user_id=request.user.id,
                filename=uploaded_file.name,
                bucket_name=settings.YANDEX_BUCKET,
                file_path=temp_file_path,
                source_code=source_instance.code
            )
            
            messages.success(request, f'File "{uploaded_file.name}" add to queue. Task\'s ID: {task.id}')
            return HttpResponseRedirect(request.path_info)

    else:
        form = BankExportFilesForm()
    return render(request, 'money/upload.html', {'form': form})

def handle_uploaded_file(f, name_file):
    with open(name_file, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

@login_required
def get_currency_exchange_rate(request):
    if request.method == 'POST':
        form = DateCurrencyExchangeForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            extra_currency = form.cleaned_data['extra_currency']
            only_extra = form.cleaned_data['only_extra']

            # Запускаем задачу в Celery
            task = fetch_exchange_rates_task.delay(
                start_date.isoformat(),
                end_date.isoformat(),
                extra_currency=extra_currency,
                only_extra=only_extra
            )
            messages.success(request, f'Загрузка курсов валют запущена в фоновом режиме. ID задачи: {task.id}')
            return HttpResponseRedirect(request.path_info)  # Перенаправляем на ту же страницу
    else:
        form = DateCurrencyExchangeForm()

    return render(request, 'money/currency.html', {'form': form})

@csrf_exempt
@require_POST
@token_required
def upload_external_file(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    files = data.get('new_files')
    if not files or not isinstance(files, list):
        return JsonResponse({'results': {'status': 'error', 'error': 'Missing or invalid "new_files"'}}, status=200)

    results = []
    task_ids = []

    for file_info in files:
        filename = file_info.get('filename')
        signed_url = file_info.get('signed_url')
        if not filename or not signed_url:
            results.append({'filename': filename, 'status': 'error', 'error': 'Missing filename or signed_url'})
            continue
        
        # Using keyword arguments for clarity
        task = upload_files.delay(
            user_id=request.user.id,
            filename=filename,
            bucket_name=settings.YANDEX_BUCKET,
            signed_url=signed_url,
            # source_code будет использовать значение по умолчанию 'bcc' в задаче
        )
        task_ids.append(task.id)
        
    results.append({'status': 'success', 'message': 'Tasks started successfully', 'celery_task_ids': task_ids})

    return JsonResponse({'results': results}, status=200)

@csrf_exempt
@require_POST
@token_required
def parse_statement_files(request):
    results = []
    try:
        files_pending = BankExportFiles.objects.filter(status=BankExportFiles.Status.PENDING)
        
        task_ids = []

        for file in files_pending:
            task = process_statement_import.delay(settings.YANDEX_BUCKET, file.id)
            task_ids.append(task.id)

        results.append({'status': 'success', 'message': 'Tasks started successfully', 'celery_task_ids': task_ids})
    except Exception as e:
        results.append({'status': 'error', 'error': str(e)})

    return JsonResponse({'results': results}, status=200)


@csrf_exempt
@require_POST
@token_required
def run_batch_categorization(request):
    # 1. Select all transactions without a category
    qs = Transaction.objects.filter(category__isnull = True, transaction_type = 'expense', place__isnull = False).order_by('id')
    ids = list(qs.values_list('id', flat=True))

    # 2. Split into bundles of 10
    def chunks(lst, n):
        # Yield successive n-sized chunks from lst
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    batches = list(chunks(ids, settings.BATCH_CATEGORIZATION_SIZE))
    task_ids = []

    # 3. Run a task for each bundle
    for batch in batches:
        task = categorize_transactions_batch.delay(batch)
        task_ids.append(task.id)

    return JsonResponse({'results': {
        "status": "success",
        "message": f"Task started successfully: {len(batches)} batches created. Transaction to be categorized: {len(ids)}",
        "celery_task_ids": task_ids
    }}, status=200)
