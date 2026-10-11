from django.urls import path
from .views import ComparativeMatchSearchView, SearchHistoryListView, SearchDetailView, TestUIPageView

urlpatterns = [
    path('search/', ComparativeMatchSearchView.as_view(), name='match-search'),
    path('history/', SearchHistoryListView.as_view(), name='match-history'),
    path('history/<int:pk>/', SearchDetailView.as_view(), name='match-detail'),
    path('test-ui/', TestUIPageView.as_view(), name='match-test-ui'),
]

