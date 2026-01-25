"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from api import views

def home(request):
    """
    Root endpoint - returns API information
    """
    return JsonResponse({
        'message': 'Financial Analysis Agent API',
        'version': '1.0',
        'endpoints': {
            'admin': '/admin/',
            'upload_file': '/api/upload/',
            'start_analysis': '/api/start/<session_id>/',
            'download_report': '/api/report/<session_id>/',
            'websocket': 'ws://127.0.0.1:8000/ws/progress/<session_id>/'
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('api/upload/', views.upload_file, name='upload_file'),
    path('api/start/<int:session_id>/', views.start_analysis, name='start_analysis'),
    path('api/report/<int:session_id>/', views.download_report, name='download_report'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
