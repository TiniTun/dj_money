import logging
from datetime import date
from typing import Iterable, Optional

from money.models import Currency, ExchangeRate
from money.utils import frankfurter_api

logger = logging.getLogger(__name__)


def default_symbols(base: str = frankfurter_api.DEFAULT_BASE_CURRENCY) -> list:
    """All currencies known to the app except the base one."""
    return list(Currency.objects.exclude(code=base).values_list('code', flat=True))


def sync_exchange_rates(
    start_date: date,
    end_date: date,
    *,
    symbols: Optional[Iterable[str]] = None,
    base: str = frankfurter_api.DEFAULT_BASE_CURRENCY,
    overwrite: bool = True,
) -> int:
    """Fetch rates from Frankfurter for the range and store them as ExchangeRate rows.

    With overwrite=False rates that are already stored are kept untouched, so only gaps are filled.
    Returns the number of rates received from the API.
    """
    if not Currency.objects.filter(code=base).exists():
        raise ValueError(f'Base currency {base} is missing in the Currency table')

    symbols = list(symbols) if symbols is not None else default_symbols(base)
    supported = frankfurter_api.supported_currencies()
    skipped = sorted(set(symbols) - supported)
    if skipped:
        logger.warning('Frankfurter does not quote %s, skipping them', ', '.join(skipped))
    symbols = [code for code in symbols if code in supported]

    rates_by_date = frankfurter_api.rates(start_date=start_date, end_date=end_date, base=base, symbols=symbols)

    currencies = {c.code: c for c in Currency.objects.filter(code__in=[base, *symbols])}
    base_currency = currencies[base]
    rows = [
        ExchangeRate(
            source_currency=base_currency,
            target_currency=currencies[code],
            exchange_rate=round(rate, 6),
            date=day,
        )
        for day, day_rates in rates_by_date.items()
        for code, rate in day_rates.items()
        if code in currencies
    ]

    if overwrite:
        ExchangeRate.objects.bulk_create(
            rows,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=['source_currency', 'target_currency', 'date'],
            update_fields=['exchange_rate'],
        )
    else:
        ExchangeRate.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True)
    return len(rows)
