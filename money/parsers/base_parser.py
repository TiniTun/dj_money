# money/parsers/base_parser.py
from decimal import Decimal, InvalidOperation

class BaseParser:
    """
    A base class for statement parsers, providing common utility methods.
    """
    def _clean_text(self, text):
        """Removes leading/trailing whitespace from a string."""
        if text is None:
            return ""
        return text.strip()

    def _parse_amount(self, amount_str):
        """
        Parses a string into a Decimal, handling common formatting issues.
        Returns None if the string is empty or cannot be parsed.
        """
        if not amount_str or not self._clean_text(str(amount_str)):
            return None
        # Убираем пробелы-разделители и заменяем запятую на точку
        cleaned_str = self._clean_text(str(amount_str)).replace(' ', '').replace(',', '.')
        try:
            return Decimal(cleaned_str)
        except InvalidOperation:
            # Обработка случаев, когда строка не является валидным числом
            return None

    def parse(self):
        """Each subclass must implement its own parsing logic."""
        raise NotImplementedError("The 'parse' method must be implemented by subclasses.")

