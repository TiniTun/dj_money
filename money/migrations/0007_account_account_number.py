# Generated by Django 4.1.7 on 2023-05-02 14:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('money', '0006_account_bank_card'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='account_number',
            field=models.CharField(default='', max_length=255),
        ),
    ]
