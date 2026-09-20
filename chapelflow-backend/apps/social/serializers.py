from rest_framework import serializers

from .models import SocialComment, SocialPost, SocialPostMedia


def display_name(user):
    if not user:
        return "ChapelFlow member"
    name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return name or "ChapelFlow member"


class SocialPostMediaSerializer(serializers.ModelSerializer):
    url = serializers.URLField(source="upload.file_url", read_only=True)

    class Meta:
        model = SocialPostMedia
        fields = ["id", "url", "media_type", "position"]


class SocialPostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    media = SocialPostMediaSerializer(many=True, read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)

    class Meta:
        model = SocialPost
        fields = [
            "id", "caption", "status", "created_at", "updated_at", "author_name",
            "media", "like_count", "comment_count", "is_liked",
        ]

    def get_author_name(self, post):
        return display_name(post.author)


class SocialCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    is_author = serializers.SerializerMethodField()

    class Meta:
        model = SocialComment
        fields = ["id", "body", "created_at", "author_name", "is_author"]

    def get_author_name(self, comment):
        return display_name(comment.author)

    def get_is_author(self, comment):
        request = self.context.get("request")
        return bool(request and comment.author_id == request.user.id)
