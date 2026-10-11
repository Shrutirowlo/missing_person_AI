from django.urls import path
from .views import (
    MissingPersonListCreateView,
    MissingPersonDetailView,
    CasePhotoUploadView,
    ReindexEmbeddingsView,
)

urlpatterns = [
    path('', MissingPersonListCreateView.as_view(), name='case-list-create'),
    path('<int:pk>/', MissingPersonDetailView.as_view(), name='case-detail'),
    path('<int:pk>/photos/', CasePhotoUploadView.as_view(), name='case-photo-upload'),
    path('reindex/', ReindexEmbeddingsView.as_view(), name='case-reindex'),
]
