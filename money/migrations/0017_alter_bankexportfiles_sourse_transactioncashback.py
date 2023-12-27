# Generated by Django 4.1.7 on 2023-12-27 16:05

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('money', '0016_alter_bankexportfiles_sourse'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bankexportfiles',
            name='sourse',
            field=models.CharField(choices=[('halyk', 'Halyk'), ('ziirat', 'Ziirat'), ('deniz', 'Deniz'), ('kaspikz', 'Kaspi.kz'), ('bcc', 'BCC.kz')], default='halyk', max_length=10),
        ),
        migrations.CreateModel(
            name='TransactionCashback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('real_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('cashback', models.DecimalField(decimal_places=2, max_digits=10)),
                ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='money.transaction')),
            ],
        ),
    ]
