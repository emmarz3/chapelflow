from django.urls import path

from .views import ModerationDetailView, ModerationQueueView, ReportCollectionView

urlpatterns = [
    path("reports/", ReportCollectionView.as_view(), name="moderation-reports"),
    path("queue/", ModerationQueueView.as_view(), name="moderation-queue"),
    path("queue/<uuid:pk>/", ModerationDetailView.as_view(), name="moderation-detail"),
]
