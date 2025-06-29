# money/migrations/0026_refactor_bank_source.py
from django.db import migrations, models
import django.db.models.deletion

# Полный список источников, включая старые и новые
BANK_SOURCES_DATA = [
    {'code': 'halyk', 'name': 'Halyk'},
    {'code': 'ziirat', 'name': 'Ziraat'},
    {'code': 'deniz', 'name': 'Deniz'},
    {'code': 'kaspikz', 'name': 'Kaspi.kz'},
    {'code': 'bcc', 'name': 'BCC.kz'},
    {'code': 'ff', 'name': 'Freedom Finance'},
]

def populate_bank_sources(apps, schema_editor):
    BankSource = apps.get_model('money', 'BankSource')
    BankExportFiles = apps.get_model('money', 'BankExportFiles')
    db_alias = schema_editor.connection.alias

    for source_data in BANK_SOURCES_DATA:
        BankSource.objects.using(db_alias).get_or_create(
            code=source_data['code'],
            defaults={'name': source_data['name']}
        )

    for file_import in BankExportFiles.objects.using(db_alias).all():
        if hasattr(file_import, 'sourse') and file_import.sourse:
            source_obj = BankSource.objects.using(db_alias).get(code=file_import.sourse)
            file_import.source = source_obj
            file_import.save(update_fields=['source'])

def reverse_populate_bank_sources(apps, schema_editor):
    BankExportFiles = apps.get_model('money', 'BankExportFiles')
    db_alias = schema_editor.connection.alias

    for file_import in BankExportFiles.objects.using(db_alias).all():
        if file_import.source:
            file_import.sourse = file_import.source.code
            file_import.save(update_fields=['sourse'])

class Migration(migrations.Migration):

    dependencies = [
        ('money', '0025_placecategorymapping'),
    ]

    operations = [
        migrations.CreateModel(
            name='BankSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Human-readable name of the bank (e.g., 'Halyk Bank').", max_length=100, unique=True)),
                ('code', models.SlugField(help_text="A unique code for programmatic access (e.g., 'halyk').", max_length=20, unique=True)),
            ],
            options={'ordering': ['name']},
        ),
        # 2. Add the new 'source' field, making it nullable for now
        migrations.AddField(
            model_name='bankexportfiles',
            name='source',
            field=models.ForeignKey(help_text='Source bank', null=True, on_delete=django.db.models.deletion.PROTECT, to='money.banksource'),
        ),
        # 3. Run the data migration to populate the new 'source' field
        migrations.RunPython(populate_bank_sources, reverse_code=reverse_populate_bank_sources),
        # 4. Remove the old unique_together constraint that depends on 'sourse'
        migrations.AlterUniqueTogether(
            name='bankexportfiles',
            unique_together=set(),
        ),
        # 5. Now it's safe to remove the 'sourse' field
        migrations.RemoveField(
            model_name='bankexportfiles',
            name='sourse',
        ),
        # 6. Make the 'source' field non-nullable as it's now populated
        migrations.AlterField(
            model_name='bankexportfiles',
            name='source',
            field=models.ForeignKey(help_text='Source bank', on_delete=django.db.models.deletion.PROTECT, to='money.banksource'),
        ),
        # 7. Re-create the unique_together constraint with the new 'source' field
        migrations.AlterUniqueTogether(
            name='bankexportfiles',
            unique_together={('user', 's3_file_key', 'source')},
        ),
    ]
