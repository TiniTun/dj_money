from django.forms import widgets
from django import forms
from django.utils.html import format_html
    
class HierarchicalSelect(forms.Select):
    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs,choices)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        dashes = 0
        while label.startswith("-"):
            dashes += 1
            label = label[1:]
        option['label'] = format_html('{}{}', '-' * dashes, label.strip())
        return option