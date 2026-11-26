from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.PlansView.as_view()),
    path('mine/', views.MyCampaignsView.as_view()),
    path('mine/<uuid:pk>/', views.MyCampaignDetailView.as_view()),
    path('admin/', views.AdminCampaignsView.as_view()),
    path('admin/programs/', views.AdminProgramsView.as_view()),
    path('admin/programs/<uuid:pk>/', views.AdminProgramDetailView.as_view()),
    path('admin/settings/', views.AdminSettingsView.as_view()),
    path('admin/<uuid:pk>/review/', views.ReviewView.as_view()),
    path('image/', views.ImageView.as_view()),
    path('<uuid:pk>/checkout/', views.CheckoutView.as_view()),
    path('<uuid:pk>/verify/', views.VerifyView.as_view()),
    path('<uuid:pk>/cancel/', views.CancelView.as_view()),
    path('paystack/webhook/', views.WebhookView.as_view()),
    path('placement/<str:placement>/', views.PlacementView.as_view()),
    path('<uuid:pk>/click/', views.ClickView.as_view()),
]
