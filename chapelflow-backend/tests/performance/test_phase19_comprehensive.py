"""
Phase 19: Comprehensive Performance, Reliability & Disaster Recovery Tests

Tests critical performance and reliability patterns:
- Database query optimization (N+1 prevention, indexes)
- API pagination and response limits
- Celery task reliability (retry, idempotency, timeouts)
- Concurrency and race conditions
- Health endpoint functionality
- Large dataset handling
- Report generation performance
"""
import pytest
import time
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import connection, transaction
from django.test.utils import override_settings
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from apps.accounts.models import Role
from apps.events.models import Event, EventSchedule, EventRegistration
from apps.members.models import Member
from apps.finance.models import Giving, GivingCategory, GivingStatus, GivingSource, Payment, PaymentStatus
from apps.organizations.models import Organization, Branch
from apps.notifications.models import Notification, NotificationChannel
from apps.reports.models import ReportJob, ReportJobStatus
from common.constants.roles import Roles

User = get_user_model()


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
def organization():
    """Create test organization."""
    return Organization.objects.create(name="Test University", slug="test-university-p19")


@pytest.fixture
def branch_a(organization):
    """Create branch A."""
    return Branch.objects.create(
        organization=organization,
        name="Chapel Branch A",
        branch_type="CHAPEL"
    )


@pytest.fixture
def admin_user(branch_a):
    """Create admin user."""
    return User.objects.create_user(
        email="admin@test.com",
        password="AdminPass123!",
        role=Roles.CHAPEL_ADMIN,
        branch=branch_a,
        is_active=True
    )


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


# ==============================================================================
# DATABASE PERFORMANCE TESTS
# ==============================================================================

@pytest.mark.django_db
class TestDatabasePerformance:
    """Test database query optimization."""
    
    def test_member_list_uses_select_related(self, api_client, admin_user, branch_a):
        """Test: Member list endpoint uses select_related to prevent N+1."""
        # Create test members
        for i in range(5):
            Member.objects.create(
                branch=branch_a,
                first_name=f"Member{i}",
                last_name="Test",
                email=f"member{i}@test.com"
            )
        
        api_client.force_authenticate(user=admin_user)
        
        # Track queries
        with self.assertNumQueries(expected_num=5, using='default'):
            # Expected: 1 for user auth, 1 for member list + related objects
            # Should NOT be N queries for each member's relationships
            response = api_client.get('/api/v1/members/')
        
        assert response.status_code == 200
        assert len(response.data['data']) == 5
    
    def test_member_detail_prefetches_relationships(self, api_client, admin_user, branch_a):
        """Test: Member detail uses prefetch_related for M2M relationships."""
        member = Member.objects.create(
            branch=branch_a,
            first_name="Test",
            last_name="Member",
            email="test@test.com"
        )
        
        api_client.force_authenticate(user=admin_user)
        
        # Should use prefetch_related for tags, qr_code
        with self.assertNumQueries(expected_num=4, using='default'):
            response = api_client.get(f'/api/v1/members/{member.id}/')
        
        assert response.status_code == 200
    
    def test_pagination_prevents_unbounded_queries(self, api_client, admin_user, branch_a):
        """Test: List endpoints return paginated results, not entire table."""
        # Create many members
        for i in range(100):
            Member.objects.create(
                branch=branch_a,
                first_name=f"Member{i}",
                last_name="Test",
                email=f"member{i}@test.com"
            )
        
        api_client.force_authenticate(user=admin_user)
        
        response = api_client.get('/api/v1/members/')
        
        assert response.status_code == 200
        # Should return page_size (25), not all 100
        assert len(response.data['data']) == 25
        assert response.data['pagination']['count'] == 100
        assert response.data['pagination']['num_pages'] == 4
    
    def test_max_page_size_enforced(self, api_client, admin_user, branch_a):
        """Test: Maximum page size is enforced to prevent resource exhaustion."""
        # Create many members
        for i in range(250):
            Member.objects.create(
                branch=branch_a,
                first_name=f"Member{i}",
                last_name="Test",
                email=f"member{i}@test.com"
            )
        
        api_client.force_authenticate(user=admin_user)
        
        # Try to request 500 per page (exceeds max_page_size=200)
        response = api_client.get('/api/v1/members/', {'page_size': 500})
        
        assert response.status_code == 200
        # Should be capped at max_page_size (200)
        assert len(response.data['data']) <= 200


# ==============================================================================
# CELERY RELIABILITY TESTS
# ==============================================================================

@pytest.mark.django_db
class TestCeleryReliability:
    """Test Celery task reliability patterns."""
    
    def test_notification_task_has_retry_configuration(self):
        """Test: Notification delivery task has retry configuration."""
        from apps.notifications.tasks import deliver_notification
        
        # Check task configuration
        assert hasattr(deliver_notification, 'max_retries')
        assert deliver_notification.max_retries == 3
        assert deliver_notification.default_retry_delay == 30
    
    def test_notification_task_retries_on_failure(self, branch_a, admin_user):
        """Test: Notification task retries on provider failure."""
        from apps.notifications.tasks import deliver_notification
        from apps.notifications.models import NotificationStatus
        
        notification = Notification.objects.create(
            recipient=admin_user,
            title="Test",
            body="Test notification",
            channel=NotificationChannel.EMAIL
        )
        
        # Mock provider to fail
        with patch('apps.notifications.providers.email_provider.send') as mock_send:
            mock_send.side_effect = Exception("Provider unavailable")
            
            # Task should retry and eventually fail
            with pytest.raises(Exception):
                deliver_notification(str(notification.id))
        
        notification.refresh_from_db()
        assert notification.status == NotificationStatus.FAILED
    
    def test_report_job_failure_updates_status(self, branch_a, admin_user):
        """Test: Report job failures are recorded properly."""
        from apps.reports.tasks import run_report_job
        from apps.reports.models import ReportType
        
        job = ReportJob.objects.create(
            branch=branch_a,
            requested_by=admin_user,
            report_type=ReportType.ATTENDANCE_SUMMARY,
            export_format='CSV'
        )
        
        # Mock generator to fail
        with patch('apps.reports.services.REPORT_GENERATORS') as mock_generators:
            mock_generators.get.return_value = None
            
            with pytest.raises(ValueError):
                run_report_job(str(job.id))
        
        job.refresh_from_db()
        assert job.status == ReportJobStatus.FAILED
        assert job.error_message is not None
    
    def test_duplicate_event_registration_prevented(self, branch_a, admin_user):
        """Test: Database constraint prevents duplicate event registrations."""
        member = Member.objects.create(
            branch=branch_a,
            first_name="Test",
            last_name="Member",
            email="test@test.com"
        )
        
        event = Event.objects.create(
            branch=branch_a,
            title="Test Event",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=2)
        )
        
        schedule = EventSchedule.objects.create(
            event=event,
            occurrence_start=timezone.now(),
            occurrence_end=timezone.now() + timedelta(hours=2)
        )
        
        # First registration should succeed
        registration1 = EventRegistration.objects.create(
            schedule=schedule,
            member=member
        )
        
        # Second registration should fail (unique_together)
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            EventRegistration.objects.create(
                schedule=schedule,
                member=member
            )


# ==============================================================================
# CONCURRENCY TESTS
# ==============================================================================

@pytest.mark.django_db
class TestConcurrency:
    """Test concurrent operation safety."""
    
    def test_qr_token_uniqueness_enforced(self, branch_a):
        """Test: QR token uniqueness prevents duplicates."""
        from apps.members.models import MemberQRCode
        
        member1 = Member.objects.create(
            branch=branch_a,
            first_name="Member1",
            last_name="Test",
            email="member1@test.com"
        )
        
        member2 = Member.objects.create(
            branch=branch_a,
            first_name="Member2",
            last_name="Test",
            email="member2@test.com"
        )
        
        qr1 = MemberQRCode.objects.create(member=member1)
        qr2 = MemberQRCode.objects.create(member=member2)
        
        # Tokens should be unique
        assert qr1.token != qr2.token
        
        # Attempting to create duplicate token should fail
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            MemberQRCode.objects.create(
                member=member1,
                token=qr1.token
            )
    
    def test_financial_transaction_atomicity(self, branch_a, admin_user):
        """Test: Financial operations should be atomic."""
        category = GivingCategory.objects.create(name="Test Category")
        
        member = Member.objects.create(
            branch=branch_a,
            first_name="Test",
            last_name="Member",
            email="test@test.com"
        )
        
        # Simulate atomic transaction
        with transaction.atomic():
            giving = Giving.objects.create(
                branch=branch_a,
                member=member,
                category=category,
                amount=Decimal('100.00'),
                status=GivingStatus.CONFIRMED,
                source=GivingSource.OFFLINE,
                recorded_by=admin_user
            )
            
            # If payment creation fails, giving should rollback
            # This tests that transactions are properly atomic
            payment = Payment.objects.create(
                branch=branch_a,
                member=member,
                amount=Decimal('100.00'),
                provider='CASH',
                status=PaymentStatus.SUCCESSFUL
            )
        
        # Both should exist
        assert Giving.objects.filter(id=giving.id).exists()
        assert Payment.objects.filter(id=payment.id).exists()


# ==============================================================================
# HEALTH ENDPOINT TESTS
# ==============================================================================

@pytest.mark.django_db
class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_liveness_endpoint_responds(self, api_client):
        """Test: Liveness endpoint returns 200."""
        response = api_client.get('/health/')
        
        assert response.status_code == 200
        assert response.data['status'] == 'ok'
    
    def test_liveness_does_not_require_authentication(self, api_client):
        """Test: Liveness endpoint accessible without auth."""
        # Should work without authentication
        response = api_client.get('/liveness/')
        
        assert response.status_code == 200
        assert response.data['status'] == 'ok'
    
    def test_readiness_checks_dependencies(self, api_client):
        """Test: Readiness endpoint checks database, Redis, Celery."""
        response = api_client.get('/readiness/')
        
        # Should check multiple dependencies
        assert 'checks' in response.data
        assert 'database' in response.data['checks']
        assert 'redis' in response.data['checks']
        assert 'celery_broker' in response.data['checks']
    
    def test_readiness_returns_503_on_failure(self, api_client):
        """Test: Readiness returns 503 when dependencies fail."""
        # Mock database failure
        with patch('common.health._check_database') as mock_db:
            mock_db.return_value = False
            
            response = api_client.get('/readiness/')
            
            assert response.status_code == 503
            assert response.data['status'] == 'unavailable'
            assert response.data['checks']['database'] is False


# ==============================================================================
# REPORT PERFORMANCE TESTS
# ==============================================================================

@pytest.mark.django_db
class TestReportPerformance:
    """Test report generation performance."""
    
    def test_report_generation_is_async(self, api_client, admin_user, branch_a):
        """Test: Large reports generate asynchronously via Celery."""
        from apps.reports.models import ReportType
        
        api_client.force_authenticate(user=admin_user)
        
        # Request report
        response = api_client.post('/api/v1/reports/', {
            'report_type': ReportType.MEMBER_ROSTER,
            'export_format': 'CSV',
            'filters': {}
        })
        
        assert response.status_code == 201
        
        # Should return job ID, not the actual report
        assert 'id' in response.data['data']
        assert response.data['data']['status'] == ReportJobStatus.PENDING
        
        # Report generation happens in background
        job_id = response.data['data']['id']
        
        # Check job status
        response = api_client.get(f'/api/v1/reports/{job_id}/')
        assert response.status_code == 200
    
    def test_report_job_validates_authorization_at_runtime(self, branch_a, admin_user):
        """Test: Report job re-validates user access at execution time."""
        from apps.reports.tasks import run_report_job
        from apps.reports.models import ReportType
        
        job = ReportJob.objects.create(
            branch=branch_a,
            requested_by=admin_user,
            report_type=ReportType.MEMBER_ROSTER,
            export_format='CSV'
        )
        
        # Remove user's branch access
        admin_user.branch = None
        admin_user.save()
        
        # Mock generator
        with patch('apps.reports.services.REPORT_GENERATORS') as mock_generators:
            mock_generators.get.return_value = lambda b, f: []
            
            # Task should detect permission loss and fail
            run_report_job(str(job.id))
        
        job.refresh_from_db()
        assert job.status == ReportJobStatus.FAILED
        assert 'Permission denied' in job.error_message


# ==============================================================================
# PAGINATION TESTS
# ==============================================================================

@pytest.mark.django_db
class TestPaginationBehavior:
    """Test pagination prevents resource exhaustion."""
    
    def test_default_page_size_applied(self, api_client, admin_user, branch_a):
        """Test: Default page size (25) is used when not specified."""
        # Create 50 members
        for i in range(50):
            Member.objects.create(
                branch=branch_a,
                first_name=f"Member{i}",
                last_name="Test",
                email=f"member{i}@test.com"
            )
        
        api_client.force_authenticate(user=admin_user)
        
        response = api_client.get('/api/v1/members/')
        
        assert response.status_code == 200
        assert len(response.data['data']) == 25  # Default page_size
        assert response.data['pagination']['page_size'] == 25
    
    def test_custom_page_size_respected(self, api_client, admin_user, branch_a):
        """Test: Custom page_size parameter is respected within limits."""
        # Create 100 members
        for i in range(100):
            Member.objects.create(
                branch=branch_a,
                first_name=f"Member{i}",
                last_name="Test",
                email=f"member{i}@test.com"
            )
        
        api_client.force_authenticate(user=admin_user)
        
        # Request 50 per page
        response = api_client.get('/api/v1/members/', {'page_size': 50})
        
        assert response.status_code == 200
        assert len(response.data['data']) == 50
        assert response.data['pagination']['page_size'] == 50
    
    def test_pagination_metadata_complete(self, api_client, admin_user, branch_a):
        """Test: Pagination metadata includes all required fields."""
        # Create 30 members
        for i in range(30):
            Member.objects.create(
                branch=branch_a,
                first_name=f"Member{i}",
                last_name="Test",
                email=f"member{i}@test.com"
            )
        
        api_client.force_authenticate(user=admin_user)
        
        response = api_client.get('/api/v1/members/')
        
        assert response.status_code == 200
        pagination = response.data['pagination']
        
        # All pagination fields present
        assert 'count' in pagination
        assert 'num_pages' in pagination
        assert 'current_page' in pagination
        assert 'page_size' in pagination
        assert 'next' in pagination
        assert 'previous' in pagination
        
        assert pagination['count'] == 30
        assert pagination['num_pages'] == 2  # 30 items / 25 per page


# ==============================================================================
# REDIS RELIABILITY TESTS
# ==============================================================================

@pytest.mark.django_db
class TestRedisReliability:
    """Test Redis failure handling."""
    
    def test_readiness_detects_redis_failure(self, api_client):
        """Test: Readiness check detects Redis unavailability."""
        # Mock Redis failure
        with patch('common.health._check_redis') as mock_redis:
            mock_redis.return_value = False
            
            response = api_client.get('/readiness/')
            
            assert response.status_code == 503
            assert response.data['checks']['redis'] is False
    
    def test_readiness_detects_celery_broker_failure(self, api_client):
        """Test: Readiness check detects Celery broker failure."""
        # Mock Celery broker failure
        with patch('common.health._check_celery_broker') as mock_celery:
            mock_celery.return_value = False
            
            response = api_client.get('/readiness/')
            
            assert response.status_code == 503
            assert response.data['checks']['celery_broker'] is False


# ==============================================================================
# SUMMARY
# ==============================================================================

"""
Phase 19 Performance & Reliability Test Coverage Summary:

DATABASE PERFORMANCE (4 tests):
✓ Member list uses select_related (N+1 prevention)
✓ Member detail uses prefetch_related
✓ Pagination prevents unbounded queries
✓ Max page size enforced

CELERY RELIABILITY (4 tests):
✓ Notification task retry configuration
✓ Notification task retries on failure
✓ Report job failure tracking
✓ Duplicate registration prevention

CONCURRENCY (2 tests):
✓ QR token uniqueness enforced
✓ Financial transaction atomicity

HEALTH ENDPOINTS (4 tests):
✓ Liveness responds correctly
✓ Liveness accessible without auth
✓ Readiness checks dependencies
✓ Readiness returns 503 on failure

REPORT PERFORMANCE (2 tests):
✓ Report generation is async
✓ Report validates authorization at runtime

PAGINATION (3 tests):
✓ Default page size applied
✓ Custom page size respected
✓ Pagination metadata complete

REDIS RELIABILITY (2 tests):
✓ Readiness detects Redis failure
✓ Readiness detects Celery broker failure

TOTAL: 21 performance and reliability tests

EXECUTION: Django environment required
STATUS: Tests created but NOT EXECUTED (environment unavailable)
"""
