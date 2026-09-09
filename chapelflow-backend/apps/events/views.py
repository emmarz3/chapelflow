from rest_framework import viewsets
from common.viewsets import StandardModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from dateutil.relativedelta import relativedelta

from common.constants.roles import PermissionCodes
from common.permissions.rbac import HasRolePermission
from common.permissions.scoping import BranchScopedQuerysetMixin
from common.utils.responses import error_response, success_response
from .models import Event, EventRegistration, EventSchedule, EventType, Location
from .serializers import (
    EventRegistrationSerializer, EventScheduleSerializer, EventSerializer,
    EventTypeSerializer, LocationSerializer,
)
from .services import generate_event_schedules


class EventTypeViewSet(StandardModelViewSet):
    queryset = EventType.objects.all().order_by("name")
    serializer_class = EventTypeSerializer
    permission_classes = [HasRolePermission]
    permission_action_map = {
        "list": PermissionCodes.EVENTS_VIEW, "retrieve": PermissionCodes.EVENTS_VIEW,
        "create": PermissionCodes.EVENTS_CREATE, "update": PermissionCodes.EVENTS_UPDATE,
        "partial_update": PermissionCodes.EVENTS_UPDATE, "destroy": PermissionCodes.EVENTS_DELETE,
    }


class LocationViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch"]
    permission_action_map = {
        "list": PermissionCodes.EVENTS_VIEW, "retrieve": PermissionCodes.EVENTS_VIEW,
        "create": PermissionCodes.EVENTS_CREATE, "update": PermissionCodes.EVENTS_UPDATE,
        "partial_update": PermissionCodes.EVENTS_UPDATE, "destroy": PermissionCodes.EVENTS_DELETE,
    }

    def get_base_queryset(self):
        return Location.objects.select_related("branch")


class EventViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["branch", "event_type", "is_public", "requires_registration"]
    search_fields = ["title", "description"]
    ordering_fields = ["start_time", "created_at"]

    permission_action_map = {
        "list": PermissionCodes.EVENTS_VIEW,
        "retrieve": PermissionCodes.EVENTS_VIEW,
        "create": PermissionCodes.EVENTS_CREATE,
        "update": PermissionCodes.EVENTS_UPDATE,
        "partial_update": PermissionCodes.EVENTS_UPDATE,
        "destroy": PermissionCodes.EVENTS_DELETE,
        "generate_schedules": PermissionCodes.EVENTS_UPDATE,
        "calendar": PermissionCodes.EVENTS_VIEW,
        "public": None,  # AllowAny, see get_permissions() below — not RBAC-gated at all
    }

    def get_permissions(self):
        if self.action == "public":
            return [AllowAny()]
        return super().get_permissions()

    def get_base_queryset(self):
        return Event.objects.select_related("branch", "event_type", "location").prefetch_related("schedules")

    def perform_create(self, serializer):
        event = serializer.save()
        generate_event_schedules(event)

    @action(detail=True, methods=["post"], url_path="generate-schedules")
    def generate_schedules(self, request, pk=None):
        event = self.get_object()
        schedules = generate_event_schedules(event)
        return success_response(
            EventScheduleSerializer(schedules, many=True).data,
            message=f"{len(schedules)} occurrence(s) generated.",
        )

    @action(detail=False, methods=["get"])
    def public(self, request):
        """
        GET /api/v1/events/public/ — spec section 12: "Public events must
        not require authenticated membership merely to browse." No auth,
        no branch scoping (deliberately — a visitor doesn't have a branch
        yet), restricted to is_public=True, is_active branch events only.
        """
        qs = Event.objects.filter(is_public=True, branch__is_active=True).select_related(
            "branch", "event_type", "location"
        ).prefetch_related("schedules")
        branch_id = request.query_params.get("branch")
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        page = self.paginate_queryset(qs)
        serializer = EventSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return success_response(serializer.data)

    @action(detail=False, methods=["get"])
    def calendar(self, request):
        """
        GET /api/v1/events/calendar/?view=day|week|month&date=YYYY-MM-DD
        Spec Phase 7: day/week/month/date-range calendar views, correct
        timezone behavior. Returns EventSchedule occurrences (not raw
        Events) in the window, since those are the actual bookable/
        attendable units on the calendar. Scoped by the same
        branch/org/leader visibility as the rest of this ViewSet — this
        reuses self.get_queryset() (the Event side) rather than querying
        EventSchedule directly, so scope can never drift between the two.
        """
        import datetime as dt

        from django.utils import timezone as djtz

        view = request.query_params.get("view", "week")
        date_str = request.query_params.get("date")
        try:
            anchor = dt.date.fromisoformat(date_str) if date_str else djtz.localdate()
        except ValueError:
            return error_response("date must be in YYYY-MM-DD format.", status=400)

        if view == "day":
            range_start, range_end = anchor, anchor + dt.timedelta(days=1)
        elif view == "month":
            range_start = anchor.replace(day=1)
            range_end = (range_start + relativedelta(months=1))
        elif view == "week":
            range_start = anchor - dt.timedelta(days=anchor.weekday())
            range_end = range_start + dt.timedelta(days=7)
        elif view == "range":
            end_str = request.query_params.get("end_date")
            if not end_str:
                return error_response("end_date is required when view=range.", status=400)
            try:
                range_end = dt.date.fromisoformat(end_str) + dt.timedelta(days=1)
            except ValueError:
                return error_response("end_date must be in YYYY-MM-DD format.", status=400)
            range_start = anchor
        else:
            return error_response("view must be one of day, week, month, range.", status=400)

        current_tz = djtz.get_current_timezone()
        start_dt = djtz.make_aware(dt.datetime.combine(range_start, dt.time.min), current_tz)
        end_dt = djtz.make_aware(dt.datetime.combine(range_end, dt.time.min), current_tz)

        accessible_event_ids = self.filter_queryset(self.get_queryset()).values_list("id", flat=True)
        schedules = EventSchedule.objects.filter(
            event_id__in=accessible_event_ids,
            occurrence_start__gte=start_dt, occurrence_start__lt=end_dt,
            is_cancelled=False,
        ).select_related("event", "event__branch", "event__location").order_by("occurrence_start")

        return success_response(
            EventScheduleSerializer(schedules, many=True).data,
            message=f"{schedules.count()} occurrence(s) between {range_start.isoformat()} and "
                    f"{(range_end - dt.timedelta(days=1)).isoformat()}.",
        )


class EventRegistrationViewSet(BranchScopedQuerysetMixin, StandardModelViewSet):
    """
    NOTE (Phase 0 audit sweep): this previously had its own hand-rolled
    get_queryset() — the exact anti-pattern common/permissions/scoping.py's
    own docstring warns about. Concretely, it never handled
    Roles.ORG_WIDE_SCOPE_ROLES, so Chaplain incorrectly fell through to
    single-branch visibility here even though Chaplain scope was fixed
    everywhere else. Refactored onto BranchScopedQuerysetMixin so this
    gets the same tested branch/org-wide/global scoping as every other
    ViewSet, instead of a second copy that can silently drift.
    """
    serializer_class = EventRegistrationSerializer
    permission_classes = [HasRolePermission]
    filterset_fields = ["schedule", "member", "attended", "status"]
    branch_field_lookup = "schedule__event__branch"
    permission_action_map = {
        "list": PermissionCodes.EVENTS_VIEW, "retrieve": PermissionCodes.EVENTS_VIEW,
        "create": PermissionCodes.EVENTS_VIEW,  # members register themselves
        "update": PermissionCodes.EVENTS_UPDATE, "partial_update": PermissionCodes.EVENTS_UPDATE,
        "destroy": PermissionCodes.EVENTS_UPDATE,
        "cancel": PermissionCodes.EVENTS_VIEW,  # a member can cancel their own registration
    }

    def get_base_queryset(self):
        return EventRegistration.objects.select_related("schedule", "member", "schedule__event")

    def create(self, request, *args, **kwargs):
        """
        Spec Phase 7: capacity/waitlist/cancellation/duplicate-prevention/
        deadline all live in services.register_for_event now (see that
        docstring for why this couldn't safely stay in the serializer's
        `validate()`), so creation is routed through it directly instead
        of the default ModelViewSet.create()/perform_create() flow.
        """
        from .models import EventSchedule
        from .services import RegistrationError, register_for_event

        schedule_id = request.data.get("schedule")
        member_id = request.data.get("member")
        if not schedule_id or not member_id:
            return error_response("Both schedule and member are required.", status=400)

        schedule = self._scoped_schedule_or_404(schedule_id)
        if schedule is None:
            return error_response("Schedule not found.", status=404)

        from apps.members.models import Member
        member = Member.objects.filter(id=member_id).first()
        if member is None:
            return error_response("Member not found.", status=404)
        from common.permissions.scoping import user_can_access_branch
        if member.branch_id != schedule.event.branch_id and not user_can_access_branch(request.user, member.branch_id):
            # A staff member registering someone else on their behalf must
            # still be authorized for THAT member's branch too, not just
            # the event's branch (e.g. an org-wide Chaplain can, a
            # single-branch Chapel Admin registering a member from
            # another branch cannot).
            return error_response("You are not authorized to register this member.", status=403)

        try:
            registration, created = register_for_event(schedule, member)
        except RegistrationError as exc:
            return error_response(str(exc), status=400)

        return success_response(
            EventRegistrationSerializer(registration).data,
            message="Registered." if registration.status == "CONFIRMED" else "Added to waitlist.",
            status=201 if created else 200,
        )

    def _scoped_schedule_or_404(self, schedule_id):
        from .models import EventSchedule
        from common.permissions.scoping import user_can_access_branch
        # Reuse the same branch-scope check used everywhere else so
        # `schedule` can't be used as an unchecked direct-ID field to
        # register into an Event outside the caller's own branch/org
        # scope -- exactly the class of bug fixed on GroupMembership.group
        # in Phase 4/6.
        schedule = EventSchedule.objects.filter(id=schedule_id).select_related("event", "event__branch").first()
        if schedule is None:
            return None
        if not user_can_access_branch(self.request.user, schedule.event.branch_id):
            return None
        return schedule

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """POST /api/v1/event-registrations/{id}/cancel/ -- cancels and promotes the next waitlisted registration, if any."""
        from .services import cancel_registration

        registration = self.get_object()
        cancel_registration(registration)
        registration.refresh_from_db()
        return success_response(EventRegistrationSerializer(registration).data, message="Registration cancelled.")
