# Generated by Django 4.1.7 on 2023-05-01 20:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('money', '0002_accounttype_expensecategory_parent_category_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=3)),
                ('name', models.CharField(max_length=255)),
            ],
        ),
    ]
