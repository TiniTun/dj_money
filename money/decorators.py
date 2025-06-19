# dj_money/money/decorators.py
from functools import wraps
from django.http import JsonResponse
from django.conf import settings

def token_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        token = request.headers.get('Authorization')
        expected_token = f'Token {settings.DOWNLOAD_API_TOKEN}'

        if token != expected_token:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
