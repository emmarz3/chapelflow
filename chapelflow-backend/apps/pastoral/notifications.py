"""
Phase 13: Pastoral Care Notification Integration

Sends notifications for key pastoral care events:
- Case assignment to chaplain/pastoral staff
- Case status changes (escalation, closure)
- Case escalation alerts
- Follow-up reminders

Privacy considerations:
- Notifications contain minimal sensitive information
- Full details only accessible via authenticated API
- No pastoral case details in notification body
"""

<<<<<<< HEAD
from apps.notifications.models import NotificationCategory, NotificationChannel
from apps.notifications.preferences import queue_notification
=======
from apps.notifications.models import Notification, NotificationChannel
from apps.notifications.tasks import deliver_notification
>>>>>>> origin/main


def notify_case_assigned(pastoral_case, assigned_to_user):
    """
    Notify chaplain/pastoral staff when assigned a pastoral case.
    
    Privacy: Does NOT include case details, only member name and category.
    Staff must access the system to view full case.
    """
    if not assigned_to_user or not assigned_to_user.email:
        return
    
    member_name = pastoral_case.member.full_name if pastoral_case.member else "Unknown"
    
<<<<<<< HEAD
    notification = queue_notification(
        recipient=assigned_to_user,
        category=NotificationCategory.ADMIN_ALERT,
=======
    notification = Notification.objects.create(
        recipient=assigned_to_user,
>>>>>>> origin/main
        channel=NotificationChannel.EMAIL,
        title=f"Pastoral Case Assigned: {pastoral_case.category}",
        body=(
            f"You have been assigned a new pastoral case.\n\n"
            f"Member: {member_name}\n"
            f"Category: {pastoral_case.category}\n"
            f"Priority: {pastoral_case.get_priority_display()}\n\n"
            f"Please log in to ChapelFlow to view full case details and take action."
        )
    )
    
<<<<<<< HEAD
    return notification
=======
    deliver_notification.delay(str(notification.id))
>>>>>>> origin/main


def notify_case_escalated(pastoral_case, escalated_by_user):
    """
    Notify senior pastoral staff when a case is escalated.
    
    Sends to:
    - Branch chaplain (if not the one who escalated)
    - Super admins in the same branch
    """
    from apps.accounts.models import User
    from common.constants.roles import Roles
    
    # Find recipients: chaplains and super admins in same branch
    recipients = User.objects.filter(
        branch=pastoral_case.branch,
<<<<<<< HEAD
        role__in=[Roles.CHAPLAIN, Roles.PASTOR, Roles.SUPER_ADMIN],
=======
        role__in=[Roles.CHAPLAIN, Roles.SENIOR_PASTOR, Roles.SUPER_ADMIN],
>>>>>>> origin/main
        is_active=True
    ).exclude(id=escalated_by_user.id if escalated_by_user else None)
    
    member_name = pastoral_case.member.full_name if pastoral_case.member else "Unknown"
<<<<<<< HEAD
    escalated_by_name = escalated_by_user.full_name if escalated_by_user else "Unknown"
=======
    escalated_by_name = escalated_by_user.get_full_name() if escalated_by_user else "Unknown"
>>>>>>> origin/main
    
    for recipient in recipients:
        if not recipient.email:
            continue
        
<<<<<<< HEAD
        queue_notification(
            recipient=recipient,
            category=NotificationCategory.ADMIN_ALERT,
=======
        notification = Notification.objects.create(
            recipient=recipient,
>>>>>>> origin/main
            channel=NotificationChannel.EMAIL,
            title=f"⚠️ Pastoral Case Escalated: {pastoral_case.category}",
            body=(
                f"A pastoral case has been escalated and requires senior attention.\n\n"
                f"Member: {member_name}\n"
                f"Category: {pastoral_case.category}\n"
                f"Priority: {pastoral_case.get_priority_display()}\n"
                f"Escalated by: {escalated_by_name}\n"
                f"Reason: {pastoral_case.escalation_reason or 'Not specified'}\n\n"
                f"Please log in to ChapelFlow to review and address this case."
            )
        )
        
<<<<<<< HEAD
=======
        deliver_notification.delay(str(notification.id))
>>>>>>> origin/main


def notify_case_closed(pastoral_case, closed_by_user):
    """
    Notify relevant parties when a case is closed.
    
    Sends to:
    - The member (if they have a user account)
    - The chaplain who closed it (confirmation)
    """
    notifications_sent = []
    
    # Notify member (privacy-safe: just confirmation, no details)
    if pastoral_case.member and pastoral_case.member.user and pastoral_case.member.user.email:
<<<<<<< HEAD
        member_notification = queue_notification(
            recipient=pastoral_case.member.user,
            recipient_member=pastoral_case.member,
            category=NotificationCategory.ADMIN_ALERT,
=======
        member_notification = Notification.objects.create(
            recipient=pastoral_case.member.user,
            recipient_member=pastoral_case.member,
>>>>>>> origin/main
            channel=NotificationChannel.EMAIL,
            title="Pastoral Care Follow-Up Complete",
            body=(
                f"Dear {pastoral_case.member.first_name},\n\n"
                f"Your pastoral care request regarding {pastoral_case.category} "
                f"has been completed.\n\n"
                f"If you need further support, please don't hesitate to reach out "
                f"to your fellowship leader or chaplain.\n\n"
                f"Grace and peace,\n"
                f"ChapelFlow Pastoral Team"
            )
        )
<<<<<<< HEAD
        if member_notification:
            notifications_sent.append(member_notification)
=======
        deliver_notification.delay(str(member_notification.id))
        notifications_sent.append(member_notification)
>>>>>>> origin/main
    
    # Notify assigned chaplain (confirmation)
    if pastoral_case.assigned_to and pastoral_case.assigned_to.email:
        if closed_by_user and pastoral_case.assigned_to.id != closed_by_user.id:
            # Only notify if someone else closed it
<<<<<<< HEAD
            chaplain_notification = queue_notification(
                recipient=pastoral_case.assigned_to,
                category=NotificationCategory.ADMIN_ALERT,
=======
            chaplain_notification = Notification.objects.create(
                recipient=pastoral_case.assigned_to,
>>>>>>> origin/main
                channel=NotificationChannel.EMAIL,
                title=f"Pastoral Case Closed: {pastoral_case.category}",
                body=(
                    f"A pastoral case assigned to you has been closed.\n\n"
                    f"Member: {pastoral_case.member.full_name if pastoral_case.member else 'Unknown'}\n"
                    f"Category: {pastoral_case.category}\n"
<<<<<<< HEAD
                    f"Closed by: {closed_by_user.full_name if closed_by_user else 'Unknown'}\n"
=======
                    f"Closed by: {closed_by_user.get_full_name() if closed_by_user else 'Unknown'}\n"
>>>>>>> origin/main
                    f"Reason: {pastoral_case.closure_reason or 'Not specified'}\n\n"
                    f"Log in to ChapelFlow to view the complete case history."
                )
            )
<<<<<<< HEAD
            if chaplain_notification:
                notifications_sent.append(chaplain_notification)
=======
            deliver_notification.delay(str(chaplain_notification.id))
            notifications_sent.append(chaplain_notification)
>>>>>>> origin/main
    
    return notifications_sent


def notify_follow_up_due(pastoral_case):
    """
    Send reminder when a follow-up is due on a pastoral case.
    
    Triggered by scheduled task checking next_follow_up_date.
    """
    if not pastoral_case.assigned_to or not pastoral_case.assigned_to.email:
        return
    
    member_name = pastoral_case.member.full_name if pastoral_case.member else "Unknown"
    
<<<<<<< HEAD
    notification = queue_notification(
        recipient=pastoral_case.assigned_to,
        category=NotificationCategory.ADMIN_ALERT,
=======
    notification = Notification.objects.create(
        recipient=pastoral_case.assigned_to,
>>>>>>> origin/main
        channel=NotificationChannel.EMAIL,
        title=f"📅 Follow-Up Due: {pastoral_case.category}",
        body=(
            f"A pastoral case assigned to you requires follow-up.\n\n"
            f"Member: {member_name}\n"
            f"Category: {pastoral_case.category}\n"
            f"Priority: {pastoral_case.get_priority_display()}\n"
            f"Status: {pastoral_case.get_status_display()}\n\n"
            f"Please log in to ChapelFlow to follow up with this member."
        )
    )
    
<<<<<<< HEAD
    return notification
=======
    deliver_notification.delay(str(notification.id))
>>>>>>> origin/main


def notify_urgent_case_created(pastoral_case, created_by_user):
    """
    Immediate notification for URGENT priority cases.
    
    Sends to all active chaplains in the branch.
    """
    from apps.accounts.models import User
    from common.constants.roles import Roles
    
    if pastoral_case.priority != 'URGENT':
        return
    
    # Find all pastoral staff in same branch
    recipients = User.objects.filter(
        branch=pastoral_case.branch,
<<<<<<< HEAD
        role__in=[Roles.CHAPLAIN, Roles.PASTOR],
=======
        role__in=[Roles.CHAPLAIN, Roles.SENIOR_PASTOR],
>>>>>>> origin/main
        is_active=True
    )
    
    member_name = pastoral_case.member.full_name if pastoral_case.member else "Unknown"
<<<<<<< HEAD
    created_by_name = created_by_user.full_name if created_by_user else "Unknown"
=======
    created_by_name = created_by_user.get_full_name() if created_by_user else "Unknown"
>>>>>>> origin/main
    
    for recipient in recipients:
        if not recipient.email:
            continue
        
<<<<<<< HEAD
        queue_notification(
            recipient=recipient,
            category=NotificationCategory.ADMIN_ALERT,
=======
        notification = Notification.objects.create(
            recipient=recipient,
>>>>>>> origin/main
            channel=NotificationChannel.EMAIL,
            title=f"🚨 URGENT Pastoral Case: {pastoral_case.category}",
            body=(
                f"An URGENT pastoral case requires immediate attention.\n\n"
                f"Member: {member_name}\n"
                f"Category: {pastoral_case.category}\n"
                f"Created by: {created_by_name}\n\n"
                f"Please log in to ChapelFlow immediately to review and assign this case."
            )
        )
        
<<<<<<< HEAD
=======
        deliver_notification.delay(str(notification.id))
>>>>>>> origin/main
