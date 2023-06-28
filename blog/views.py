from django.shortcuts import render
from django.conf import settings

def index(request):

    return render(request, 'blog/index.html', {'url': settings.STATIC_URL, 'root': settings.STATIC_ROOT, 'base': settings.BASE_DIR})
