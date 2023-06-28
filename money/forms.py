from django import forms
from .models import BankExportFiles

class BankExportFilesForm(forms.ModelForm):
    class Meta:
        model = BankExportFiles
        fields = ('sourse', 'description', 'document')

    
