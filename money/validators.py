from django.core.exceptions import ValidationError


def validate_file_extension(value):
    import os
    ext = os.path.splitext(value.name)[1]
    valid_extensions = ['.csv']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension. Please upload a CSV file.')