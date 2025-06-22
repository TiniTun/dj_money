# finance/tasks.py
import requests
import tempfile
import os
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import transaction as db_transaction
from openai import OpenAI

from .models import Transaction, BankExportFiles, Account, User, Currency, ExpenseCategory, GptLog, PlaceCategoryMapping
from .parsers.bcc_parser import BccStatementParser
from .utils.s3_utils import get_s3_client

from yandex_cloud_ml_sdk import YCloudML

oai_client = OpenAI(api_key = settings.OPENAI_API_KEY)
ya_sdk = YCloudML(folder_id=settings.YANDEX_ID_FOLDER, auth=settings.YANDEX_GPT_SECRET_KEY)

@shared_task(bind=True, max_retries=3, default_retry_delay=60) # bind=True для доступа к self (для retry)
def upload_files(self, user_id, filename, signed_url, bucket_name):
    try:
        user = User.objects.get(username="Egor") if user_id is None else User.objects.get(id=user_id) # Получаем объект пользователя по ID
        s3_client = get_s3_client()

        # Качаем файл
        response = requests.get(signed_url, stream=True, timeout=60)
        response.raise_for_status()

        # Используем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name

        full_file_path = f'statement/{filename}'

        with open(tmp_path, 'rb') as data_file:
            s3_client.upload_fileobj(data_file, bucket_name, full_file_path)

        # Delete tmp file
        os.remove(tmp_path)

        # Creating an import record
        lookup_params = {
            'user': user,
            's3_file_key': full_file_path,
            'sourse': 'bcc',
        }
        defaults_params = {
            'status': BankExportFiles.Status.PENDING
        }
        bank_export_file_instance, new_import = BankExportFiles.objects.get_or_create(**lookup_params, defaults=defaults_params)

        if new_import:
            return f'File imported successfully and new record created. ID: {bank_export_file_instance.id}'
        else:
            return f'File record already exists. ID: {bank_export_file_instance.id}'
    except Exception as e:
        raise self.retry(exc=e) # Повторить задачу в случае ошибки

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
        html_content = response['Body'].read().decode('utf-8')

        # Вызываем наш парсер
        parser = BccStatementParser(html_content)
        parsed_data = parser.parse()

        header = parsed_data['header']
        transactions_data = parsed_data['transactions']

        with db_transaction.atomic():
            # Находим или создаем банковский счет
            bank_account = Account.objects.filter(currency__code = header['currency'], account_number__startswith = header['account_number']).first()
            user = bank_account.user
            
            
            created_count = 0
            skipped_count = 0
            for tx_data in transactions_data:
                amount = 0
                
                currency = Currency.objects.filter(code = header['currency']).first()
                original_currency = Currency.objects.filter(code = 'USD').first()

                original_amount = (-1)*float(tx_data['amount'])
                if tx_data.get('currency') and isinstance(tx_data['currency'], str):
                    c = tx_data['currency'].split('-')
                    if len(c) == 2:
                        currency = Currency.objects.filter(code = c[0]).first()
                        original_currency = Currency.objects.filter(code = c[1]).first()
                else:
                    amount = original_amount

                income_category = None
                expense_category = None
                to_account = None

                # Ищем категорию по справочнику, если это расход и есть место
                if tx_data['type'] == 'expense' and tx_data.get('place'):
                    expense_category = _find_category_for_place(tx_data['place'], user)

                exchange_rate_value = None
                if tx_data.get('rate') is not None:
                    try:
                        exchange_rate_value = 1 / float(tx_data['rate'])
                    except (ValueError, TypeError, ZeroDivisionError): # Обработка если rate не число или 0
                        exchange_rate_value = 1.55

                if tx_data['type'] == 'transfer':
                    continue  # Пропускаем переводы между счетами
                    to_account = bank_account
                    bank_account = Account.objects.filter(currency__code = 'KZT', name__startswith = 'BCC').first()

                # Поля для поиска существующей транзакции (согласно unique_together + user)
                lookup_params = {
                    'user': user,
                    'account': bank_account,
                    'transaction_type': tx_data['type'],
                    'date': tx_data['real_date'],
                    'date_processing': tx_data['trans_date'],
                    'original_amount': original_amount,
                    'original_currency': original_currency,
                    'comment': tx_data['description'],
                }
                # Поля, которые будут установлены, если транзакция создается
                defaults_params = {
                    'category': expense_category,
                    'income_category': income_category,
                    'amount': amount, # amount все еще 0, но теперь используется только при создании
                    'currency': currency,
                    'exchange_rate': exchange_rate_value,
                    'place': tx_data['place'],
                    'to_account': to_account,
                    'statement_import': bank_statement
                }
                _, created = Transaction.objects.get_or_create(**lookup_params, defaults=defaults_params)
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        
        # Обновляем статус импорта
        bank_statement.status = BankExportFiles.Status.COMPLETED
        bank_statement.processed_at = timezone.now()
        bank_statement.notes = f"Успешно обработано. Создано новых транзакций: {created_count}. Пропущено дубликатов: {skipped_count}."
        bank_statement.save()

    except Exception as e:
        # В случае любой ошибки, помечаем задачу как проваленную и записываем ошибку
        if 'statement_import' in locals():
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
            
                
        return f"Categorized {transactions.count()} transactions successfully."
    except Exception as e:
        # В случае ошибки обновляем лог
        log_entry.status = GptLog.Status.FAILED
        log_entry.error_message = str(e)
        log_entry.save(update_fields=['status', 'error_message', 'updated_at'])
        raise self.retry(exc=e)