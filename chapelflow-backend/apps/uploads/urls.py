from django.urls import path

from .views import UploadListView, UploadView

urlpatterns = [
    path("", UploadListView.as_view({"get": "list"}), name="uploads-list"),
    path("<uuid:pk>/", UploadListView.as_view({"get": "retrieve"}), name="uploads-detail"),
    path("upload/", UploadView.as_view(), name="uploads-create"),
]
