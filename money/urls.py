from django.urls import path

from . import views

app_name = 'money'
urlpatterns = [
    path('', views.index, name='index'),
    path('transactions/', views.TransactionView.as_view(), name='transactions'),
    path('upload/', views.upload_file, name='upload_file'),
    path('get_currency/', views.get_currency_exchange_rate, name='get_currency'),
    path('api/upload_external_file/', views.upload_external_file, name='upload_external_file'),
    path('api/parse_statement_files/', views.parse_statement_files, name='parse_statement_files'),
    path('api/run_batch_categorization/', views.run_batch_categorization, name='run_batch_categorization'),
]