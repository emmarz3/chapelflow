from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.uploads.models import Upload, UploadCategory
from apps.uploads.storage import generate_storage_filename, get_storage_service
from apps.uploads.validators import validate_upload
from common.constants.roles import Roles
from common.utils.responses import success_response

from .models import (
    SocialComment,
    SocialCommentStatus,
    SocialMediaType,
    SocialPost,
    SocialPostMedia,
    SocialPostStatus,
    SocialReaction,
)
from .serializers import SocialCommentSerializer, SocialPostSerializer


def _branch(user):
    if not user.branch_id:
        raise ValidationError({"account": "Your account must be linked to a chapel branch before using The Upper Room."})
    return user.branch


def _role(user):
    return user.get_role_code() if hasattr(user, "get_role_code") else user.role


def _can_moderate(user):
    return _role(user) in {Roles.SUPER_ADMIN, Roles.CHAPEL_ADMIN, Roles.CHAPLAIN, Roles.STUDENT_CHAPLAIN}


def _posts_for(user):
    branch = _branch(user)
    return (
        SocialPost.objects.filter(branch=branch, status=SocialPostStatus.PUBLISHED)
        .select_related("author")
        .prefetch_related("media__upload")
        .annotate(
            like_count=Count("likes", distinct=True),
            comment_count=Count("comments", filter=Q(comments__status=SocialCommentStatus.PUBLISHED), distinct=True),
            is_liked=Exists(SocialReaction.objects.filter(post_id=OuterRef("pk"), user=user)),
        )
        .order_by("-created_at")
    )


def _post_or_404(user, pk):
    post = _posts_for(user).filter(pk=pk).first()
    if not post:
        raise ValidationError({"post": "This post is unavailable in your chapel feed."})
    return post


class SocialPostCollectionView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except ValueError as exc:
            raise ValidationError({"page": "Enter a valid page number."}) from exc
        page_size = min(30, max(1, int(request.query_params.get("page_size", "15"))))
        queryset = _posts_for(request.user)
        start = (page - 1) * page_size
        posts = list(queryset[start : start + page_size + 1])
        has_more = len(posts) > page_size
        return success_response({
            "items": SocialPostSerializer(posts[:page_size], many=True, context={"request": request}).data,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        })

    def post(self, request):
        branch = _branch(request.user)
        caption = str(request.data.get("caption", "")).strip()
        files = request.FILES.getlist("files")
        if not caption and not files:
            raise ValidationError({"post": "Add a caption, a photo, or a video before posting."})
        if len(caption) > 1_000:
            raise ValidationError({"caption": "Keep your caption within 1,000 characters."})
        if len(files) > 4:
            raise ValidationError({"files": "Add up to four photos or videos in one post."})

        media = []
        for file_obj in files:
            content_type = (file_obj.content_type or "").lower()
            if content_type.startswith("image/"):
                media_type = SocialMediaType.IMAGE
            elif content_type.startswith("video/"):
                media_type = SocialMediaType.VIDEO
            else:
                raise ValidationError({"files": "The Upper Room accepts image and video files only."})
            validate_upload(file_obj, max_size_mb=getattr(settings, "MAX_MEDIA_UPLOAD_SIZE_MB", 100))
            media.append((file_obj, media_type))

        storage = get_storage_service()
        with transaction.atomic():
            post = SocialPost.objects.create(branch=branch, author=request.user, caption=caption)
            for position, (file_obj, media_type) in enumerate(media):
                file_url = storage.upload_bytes(
                    file_obj.read(),
                    generate_storage_filename(file_obj.name, prefix="upper-room"),
                    content_type=file_obj.content_type,
                )
                upload = Upload.objects.create(
                    branch=branch,
                    uploaded_by=request.user,
                    category=UploadCategory.SOCIAL_POST,
                    original_filename=file_obj.name,
                    file_url=file_url,
                    content_type=file_obj.content_type or "",
                    size_bytes=file_obj.size,
                )
                SocialPostMedia.objects.create(post=post, upload=upload, media_type=media_type, position=position)
        post = _posts_for(request.user).get(pk=post.pk)
        return success_response(SocialPostSerializer(post, context={"request": request}).data, message="Posted to The Upper Room.", status=201)


class SocialPostDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        post = SocialPost.objects.filter(pk=pk, branch=_branch(request.user), status=SocialPostStatus.PUBLISHED).first()
        if not post:
            raise ValidationError({"post": "This post is unavailable in your chapel feed."})
        if post.author_id != request.user.id and not _can_moderate(request.user):
            raise PermissionDenied("You can remove only your own posts.")
        post.status = SocialPostStatus.REMOVED
        post.save(update_fields=["status", "updated_at"])
        return success_response(message="Post removed from The Upper Room.")


class SocialLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = _post_or_404(request.user, pk)
        with transaction.atomic():
            reaction = SocialReaction.objects.filter(post=post, user=request.user).first()
            if reaction:
                reaction.delete()
                liked = False
            else:
                try:
                    SocialReaction.objects.create(post=post, user=request.user)
                    liked = True
                except IntegrityError:
                    liked = True
        count = SocialReaction.objects.filter(post=post).count()
        return success_response({"liked": liked, "like_count": count})


class SocialCommentCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        post = _post_or_404(request.user, pk)
        comments = SocialComment.objects.filter(post=post, status=SocialCommentStatus.PUBLISHED).select_related("author")[:100]
        return success_response(SocialCommentSerializer(comments, many=True, context={"request": request}).data)

    def post(self, request, pk):
        post = _post_or_404(request.user, pk)
        body = str(request.data.get("body", "")).strip()
        if not body:
            raise ValidationError({"body": "Write a comment before posting it."})
        if len(body) > 750:
            raise ValidationError({"body": "Keep comments within 750 characters."})
        comment = SocialComment.objects.create(post=post, author=request.user, body=body)
        return success_response(SocialCommentSerializer(comment, context={"request": request}).data, message="Comment posted.", status=201)


class SocialCommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, comment_pk):
        post = _post_or_404(request.user, pk)
        comment = SocialComment.objects.filter(pk=comment_pk, post=post, status=SocialCommentStatus.PUBLISHED).first()
        if not comment:
            raise ValidationError({"comment": "This comment is unavailable."})
        if comment.author_id != request.user.id and not _can_moderate(request.user):
            raise PermissionDenied("You can remove only your own comments.")
        comment.status = SocialCommentStatus.REMOVED
        comment.save(update_fields=["status", "updated_at"])
        return success_response(message="Comment removed.")
