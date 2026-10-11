from django.urls import path
from .views import StationListCreateView, StationDetailView

urlpatterns = [
    path('', StationListCreateView.as_view(), name='station-list-create'),
    path('<int:pk>/', StationDetailView.as_view(), name='station-detail'),
]
