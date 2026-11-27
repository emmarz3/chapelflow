import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  CalendarDays,
  Camera,
  CheckCircle2,
  Clock3,
  Coins,
  MessageCircle,
  QrCode,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Badge, ErrorState, LoadingState, PageHeader } from "../components/ui";
import { attendanceService, communityService, eventService } from "../services/chapelflow";
import { useAuth } from "./auth-context";
import { markAppPerformance } from "../lib/performance";

function CommunityCard({ label, name, unread }: { label: string; name: string; unread?: number }) {
  return <div className="student-community-card"><Users /><div><small>{label}</small><strong>{name}</strong></div>{Boolean(unread) && <Badge tone="purple">{unread} new</Badge>}</div>;
}

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
  useEffect(() => {
    markAppPerformance("student_dashboard_mounted");
  }, []);
  useEffect(() => {
    if (pass.isSuccess) markAppPerformance("student_dashboard_essential_data_ready");
  }, [pass.isSuccess]);
  if (pass.isPending) return <LoadingState label="Loading your chapel activity" />;
  if (pass.isError)
    return <ErrorState description={pass.error.message} onRetry={() => void pass.refetch()} />;

  const student = pass.data.student;
  const session = pass.data.session;
  const records = history.data ?? [];
  const studentCommunities = communities.data ?? [];
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
      <section className="student-giving-prompt student-upper-room-prompt">
        <MessageCircle aria-hidden="true" />
        <div><p className="eyebrow">CUC community</p><h2>Meet us in The Upper Room</h2><p>Share chapel moments, encourage others, and join the conversation with grace.</p></div>
        <Link className="button button--secondary" to="/app/upper-room">Open The Upper Room</Link>
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

      {communities.isSuccess && <section className="panel student-community-summary"><header className="panel-heading"><div><h2>Your chapel communities</h2><p>Updates from your Fellowship and Chapel Units.</p></div><Link className="text-link" to="/app/communities">Open communities</Link></header>{studentCommunities.length ? <div>{studentCommunities.map((community) => <CommunityCard key={community.id} label={community.type === "unit" ? "Chapel unit" : "Fellowship"} name={community.name} unread={community.unreadCount} />)}</div> : <p className="empty-copy">You have not joined a Fellowship or Chapel Unit yet. <Link className="text-link" to="/app/join-community">Browse Fellowships and Units</Link></p>}</section>}
    </div>
  );
}
