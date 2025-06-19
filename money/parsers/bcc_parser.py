# money/parsers/bcc_parser.py
import re
from datetime import datetime
from decimal import Decimal
from bs4 import BeautifulSoup

class BccStatementParser:
    def __init__(self, file_content):
        # BeautifulSoup лучше работает с lxml парсером
        self.soup = BeautifulSoup(file_content, 'html.parser')
        self.data = {
            'header': {},
            'transactions': [],
            'totals': {},
            'balances': {}
        }

    def _clean_text(self, text):
        return text.strip()

    def _parse_amount(self, amount_str):
        if not amount_str or not amount_str.strip():
            return None
        # Убираем пробелы-разделители и заменяем запятую на точку, если нужно
        cleaned_str = amount_str.strip().replace(' ', '').replace(',', '.')
        return Decimal(cleaned_str)

    def _parse_header(self):
        header_data = {}
        # Находим все строки таблицы с заголовком
        rows = self.soup.find('table', {'width': '90%'}).find_all('tr', recursive=False)
        for row in rows:
            cols = row.find_all('td')
            if len(cols) == 2:
                key = self._clean_text(cols[0].text).replace(':', '')
                value = self._clean_text(cols[1].text)
                header_data[key] = value
        
        self.data['header'] = {
            'account_number': header_data.get('Выписка по счету')[1:],
            'owner_name': header_data.get('Ф.И.О. клиента'),
            'currency': header_data.get('Валюта депозита'),
        }
    
    def _parse_transaction_line(self,line):
        """
        Разбирает строку транзакции для извлечения Даты, Места, 
        и опционально Валют и IPS.
        """
        # Регулярное выражение для разбора строки транзакции
        pattern = re.compile(
            r"Retail\. Номер устройства в ПЦ, "
            r"(?P<date>\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}),\s*"
            r"(?P<place>.*?)"  # Нежадный захват Места
            r",\s*Карта:\s*[^ ]+"  # Разделитель: ", Карта: НОМЕР_КАРТЫ "
            # Необязательная группа для Валют и IPS
            r"(?:\s+Валюты:(?P<currency>[A-Z]{3}-[A-Z]{3})\|\s*IPS:\s*(?P<rate>\d+\.\d+))?"
            r"(?:.*)"  # Соответствует оставшейся части строки
        )

        match = pattern.match(line.strip()) # Используем .match(), так как шаблон описывает начало строки
        if match:
            data = match.groupdict()
            # Очищаем пробелы по краям для "Места"
            if data.get("place"):
                data["place"] = data["place"].strip()
            return data
        return None


    def _parse_transactions(self):
        # Находим таблицу с транзакциями. Она идет после таблицы с входящим остатком.
        transaction_table = self.soup.find_all('table', {'cellpadding': '2', 'cellspacing': '1'})[1]
        if not transaction_table:
            raise ValueError("Таблица транзакций не найдена в файле.")
        
        rows = transaction_table.find_all('tr')
        # Пропускаем заголовок (th) и итоговую строку
        for row in rows[1:-1]: # Пропускаем заголовок и итоговую строку
            real_date = None
            place = None
            currency = None
            rate = None
            
            cols = row.find_all('td')
            if len(cols) != 5:
                continue

            debit_str = self._clean_text(cols[2].text)
            credit_str = self._clean_text(cols[3].text)
            
            # Определяем тип и сумму
            if debit_str:
                amount = self._parse_amount(debit_str)
                trans_type = 'expense'
            elif credit_str:
                amount = self._parse_amount(credit_str)
                trans_type = 'income'
            else:
                continue # Пропускаем, если нет ни дебета ни кредита

            # Парсим дату. В HTML она в формате dd.mm.yyyy
            date_str = self._clean_text(cols[1].text)
            trans_date = datetime.strptime(date_str, '%d.%m.%Y').date()

            # Парсим дополнительные данные из колонки с описанием
            parse_data = self._parse_transaction_line(cols[4].text)
            if not parse_data:
                trans_type = 'transfer'
            else:
                real_date =  datetime.strptime(parse_data.get('date'), '%d.%m.%Y %H:%M:%S').date()
                place = parse_data.get('place')
                currency = parse_data.get('currency')
                rate = parse_data.get('rate')



            self.data['transactions'].append({
                'trans_date': trans_date,
                'real_date': real_date,
                'place': place, # @todo Место транзакции, добавить в модель
                'currency': currency,
                'rate': self._parse_amount(rate),
                'description': self._clean_text(cols[4].text),
                'amount': amount,
                'type': trans_type,
            })

    def parse(self):
        """Основной метод, запускающий парсинг всего документа."""
        try:
            self._parse_header()
            self._parse_transactions()
            return self.data
        except Exception as e:
            # Логируем или пробрасываем ошибку выше
            raise ValueError(f"Ошибка при парсинге файла: {e}")