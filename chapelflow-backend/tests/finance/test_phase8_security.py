"""
Phase 8: Comprehensive financial security test matrix.

Tests cover all 10 attack scenarios from the Phase 8 master prompt:
1. Member substitution
2. Scope substitution (branch)
3. Amount manipulation
4. Status manipulation
5. Payment spoofing
6. Webhook replay
7. Refund abuse
8. Over-refund
9. Financial report bypass
10. Direct-ID access
"""
import json
from decimal import Decimal

import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestPhase8SecurityAttacks:
    """
    Phase 8: Critical security attack scenarios.
    
    Each test represents a real attack that must be blocked.
    """
    
    # ========================================================================
    # ATTACK 1: Member Substitution
    # ========================================================================
    
    def test_attack_member_substitution_create_giving_for_another_member(
        self, api_client, branch_a, finance_user
    ):
        """
        ATTACK: User attempts to create giving record for another member.
        EXPECTED: Serializer validation blocks member assignment or server derives from auth.
        """
        from apps.finance.models import GivingCategory
        from apps.members.models import Member
        
        # Create two members
        victim = Member.objects.create(branch=branch_a, first_name="Victim", last_name="Member")
        attacker_member = Member.objects.create(branch=branch_a, first_name="Attacker", last_name="Member")
        
        category = GivingCategory.objects.create(name="Tithe")
        
        # Finance user attempts to assign giving to victim
        api_client.force_authenticate(user=finance_user)
        response = api_client.post("/api/v1/giving/", {
            "branch": branch_a.id,
            "member": victim.id,  # ← Attempting to assign to another member
            "category": category.id,
            "amount": "1000.00",
            "currency": "NGN",
            "source": "CASH",
        })
        
        # Should succeed for finance staff (they can record for anyone)
        # But member field must be validated against branch scope
        assert response.status_code in [200, 201]
        
        # Verify member belongs to same branch
        from apps.finance.models import Giving
        giving = Giving.objects.get(id=response.data["id"])
        assert giving.member.branch == giving.branch
    
    # ========================================================================
    # ATTACK 2: Scope Substitution (Branch)
    # ========================================================================
    
    def test_attack_branch_substitution_assign_to_unauthorized_branch(
        self, api_client, branch_a, branch_b, finance_user
    ):
        """
        ATTACK: User from Branch A attempts to create giving for Branch B.
        EXPECTED: Serializer validation blocks or server overrides with user's branch.
        """
        from apps.finance.models import GivingCategory
        
        category = GivingCategory.objects.create(name="Offering")
        
        # Finance user belongs to branch_a
        finance_user.branch = branch_a
        finance_user.save()
        
        api_client.force_authenticate(user=finance_user)
        response = api_client.post("/api/v1/giving/", {
            "branch": branch_b.id,  # ← Attempting to assign to different branch
            "category": category.id,
            "amount": "500.00",
            "currency": "NGN",
            "source": "CASH",
        })
        
        # Should either fail (403/400) or server overrides branch
        if response.status_code in [200, 201]:
            from apps.finance.models import Giving
            giving = Giving.objects.get(id=response.data["id"])
            # Server must have overridden with user's branch
            assert giving.branch == branch_a
        else:
            assert response.status_code in [400, 403]
    
    # ========================================================================
    # ATTACK 3: Amount Manipulation
    # ========================================================================
    
    def test_attack_negative_amount(self, api_client, branch_a, finance_user):
        """
        ATTACK: Submit negative amount.
        EXPECTED: Validation error.
        """
        from apps.finance.models import GivingCategory
        
        category = GivingCategory.objects.create(name="Building Fund")
        api_client.force_authenticate(user=finance_user)
        
        response = api_client.post("/api/v1/giving/", {
            "branch": branch_a.id,
            "category": category.id,
            "amount": "-1000.00",  # ← Negative
            "currency": "NGN",
            "source": "CASH",
        })
        
        assert response.status_code == 400
        assert "amount" in str(response.data).lower()
    
    def test_attack_zero_amount(self, api_client, branch_a, finance_user):
        """
        ATTACK: Submit zero amount.
        EXPECTED: Validation error.
        """
        from apps.finance.models import GivingCategory
        
        category = GivingCategory.objects.create(name="Missions")
        api_client.force_authenticate(user=finance_user)
        
        response = api_client.post("/api/v1/giving/", {
            "branch": branch_a.id,
            "category": category.id,
            "amount": "0.00",  # ← Zero
            "currency": "NGN",
            "source": "CASH",
        })
        
        assert response.status_code == 400
        assert "amount" in str(response.data).lower()
    
    # ========================================================================
    # ATTACK 4: Status Manipulation
    # ========================================================================
    
    def test_attack_client_controlled_status(self, api_client, branch_a, finance_user):
        """
        ATTACK: Client attempts to set status to VOIDED on create.
        EXPECTED: Status is read-only, server controls it.
        """
        from apps.finance.models import GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Tithe")
        api_client.force_authenticate(user=finance_user)
        
        response = api_client.post("/api/v1/giving/", {
            "branch": branch_a.id,
            "category": category.id,
            "amount": "1000.00",
            "currency": "NGN",
            "source": "CASH",
            "status": "VOIDED",  # ← Attempting to set status
        })
        
        if response.status_code in [200, 201]:
            from apps.finance.models import Giving
            giving = Giving.objects.get(id=response.data["id"])
            # Status must be CONFIRMED (server-controlled)
            assert giving.status == GivingStatus.CONFIRMED
    
    def test_attack_modify_confirmed_giving(self, api_client, branch_a, finance_user):
        """
        ATTACK: Attempt to modify amount on confirmed giving.
        EXPECTED: Immutability protection blocks modification.
        """
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Offering")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("1000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
            recorded_by=finance_user,
        )
        
        api_client.force_authenticate(user=finance_user)
        response = api_client.patch(f"/api/v1/giving/{giving.id}/", {
            "amount": "999999.00",  # ← Attempting to alter amount
        })
        
        # Should fail (immutability protection)
        assert response.status_code in [400, 403]
        
        # Verify amount unchanged
        giving.refresh_from_db()
        assert giving.amount == Decimal("1000.00")
    
    # ========================================================================
    # ATTACK 5: Payment Spoofing
    # ========================================================================
    
    def test_attack_client_links_arbitrary_payment(self, api_client, branch_a, finance_user):
        """
        ATTACK: Client attempts to link arbitrary payment to giving.
        EXPECTED: Payment field is read-only.
        """
        from apps.finance.models import GivingCategory, Payment, PaymentStatus
        
        category = GivingCategory.objects.create(name="Tithe")
        payment = Payment.objects.create(
            branch=branch_a,
            provider="PAYSTACK",
            provider_reference="fake-ref",
            amount=Decimal("1000.00"),
            status=PaymentStatus.SUCCESSFUL,
        )
        
        api_client.force_authenticate(user=finance_user)
        response = api_client.post("/api/v1/giving/", {
            "branch": branch_a.id,
            "category": category.id,
            "amount": "1000.00",
            "currency": "NGN",
            "source": "ONLINE",
            "payment": payment.id,  # ← Attempting to link payment
        })
        
        if response.status_code in [200, 201]:
            from apps.finance.models import Giving
            giving = Giving.objects.get(id=response.data["id"])
            # Payment should be null (read-only field ignored)
            assert giving.payment is None
    
    # ========================================================================
    # ATTACK 6: Webhook Replay (Already tested in test_payments.py)
    # ========================================================================
    
    # Covered by test_replayed_webhook_is_idempotent_noop
    
    # ========================================================================
    # ATTACK 7: Refund Abuse
    # ========================================================================
    
    def test_attack_unauthorized_user_creates_refund(self, api_client, branch_a):
        """
        ATTACK: Regular member attempts to create refund.
        EXPECTED: 403 Forbidden (requires finance authorization).
        """
        from apps.accounts.models import User
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Tithe")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("1000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
        )
        
        # Regular member user
        member_user = User.objects.create_user(
            email="member@test.com",
            password="Pass12345!",
            role="MEMBER",
            branch=branch_a
        )
        
        api_client.force_authenticate(user=member_user)
        response = api_client.post("/api/v1/refunds/", {
            "original_giving": str(giving.id),
            "amount": "500.00",
            "reason": "Duplicate transaction",
        })
        
        assert response.status_code == 403
    
    # ========================================================================
    # ATTACK 8: Over-Refund
    # ========================================================================
    
    def test_attack_refund_exceeds_original_amount(self, api_client, branch_a, finance_user):
        """
        ATTACK: Refund amount exceeds original giving amount.
        EXPECTED: Validation error.
        """
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Offering")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("1000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
            recorded_by=finance_user,
        )
        
        api_client.force_authenticate(user=finance_user)
        response = api_client.post("/api/v1/refunds/", {
            "original_giving": str(giving.id),
            "amount": "1500.00",  # ← Exceeds original 1000
            "reason": "Test",
        })
        
        assert response.status_code == 400
        assert "amount" in str(response.data).lower()
    
    def test_attack_multiple_refunds_exceed_total(self, api_client, branch_a, finance_user):
        """
        ATTACK: Multiple partial refunds that together exceed original.
        EXPECTED: Second refund validation fails.
        """
        from apps.finance.models import Giving, GivingCategory, GivingStatus, Refund
        
        category = GivingCategory.objects.create(name="Building Fund")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("1000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
            recorded_by=finance_user,
        )
        
        # First refund: 600
        Refund.objects.create(
            original_giving=giving,
            amount=Decimal("600.00"),
            reason="Partial refund 1",
            refunded_by=finance_user,
        )
        
        # Second refund: 500 (total 1100 > 1000)
        api_client.force_authenticate(user=finance_user)
        response = api_client.post("/api/v1/refunds/", {
            "original_giving": str(giving.id),
            "amount": "500.00",  # ← Total would be 1100
            "reason": "Partial refund 2",
        })
        
        assert response.status_code == 400
        assert "amount" in str(response.data).lower() or "refund" in str(response.data).lower()
    
    # ========================================================================
    # ATTACK 9: Financial Report Bypass
    # ========================================================================
    
    def test_attack_member_accesses_another_members_giving_history(
        self, api_client, branch_a
    ):
        """
        ATTACK: Member A attempts to view Member B's giving history.
        EXPECTED: Can only view own history via /me/giving/.
        """
        from apps.accounts.models import User
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        from apps.members.models import Member
        
        # Create two members with user accounts
        member_a = Member.objects.create(branch=branch_a, first_name="Alice", last_name="Member")
        member_b = Member.objects.create(branch=branch_a, first_name="Bob", last_name="Member")
        
        user_a = User.objects.create_user(
            email="alice@test.com",
            password="Pass12345!",
            role="MEMBER",
            branch=branch_a
        )
        user_a.member_profile = member_a
        user_a.save()
        
        user_b = User.objects.create_user(
            email="bob@test.com",
            password="Pass12345!",
            role="MEMBER",
            branch=branch_a
        )
        user_b.member_profile = member_b
        user_b.save()
        
        # Create giving for member_b
        category = GivingCategory.objects.create(name="Tithe")
        Giving.objects.create(
            branch=branch_a,
            member=member_b,
            category=category,
            amount=Decimal("5000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
        )
        
        # User A tries to access /me/giving/ (should only see their own, not B's)
        api_client.force_authenticate(user=user_a)
        response = api_client.get("/api/v1/me/giving/")
        
        assert response.status_code == 200
        # Should be empty (member_a has no giving)
        assert response.data["data"]["total_count"] == 0
    
    def test_attack_branch_a_user_queries_branch_b_giving(
        self, api_client, branch_a, branch_b
    ):
        """
        ATTACK: Finance user from Branch A attempts to query Branch B giving.
        EXPECTED: Branch scoping blocks access.
        """
        from apps.accounts.models import User
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        # Create finance user in branch_a
        finance_a = User.objects.create_user(
            email="finance_a@test.com",
            password="Pass12345!",
            role="FINANCE_OFFICER",
            branch=branch_a
        )
        
        # Create giving in branch_b
        category = GivingCategory.objects.create(name="Offering")
        giving_b = Giving.objects.create(
            branch=branch_b,
            category=category,
            amount=Decimal("3000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
        )
        
        # Try to query all giving (should be scoped to branch_a)
        api_client.force_authenticate(user=finance_a)
        response = api_client.get("/api/v1/giving/")
        
        assert response.status_code == 200
        # Should not include branch_b giving
        ids = [item["id"] for item in response.data["results"]]
        assert str(giving_b.id) not in ids
    
    # ========================================================================
    # ATTACK 10: Direct-ID Access
    # ========================================================================
    
    def test_attack_direct_id_access_to_unauthorized_giving(
        self, api_client, branch_a, branch_b
    ):
        """
        ATTACK: User knows giving ID from Branch B, attempts direct access.
        EXPECTED: 404 or 403 (branch scoping prevents access).
        """
        from apps.accounts.models import User
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        finance_a = User.objects.create_user(
            email="finance_a@test.com",
            password="Pass12345!",
            role="FINANCE_OFFICER",
            branch=branch_a
        )
        
        # Create giving in branch_b
        category = GivingCategory.objects.create(name="Tithe")
        giving_b = Giving.objects.create(
            branch=branch_b,
            category=category,
            amount=Decimal("2000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
        )
        
        # Try direct access to branch_b giving
        api_client.force_authenticate(user=finance_a)
        response = api_client.get(f"/api/v1/giving/{giving_b.id}/")
        
        # Should be blocked by branch scoping
        assert response.status_code in [403, 404]


@pytest.mark.django_db
class TestPhase8FinancialIntegrity:
    """
    Phase 8: Financial integrity and business logic tests.
    """
    
    def test_giving_immutability_only_note_can_be_updated(
        self, api_client, branch_a, finance_user
    ):
        """
        Verified: Confirmed giving records can only update note field.
        """
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Tithe")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("1000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
            recorded_by=finance_user,
            note="Original note",
        )
        
        api_client.force_authenticate(user=finance_user)
        
        # Updating note should succeed
        response = api_client.patch(f"/api/v1/giving/{giving.id}/", {
            "note": "Updated note",
        })
        
        assert response.status_code == 200
        giving.refresh_from_db()
        assert giving.note == "Updated note"
    
    def test_void_action_creates_audit_trail(self, api_client, branch_a, finance_user):
        """
        Verified: Void action changes status and creates audit log.
        """
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Offering")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("500.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.CONFIRMED,
            given_at=timezone.now(),
            recorded_by=finance_user,
        )
        
        api_client.force_authenticate(user=finance_user)
        response = api_client.post(f"/api/v1/giving/{giving.id}/void/", {
            "reason": "Duplicate entry",
        })
        
        assert response.status_code == 200
        giving.refresh_from_db()
        assert giving.status == GivingStatus.VOIDED
        assert "VOIDED" in giving.note
    
    def test_refund_voided_transaction_fails(self, api_client, branch_a, finance_user):
        """
        Verified: Cannot refund a voided transaction.
        """
        from apps.finance.models import Giving, GivingCategory, GivingStatus
        
        category = GivingCategory.objects.create(name="Missions")
        giving = Giving.objects.create(
            branch=branch_a,
            category=category,
            amount=Decimal("1000.00"),
            currency="NGN",
            source="CASH",
            status=GivingStatus.VOIDED,  # Already voided
            given_at=timezone.now(),
        )
        
        api_client.force_authenticate(user=finance_user)
        response = api_client.post("/api/v1/refunds/", {
            "original_giving": str(giving.id),
            "amount": "500.00",
            "reason": "Test",
        })
        
        assert response.status_code == 400
        assert "void" in str(response.data).lower()
    
    def test_pledge_fulfillment_validation(self, api_client, branch_a, finance_user):
        """
        Verified: amount_fulfilled cannot exceed amount_pledged (DB constraint).
        """
        from apps.finance.models import Pledge, GivingCategory
        from apps.members.models import Member
        from django.db import IntegrityError
        
        member = Member.objects.create(branch=branch_a, first_name="Test", last_name="Member")
        category = GivingCategory.objects.create(name="Building Fund")
        
        pledge = Pledge.objects.create(
            branch=branch_a,
            member=member,
            category=category,
            amount_pledged=Decimal("1000.00"),
            amount_fulfilled=Decimal("0.00"),
            start_date=timezone.now().date(),
        )
        
        # Attempt to set amount_fulfilled > amount_pledged
        with pytest.raises(IntegrityError):
            pledge.amount_fulfilled = Decimal("1500.00")
            pledge.save()
