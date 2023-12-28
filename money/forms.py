from django import forms
from .models import BankExportFiles

class BankExportFilesForm(forms.ModelForm):
    class Meta:
        model = BankExportFiles
        fields = ('sourse', 'description', 'document')

    
class DateCurrencyExchangeForm(forms.Form):
    start_date = forms.DateField()
    end_date = forms.DateField()
    extra_currency = forms.Field()
    only_extra = forms.BooleanField()
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        extra_currency = cleaned_data.get('extra_currency')
        only_extra = cleaned_data.get('only_extra')
        
        if only_extra:
            if not extra_currency:
                raise forms.ValidationError("Add extra currency.")

        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("End date should be greater than start date.")