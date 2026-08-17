from django.urls import path

from .views import (
    MissingPersonListCreateView,
    MissingPersonDetailView,
    PersonImageUploadView,
)


urlpatterns = [
    path(
        "",
        MissingPersonListCreateView.as_view(),
        name="person-list-create",
    ),

    path(
        "<int:pk>/",
        MissingPersonDetailView.as_view(),
        name="person-detail",
    ),
    path(
        "<int:pk>/images/",
        PersonImageUploadView.as_view(),
        name="person-image-upload",
    ),
]