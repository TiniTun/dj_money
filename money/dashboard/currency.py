from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from money.models import ExchangeRate

BASE_CODE = 'USD'


class RateBook:
    """USD-based exchange rates held in memory, loaded with a single query."""

    def __init__(self, codes: Iterable[str], until: date):
        rates = ExchangeRate.objects.filter(
            source_currency__code=BASE_CODE, target_currency__code__in=set(codes), date__lte=until,
        ).order_by('date').values_list('target_currency__code', 'date', 'exchange_rate')
        self.dates = defaultdict(list)
        self.values = defaultdict(list)
        for code, rate_date, rate in rates:
            self.dates[code].append(rate_date)
            self.values[code].append(rate)

    def rate(self, code: str, on: date) -> Decimal | None:
        """Units of the currency per 1 USD: the last rate on or before the date, None if there is none."""
        if code == BASE_CODE:
            return Decimal(1)
        index = bisect_right(self.dates[code], on)
        return self.values[code][index - 1] if index else None

    def convert(self, amount: Decimal, from_code: str, to_code: str, on: date) -> Decimal | None:
        if from_code == to_code:
            return amount
        from_rate, to_rate = self.rate(from_code, on), self.rate(to_code, on)
        if from_rate is None or to_rate is None:
            return None
        return amount / from_rate * to_rate


def available_currencies() -> list[str]:
    """Currencies the dashboard can show totals in: USD plus everything quoted against it."""
    quoted = ExchangeRate.objects.filter(source_currency__code=BASE_CODE).values_list('target_currency__code', flat=True)
    return sorted({BASE_CODE, *quoted})
