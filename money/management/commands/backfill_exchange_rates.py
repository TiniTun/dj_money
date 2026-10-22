from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min

from money.models import Transaction
from money.utils.exchange_rates import sync_exchange_rates


class Command(BaseCommand):
    help = 'Load historical USD exchange rates from Frankfurter into ExchangeRate.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=date.fromisoformat, help='First date, YYYY-MM-DD. Defaults to the earliest transaction.')
        parser.add_argument('--end', type=date.fromisoformat, help='Last date, YYYY-MM-DD. Defaults to today.')
        parser.add_argument('--currencies', help='Comma-separated codes, e.g. KZT,RUB. Defaults to all currencies in the app.')
        parser.add_argument('--overwrite', action='store_true', help='Replace rates that are already stored. By default only gaps are filled.')

    def handle(self, *args, **options):
        start = options['start'] or Transaction.objects.aggregate(first=Min('date'))['first']
        if start is None:
            raise CommandError('No transactions yet, pass --start.')
        end = options['end'] or date.today()
        symbols = options['currencies'].upper().split(',') if options['currencies'] else None

        count = sync_exchange_rates(start, end, symbols=symbols, overwrite=options['overwrite'])
        self.stdout.write(self.style.SUCCESS(
            f'Received {count} rates from {start.isoformat()} to {end.isoformat()}'
            f' ({"overwritten" if options["overwrite"] else "only missing ones saved"}).'
        ))
