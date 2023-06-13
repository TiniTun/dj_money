from django.forms import widgets

class CustomSelectWidget(widgets.Select):
    template_name = 'widgets/select.html'
    option_inherits_attrs = True
