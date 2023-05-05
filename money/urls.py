from django.urls import path

from . import views

app_name = 'money'
urlpatterns = [
    path('', views.index, name='index'),
    path('transactions/', views.TransactionView.as_view(), name='transactions'),
    path('halyk/', views.halyk_converter, name='halyk')
]