from django import forms
from django.core.validators import FileExtensionValidator
from .models import BankExportFiles

VALID_EXTENSIONS = ['csv']

class BankExportFilesForm(forms.ModelForm):
    class Meta:
        model = BankExportFiles
        fields = ('description', 'document')

    
