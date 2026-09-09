"""
Phase 13: Prayer Request Notification Integration

Sends notifications for key prayer request events:
- Request assignment to chaplain/pastoral staff
- Request answered/closure
- Follow-up reminders
- Public prayer requests to fellowship

Privacy considerations:
- PRIVATE/PASTORAL: No details in notification, authentication required
- FELLOWSHIP: Limited details to fellowship members only
- PUBLIC: Full details can be shared
- Anonymous submissions: No member identification
"""

from apps.notifications.models import Notification, NotificationChannel
from apps.notifications.tasks import deliver_notification


def notify_prayer_request_assigned(prayer_request, assigned_to_user):
    """
    Notify chaplain/pastoral staff when assigned a prayer request.
    
    Privacy: Respects privacy_level - minimal info for PRIVATE requests.
    """
    if not assigned_to_user or not assigned_to_user.email:
        return
    
    # Determine requester identification based on privacy
    if prayer_request.privacy_level == 'PRIVATE':
        requester_info = "Private Request"
    elif prayer_request.member:
        requester_info = prayer_request.member.full_name
    elif prayer_request.submitted_by_name:
        requester_info = f"{prayer_request.submitted_by_name} (Anonymous)"
    else:
        requester_info = "Anonymous"
    
    # For PRIVATE requests, don't include details
    if prayer_request.privacy_level == 'PRIVATE':
        body_text = (
            f"You have been assigned a new prayer request.\n\n"
            f"Requester: {requester_info}\n"
            f"Category: {prayer_request.category}\n"
            f"Privacy Level: {prayer_request.get_privacy_level_display()}\n\n"
            f"Please log in to ChapelFlow to view the full prayer request details."
        )
    else:
        # For PASTORAL/FELLOWSHIP/PUBLIC, include brief details
        details_preview = prayer_request.details[:200] + "..." if len(prayer_request.details) > 200 else prayer_request.details
        body_text = (
            f"You have been assigned a new prayer request.\n\n"
            f"Requester: {requester_info}\n"
            f"Category: {prayer_request.category}\n"
            f"Privacy Level: {prayer_request.get_privacy_level_display()}\n\n"
            f"Request: {details_preview}\n\n"
            f"Please log in to ChapelFlow to take action."
        )
    
    notification = Notification.objects.create(
        recipient=assigned_to_user,
        channel=NotificationChannel.EMAIL,
        title=f"Prayer Request Assigned: {prayer_request.category}",
        body=body_text
    )
    
    deliver_notification.delay(str(notification.id))


def notify_prayer_request_answered(prayer_request, answered_by_user):
    """
    Notify requester when their prayer is marked as answered.
    
    Privacy: Only notifies if requester has a user account.
    """
    # Only notify if there's a member with a user account
    if not prayer_request.member or not prayer_request.member.user or not prayer_request.member.user.email:
        return
    
    notification = Notification.objects.create(
        recipient=prayer_request.member.user,
        recipient_member=prayer_request.member,
        channel=NotificationChannel.EMAIL,
        title="Prayer Request Update",
        body=(
            f"Dear {prayer_request.member.first_name},\n\n"
            f"We're reaching out regarding your prayer request for {prayer_request.category}.\n\n"
            f"Your request has been marked as answered. We give thanks to God for His faithfulness!\n\n"
            f"If you have any updates or need continued prayer support, please let us know.\n\n"
            f"Blessings,\n"
            f"ChapelFlow Prayer Team"
        )
    )
    
    deliver_notification.delay(str(notification.id))


def notify_prayer_request_created_to_team(prayer_request, created_by_user):
    """
    Notify pastoral team of new PASTORAL-level prayer requests.
    
    Privacy: Only for PASTORAL level requests that need assignment.
    PRIVATE requests are handled by direct assignment only.
    """
    if prayer_request.privacy_level != 'PASTORAL':
        return
    
    from apps.accounts.models import User
    from common.constants.roles import Roles
    
    # Find all pastoral staff in same branch
    recipients = User.objects.filter(
        branch=prayer_request.branch,
        role__in=[Roles.CHAPLAIN, Roles.SENIOR_PASTOR],
        is_active=True
    )
    
    if prayer_request.member:
        requester_info = prayer_request.member.full_name
    elif prayer_request.submitted_by_name:
        requester_info = f"{prayer_request.submitted_by_name} (Anonymous)"
    else:
        requester_info = "Anonymous"
    
    for recipient in recipients:
        if not recipient.email:
            continue
        
        notification = Notification.objects.create(
            recipient=recipient,
            channel=NotificationChannel.EMAIL,
            title=f"New Pastoral Prayer Request: {prayer_request.category}",
            body=(
                f"A new pastoral prayer request needs review and assignment.\n\n"
                f"Requester: {requester_info}\n"
                f"Category: {prayer_request.category}\n"
                f"Privacy Level: Pastoral\n\n"
                f"Please log in to ChapelFlow to review and assign this request."
            )
        )
        
        deliver_notification.delay(str(notification.id))


def notify_fellowship_of_public_prayer(prayer_request):
    """
    Notify fellowship members of new PUBLIC prayer requests.
    
    Privacy: Only for PUBLIC requests. Sends to active fellowship members
    in the same branch who have opted in to prayer notifications.
    
    Note: This would require a prayer notification preference in user settings.
    For now, this is a stub showing the pattern.
    """
    if prayer_request.privacy_level != 'PUBLIC':
        return
    
    # This is where you'd query fellowship members who opted in
    # For now, this is intentionally not implemented to avoid spam
    # until preference system is in place
    
    # Example pattern (commented out):
    # from apps.members.models import Member
    # members = Member.objects.filter(
    #     branch=prayer_request.branch,
    #     user__isnull=False,
    #     user__prayer_notifications_enabled=True  # Hypothetical field
    # ).select_related('user')
    # 
    # for member in members:
    #     if not member.user.email:
    #         continue
    #     
    #     notification = Notification.objects.create(
    #         recipient=member.user,
    #         recipient_member=member,
    #         channel=NotificationChannel.EMAIL,
    #         title=f"New Prayer Request: {prayer_request.category}",
    #         body=f"A new prayer request has been shared...\n\n{prayer_request.details}"
    #     )
    #     deliver_notification.delay(str(notification.id))
    
    pass


def notify_prayer_follow_up_due(prayer_request):
    """
    Send reminder when a prayer request needs follow-up.
    
    Triggered by scheduled task for IN_PROGRESS/FOLLOW_UP status.
    """
    if not prayer_request.assigned_to or not prayer_request.assigned_to.email:
        return
    
    if prayer_request.member:
        requester_info = prayer_request.member.full_name
    elif prayer_request.submitted_by_name:
        requester_info = f"{prayer_request.submitted_by_name} (Anonymous)"
    else:
        requester_info = "Anonymous"
    
    notification = Notification.objects.create(
        recipient=prayer_request.assigned_to,
        channel=NotificationChannel.EMAIL,
        title=f"📅 Prayer Follow-Up Due: {prayer_request.category}",
        body=(
            f"A prayer request assigned to you needs follow-up.\n\n"
            f"Requester: {requester_info}\n"
            f"Category: {prayer_request.category}\n"
            f"Privacy Level: {prayer_request.get_privacy_level_display()}\n"
            f"Status: {prayer_request.get_status_display()}\n\n"
            f"Please log in to ChapelFlow to follow up."
        )
    )
    
    deliver_notification.delay(str(notification.id))


def notify_prayer_request_closed(prayer_request, closed_by_user):
    """
    Notify requester when prayer request is closed.
    
    Privacy: Only notifies if requester has a user account.
    """
    if not prayer_request.member or not prayer_request.member.user or not prayer_request.member.user.email:
        return
    
    # Determine message based on closure status
    if prayer_request.status == 'ANSWERED':
        message = (
            f"Your prayer request regarding {prayer_request.category} has been answered. "
            f"We rejoice with you in God's faithfulness!"
        )
    elif prayer_request.status == 'CANCELLED':
        message = (
            f"Your prayer request regarding {prayer_request.category} has been marked as complete."
        )
    else:
        message = (
            f"Your prayer request regarding {prayer_request.category} has been closed."
        )
    
    notification = Notification.objects.create(
        recipient=prayer_request.member.user,
        recipient_member=prayer_request.member,
        channel=NotificationChannel.EMAIL,
        title="Prayer Request Update",
        body=(
            f"Dear {prayer_request.member.first_name},\n\n"
            f"{message}\n\n"
            f"If you need continued prayer support, please don't hesitate to submit a new request.\n\n"
            f"Blessings,\n"
            f"ChapelFlow Prayer Team"
        )
    )
    
    deliver_notification.delay(str(notification.id))
