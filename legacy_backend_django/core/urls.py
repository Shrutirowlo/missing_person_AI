"""
URL configuration for core project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from matching.views import TestUIPageView

urlpatterns = [
    path('', TestUIPageView.as_view(), name='home-test-ui'),
    path('test-ui/', TestUIPageView.as_view(), name='test-ui'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/stations/', include('stations.urls')),
    path('api/cases/', include('cases.urls')),
    path('api/match/', include('matching.urls')),
    path('api/analytics/', include('analytics.urls')),
]

# Serve media and static files in development
if settings.DEBUG:
    from django.views.static import serve
    from django.urls import re_path
    from pathlib import Path

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    dist_dir = Path(settings.BASE_DIR).parent / 'frontend' / 'dist'
    if dist_dir.exists():
        urlpatterns += [
            re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': dist_dir / 'assets'}),
            re_path(r'^samples/(?P<path>.*)$', serve, {'document_root': dist_dir / 'samples'}),
        ]

