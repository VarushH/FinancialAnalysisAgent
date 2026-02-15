"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
        'version': '2.0 - Supervisor Agent Architecture',
        'endpoints': {
            'admin': '/admin/',
            'upload_file': 'POST /api/upload/',
            'start_analysis': 'POST /api/sessions/<session_id>/start/',
            'approve_checkpoint': 'POST /api/sessions/<session_id>/approve/',
            'get_status': 'GET /api/sessions/<session_id>/status/',
            'download_report': 'GET /api/sessions/<session_id>/report/',
            'retry_analysis': 'POST /api/sessions/<session_id>/retry/',
            'list_sessions': 'GET /api/sessions/',
            'websocket': 'ws://127.0.0.1:8000/ws/progress/<session_id>/'
        },
        'features': [
            'Supervisor agent pattern',
            'Human-in-the-loop checkpoints',
            'Async parallel execution',
            'State persistence',
            'Retry mechanisms'
        ]
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    
    # File upload
    path('api/upload/', views.upload_file, name='upload_file'),
    
    # Session management
    path('api/sessions/', views.list_sessions, name='list_sessions'),
    path('api/sessions/<int:session_id>/start/', views.start_analysis, name='start_analysis'),
    path('api/sessions/<int:session_id>/status/', views.get_session_status, name='get_session_status'),
    path('api/sessions/<int:session_id>/approve/', views.approve_checkpoint, name='approve_checkpoint'),
    path('api/sessions/<int:session_id>/report/', views.download_report, name='download_report'),
    path('api/sessions/<int:session_id>/retry/', views.retry_analysis, name='retry_analysis'),
    
    # Legacy endpoints for backward compatibility
    path('api/start/<int:session_id>/', views.start_analysis, name='start_analysis_legacy'),
    path('api/report/<int:session_id>/', views.download_report, name='download_report_legacy'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
