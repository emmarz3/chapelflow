from django.urls import path

from .views import PublicMediaView, UploadListView, UploadView

urlpatterns = [
    path("public/<uuid:pk>/", PublicMediaView.as_view(), name="uploads-public-media"),
    path("", UploadListView.as_view({"get": "list"}), name="uploads-list"),
    path("<uuid:pk>/", UploadListView.as_view({"get": "retrieve"}), name="uploads-detail"),
    path("upload/", UploadView.as_view(), name="uploads-create"),
]
