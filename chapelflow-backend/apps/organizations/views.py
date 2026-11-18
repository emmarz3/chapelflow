from rest_framework import viewsets
from django.db.models import Q
from django.utils import timezone
from common.viewsets import StandardModelViewSet

from common.constants.roles import Roles
from common.permissions.rbac import IsSuperAdmin
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from .models import Branch, Organization
from .serializers import BranchSerializer, OrganizationSerializer


class PublicContentView(APIView):
    """Published CMS pages and collections; drafts never cross this boundary."""
    permission_classes = [AllowAny]

    collection_types = {
        "sermons": (("SERMON", "SERMON_SERIES", "MEDIA"), "Messages, series and resources", "/sermons"),
        "news": (("NEWS",), "Chapel news", "/news"),
        "gallery": (("GALLERY",), "Chapel gallery", "/gallery"),
    }

    def get(self, request, slug):
        from apps.operations.models import ContentEntry, ContentStatus, ContentType

        published = ContentEntry.objects.filter(status=ContentStatus.PUBLISHED)
        if slug in self.collection_types:
            content_types, title, prefix = self.collection_types[slug]
            entries = published.filter(content_type__in=content_types)
            if slug == "sermons":
                entries = entries.exclude(content_type=ContentType.MEDIA, parent__isnull=False)
            search = request.query_params.get("search", "").strip()
            if search:
                entries = entries.filter(
                    Q(title__icontains=search) | Q(summary__icontains=search) | Q(author_name__icontains=search)
                )
            entries = entries.order_by("-published_at", "-updated_at")
            return success_response({
                "slug": slug,
                "eyebrow": "Chrisland University Chapel",
                "title": title,
                "description": "Published resources from the chapel editorial team.",
                "sections": [{
                    "id": str(entry.id),
                    "heading": entry.title,
                    "body": entry.summary or entry.details,
                    "imageUrl": entry.cover_image_url or None,
                    "imageAlt": entry.title if entry.cover_image_url else "",
                    "action": {
                        "label": "Open collection" if entry.content_type == ContentType.GALLERY else (
                            "View series" if entry.content_type == ContentType.SERMON_SERIES else (
                            "Open resource" if entry.content_type == ContentType.MEDIA else "Play message"
                            )
                        ),
                        "href": f"{prefix}/{entry.slug}",
                    },
                } for entry in entries],
                "updatedAt": timezone.now().isoformat(),
            })

        if slug == "livestream":
            stream = published.filter(content_type=ContentType.LIVESTREAM).order_by("-published_at").first()
            if not stream:
                return error_response("No livestream has been published.", status=404)
            return success_response({
                "slug": slug,
                "eyebrow": "Live from the chapel",
                "title": stream.title,
                "description": stream.summary or stream.details,
                "sections": [{
                    "id": str(stream.id), "body": stream.details,
                    "imageUrl": stream.cover_image_url or None,
                    "imageAlt": stream.title if stream.cover_image_url else "",
                    "action": {"label": "Watch livestream", "href": stream.media_url},
                }],
                "updatedAt": stream.updated_at.isoformat(),
            })

        page = (
            published.filter(slug=slug, content_type=ContentType.PAGE)
            .order_by("-published_at", "-updated_at")
            .first()
        )
        if not page:
            return error_response("Published page content was not found.", status=404)
        children = published.filter(parent=page).order_by("sort_order", "published_at")
        sections = [{
            "id": str(child.id), "heading": child.title, "body": child.details,
            "imageUrl": child.cover_image_url or None,
            "imageAlt": child.title if child.cover_image_url else "",
            **({"action": {"label": "Open resource", "href": child.media_url}} if child.media_url else {}),
        } for child in children]
        if not sections:
            sections = [{"id": str(page.id), "body": page.details}]
        return success_response({
            "slug": page.slug,
            "eyebrow": "Chrisland University Chapel",
            "title": page.title,
            "description": page.summary,
            "sections": sections,
            "updatedAt": page.updated_at.isoformat(),
        })


class PublicDetailView(APIView):
    """Published CMS detail for sermons/news, without exposing drafts."""
    permission_classes = [AllowAny]

    def get(self, request, kind, slug):
        if kind == "events":
            from apps.events.models import Event

            event = Event.objects.filter(pk=slug, is_public=True).select_related("location").first()
            if not event:
                return error_response("Published event was not found.", status=404)
            return success_response({
                "slug": str(event.id),
                "eyebrow": "Upcoming event",
                "title": event.title,
                "description": event.description,
                "sections": [{
                    "id": str(event.id),
                    "heading": event.location.name if event.location else "Chrisland University Chapel",
                    "body": event.description,
                }],
                "updatedAt": event.updated_at.isoformat(),
            })

        from apps.operations.models import ContentEntry, ContentStatus, ContentType

        expected_types = {
            "sermons": (ContentType.SERMON, ContentType.SERMON_SERIES, ContentType.MEDIA),
            "news": (ContentType.NEWS,),
            "gallery": (ContentType.GALLERY,),
        }.get(kind)
        if expected_types is None:
            return error_response("Published content type was not found.", status=404)

        entry = (
            ContentEntry.objects.filter(
                slug=slug, status=ContentStatus.PUBLISHED, content_type__in=expected_types,
            )
            .order_by("-published_at", "-updated_at")
            .first()
        )
        if entry is None:
            return error_response("Published content was not found.", status=404)
        sections = [{
            "id": str(entry.id), "body": entry.details,
            "imageUrl": entry.cover_image_url or None,
            "imageAlt": entry.title if entry.cover_image_url else "",
            **({"action": {
                "label": "Download resource" if entry.metadata.get("downloadable") else "Open media",
                "href": entry.media_url,
            }} if entry.media_url else {}),
        }]
        if entry.content_type == ContentType.GALLERY:
            images = ContentEntry.objects.filter(
                parent=entry,
                status=ContentStatus.PUBLISHED,
                content_type__in=(ContentType.GALLERY_IMAGE, ContentType.GALLERY_VIDEO, ContentType.MEDIA),
            ).order_by("sort_order", "published_at", "updated_at")
            sections = [{
                "id": str(image.id),
                "heading": image.title,
                "body": image.summary or image.details,
                "imageUrl": (
                    image.cover_image_url or None
                    if image.content_type == ContentType.MEDIA
                    else image.media_url or image.cover_image_url or None
                ),
                "imageAlt": image.title,
                "mediaType": "video" if image.content_type == ContentType.GALLERY_VIDEO else (
                    "file" if image.content_type == ContentType.MEDIA else "image"
                ),
                **({"action": {"label": "Open or download file", "href": image.media_url}}
                   if image.content_type == ContentType.MEDIA else {}),
            } for image in images]
        elif entry.content_type == ContentType.SERMON_SERIES:
            sermons = ContentEntry.objects.filter(
                parent=entry, status=ContentStatus.PUBLISHED, content_type=ContentType.SERMON,
            ).order_by("sort_order", "published_at", "updated_at")
            sections = [{
                "id": str(sermon.id), "heading": sermon.title,
                "body": sermon.summary or sermon.details,
                "imageUrl": sermon.cover_image_url or None,
                "imageAlt": sermon.title if sermon.cover_image_url else "",
                "action": {"label": "Play message", "href": f"/sermons/{sermon.slug}"},
            } for sermon in sermons] or sections
        return success_response({
            "slug": entry.slug,
            "eyebrow": kind.replace("-", " ").title(),
            "title": entry.title,
            "description": entry.summary,
            "sections": sections,
            "updatedAt": entry.updated_at.isoformat(),
        })


class OrganizationViewSet(StandardModelViewSet):
    """Only super admins manage organizations (top of the hierarchy)."""
    queryset = Organization.objects.all().order_by("name")
    serializer_class = OrganizationSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsSuperAdmin()]


class BranchViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    Phase 1 fix: previously this hand-rolled branch scoping and, in doing
    so, missed the ORG_WIDE_SCOPE_ROLES (Chaplain) case entirely — a
    Chaplain fell through to the branch-only check and could list only
    their own single branch, not every branch in their Organization as
    intended everywhere else. Moved onto the shared mixin (extended with
    an "id" self-lookup, since this model IS the branch, not something
    pointing at one) so this gets the same three-tier scoping as every
    other branch-scoped endpoint and can't drift from it again.
    """
    serializer_class = BranchSerializer
    filterset_fields = ["organization", "branch_type", "parent", "is_active"]
    search_fields = ["name", "city"]
    branch_field_lookup = "id"

    def get_base_queryset(self):
        return Branch.objects.select_related("organization", "parent").order_by("name")

    def get_permissions(self):
        if self.action == "list":
            # Registration needs a branch identifier before a user has an
            # account. The list exposes only ordinary location metadata;
            # create/update/delete remain super-admin-only.
            return [AllowAny()]
        if self.action == "retrieve":
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
