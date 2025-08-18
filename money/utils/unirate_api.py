import requests
from datetime import date
from typing import Iterable, Optional, List, Dict, Any

from django.conf import settings


UNIRATE_API_URL: str = getattr(settings, 'UNIRATE_API_URL', 'https://api.unirateapi.com')
UNIRATE_API_KEY: Optional[str] = getattr(settings, 'UNIRATE_API_KEY', None)

DEFAULT_BASE_CURRENCY = 'USD'
DEFAULT_SYMBOLS = ['AUD', 'KZT', 'RUB']


def _require_api_key() -> str:
    if not UNIRATE_API_KEY:
        raise ValueError('UNIRATE_API_KEY is not configured in Django settings')
    return UNIRATE_API_KEY


def _base_url() -> str:
    return UNIRATE_API_URL.rstrip('/')


def latest(
    *,
    base: str = DEFAULT_BASE_CURRENCY,
    symbols: Iterable[str] = tuple(DEFAULT_SYMBOLS),
    for_date: Optional[date] = None,
    extra_currency: Optional[str] = None,
    only_extra: bool = False,
) -> Dict[str, Any]:
    """Fetch latest rates by calling Unirate `/api/rates` per symbol.

    If `for_date` is provided, it is used as the record date; otherwise, today's date is used.
    """
    api_key = _require_api_key()

    query_date = for_date or date.today()

    # Normalize symbols to a list
    if only_extra:
        target_symbols: List[str] = [extra_currency] if extra_currency else []
    else:
        target_symbols = list(symbols) if symbols is not None else list(DEFAULT_SYMBOLS)
        if extra_currency and extra_currency not in target_symbols:
            target_symbols.append(extra_currency)

    collected_rates: Dict[str, float] = {}
    for target_code in target_symbols:
        response = requests.get(
            f"{_base_url()}/api/rates",
            params={
                'api_key': api_key,
                'amount': 1,
                'from': base,
                'to': target_code,
                'format': 'json',
            },
            headers={'accept': 'application/json'},
        )
        response.raise_for_status()

        payload = response.json()
        rate_value = payload.get('rate')
        if rate_value is None:
            continue
        collected_rates[target_code] = rate_value

    return {
        'date': query_date,
        'base': base,
        'rates': collected_rates,
    }


def history(
    *,
    on_date: date,
    base: str = DEFAULT_BASE_CURRENCY,
    symbols: Iterable[str] = tuple(DEFAULT_SYMBOLS),
    extra_currency: Optional[str] = None, 
    only_extra: bool = False
) -> Dict[str, Any]:
    """Fetch historical rates for a single date via /api/historical/rates and persist.

    Iteration over multiple dates should be handled by the caller.
    """
    api_key = _require_api_key()

    # Normalize symbols to a list
    if only_extra:
        target_symbols: List[str] = [extra_currency] if extra_currency else []
    else:
        target_symbols = list(symbols) if symbols is not None else list(DEFAULT_SYMBOLS)
        if extra_currency and extra_currency not in target_symbols:
            target_symbols.append(extra_currency)

    collected_rates: Dict[str, float] = {}
    for target_code in target_symbols:
        response = requests.get(
            f"{_base_url()}/api/historical/rates",
            params={
                'api_key': api_key,
                'date': on_date.isoformat(),
                'amount': 1,
                'from': base,
                'to': target_code,
                'format': 'json',
            },
            headers={'accept': 'application/json'},
        )
        response.raise_for_status()

        payload = response.json()
        rate_value = payload.get('rate')
        if rate_value is None:
            continue
        collected_rates[target_code] = rate_value

    return {
        'date': on_date,
        'base': base,
        'rates': collected_rates,
    }


def timeseries(
    *,
    start_date: date,
    end_date: date,
    base: str = DEFAULT_BASE_CURRENCY,
    symbols: Iterable[str] = tuple(DEFAULT_SYMBOLS),
    extra_currency: Optional[str] = None, 
    only_extra: bool = False
) -> Dict[str, Any]:
    """Fetch rates for a date range via /api/historical/timeseries and persist.

    Both dates are inclusive. Expects response with `data` mapping of date -> { currency: rate }.
    """
    api_key = _require_api_key()

    # Normalize symbols to a list and format for API
    if only_extra:
        target_symbols: List[str] = [extra_currency] if extra_currency else []
    else:
        target_symbols = list(symbols) if symbols is not None else list(DEFAULT_SYMBOLS)
        if extra_currency and extra_currency not in target_symbols:
            target_symbols.append(extra_currency)
            
    currencies_param = ', '.join(target_symbols)

    response = requests.get(
        f"{_base_url()}/api/historical/timeseries",
        params={
            'api_key': api_key,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'amount': 1,
            'base': base,
            'format': 'json',
            'currencies': currencies_param,
        },
        headers={'accept': 'application/json'},
    )
    response.raise_for_status()

    payload = response.json()
    data_map = payload.get('data') or {}

    # Return normalized structure
    normalized: Dict[str, Dict[str, float]] = {}
    if isinstance(data_map, dict):
        for date_str, day_rates in data_map.items():
            if not isinstance(day_rates, dict):
                continue
            normalized[date_str] = {str(code): float(rate) for code, rate in day_rates.items()}

    return {
        'base': base,
        'start_date': start_date,
        'end_date': end_date,
        'data': normalized,
    }


