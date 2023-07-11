import requests
from datetime import date, timedelta
from django.conf import settings
from money.models import Currency, ExchangeRate  # replace 'your_app' with your app's name

def fetch_historical_exchange_rates(start_date: date, end_date: date, base_currency_code='USD'):
    access_key = settings.FIXER_API_KEY  # replace with your actual API key

    target_currency_codes = ['RUB', 'TRY', 'EUR', 'KZT', 'AUD']
    symbols = ','.join(target_currency_codes)

    try:
        response = requests.get(f'{settings.FIXER_API_URL}timeseries', params={
            'access_key': access_key,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'base': base_currency_code,
            'symbols': symbols,
        })
        
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching exchange rates: {e}")
        # Here you can decide how you want to handle the exception, for example:
        # - You might want to re-raise the exception.
        # - You could return from the function.
        # - If you're in a loop, you could continue to the next iteration.
        # For this example, let's re-raise the exception
        raise e

    data = response.json()

    if data['success']:
        base_currency = Currency.objects.get(code=base_currency_code)

        for date_str, rates in data['rates'].items():
            for target_currency_code, exchange_rate in rates.items():
                target_currency = Currency.objects.get(code=target_currency_code)
                ExchangeRate.objects.create(
                    source_currency=base_currency,
                    target_currency=target_currency,
                    exchange_rate=exchange_rate,
                    date=date.fromisoformat(date_str),
                )
        return 
    else:
        error_info = data.get('error', {})  # The API might provide error details under 'error'
        print(f"Failed to fetch historical exchange rates: {error_info}")


def fetch_exchange_rates_for_date(target_date: date, base_currency_code='USD'):
    access_key = settings.FIXER_API_KEY  # replace with your actual API key

    target_currency_codes = ['RUB', 'TRY', 'EUR', 'KZT', 'AUD']
    symbols = ','.join(target_currency_codes)

    try:
        response = requests.get(f'{settings.FIXER_API_URL}{target_date.isoformat()}', params={
            'access_key': access_key,
            'base': base_currency_code,
            'symbols': symbols,
        })

        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching exchange rates: {e}")
        raise e

    data = response.json()

    if data['success']:
        base_currency = Currency.objects.get(code=base_currency_code)

        for target_currency_code, exchange_rate in data['rates'].items():
            target_currency = Currency.objects.get(code=target_currency_code)
            ExchangeRate.objects.create(
                source_currency=base_currency,
                target_currency=target_currency,
                exchange_rate=exchange_rate,
                date=target_date,
            )
    else:
        error_info = data.get('error', {})  # The API might provide error details under 'error'
        print(f"Failed to fetch exchange rates for {target_date}: {error_info}")

def date_range(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)