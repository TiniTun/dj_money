from django.urls import path

from . import views

app_name = 'money'
urlpatterns = [
    path('', views.index, name='index'),
    path('transactions/', views.TransactionView.as_view(), name='transactions'),
    path('halyk/', views.halyk_converter, name='halyk'),
    path('ziirat/', views.ziirat_converter, name='ziirat'),
    path('deniz/', views.deniz_converter, name='deniz'),
    path('kaspikz/', views.kaspikz_converter, name='kaspikz'),
    path('bcckz/', views.bcckz_converter, name='bcckz'),
    path('upload/', views.upload_file, name='upload_file'),
    path('get_currency/', views.get_currency_exchange_rate, name='get_currency'),
]