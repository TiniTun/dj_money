import requests
from datetime import date
from typing import Iterable, Optional, Dict, Set

from django.conf import settings


FRANKFURTER_API_URL: str = getattr(settings, 'FRANKFURTER_API_URL', 'https://api.frankfurter.dev/v2')
REQUEST_TIMEOUT = 60

DEFAULT_BASE_CURRENCY = 'USD'


def _base_url() -> str:
    return FRANKFURTER_API_URL.rstrip('/')


def is_transient_error(exc: Exception) -> bool:
    """Network failures and 5xx are worth retrying; 4xx (bad currency, bad date) will fail again."""
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def supported_currencies() -> Set[str]:
    """ISO codes the API can quote. A single unknown code makes /rates reject the whole request."""
    response = requests.get(f"{_base_url()}/currencies", headers={'accept': 'application/json'}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return {row['iso_code'] for row in response.json()}


def rates(
    *,
    start_date: date,
    end_date: Optional[date] = None,
    base: str = DEFAULT_BASE_CURRENCY,
    symbols: Iterable[str],
) -> Dict[date, Dict[str, float]]:
    """Fetch daily rates for an inclusive date range in a single request.

    Returns a mapping of date -> {currency: rate}, where rate is the amount of
    `currency` for 1 unit of `base`. Days without published rates are absent.
    """
    quotes = [code for code in symbols if code != base]
    if not quotes:
        return {}

    response = requests.get(
        f"{_base_url()}/rates",
        params={
            'base': base,
            'quotes': ','.join(quotes),
            'from': start_date.isoformat(),
            'to': (end_date or start_date).isoformat(),
        },
        headers={'accept': 'application/json'},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    result: Dict[date, Dict[str, float]] = {}
    for row in response.json():
        day = date.fromisoformat(row['date'])
        result.setdefault(day, {})[row['quote']] = float(row['rate'])
    return result
