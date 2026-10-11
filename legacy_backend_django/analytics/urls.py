from django.urls import path
from .views import DashboardAnalyticsView

urlpatterns = [
    path('summary/', DashboardAnalyticsView.as_view(), name='analytics-summary'),
]
