from django.urls import path

from .views import (
    SocialCommentCollectionView,
    SocialCommentDetailView,
    SocialLikeView,
    SocialPostCollectionView,
    SocialPostDetailView,
)


urlpatterns = [
    path("posts/", SocialPostCollectionView.as_view(), name="social-posts"),
    path("posts/<uuid:pk>/", SocialPostDetailView.as_view(), name="social-post-detail"),
    path("posts/<uuid:pk>/like/", SocialLikeView.as_view(), name="social-like"),
    path("posts/<uuid:pk>/comments/", SocialCommentCollectionView.as_view(), name="social-comments"),
    path("posts/<uuid:pk>/comments/<uuid:comment_pk>/", SocialCommentDetailView.as_view(), name="social-comment-detail"),
]
