# money/parsers/generic_csv_parser.py
import csv
from io import StringIO
from datetime import datetime
from .base_parser import BaseParser

class GenericCsvParser(BaseParser):
    """
    Parses a generic CSV file with a specific format:
    date;account_id;debit;credit;comment;to_account
    """
    def __init__(self, file_content):
        self.file_content = file_content
        self.data = {
            'header': {},  # CSV might not have a header, but we keep the structure
            'transactions': [],
            'errors': []  # Add a list to store parsing errors
        }

    def parse(self):
        """
        Main method to parse the CSV content.
        """
        # Use StringIO to treat the string content as a file-like object
        csv_file = StringIO(self.file_content)
        reader = csv.reader(csv_file, delimiter=';')

        # You can uncomment the next line if your CSV has a header row to skip
        # next(reader, None)

        for row_num, row in enumerate(reader, 1):
            try:
                if not row or len(row) < 6:
                    self.data['errors'].append(f"Row {row_num}: Malformed row, expected at least 6 columns, got {len(row)}. Content: {row}")
                    continue  # Skip empty or malformed rows

                date_str, account_id_str, debit_str, credit_str, to_account_str, comment_str = row[:6]

                # Use helper methods from BaseParser
                debit = self._parse_amount(debit_str)
                credit = self._parse_amount(credit_str)
                comment = self._clean_text(comment_str)

                # Determine transaction type and amount
                if debit and debit > 0:
                    trans_type = 'expense'
                    amount = -debit
                elif credit and credit > 0:
                    trans_type = 'income'
                    amount = credit
                else:
                    continue # Skip rows without a valid debit or credit

                # Parse date with error handling
                try:
                    trans_date = datetime.strptime(self._clean_text(date_str), '%d.%m.%Y').date()
                except ValueError:
                    self.data['errors'].append(f"Row {row_num}: Invalid date format for '{date_str}'. Expected DD.MM.YYYY.")
                    continue # Skip this row

                # Append transaction data in a standardized format
                self.data['transactions'].append({
                    'trans_date': trans_date,
                    'real_date': trans_date,
                    'place': comment,
                    'description': comment,
                    'amount': amount,
                    'type': trans_type,
                    # We can pass raw IDs to be resolved later
                    'account_id': self._clean_text(account_id_str),
                    'to_account': self._clean_text(to_account_str),
                })
            except Exception as e:
                # Catch any other unexpected errors during row processing
                self.data['errors'].append(f"Row {row_num}: An unexpected error occurred: {e}. Row content: {row}")
                continue

        # Since a generic CSV doesn't have a clear header, we can set placeholders.
        # The main processing task will use the account_id from each row.
        self.data['header'] = {
            'account_number': 'FROM_CSV',
            'currency': 'UNKNOWN' # Currency should be determined by the account
        }

        return self.data