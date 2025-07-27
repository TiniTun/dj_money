# money/parsers/commbank_parser.py
import csv
import re
from .base_parser import BaseParser
from io import StringIO
from datetime import datetime
from decimal import Decimal


class CommbankStatementParser(BaseParser):
    """
    Parser for Comm Bank statements.
    Parses CSV files with columns: Date, Transaction details, Amount, Balance
    """
    def __init__(self, file_content):
        # Call the parent's constructor to correctly initialize
        self.file_content = file_content
        self.data = {
            'header': {},  # CSV might not have a header, but we keep the structure
            'transactions': [],
            'errors': []  # Add a list to store parsing errors
        }

    def _parse_amount(self, amount_str):
        """
        Parses an amount string into a Decimal.
        """
        if not amount_str or not self._clean_text(str(amount_str)):
            return None
        # Remove thousands separators and replace comma with dot
        cleaned_str = self._clean_text(str(amount_str)).replace(' ', '').replace(',', '').replace('$', '')
        try:
            return Decimal(cleaned_str)
        except Exception:
            return None

    def _parse_description(self, description):
        """
        Extracts 'place' and 'real_date' from the description string.
        """
        place = None
        real_date = None
        # Try to extract Value Date
        match = re.search(r'Value Date: (\d{2}/\d{2}/\d{4}|\d{2}\.\d{2}\.\d{4}|\d{2}-\d{2}-\d{4})', description)
        if match:
            date_str = match.group(1)
            for fmt in ('%d/%m/%Y', '%d.%m.%Y', '%d-%m-%Y'):
                try:
                    real_date = datetime.strptime(date_str, fmt).date()
                    break
                except Exception:
                    continue
        # Place: take everything before 'Card' or 'Value Date'
        place_match = re.match(r'^(.*?)(?:\s+Card|\s+Value Date:)', description)
        if place_match:
            place = place_match.group(1).strip()
        else:
            # Fallback: take first words before Value Date
            place = description.split('Value Date:')[0].strip()
        return place, real_date

    def parse(self):
        """
        Main method to parse the CSV file and extract transactions.
        """
        try:
            csv_file = StringIO(self.file_content)
            reader = csv.reader(csv_file, delimiter=';')

            for row_num, row in enumerate(reader, 1):
                if not row or len(row) < 5:
                    self.data['errors'].append(f"Row {row_num}: Malformed row, expected at least 4 columns, got {len(row)}. Content: {row}")
                    continue  # Skip empty or malformed rows
                
                date_str, account_id, comment_str, amount_str, balance_str = row[:5]
                # Parse date
                try:
                    trans_date = datetime.strptime(date_str, '%d.%b.%y').date() if date_str else None
                except Exception:
                    self.data['errors'].append(f"Row {row_num}: Invalid date format '{date_str}'.")
                    trans_date = None
                # Parse amount
                amount = self._parse_amount(amount_str)
                # Parse balance
                balance = self._parse_amount(balance_str)
                # Determine type
                trans_type = 'income' if amount and amount > 0 else 'expense'
                place, real_date = self._parse_description(comment_str)
                self.data['transactions'].append({
                    'trans_date': trans_date,
                    'real_date': real_date if real_date else trans_date,
                    'account_id': self._clean_text(account_id),
                    'place': place,
                    'description': comment_str,
                    'amount': amount,
                    'balance': balance,
                    'type': trans_type
                })
            
            # Since a generic CSV doesn't have a clear header, we can set placeholders.
            # The main processing task will use the account_id from each row.
            self.data['header'] = {
                'account_number': 'FROM_CSV',
                'currency': 'AUD' # Currency should be determined by the account
            }
            return self.data
        except Exception as e:
            raise ValueError(f"Error parsing CommBank CSV: {e}")