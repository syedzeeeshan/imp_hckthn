"""
URL configuration for Campus Club Management Suite
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse  # Add this import
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# API URL patterns
api_v1_patterns = [
    path('auth/', include('apps.authentication.urls')),
    path('clubs/', include('apps.clubs.urls')),
    path('events/', include('apps.events.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('collaboration/', include('apps.collaboration.urls')),
    path('gamification/', include('apps.gamification.urls')),
    path('messaging/', include('apps.messaging.urls')),
    path('notifications/', include('apps.notifications.urls')),
]

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API
    path('api/v1/', include(api_v1_patterns)),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # Health check
    path('health/', lambda request: HttpResponse('OK')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site configuration
admin.site.site_header = 'Campus Club Management Suite'
admin.site.site_title = 'Campus Club Management'
admin.site.index_title = 'Administration Dashboard'
