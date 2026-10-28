from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from money.models import ExpenseCategory, Transaction
from money.tasks import _find_category_for_place


class Command(BaseCommand):
    help = 'Apply PlaceCategoryMapping rules to expenses that are already loaded, the same way a statement import does.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only print what would change.')
        parser.add_argument('--overwrite', action='store_true', help='Also recategorize expenses that already have a category. By default only uncategorized ones are filled.')
        parser.add_argument('--category', help='Apply only rules for the category with this name, e.g. "Переводы между своими".')

    def handle(self, *args, **options):
        only = options['category']
        if only and not ExpenseCategory.objects.filter(name__iexact=only).exists():
            raise CommandError(f'No expense category named {only!r}.')

        expenses = (Transaction.objects.filter(transaction_type='expense').exclude(place__isnull=True)
                    .exclude(place='').select_related('account', 'category').order_by('date', 'id'))
        matches = {}  # (user_id, place) -> category; statements repeat the same place many times
        changes = defaultdict(list)
        kept = 0
        for tx in expenses:
            key = (tx.user_id, tx.place)
            if key not in matches:
                matches[key] = _find_category_for_place(tx.place, tx.user_id)
            category = matches[key]
            if category is None or category.id == tx.category_id:
                continue
            if only and category.name.lower() != only.lower():
                continue
            if tx.category_id and not options['overwrite']:
                kept += 1
                continue
            changes[category].append(tx)
            self.stdout.write(f'{tx.date} {tx.account.name}: {tx.place} | {tx.category or "—"} -> {category}')

        total = sum(len(txs) for txs in changes.values())
        if kept:
            self.stdout.write(f'{kept} expenses already have another category, pass --overwrite to change them.')
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'Dry run: {total} expenses would be recategorized, nothing saved.'))
            return

        with db_transaction.atomic():
            for category, txs in changes.items():
                # update() skips Transaction.save, which recomputes exchange rates
                Transaction.objects.filter(id__in=[tx.id for tx in txs]).update(category=category)
        self.stdout.write(self.style.SUCCESS(f'Recategorized {total} expenses.'))
