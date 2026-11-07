# PHASE 10 - PRIORITIZED ACTION PLAN

**Generated:** September 1, 2026  
**Current Completion:** 36% (per comprehensive audit)  
**Target:** Production-ready (genuine 100%)

---

## AUDIT SUMMARY

**Audit Document:** `PHASE10_COMPREHENSIVE_AUDIT.md`

**Key Findings:**
- ✅ Core CRUD working
- ✅ Authorization/preferences working
- ✅ Email notifications working
- ❌ Scheduling not implemented
- ❌ SMS/Push stubbed
- ❌ Phase 7 integration missing
- ❌ Webhook security missing
- ❌ Tests unexecuted

---

## EXECUTION PLAN (Following 20-Step Directive)

### Step 1: ✅ Audit Complete
- Created `PHASE10_COMPREHENSIVE_AUDIT.md`
- Identified what's working vs broken
- Calculated honest 36% completion

### Step 2: ✅ Preserve Working Components
**DO NOT REBUILD:**
- ✅ Models (reconciled with migration 0003)
- ✅ Serializers (security protections in place)
- ✅ services.py (authorization/resolution working)
- ✅ Basic views CRUD (working)
- ✅ CommunicationPreference model + viewset
- ✅ Phase 9 integration (volunteer reminders)
- ✅ Email provider

### Step 3: Fix Announcement Lifecycle Semantics
**Issues:** SCHEDULED status unused, publish_at ignored

**Action:**
1. Fix `views.py publish` action to check `publish_at`
2. Add `dispatch_scheduled_announcements` periodic task
3. Add CELERY_BEAT_SCHEDULE configuration

### Step 4: Implement Real Scheduling
**Dependencies:** Step 3

**Action:**
1. Create periodic task (runs every minute)
2. Query SCHEDULED announcements where `publish_at <= now`
3. Transition to QUEUED + queue dispatch
4. Add `skip_locked=True` for concurrency

### Step 5: Fix Cancellation Semantics
**Issues:** Can't cancel SENDING announcements properly

**Action:**
1. Update `cancel` action to handle SENDING status
2. Add mid-dispatch cancellation check in dispatch task
3. Add warning message for partial sends

### Step 6: Harden Audience Targeting
**Status:** Mostly working, check FELLOWSHIP/UNIT

**Action:**
1. Verify Member model has fellowship/unit fields
2. If yes, implement explicit handling in `resolve_audience_members`
3. If no, document that CUSTOM + target_groups is correct approach

### Step 7: ✅ CommunicationPreference (Already Complete)
**Status:** Working, no changes needed

### Step 8: Strengthen Notification/Delivery Architecture
**Issues:** SMS/Push stubbed

**Action:**
1. Implement SMSProvider with Twilio
2. Implement DeviceToken model + registration
3. Implement PushProvider with FCM
4. Fix hard-coded empty device_token

### Step 9: Fix Idempotency
**Issues:** Task error handling wrong

**Action:**
1. Remove `raise` in dispatch_announcement exception handler
2. Return `{"status": "failed"}` instead
3. Let Celery see task as completed (failure recorded in DB)

### Step 10: Fix Celery Completion Semantics
**Dependencies:** Step 9 (same fix)

**Action:** Same as Step 9

### Step 11: Harden Webhook Verification
**Issues:** No signature verification

**Action:**
1. Add webhook signature verification utilities
2. Create provider-specific webhook views (Twilio, FCM)
3. Add replay protection (timestamp + nonce)
4. Register webhook URLs

### Step 12: ✅ SMS Provider (Covered in Step 8)

### Step 13: ✅ Push/Device-Token (Covered in Step 8)

### Step 14: Integrate Phase 7 Reminders
**Issues:** Event reminders don't check preferences

**Action:**
1. Modify `apps/events/tasks.py send_due_event_reminders`
2. Add preference check before creating notification
3. Test with Phase 7 integration tests

### Step 15: ✅ Phase 9 Integration (Already Complete)
**Status:** Working, no changes needed

### Step 16: ✅ RBAC/Branch Scope (Already Working)
**Status:** Verified working, no changes needed

### Step 17: Add Missing Security Tests
**Status:** Tests exist but need execution

**Action:**
1. Setup Python/Django environment
2. Run existing test suite
3. Fix any failures
4. Add integration tests for new features (scheduling, webhooks)

### Step 18: Run Migrations/Checks
**Action:**
```bash
python manage.py makemigrations --check  # Should be clean
python manage.py migrate  # Apply any new migrations (device tokens)
python manage.py check  # Verify no system issues
```

### Step 19: Run Complete Test Suite
**Action:**
```bash
pytest apps/communications/tests/ -v --cov=apps/communications
pytest apps/events/tests/ -v  # Phase 7 integration
pytest apps/volunteers/tests/ -v  # Phase 9 integration
pytest apps/notifications/tests/ -v  # Notification layer
```

### Step 20: Calculate Real Percentage
**Action:** Re-audit after all fixes, calculate completion based on:
- All features implemented
- All features working
- All tests passing
- Integration complete

---

## DETAILED IMPLEMENTATION STEPS

### PRIORITY 0 - CRITICAL FIXES

#### P0.1: Implement Scheduling (Steps 3-4)

**File:** `apps/communications/views.py`
```python
@action(detail=True, methods=["post"], url_path="publish")
def publish(self, request, pk=None):
    announcement = self.get_object()
    serializer = AnnouncementPublishSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    if announcement.status != AnnouncementStatus.DRAFT:
        return Response({"detail": "Can only publish DRAFT announcements"}, status=400)
    
    # Re-authorize
    services.authorize_audience(...)
    
    # NEW: Check if scheduled for future
    from django.utils import timezone
    now = timezone.now()
    
    if announcement.publish_at > now:
        # Schedule for future
        announcement.status = AnnouncementStatus.SCHEDULED
        announcement.save(update_fields=["status"])
        return Response({
            "data": self.get_serializer(announcement).data,
            "message": f"Announcement scheduled for {announcement.publish_at}"
        })
    else:
        # Dispatch immediately
        announcement.status = AnnouncementStatus.QUEUED
        announcement.save(update_fields=["status"])
        dispatch_announcement.delay(str(announcement.id))
        return Response({"data": self.get_serializer(announcement).data})
```

**File:** `apps/communications/tasks.py`
```python
@shared_task
def dispatch_scheduled_announcements():
    """
    Periodic task (CELERY_BEAT): Check for SCHEDULED announcements
    where publish_at has arrived, transition to QUEUED and dispatch.
    """
    from django.db import transaction
    from django.utils import timezone
    from .models import Announcement, AnnouncementStatus
    
    now = timezone.now()
    
    # Use select_for_update with skip_locked for concurrency safety
    due_announcements = Announcement.objects.select_for_update(
        skip_locked=True
    ).filter(
        status=AnnouncementStatus.SCHEDULED,
        publish_at__lte=now
    )
    
    count = 0
    with transaction.atomic():
        for announcement in due_announcements:
            announcement.status = AnnouncementStatus.QUEUED
            announcement.save(update_fields=["status"])
            dispatch_announcement.delay(str(announcement.id))
            count += 1
    
    return {"dispatched": count, "timestamp": now.isoformat()}
```

**File:** `config/celery.py` or `settings.py`
```python
CELERY_BEAT_SCHEDULE = {
    'dispatch-scheduled-announcements': {
        'task': 'apps.communications.tasks.dispatch_scheduled_announcements',
        'schedule': 60.0,  # Every 60 seconds
    },
    # ... existing beat tasks
}
```

---

#### P0.2: Implement SMS Provider (Step 8a)

**Dependencies:**
```bash
pip install twilio
```

**File:** `apps/notifications/providers.py`
```python
class SMSProvider:
    def send(self, *, to: str, body: str):
        # Validate phone number format
        if not to or len(to) < 10:
            return {"status": "failed", "error": "Invalid phone number"}
        
        # Check if configured
        if not hasattr(settings, 'TWILIO_ACCOUNT_SID'):
            logger.warning("SMS provider not configured, stubbing send")
            return {"status": "stubbed", "provider": "unconfigured"}
        
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            message = client.messages.create(
                to=to,
                from_=settings.TWILIO_PHONE_NUMBER,
                body=body
            )
            
            return {
                "status": "sent",
                "message_sid": message.sid,
                "provider": "twilio",
                "to": to
            }
        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return {"status": "failed", "error": str(e)}
```

**File:** `settings.py` or `.env`
```python
# Twilio Configuration
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = env('TWILIO_PHONE_NUMBER', default='')
```

---

#### P0.3: Implement Device Token Management (Step 8b)

**File:** `apps/notifications/models.py`
```python
class DeviceToken(models.Model):
    """
    Push notification device token registration.
    
    Users can have multiple devices (phone, tablet, etc.).
    Tokens must be refreshed when they expire.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens"
    )
    device_id = models.CharField(
        max_length=255,
        help_text="Unique device identifier (UUID from app)"
    )
    token = models.CharField(
        max_length=512,
        help_text="FCM registration token or APNs device token"
    )
    platform = models.CharField(
        max_length=10,
        choices=[('IOS', 'iOS'), ('ANDROID', 'Android'), ('WEB', 'Web')]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "notifications_device_token"
        unique_together = [['user', 'device_id']]
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.platform} device for {self.user}"
```

**Create Migration:**
```bash
python manage.py makemigrations notifications
```

**File:** `apps/notifications/serializers.py`
```python
class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'device_id', 'token', 'platform', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
```

**File:** `apps/notifications/views.py`
```python
class DeviceTokenViewSet(StandardModelViewSet):
    """
    Device token registration for push notifications.
    
    POST /device-tokens/ - Register device
    GET /device-tokens/ - List user's devices
    DELETE /device-tokens/{id}/ - Unregister device
    """
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return DeviceToken.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Update or create (upsert on device_id)
        device_id = serializer.validated_data['device_id']
        token, created = DeviceToken.objects.update_or_create(
            user=self.request.user,
            device_id=device_id,
            defaults={
                'token': serializer.validated_data['token'],
                'platform': serializer.validated_data['platform'],
                'is_active': True,
            }
        )
        return token
```

---

#### P0.4: Implement Push Provider (Step 8c)

**Dependencies:**
```bash
pip install firebase-admin
```

**File:** `apps/notifications/providers.py`
```python
class PushProvider:
    def __init__(self):
        # Initialize Firebase Admin SDK
        if not hasattr(settings, 'FCM_CREDENTIALS_PATH'):
            self._initialized = False
            return
        
        try:
            import firebase_admin
            from firebase_admin import credentials
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(settings.FCM_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
            self._initialized = True
        except Exception as e:
            logger.error(f"FCM initialization failed: {e}")
            self._initialized = False
    
    def send(self, *, device_token: str, title: str, body: str):
        if not device_token:
            return {"status": "failed", "error": "No device token provided"}
        
        if not self._initialized:
            logger.info("push_stub_send (FCM not configured)")
            return {"status": "stubbed", "provider": "FCM not configured"}
        
        try:
            from firebase_admin import messaging
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=device_token,
            )
            
            response = messaging.send(message)
            
            return {
                "status": "sent",
                "message_id": response,
                "provider": "FCM",
                "device_token": device_token[:10] + "..."  # Partial for logging
            }
        except messaging.UnregisteredError:
            # Token expired/invalid
            return {"status": "failed", "error": "Device token expired"}
        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return {"status": "failed", "error": str(e)}
```

**File:** `apps/notifications/tasks.py`
```python
# Modify deliver_notification to query device tokens:
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def deliver_notification(self, notification_id):
    notification = Notification.objects.select_related("recipient").get(id=notification_id)

    try:
        if notification.channel == NotificationChannel.EMAIL and notification.recipient and notification.recipient.email:
            response = email_provider.send(...)
        
        elif notification.channel == NotificationChannel.SMS and notification.recipient and notification.recipient.phone_number:
            response = sms_provider.send(...)
        
        elif notification.channel == NotificationChannel.PUSH:
            # NEW: Query user's active device tokens
            from .models import DeviceToken
            device_tokens = DeviceToken.objects.filter(
                user=notification.recipient,
                is_active=True
            )
            
            if not device_tokens.exists():
                notification.status = NotificationStatus.FAILED
                notification.provider_response = {"error": "No registered devices"}
                notification.save()
                return
            
            # Send to all devices (first success wins)
            responses = []
            for device in device_tokens:
                response = push_provider.send(
                    device_token=device.token,
                    title=notification.title,
                    body=notification.body
                )
                responses.append(response)
                
                # If successful, use this response
                if response.get("status") == "sent":
                    break
                
                # If token expired, deactivate it
                if "expired" in response.get("error", "").lower():
                    device.is_active = False
                    device.save()
            
            # Use last response (or first successful)
            response = next((r for r in responses if r.get("status") == "sent"), responses[-1] if responses else {"status": "failed"})
        
        else:
            notification.status = NotificationStatus.FAILED
            notification.provider_response = {"error": "No valid recipient"}
            notification.save()
            return

        # ... rest of existing logic
```

---

### PRIORITY 1 - HIGH PRIORITY

#### P1.1: Fix Cancellation Semantics (Step 5)

**File:** `apps/communications/views.py`
```python
@action(detail=True, methods=["post"], url_path="cancel")
def cancel(self, request, pk=None):
    announcement = self.get_object()
    serializer = AnnouncementCancelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    reason = serializer.validated_data.get("reason", "")
    
    # Cannot cancel completed
    if announcement.status == AnnouncementStatus.COMPLETED:
        return Response(
            {"detail": "Cannot cancel COMPLETED announcement"},
            status=400
        )
    
    # Handle SENDING status specially
    if announcement.status == AnnouncementStatus.SENDING:
        announcement.status = AnnouncementStatus.FAILED
        announcement.failure_reason = f"Cancelled during send: {reason}" if reason else "Cancelled during send"
        announcement.save()
        
        return Response({
            "data": self.get_serializer(announcement).data,
            "warning": "Cancellation requested, but some notifications may have already been sent."
        })
    
    # Handle other statuses (DRAFT/SCHEDULED/QUEUED)
    announcement.status = AnnouncementStatus.FAILED
    announcement.failure_reason = f"Cancelled: {reason}" if reason else "Cancelled by user"
    announcement.save()
    
    return Response({"data": self.get_serializer(announcement).data})
```

**File:** `apps/communications/tasks.py`
```python
@shared_task
def dispatch_announcement(announcement_id):
    # ... existing atomic block ...
    
    try:
        members = services.resolve_audience_members(announcement)
        channels = announcement.channels if announcement.channels else ["EMAIL"]
        
        for channel in channels:
            # NEW: Check if cancelled mid-dispatch
            announcement.refresh_from_db()
            if announcement.status == AnnouncementStatus.FAILED:
                # Cancelled externally
                return {
                    "status": "cancelled",
                    "reason": announcement.failure_reason,
                    "partial_send": True
                }
            
            filtered_members = services.filter_by_preference(members, channel)
            # ... rest of dispatch
```

---

#### P1.2: Fix Celery Error Handling (Steps 9-10)

**File:** `apps/communications/tasks.py`
```python
@shared_task
def dispatch_announcement(announcement_id):
    # ... existing code ...
    
    try:
        # ... dispatch logic ...
        
        announcement.status = AnnouncementStatus.COMPLETED
        announcement.completed_at = timezone.now()
        announcement.save()
        
        return {
            "status": "completed",
            "channels": channels,
            "total_members": members.count(),
        }
    
    except Exception as e:
        # Mark as failed
        announcement.status = AnnouncementStatus.FAILED
        announcement.failure_reason = str(e)
        announcement.save()
        
        # DON'T re-raise - task completed (with failure recorded)
        return {
            "status": "failed",
            "reason": str(e),
            "announcement_id": str(announcement_id)
        }
        # ❌ REMOVED: raise
```

---

#### P1.3: Integrate Phase 7 (Step 14)

**File:** `apps/events/tasks.py`
```python
@shared_task
def send_due_event_reminders():
    # ... existing code up to notification creation ...
    
    for registration in registrations:
        if not registration.member.user_id:
            continue
        
        # NEW: Check communication preferences
        member = registration.member
        if hasattr(member, 'communication_preference'):
            prefs = member.communication_preference
            
            # Check if opted out of this channel
            if reminder.channel == 'EMAIL' and not prefs.email_enabled:
                continue
            elif reminder.channel == 'SMS' and not prefs.sms_enabled:
                continue
            elif reminder.channel == 'PUSH' and not prefs.push_enabled:
                continue
            
            # Check if opted out of announcements/reminders
            if not prefs.announcements_enabled:
                continue
        
        # Create notification (only if preferences allow)
        notification = Notification.objects.create(...)
        deliver_notification.delay(str(notification.id))
        notifications_created += 1
```

---

### PRIORITY 2 - MEDIUM PRIORITY

#### P2.1: Add Webhook Verification (Step 11)

**File:** `apps/notifications/webhooks.py` (new file)
```python
import hmac
import hashlib
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


def verify_twilio_signature(url, params, signature):
    """
    Verify Twilio webhook signature.
    https://www.twilio.com/docs/usage/security#validating-requests
    """
    if not hasattr(settings, 'TWILIO_AUTH_TOKEN'):
        return False
    
    # Twilio signature validation logic
    data = url
    for key in sorted(params.keys()):
        data += key + params[key]
    
    expected_signature = hmac.new(
        settings.TWILIO_AUTH_TOKEN.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha1
    ).digest().hex()
    
    return hmac.compare_digest(expected_signature, signature)


class TwilioWebhookView(APIView):
    """
    Twilio SMS delivery status webhook.
    POST /api/v1/notifications/webhooks/twilio/
    """
    authentication_classes = []  # Webhook, not user auth
    permission_classes = []
    
    def post(self, request):
        # Verify signature
        signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
        url = request.build_absolute_uri()
        
        if not verify_twilio_signature(url, request.POST, signature):
            return Response({"error": "Invalid signature"}, status=403)
        
        # Process delivery status
        message_sid = request.data.get('MessageSid')
        message_status = request.data.get('MessageStatus')
        
        # Find notification by provider_response.message_sid
        from .models import Notification
        try:
            notification = Notification.objects.get(
                provider_response__message_sid=message_sid
            )
            
            if message_status == 'delivered':
                from .tasks import mark_notification_delivered
                mark_notification_delivered.delay(
                    str(notification.id),
                    {"twilio_status": message_status}
                )
        except Notification.DoesNotExist:
            pass  # Ignore unknown message_sid
        
        return Response(status=200)


class FCMWebhookView(APIView):
    """
    FCM delivery receipt webhook (if configured).
    """
    # Similar implementation for FCM
    pass
```

**File:** `apps/notifications/urls.py`
```python
from django.urls import path
from .webhooks import TwilioWebhookView, FCMWebhookView

urlpatterns = [
    # ... existing routes ...
    path('webhooks/twilio/', TwilioWebhookView.as_view(), name='twilio-webhook'),
    path('webhooks/fcm/', FCMWebhookView.as_view(), name='fcm-webhook'),
]
```

---

## TESTING REQUIREMENTS

### Test Environment Setup
```bash
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-django pytest-cov

# Setup test database
python manage.py migrate --settings=config.settings_test
```

### Run Test Suite
```bash
# Phase 10 tests
pytest apps/communications/tests/ -v --cov=apps/communications

# Integration tests
pytest apps/events/tests/ -v  # Phase 7
pytest apps/volunteers/tests/ -v  # Phase 9
pytest apps/notifications/tests/ -v  # Notification layer

# Full suite
pytest --cov=apps --cov-report=html
```

### Test Coverage Goals
- Unit tests: 80%+
- Integration tests: Critical paths
- Security tests: All 8 vulnerabilities

---

## COMPLETION CRITERIA

### Feature Completeness
- [ ] Scheduling implemented and working
- [ ] SMS provider integrated (Twilio)
- [ ] Push notifications working (FCM + device tokens)
- [ ] Phase 7 integration complete
- [ ] Webhook security implemented
- [ ] Cancellation semantics correct
- [ ] Celery error handling fixed

### Quality Gates
- [ ] All migrations applied
- [ ] `python manage.py check` passes
- [ ] All tests pass
- [ ] Test coverage >80%
- [ ] No security vulnerabilities
- [ ] Documentation updated

### Integration Verified
- [ ] Phase 7 reminders respect preferences
- [ ] Phase 9 reminders respect preferences
- [ ] Notifications track source_announcement
- [ ] Delivery status rollup works

---

## ESTIMATED COMPLETION

**Current:** 36%  
**After P0 fixes:** ~70%  
**After P1 fixes:** ~85%  
**After P2 fixes + testing:** ~95%  
**After integration tests pass:** **100%**

---

## NEXT IMMEDIATE ACTIONS

1. **Setup Python environment** (blocked on this for execution)
2. **Implement P0.1** (Scheduling) - 2-3 hours
3. **Implement P0.2-P0.4** (SMS/Push) - 4-6 hours
4. **Run tests** - Verify nothing broke
5. **Continue through P1-P2** - 4-6 hours
6. **Final testing** - 2-4 hours

**Total Estimated Time:** 12-20 hours of development work

**Blocker:** Python environment must be setup before any code changes can be tested.

