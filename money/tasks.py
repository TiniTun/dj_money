# finance/tasks.py
import requests
import tempfile
import os
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_transaction, IntegrityError
from openai import OpenAI

from datetime import date, datetime
from .models import Transaction, BankExportFiles, Account, User, Currency, ExpenseCategory, GptLog, PlaceCategoryMapping, BankSource, TransactionCategoryLog
from .parsers.bcc_parser import BccStatementParser
from .parsers.ff_parser import FFStatementParser
from .parsers.commbank_parser import CommbankStatementParser
from .utils.s3_utils import get_s3_client
from .utils.fixed_api import fetch_exchange_rates_for_date, date_range

from yandex_cloud_ml_sdk import YCloudML

PARSER_MAP = {
    'BccStatementParser': BccStatementParser,
    'FFStatementParser': FFStatementParser,
    'CommbankStatementParser': CommbankStatementParser,
}

oai_client = OpenAI(api_key = settings.OPENAI_API_KEY)
ya_sdk = YCloudML(folder_id=settings.YANDEX_ID_FOLDER, auth=settings.YANDEX_GPT_SECRET_KEY)

@shared_task(bind=True, max_retries=3, default_retry_delay=60) # bind=True для доступа к self (для retry)
def upload_files(self, user_id, filename, bucket_name, signed_url=None, file_path=None, source_code='bcc'):
    """
    Uploads a file to S3. The file can be sourced from a URL or a local file path.
    The task is responsible for cleaning up any temporary files it creates or is given.
    """
    if not signed_url and not file_path:
        raise ValueError("Either signed_url or file_path must be provided.")

    # This will hold the path to the file that needs to be uploaded and then deleted.
    path_to_process = None
    try:
        user = User.objects.get(username="Egor") if user_id is None else User.objects.get(id=user_id) # Получаем объект пользователя по ID
        source_obj = BankSource.objects.get(code=source_code)
        s3_client = get_s3_client()

        if signed_url:
            # Case 1: Download from URL into a temporary file.
            response = requests.get(signed_url, stream=True, timeout=60)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                path_to_process = tmp.name
        else:
            # Case 2: A path to a local (temporary) file was provided.
            path_to_process = file_path

        full_s3_path = f'statement/{filename}'

        with open(path_to_process, 'rb') as data_file:
            s3_client.upload_fileobj(data_file, bucket_name, full_s3_path)

        # Creating an import record
        lookup_params = {
            'user': user,
            's3_file_key': full_s3_path,
            'source': source_obj,
        }
        defaults_params = {
            'status': BankExportFiles.Status.PENDING
        }
        bank_export_file_instance, created = BankExportFiles.objects.get_or_create(**lookup_params, defaults=defaults_params)

        if created:
            return f'File imported successfully and new record created. ID: {bank_export_file_instance.id}'
        else:
            return f'File record already exists. ID: {bank_export_file_instance.id}'
    except Exception as e:
        raise self.retry(exc=e) # Повторить задачу в случае ошибки
    finally:
        # Cleanup: remove the temporary file if its path was set.
        if path_to_process and os.path.exists(path_to_process):
            os.remove(path_to_process)

def _find_category_for_place(place, user):
    """
    Finds a pre-defined category for a given place based on user's mapping rules.
    """
    if not place:
        return None

    # 1. Check for an exact match first (more specific)
    exact_match = PlaceCategoryMapping.objects.filter(
        user=user,
        place_keyword__iexact=place,
        match_type=PlaceCategoryMapping.MatchType.EXACT
    ).first()
    if exact_match:
        return exact_match.category

    # 2. Check for 'contains' matches
    contains_rules = PlaceCategoryMapping.objects.filter(
        user=user,
        match_type=PlaceCategoryMapping.MatchType.CONTAINS
    )
    for rule in contains_rules:
        # Case-insensitive check
        if rule.place_keyword.lower() in place.lower():
            return rule.category

    return None


@shared_task(bind=True, max_retries=3, default_retry_delay=60) # bind=True для доступа к self (для retry)
def process_statement_import(self, bucket_name, object_key):
    try:
        bank_statement = BankExportFiles.objects.get(id=object_key)
        bank_statement.status = BankExportFiles.Status.PROCESSING
        bank_statement.save()

        s3_client = get_s3_client()

        response = s3_client.get_object(Bucket=bucket_name, Key=bank_statement.s3_file_key)
        file_content = response['Body'].read().decode('utf-8')

        # Вызываем наш парсер
        #parser = BccStatementParser(html_content)
        parser_name = bank_statement.source.parser
        parser_class = PARSER_MAP.get(parser_name)
        if not parser_class:
            raise ValueError(f"Parser '{parser_name}' not found in PARSER_MAP for source '{bank_statement.source.code}'")
        
        parser = parser_class(file_content)
        parsed_data = parser.parse()

        header = parsed_data['header']
        transactions_data = parsed_data['transactions']
        errors = parsed_data.get('errors', [])

        with db_transaction.atomic():
  
            user = bank_statement.user

            bank_account_from_header = None
            if header.get('account_number') and header['account_number'] != 'FROM_CSV':
                bank_account_from_header = Account.objects.filter(user = user, currency__code = header.get('currency'), account_number__startswith = header['account_number']).first()
            
            created_count = 0
            skipped_count = 0
            print(transactions_data)
            for i, tx_data in enumerate(transactions_data):
                amount = 0
                original_amount = float(tx_data['amount'])

                # 1. Определяем счет для текущей транзакции
                transaction_account = None
                if tx_data.get('account_id'):
                    # Для CSV-парсеров, где счет указан в каждой строке
                    transaction_account = Account.objects.filter(user = user, account_number__startswith = tx_data['account_id']).first()
                else:
                    # Для остальных используем счет из заголовка
                    transaction_account = bank_account_from_header

                if not transaction_account:
                    errors.append(f"Could not find account for transaction: {tx_data}. Skipping.")
                    skipped_count += 1
                    continue

                # 2. Определяем валюты
                currency = transaction_account.currency
                original_currency =  Currency.objects.filter(code = 'USD').first() # Deffault USD

                if tx_data.get('currency') and isinstance(tx_data['currency'], str):
                    # Для парсеров, которые предоставляют информацию о конвертации (например, BCC)
                    curr_codes = tx_data['currency'].split('-')
                    if len(curr_codes) == 2:
                        currency = Currency.objects.filter(code=curr_codes[0]).first() or currency
                        original_currency = Currency.objects.filter(code=curr_codes[1]).first() or original_currency
                else:
                    amount = original_amount
                    original_amount = 0


                # 3. Ищем категорию по справочнику правил
                expense_category = None
                income_category = None
                # Ищем категорию по справочнику, если это расход и есть место
                if tx_data['type'] == 'expense' and tx_data.get('place'):
                    expense_category = _find_category_for_place(tx_data['place'], user)

                exchange_rate_value = None
                if tx_data.get('rate') is not None:
                    try:
                        exchange_rate_value = 1 / float(tx_data['rate'])
                    except (ValueError, TypeError, ZeroDivisionError): # Обработка если rate не число или 0
                        exchange_rate_value = 1.55

                # 4. Определяем счет-получатель для переводов
                to_account = None
                if tx_data['type'] == 'transfer' and tx_data.get('to_account'):
                    to_account = Account.objects.filter(user = user, account_number__startswith = tx_data['to_account']).first()
                    income_category = None
                    expense_category = None
                    original_currency = Currency.objects.filter(code = 'KZT').first()
                    original_amount = (-1) * amount

                # Поля для поиска существующей транзакции (согласно unique_together + user)
                lookup_params = {
                    'user': user,
                    'account': transaction_account,
                    'transaction_type': tx_data['type'],
                    'date': tx_data['real_date'],
                    'date_processing': tx_data.get('trans_date', tx_data['real_date']),
                    'amount': amount, 
                    'currency': currency,
                    'original_amount': original_amount,
                    'original_currency': original_currency,
                    'comment': tx_data['description'],
                }
                # Поля, которые будут установлены, если транзакция создается
                defaults_params = {
                    'category': expense_category,
                    'income_category': income_category,
                    'exchange_rate': exchange_rate_value,
                    'place': tx_data['place'],
                    'to_account': to_account,
                    'statement_import': bank_statement
                }
                
                # Robustly handle creation to avoid race conditions with get_or_create
                created = False
                try:
                    # Each creation attempt is wrapped in its own atomic block.
                    # If this fails, only this inner transaction is rolled back,
                    # not the entire loop.
                    with db_transaction.atomic():
                        Transaction.objects.create(**lookup_params, **defaults_params)
                        created = True
                except IntegrityError:
                    # This means the transaction already exists. We can safely ignore this
                    # and move on to the next one.
                    pass

                if created:
                    created_count += 1
                else:
                    skipped_count += 1
                    errors.append(f"Transaction already exists: {tx_data}. Skipping.")

        
        # Обновляем статус импорта
        bank_statement.status = BankExportFiles.Status.COMPLETED
        bank_statement.processed_at = timezone.now()
        notes = f"Successfully processed. New transactions: {created_count}. Skipped duplicates: {skipped_count}."
        if errors:
            notes += "\n\nErrors during processing:\n" + "\n".join(errors)
        bank_statement.notes = notes
        bank_statement.save()

    except Exception as e:
        # В случае любой ошибки, помечаем задачу как проваленную и записываем ошибку
        if 'bank_statement' in locals():
            bank_statement.status = BankExportFiles.Status.FAILED
            bank_statement.notes = str(e)
            bank_statement.processed_at = timezone.now()
            bank_statement.save()
        raise self.retry(exc=e) # Повторить задачу в случае ошибки

def _gpt_model(prompt):
    response = oai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    result = response.choices[0].message.content.strip()
    return result

def _ya_model(prompt):
    model = ya_sdk.models.completions("yandexgpt", model_version="rc")
    model = model.configure(temperature=0)
    result = model.run(
        [
            {"role": "system", "text": "Ты — полезный ассистент, который помогает классифицировать транзакции."},
            {
                "role": "user",
                "text": prompt,
            }
        ]
    )
    return result.alternatives[0].text.strip()

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def categorize_transactions_batch(self, transaction_ids):
    log_entry = GptLog.objects.create(
        celery_task_id=self.request.id,
        model_name='yandexgpt'
    )
    
    try:
        transactions = Transaction.objects.filter(category__isnull=True, id__in=transaction_ids)
        if not transactions.exists():
            result_message = "No transactions to categorize in this batch (they might have been processed already)."
            log_entry.status = GptLog.Status.SUCCESS
            log_entry.result = result_message
            log_entry.save()
            return result_message

        categories = ExpenseCategory.objects.filter(for_categorized=True)

        categories_list = []

        for category in categories:
            if category.parent_category:
                parent_category = ExpenseCategory.objects.filter(id = category.parent_category.id).first()
                categories_list.append(f'{category.id}-{parent_category.name}:{category.name}')
            else:
                categories_list.append(f'{category.id}-Main:{category.name}')


        categories_str = ';'.join(categories_list)

        # Готовим батч для GPT
        prompt = (
            f"Вот список категорий транзакций разделенных знаком \";\" каждая и в формате <id категории>-<название родительсой категории>:<название категории>: {categories_str}.\n"
            f"Для каждой строки определи, к какой категории из списка она относится. "
            "Ответ верни в формате: <номер строки>. <категория>.\n\n"
        )
        for i, t in enumerate(transactions, 1):
            prompt += f"{i}. {t.place} \n"
       
        prompt += "\nТолько категории, никаких комментариев."
        
        # Сохраняем промпт в лог
        log_entry.prompt = prompt
        log_entry.save(update_fields=['prompt'])

        # Отправляем в OpenAI
        result = _ya_model(prompt)
        
        # Сохраняем результат в лог
        log_entry.result = result
        log_entry.status = GptLog.Status.SUCCESS
        log_entry.save(update_fields=['result', 'status', 'updated_at'])

        with db_transaction.atomic():
            lines = result.splitlines()
            for line, transaction in zip(lines, transactions):
                expense_category = ExpenseCategory.objects.filter(id = 1).first()
                parts = line.split('.')
                if len(parts) >= 2:
                    category_id = parts[1].strip().split('-')[0].strip()
                    if category_id:
                        expense_category = ExpenseCategory.objects.filter(id = int(category_id)).first()

                transaction.category = expense_category
                transaction.save(update_fields=["category"])
                TransactionCategoryLog.objects.create(
                    transaction=transaction,
                    category_log=parts[1].strip(),
                    gpt_log=log_entry
                )
            
                
        return f"Categorized {transactions.count()} transactions successfully."
    except Exception as e:
        # В случае ошибки обновляем лог
        log_entry.status = GptLog.Status.FAILED
        log_entry.error_message = str(e)
        log_entry.save(update_fields=['status', 'error_message', 'updated_at'])
        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=180)
def fetch_exchange_rates_task(self, start_date_str=None, end_date_str=None, extra_currency=None, only_extra=False):
    """
    Fetches exchange rates for a given date range in the background.
    """
    try:
        if start_date_str is None:
            start_date = date.today()
        else:
            start_date = date.fromisoformat(start_date_str)
        if end_date_str is None:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end_date_str)

        for single_date in date_range(start_date, end_date):
            fetch_exchange_rates_for_date(
                single_date,
                extra_currency=extra_currency,
                only_extra=only_extra
            )
        return f"Successfully fetched exchange rates from {start_date_str} to {end_date_str}."
    except Exception as e:
        raise self.retry(exc=e)