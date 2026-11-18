# ChapelFlow moderation guide

## Coverage

Members can report Upper Room posts (including attached images and video), comments, group messages, group resource links, group announcements, prayer requests they can already see, and their own testimonies. Prayer notes and private requests belonging to someone else cannot be reported or retrieved by ordinary members. Testimonies remain subject to the existing pastoral approval and consent process.

Report reasons are harassment, bullying, spam, impersonation, hate speech, inappropriate content, privacy violation, and other. A report stores its reporter, target type and ID, branch, reason, optional explanation, content snapshot, creation time, and status. The reporter's "My reports" view shows status without moderator notes, actor details, or other reports.

## Review workflow

1. Open **Community safety**. Authorized pastoral moderators see the queue for their chapel branch; Super Admin can see all branches. The moderator must satisfy the existing MFA requirement for their role. Reports they submitted or about their own content are excluded from their review scope, protecting the reporter from the reported moderator.
2. Filter by pending, reviewed, dismissed, escalated, or all. Open a report to see the submitted content snapshot, reason, reporter ID, assignment, restriction state, review time, and action history.
3. Record **review**, **dismiss**, **hide**, **remove**, **restore**, or **escalate**. A reason is required for dismissal, hide, remove, and escalation. The first reviewing moderator is assigned automatically. Only Super Admin can suspend the content author; self-suspension and Super Admin suspension are rejected.
4. Each action creates an append-only moderation event and a central audit log entry. Reporter status is updated and an in-app notification is sent. Hide, remove, and restore also notify the author without revealing who reported them.

Hidden or removed content is excluded server-side from its normal feed, conversation, resource library, or prayer/testimony query. Restore removes the moderation restriction. It does not resurrect a post or comment that its author deleted independently.

## Safeguards and operations

Reports are limited to five per hour per account, and repeat reports of the same target within 24 hours are rejected. Posts are limited to ten per minute; comments and group messages to twenty per minute. Identical text submitted by the same author to the same location within a minute is rejected. Community resource links must be HTTP or HTTPS and cannot contain embedded credentials. Social media uploads require an allowed extension, matching MIME type, and matching file signature. Moderation is a human decision; no automated classifier suspends accounts.

Apply the `moderation` migrations before enabling the UI. In-app notifications depend on the existing notification centre. If a report involves immediate safety concerns, escalate it and follow the chapel's offline incident process; the app does not send an emergency alert.
