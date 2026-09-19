import QRCode from "qrcode";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  CalendarDays,
  Camera,
  CheckCircle2,
  Coins,
  Clock3,
  QrCode,
  Users,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, ErrorState, LoadingState, PageHeader, useToast } from "../components/ui";
import { attendanceService, authService, communityService, eventService, notificationService, studentContentService } from "../services/chapelflow";
import { useAuth } from "./auth-context";
import { isStudentMember } from "../lib/permissions";

const stateTone = {
  upcoming: "neutral",
  open: "success",
  paused: "warning",
  closed: "danger",
} as const;

function displayDate(value?: string | null) {
  if (!value) return "Time will be confirmed by the chapel.";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Time will be confirmed by the chapel."
    : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function StudentDashboardPage() {
  const { user } = useAuth();
  const pass = useQuery({
    queryKey: ["attendance-pass"],
    queryFn: async () => (await attendanceService.pass()).data,
  });
  const history = useQuery({
    queryKey: ["attendance-history", "me"],
    queryFn: async () => (await attendanceService.history()).data,
  });
  const events = useQuery({
    queryKey: ["student-events"],
    queryFn: async () => (await eventService.list({ page: 1, pageSize: 3 })).data,
  });
  const communities = useQuery({
    queryKey: ["communities"],
    queryFn: async () => (await communityService.mine()).data,
  });
  if (pass.isPending) return <LoadingState label="Loading your chapel activity" />;
  if (pass.isError)
    return <ErrorState description={pass.error.message} onRetry={() => void pass.refetch()} />;

  const student = pass.data.student;
  const session = pass.data.session;
  const records = history.data ?? [];
  const unit = communities.data?.find((community) => community.type === "unit");
  const fellowship = communities.data?.find((community) => community.type !== "unit");
  const firstName = student.name.split(/\s+/)[0] || user?.name.split(/\s+/)[0] || "student";
  const state = session?.state ?? "closed";
  const summary = pass.data.attendance_summary;
  return (
    <div className="student-workspace">
      <PageHeader
        eyebrow={new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" }).format(new Date())}
        title={`Good day, ${firstName}.`}
        description="Here is your chapel activity for this week."
        actions={<Link className="button button--primary" to="/app/chapel-pass"><Camera /> Scan usher QR</Link>}
      />
      <section className="student-identity-strip" aria-label="Your chapel profile">
        {student.photoUrl ? <img src={student.photoUrl} alt="" /> : <span>{student.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("")}</span>}
        <div><strong>{student.identifier}</strong><small>{student.programme || "Academic details are managed by the chapel office."}{student.level ? ` · ${student.level}` : ""}</small></div>
        <Link to="/app/notifications" className="icon-button" aria-label="Open notifications"><Bell /></Link>
      </section>

      <section className="student-attendance-card">
        <div>
          <p className="eyebrow">Attendance checkpoint</p>
          <h2>{session?.title || "No service is open right now"}</h2>
          <p><Clock3 /> {displayDate(session?.opens_at)}</p>
          <Badge tone={stateTone[state] ?? "neutral"}>{session ? state : "upcoming"}</Badge>
        </div>
        <div className="student-attendance-card__action">
          <QrCode aria-hidden="true" />
          <Link className="button button--primary" to="/app/chapel-pass">Scan usher QR</Link>
          <small>Camera access is requested only when you open the scanner.</small>
        </div>
      </section>

      <section className="student-summary-grid" aria-label="Your attendance summary">
        <article><small>Services attended</small><strong>{summary?.attended_services ?? records.length}</strong><p>From completed chapel services</p></article>
        <article><small>Current status</small><strong>{session ? state : "Upcoming"}</strong><p>{session ? "For the current chapel service" : "No active attendance window"}</p></article>
        <article><small>Attendance rate</small><strong>{summary?.percentage == null ? "—" : `${summary.percentage}%`}</strong><p>{summary ? `${summary.missed_services} missed of ${summary.total_services} completed services` : "Shown after completed-service totals are available."}</p></article>
      </section>

      <section className="student-giving-prompt">
        <Coins aria-hidden="true" />
        <div><p className="eyebrow">Personal giving</p><h2>Offerings and tithes</h2><p>Give securely through Paystack. ChapelFlow records only verified successful payments.</p></div>
        <Link className="button button--secondary" to="/app/giving">Give securely</Link>
      </section>

      <div className="student-content-grid">
        <section className="panel">
          <header className="panel-heading"><div><h2>Recent attendance</h2><p>Only your own records are shown here.</p></div><Link className="text-link" to="/app/my-attendance">View history</Link></header>
          {records.length ? <div className="student-record-list">{records.slice(0, 4).map((record) => <article key={`${record.recorded_at}-${record.title}`}><CheckCircle2 /><div><strong>{record.title}</strong><small>{displayDate(record.recorded_at)}</small></div><Badge tone="success">{record.status}</Badge></article>)}</div> : <p className="empty-copy">Your completed attendance will appear here after you scan a live usher QR.</p>}
        </section>
        <section className="panel">
          <header className="panel-heading"><div><h2>Upcoming activity</h2><p>Chapel events open to you.</p></div><Link className="text-link" to="/app/events">View schedule</Link></header>
          {events.data?.length ? <div className="student-event-list">{events.data.slice(0, 3).map((event) => <Link key={event.id} to="/app/events"><CalendarDays /><span><strong>{event.title}</strong><small>{event.date} · {event.time}</small></span></Link>)}</div> : <p className="empty-copy">No upcoming activities have been published yet.</p>}
        </section>
      </div>

      {(unit || fellowship) && <section className="panel student-community-summary"><header className="panel-heading"><div><h2>Your chapel communities</h2><p>Private updates from your assigned unit and fellowship.</p></div><Link className="text-link" to="/app/communities">Open communities</Link></header><div>{unit && <CommunityCard label="Chapel unit" name={unit.name} unread={unit.unreadCount} />}{fellowship && <CommunityCard label="Fellowship" name={fellowship.name} unread={fellowship.unreadCount} />}</div></section>}
    </div>
  );
}

export function StudentJoinCommunityPage() {
  const toast = useToast();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["student-join-requests"], queryFn: async () => (await studentContentService.joinRequests()).data });
  const request = useMutation({ mutationFn: ({ group, message }: { group: string; message: string }) => studentContentService.requestJoin(group, message), onSuccess: () => { toast("Join request sent to the community leader."); void client.invalidateQueries({ queryKey: ["student-join-requests"] }); } });
  if (query.isPending) return <LoadingState label="Loading chapel communities" />;
  if (query.isError) return <ErrorState description={query.error.message} onRetry={() => void query.refetch()} />;
  return <div className="student-workspace"><PageHeader eyebrow="Chapel communities" title="Join a unit or fellowship" description="Your request is reviewed by the assigned leader. You can only request communities within your chapel branch." />
    <section className="role-workspace-grid">{query.data.groups.length ? query.data.groups.map((group) => <article className="panel" key={group.id}><p className="eyebrow">{group.type.toLowerCase()}</p><h2>{group.name}</h2><p>{group.description || "A Chrisland University Chapel community."}</p><form className="form-grid" onSubmit={(event) => { event.preventDefault(); request.mutate({ group: group.id, message: String(new FormData(event.currentTarget).get("message") || "") }); }}><label className="field field--full"><span>Optional note to the leader</span><textarea name="message" rows={2} maxLength={500} /></label><Button type="submit" loading={request.isPending}>Request to join</Button></form></article>) : <ErrorState description="There are no additional active communities available to join." />}</section>
    <section className="panel"><header className="panel-heading"><div><h2>Your requests</h2><p>Community leaders review requests from their own group workspace.</p></div></header>{query.data.requests.length ? <div className="stack-list">{query.data.requests.map((item) => <article key={item.id}><strong>{item.group}</strong><Badge tone={item.status === "APPROVED" ? "success" : item.status === "REJECTED" ? "danger" : "warning"}>{item.status.toLowerCase()}</Badge></article>)}</div> : <p className="empty-copy">You have not sent a join request.</p>}</section>
  </div>;
}

function CommunityCard({ label, name, unread }: { label: string; name: string; unread?: number }) {
  return <div className="student-community-card"><Users /><div><small>{label}</small><strong>{name}</strong></div>{Boolean(unread) && <Badge tone="purple">{unread} new</Badge>}</div>;
}

export function StudentAttendanceHistoryPage() {
  const history = useQuery({ queryKey: ["attendance-history", "me"], queryFn: async () => (await attendanceService.history()).data });
  if (history.isPending) return <LoadingState label="Loading your attendance history" />;
  if (history.isError) return <ErrorState description={history.error.message} onRetry={() => void history.refetch()} />;
  return <><PageHeader eyebrow="Personal record" title="My attendance" description="This is your private chapel-service attendance history." /><section className="panel student-history-panel">{history.data.length ? history.data.map((record) => <article key={`${record.recorded_at}-${record.title}`}><CheckCircle2 /><div><strong>{record.title}</strong><small>{displayDate(record.recorded_at)}</small></div><Badge tone="success">{record.status}</Badge></article>) : <p className="empty-copy">You have no completed attendance records yet.</p>}</section></>;
}

export function StudentNotificationsPage() {
  const client = useQueryClient();
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: async () => (await notificationService.list()).data });
  const markRead = useMutation({ mutationFn: notificationService.markRead, onSuccess: () => void client.invalidateQueries({ queryKey: ["notifications"] }) });
  if (notifications.isPending) return <LoadingState label="Loading your notifications" />;
  if (notifications.isError) return <ErrorState description={notifications.error.message} onRetry={() => void notifications.refetch()} />;
  return <><PageHeader eyebrow="Personal updates" title="Notifications" description="Updates sent to your ChapelFlow account and assigned communities." /><section className="panel student-history-panel">{notifications.data.length ? notifications.data.map((item) => <article key={item.id}><Bell /><div><strong>{item.title}</strong><small>{item.body}</small><small>{displayDate(item.created_at)}</small></div>{!item.read_at && <button className="text-link" disabled={markRead.isPending} onClick={() => markRead.mutate(item.id)}>Mark read</button>}</article>) : <p className="empty-copy">You have no notifications.</p>}</section></>;
}

export function StudentAnnouncementsPage() {
  const { user } = useAuth();
  const isStudent = isStudentMember(user);
  const announcements = useQuery({ queryKey: ["student-announcements"], queryFn: async () => (await studentContentService.announcements()).data });
  if (announcements.isPending) return <LoadingState label="Loading chapel announcements" />;
  if (announcements.isError) return <ErrorState description={announcements.error.message} onRetry={() => void announcements.refetch()} />;
  return <><PageHeader eyebrow="From your chapel" title="Announcements" description={isStudent ? "Published chapel and assigned-community updates." : "Published chapel-wide updates."} /><section className="panel student-history-panel">{announcements.data.length ? announcements.data.map((item) => <article key={item.id}><Bell /><div><strong>{item.title}</strong><small>{item.body}</small><small>{displayDate(item.published_at)}</small></div></article>) : <p className="empty-copy">No chapel-wide announcements have been published for you yet.</p>}</section></>;
}

export function StudentIdentityPassPage() {
  const pass = useQuery({ queryKey: ["identity-pass"], queryFn: async () => (await attendanceService.identityPass()).data });
  const [image, setImage] = useState("");
  useEffect(() => { if (pass.data?.token) void QRCode.toDataURL(pass.data.token, { width: 420, margin: 2, errorCorrectionLevel: "M" }).then(setImage); }, [pass.data?.token]);
  if (pass.isPending) return <LoadingState label="Preparing your chapel identity pass" />;
  if (pass.isError) return <ErrorState description={pass.error.message} onRetry={() => void pass.refetch()} />;
  return <><PageHeader eyebrow="Private identity" title="My QR pass" description="This identifies your ChapelFlow profile in approved workflows. It cannot record your own attendance." /><section className="student-identity-pass"><QrCode aria-hidden="true" /><div>{image && <img src={image} alt="Your private ChapelFlow identity QR pass" />}<p>Show this only to authorized chapel staff when they request your identity pass. To mark service attendance, use Scan usher QR instead.</p><Link className="button button--primary" to="/app/chapel-pass"><Camera /> Scan usher QR</Link></div></section></>;
}

export function StudentProfilePage() {
  const { user } = useAuth();
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const profile = useQuery({
    queryKey: ["student-profile"],
    queryFn: async () => (await authService.studentProfile()).data,
  });
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const current = String(form.get("current") || "");
    const password = String(form.get("password") || "");
    if (!current || password.length < 12) {
      setNotice("Enter your current password and a new password with at least 12 characters.");
      return;
    }
    setSaving(true);
    setNotice(null);
    try {
      await authService.changePassword(current, password);
      event.currentTarget.reset();
      setNotice("Password updated.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Password could not be updated.");
    } finally {
      setSaving(false);
    }
  }
  if (profile.isPending) return <LoadingState label="Loading your profile" />;
  if (profile.isError)
    return <ErrorState description={profile.error.message} onRetry={() => void profile.refetch()} />;
  const profileEmail = profile.data.email || user?.email;
  return <><PageHeader eyebrow="Personal account" title="Profile and security" description="Your academic identity is protected by the chapel office." /><div className="student-content-grid"><section className="panel"><header className="panel-heading"><div><h2>Your account</h2><p>Contact details shown to ChapelFlow.</p></div></header><dl className="student-profile-list"><div><dt>Name</dt><dd>{user?.name}</dd></div><div><dt>Email</dt><dd>{profileEmail}</dd></div><div><dt>Phone</dt><dd>{profile.data.phone_number || "Not recorded"}</dd></div><div><dt>Role</dt><dd>Student</dd></div></dl><p className="empty-copy">Your contact, emergency, and photo details can be changed through the secured profile API. Matric number, programme, department, level, roles, and attendance records are protected. Contact the chapel office to correct them.</p></section><section className="panel"><header className="panel-heading"><div><h2>Change password</h2><p>Use a unique password you do not reuse elsewhere.</p></div></header><form className="student-password-form" onSubmit={(event) => void changePassword(event)}><label>Current password<input name="current" type="password" autoComplete="current-password" /></label><label>New password<input name="password" type="password" autoComplete="new-password" minLength={12} /></label>{notice && <p className="form-note">{notice}</p>}<button className="button button--primary" disabled={saving}>{saving ? "Saving…" : "Update password"}</button></form></section></div></>;
}
