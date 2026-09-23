from django.urls import path

from .homepage import (
    HomepageAdminView, HomepageRequestDetailView, HomepageRequestListView,
    PublicHomepageRequestView, PublicHomepageView,
)
from .views import (
    AnalyticsOverviewView, AssetCategoryCollectionView, AssetCollectionView,
    AssetHistoryView, AssetLocationCollectionView, AssetMaintenanceActionView,
    AssetMaintenanceCollectionView, AssetMovementView, BranchOperationsView,
    CommunicationOperationsView, CommunicationSendView, ContentPublishView,
    ContentCollectionView, ContentDetailView, ContentRevisionListView,
    ContentWorkflowView, MediaCollectionView,
    DataExportRequestView, DeletionRequestView, InventoryAlertView, ModuleCollectionView,
    RosterAcknowledgeView, WorkerLeaveRequestView,
)


urlpatterns = [
    # Public homepage document and visitor requests. These live under ``site/``
    # because ``public/<kind>/<slug>/`` in the organizations app would shadow them.
    path("site/homepage/", PublicHomepageView.as_view(), name="public-homepage"),
    path("site/homepage/requests/", PublicHomepageRequestView.as_view(), name="public-homepage-requests"),
    path("operations/homepage/", HomepageAdminView.as_view(), name="operations-homepage"),
    path("operations/homepage/requests/", HomepageRequestListView.as_view(), name="operations-homepage-requests"),
    path("operations/homepage/requests/<uuid:pk>/", HomepageRequestDetailView.as_view(), name="operations-homepage-request"),
    path("operations/communication/", CommunicationOperationsView.as_view(), name="operations-communication"),
    path("operations/communication/<uuid:pk>/send/", CommunicationSendView.as_view(), name="operations-communication-send"),
    path("operations/branches/", BranchOperationsView.as_view(), name="operations-branches"),
    path("operations/workers/<uuid:pk>/acknowledge/", RosterAcknowledgeView.as_view(), name="roster-acknowledge"),
    path("operations/assets/", AssetCollectionView.as_view(), name="operations-assets"),
    path("operations/assets/categories/", AssetCategoryCollectionView.as_view(), name="asset-categories"),
    path("operations/assets/locations/", AssetLocationCollectionView.as_view(), name="asset-locations"),
    path("operations/assets/alerts/", InventoryAlertView.as_view(), name="inventory-alerts"),
    path("operations/assets/<uuid:pk>/history/", AssetHistoryView.as_view(), name="asset-history"),
    path("operations/assets/<uuid:pk>/maintenance/", AssetMaintenanceCollectionView.as_view(), name="asset-maintenance"),
    path("operations/assets/<uuid:pk>/maintenance/<uuid:maintenance_pk>/<str:action>/", AssetMaintenanceActionView.as_view(), name="asset-maintenance-action"),
    path("operations/assets/<uuid:pk>/movement/", AssetMovementView.as_view(), name="asset-movement"),
    path("operations/cms/", ContentCollectionView.as_view(), name="content-collection"),
    path("operations/media/", MediaCollectionView.as_view(), name="media-collection"),
    path("operations/cms/<uuid:pk>/", ContentDetailView.as_view(), name="content-detail"),
    path("operations/cms/<uuid:pk>/revisions/", ContentRevisionListView.as_view(), name="content-revisions"),
    path("operations/cms/<uuid:pk>/<str:action>/", ContentWorkflowView.as_view(), name="content-workflow"),
    path("operations/cms/<uuid:pk>/publish/", ContentPublishView.as_view(), name="content-publish"),
    path("operations/worker-leave-requests/", WorkerLeaveRequestView.as_view(), name="worker-leave-request"),
    path("operations/<str:module>/", ModuleCollectionView.as_view(), name="operations-module"),
    path("analytics/overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("account/data-export-requests/", DataExportRequestView.as_view(), name="data-export-request"),
    path("account/deletion-requests/", DeletionRequestView.as_view(), name="deletion-request"),
]
