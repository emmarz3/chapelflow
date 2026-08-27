import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BellRing,
  Building2,
  CalendarDays,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Coins,
  Download,
  FileText,
  Filter,
  HeartHandshake,
  ListFilter,
  MapPin,
  MoreHorizontal,
  Package,
  Plus,
  QrCode,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  TrendingUp,
  UserCheck,
  Users,
  Video,
  Wifi,
  Wrench,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Modal,
  PageHeader,
  SearchField,
  useToast,
} from "../components/ui";
import {
  attendanceTrend,
  dashboardMetrics,
  events,
  isDemoMode,
  members,
  recentAttendance,
} from "../lib/fixtures";
import { hasPermission, useAuth } from "./auth-context";
import { downloadCsv } from "../lib/export";
import type { Member, Permission } from "../types/domain";
import {
  LiveAnalyticsPage,
  LiveAttendancePage,
  LiveDashboardPage,
  LiveEventsPage,
  LiveMembersPage,
  LiveOperationsPage,
} from "./live-pages";

export function DashboardPage() {
  if (!isDemoMode) return <LiveDashboardPage />;
  return <DemoDashboardPage />;
}

function DemoDashboardPage() {
  const { user } = useAuth();
  const isMember = user?.role === "member";
  const isWorker = user?.role === "worker";
  const isPastor = user?.role === "pastor";
  if (isMember) return <MemberDashboard />;
  if (isWorker) return <WorkerDashboard />;
  const title = isPastor ? "Pastoral overview" : "Good morning, Grace.";
  return (
    <>
      <PageHeader
        eyebrow={`${user?.branchName} · 27 August 2026`}
        title={title}
        description={
          isPastor
            ? "Care priorities and engagement patterns across the chapel community."
            : "Here is what is happening across the chapel today."
        }
        actions={
          <Link className="button button--primary" to="/app/attendance">
            <Plus /> Quick action
          </Link>
        }
      />
      <div className="service-status">
        <div className="service-status__live">
          <span />
          <strong>Sunday Worship attendance is live</strong>
          <small>Check-in closes at 10:15 AM</small>
        </div>
        <div>
          <strong>842</strong>
          <small>checked in</small>
        </div>
        <div>
          <strong>28</strong>
          <small>minutes remaining</small>
        </div>
        <Link className="button button--secondary" to="/app/attendance">
          <QrCode />
          Open scanner
        </Link>
      </div>
      <div className="metric-grid">
        {dashboardMetrics.map((metric, index) => (
          <article className="metric-card" key={metric.label}>
            <div>
              <span className={`metric-icon metric-icon--${index}`}>
                {
                  [
                    <ClipboardCheck />,
                    <Users />,
                    <UserCheck />,
                    <HeartHandshake />,
                  ][index]
                }
              </span>
              <small>{metric.label}</small>
            </div>
            <strong>{metric.value}</strong>
            <p className={metric.trend === "down" ? "trend--warning" : ""}>
              {metric.trend === "up" ? (
                <ArrowUpRight />
              ) : metric.trend === "down" ? (
                <ArrowDownRight />
              ) : (
                <Activity />
              )}
              {metric.change}
            </p>
          </article>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel panel--wide">
          <PanelHeading
            title="Attendance trend"
            subtitle="Weekly worship attendance"
            action={
              <select aria-label="Attendance date range">
                <option>Last 7 weeks</option>
                <option>This semester</option>
              </select>
            }
          />
          <div
            className="chart-wrap"
            role="img"
            aria-label="Attendance has increased from 718 to 842 over seven weeks"
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={attendanceTrend}>
                <defs>
                  <linearGradient
                    id="attendanceFill"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="var(--purple-500)"
                      stopOpacity={0.32}
                    />
                    <stop
                      offset="100%"
                      stopColor="var(--purple-500)"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="var(--border)"
                />
                <XAxis
                  dataKey="week"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="attendance"
                  stroke="var(--purple-500)"
                  strokeWidth={3}
                  fill="url(#attendanceFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel">
          <PanelHeading
            title={isPastor ? "Care priorities" : "Action centre"}
            subtitle="Items needing attention"
          />
          <div className="action-list">
            <ActionItem
              tone="warning"
              icon={<HeartHandshake />}
              title="7 member follow-ups"
              text="Absent for three consecutive services"
            />
            <ActionItem
              tone="purple"
              icon={<UserCheck />}
              title="12 worker approvals"
              text="Pending department review"
            />
            <ActionItem
              tone="danger"
              icon={<Wrench />}
              title="2 assets need service"
              text="Maintenance due this week"
            />
          </div>
          <Link className="panel-link" to="/app/members">
            View all actions <ArrowRight />
          </Link>
        </section>
        <section className="panel panel--wide">
          <PanelHeading
            title="Upcoming events"
            subtitle="Registration and capacity"
            action={
              <Link className="text-link" to="/app/events">
                View calendar
              </Link>
            }
          />
          <div className="event-list">
            {events.map((event) => (
              <article key={event.id}>
                <div className="calendar-tile">
                  <strong>
                    {format(new Date(`${event.date}T12:00:00`), "dd")}
                  </strong>
                  <span>
                    {format(new Date(`${event.date}T12:00:00`), "MMM")}
                  </span>
                </div>
                <div>
                  <strong>{event.title}</strong>
                  <p>
                    {event.time} · {event.venue}
                  </p>
                </div>
                <div className="capacity">
                  <span>
                    <i
                      style={{
                        width: `${(event.registered / event.capacity) * 100}%`,
                      }}
                    />
                  </span>
                  <small>
                    {event.registered} of {event.capacity}
                  </small>
                </div>
                <Link
                  className="icon-button"
                  aria-label={`Open ${event.title}`}
                  to="/app/events"
                >
                  <MoreHorizontal />
                </Link>
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <PanelHeading title="Worker coverage" subtitle="Sunday, 30 August" />
          <div className="donut-layout">
            <div
              className="donut"
              style={{ "--progress": "94%" } as React.CSSProperties}
            >
              <strong>94%</strong>
              <small>covered</small>
            </div>
            <div>
              <p>
                <span className="legend-dot legend-dot--purple" /> 86 confirmed
              </p>
              <p>
                <span className="legend-dot legend-dot--gold" /> 3 open
              </p>
              <p>
                <span className="legend-dot legend-dot--gray" /> 5 awaiting
                reply
              </p>
            </div>
          </div>
          <Link className="panel-link" to="/app/workers">
            Manage duty roster <ArrowRight />
          </Link>
        </section>
      </div>
    </>
  );
}

function MemberDashboard() {
  return (
    <>
      <PageHeader
        eyebrow="Thursday, 27 August"
        title="Welcome back, Favour."
        description="Stay connected with worship, events, and your chapel community."
      />
      <section className="member-hero">
        <div>
          <p className="eyebrow">Next gathering</p>
          <h2>Sunday Worship Service</h2>
          <p>
            <CalendarDays /> 30 August · 9:00 AM
          </p>
          <p>
            <MapPin /> University Chapel
          </p>
          <Link className="button button--primary" to="/events/sunday-worship">
            View service details
          </Link>
        </div>
        <div className="member-id">
          <small>Digital member identity</small>
          <QrCode />
          <strong>Favour Okafor</strong>
          <span>CU/23/CSC/041</span>
        </div>
      </section>
      <div className="metric-grid metric-grid--three">
        <article className="metric-card">
          <small>Attendance this semester</small>
          <strong>86%</strong>
          <p>
            <TrendingUp /> 3% above last semester
          </p>
        </article>
        <article className="metric-card">
          <small>Events registered</small>
          <strong>3</strong>
          <p>Next: Freshers Welcome Service</p>
        </article>
        <article className="metric-card">
          <small>Profile completion</small>
          <strong>92%</strong>
          <p>Add an emergency contact</p>
        </article>
      </div>
      <div className="dashboard-grid">
        <section className="panel panel--wide">
          <PanelHeading
            title="Latest from the chapel"
            subtitle="Messages and announcements"
          />
          <div className="announcement">
            <span>
              <BellRing />
            </span>
            <div>
              <Badge tone="purple">Chapel update</Badge>
              <h3>Freshers Welcome Service registration is open</h3>
              <p>
                Help us welcome the new academic session. Registration closes 3
                September.
              </p>
            </div>
          </div>
          <div className="announcement">
            <span>
              <Video />
            </span>
            <div>
              <Badge>Latest sermon</Badge>
              <h3>Steady faith in changing seasons</h3>
              <p>Pastor Daniel Eze · 23 August 2026</p>
            </div>
          </div>
        </section>
        <section className="panel">
          <PanelHeading title="Your next event" subtitle="Registered" />
          <div className="calendar-feature">
            <strong>06</strong>
            <span>September 2026</span>
            <h3>Freshers Welcome Service</h3>
            <p>9:00 AM · University Chapel</p>
            <Link className="button button--secondary" to="/app/events">
              View ticket
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}

function WorkerDashboard() {
  return (
    <>
      <PageHeader
        eyebrow="Media & Production Team"
        title="Your next duty is Sunday."
        description="Review your assignments, availability, and team updates."
        actions={
          <Link className="button button--secondary" to="/app/workers">
            Update availability
          </Link>
        }
      />
      <section className="duty-card">
        <div className="duty-card__date">
          <strong>30</strong>
          <span>
            AUG
            <br />
            2026
          </span>
        </div>
        <div>
          <Badge tone="success">Confirmed</Badge>
          <h2>Sunday Worship Service</h2>
          <p>
            <Clock3 /> Call time 7:45 AM · Service 9:00 AM
          </p>
          <p>
            <MapPin /> Media control room · Camera position 2
          </p>
        </div>
        <Link className="button button--primary" to="/app/workers">
          View duty brief
        </Link>
      </section>
      <div className="metric-grid metric-grid--three">
        <article className="metric-card">
          <small>Services completed</small>
          <strong>18</strong>
          <p>This academic session</p>
        </article>
        <article className="metric-card">
          <small>Attendance</small>
          <strong>94%</strong>
          <p>Worker service attendance</p>
        </article>
        <article className="metric-card">
          <small>Open requests</small>
          <strong>1</strong>
          <p>Leave request awaiting review</p>
        </article>
      </div>
      <section className="panel">
        <PanelHeading
          title="September roster"
          subtitle="Your upcoming assignments"
        />
        <div className="timeline">
          <article>
            <span />
            <time>6 Sep</time>
            <div>
              <strong>Freshers Welcome Service</strong>
              <p>Camera position 2 · 7:45 AM</p>
            </div>
            <Badge tone="success">Confirmed</Badge>
          </article>
          <article>
            <span />
            <time>18 Sep</time>
            <div>
              <strong>Evening of Worship</strong>
              <p>Livestream support · 3:30 PM</p>
            </div>
            <Badge tone="warning">Acknowledge</Badge>
          </article>
        </div>
      </section>
    </>
  );
}

function PanelHeading({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="panel-heading">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}
function ActionItem({
  tone,
  icon,
  title,
  text,
}: {
  tone: string;
  icon: React.ReactNode;
  title: string;
  text: string;
}) {
  return (
    <article className="action-item">
      <span className={`action-item__icon action-item__icon--${tone}`}>
        {icon}
      </span>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
      <ArrowRight />
    </article>
  );
}

export function MembersPage() {
  return isDemoMode ? <DemoMembersPage /> : <LiveMembersPage />;
}

function DemoMembersPage() {
  const { user } = useAuth();
  const canWrite = hasPermission(user, "members:write");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<Member | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const toast = useToast();
  const filtered = useMemo(
    () =>
      members.filter(
        (member) =>
          (member.name.toLowerCase().includes(query.toLowerCase()) ||
            member.identifier.toLowerCase().includes(query.toLowerCase()) ||
            member.programme.toLowerCase().includes(query.toLowerCase())) &&
          (status === "all" || member.status === status),
      ),
    [query, status],
  );
  return (
    <>
      <PageHeader
        eyebrow="Membership"
        title="Member directory"
        description="Find, support, and manage members across the active branch."
        actions={
          <>
            <Button
              variant="secondary"
              icon={<Download />}
              disabled={!filtered.length}
              onClick={() =>
                downloadCsv(
                  "chapelflow-members-preview.csv",
                  filtered as unknown as Record<string, unknown>[],
                )
              }
            >
              Export
            </Button>
            {canWrite && (
              <Button icon={<Plus />} onClick={() => setInviteOpen(true)}>
                Add member
              </Button>
            )}
          </>
        }
      />
      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={setQuery}
          placeholder="Search name, matric number, or programme"
        />
        <label>
          <ListFilter />
          <span className="sr-only">Filter member status</span>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="follow_up">Follow-up</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <span>{filtered.length} members</span>
      </div>
      <section className="table-panel">
        <table>
          <caption className="sr-only">
            Members in the active chapel branch
          </caption>
          <thead>
            <tr>
              <th>
                <input type="checkbox" aria-label="Select all members" />
              </th>
              <th>Member</th>
              <th>Programme</th>
              <th>Team</th>
              <th>Status</th>
              <th>Attendance</th>
              <th>Last seen</th>
              <th>
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((member) => (
              <tr key={member.id} onClick={() => setSelected(member)}>
                <td onClick={(event) => event.stopPropagation()}>
                  <input type="checkbox" aria-label={`Select ${member.name}`} />
                </td>
                <td>
                  <span className="table-avatar">
                    {member.name
                      .split(" ")
                      .map((part) => part[0])
                      .join("")}
                  </span>
                  <span>
                    <strong>{member.name}</strong>
                    <small>{member.identifier}</small>
                  </span>
                </td>
                <td>
                  <strong>{member.programme}</strong>
                  <small>Level {member.level}</small>
                </td>
                <td>{member.department}</td>
                <td>
                  <Badge
                    tone={
                      member.status === "active"
                        ? "success"
                        : member.status === "follow_up"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {member.status.replace("_", " ")}
                  </Badge>
                </td>
                <td>
                  <span className="progress-cell">
                    <i>
                      <b style={{ width: `${member.attendanceRate}%` }} />
                    </i>
                    {member.attendanceRate}%
                  </span>
                </td>
                <td>
                  {format(
                    new Date(`${member.lastSeen}T12:00:00`),
                    "d MMM yyyy",
                  )}
                </td>
                <td>
                  <button
                    className="icon-button"
                    aria-label={`Actions for ${member.name}`}
                    onClick={() => setSelected(member)}
                  >
                    <MoreHorizontal />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <EmptyState
            icon={<Search />}
            title="No members match these filters"
            description="Try a different search term or clear the current filters."
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  setQuery("");
                  setStatus("all");
                }}
              >
                Clear filters
              </Button>
            }
          />
        )}
      </section>
      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.name || "Member"}
        description={selected?.identifier}
      >
        <div className="profile-summary">
          <span className="profile-summary__avatar">
            {selected?.name
              .split(" ")
              .map((part) => part[0])
              .join("")}
          </span>
          <div>
            <Badge tone={selected?.status === "active" ? "success" : "warning"}>
              {selected?.status.replace("_", " ")}
            </Badge>
            <p>{selected?.email}</p>
            <p>
              {selected?.programme} · Level {selected?.level}
            </p>
          </div>
        </div>
        <div className="detail-grid">
          <div>
            <small>Attendance rate</small>
            <strong>{selected?.attendanceRate}%</strong>
          </div>
          <div>
            <small>Service team</small>
            <strong>{selected?.department}</strong>
          </div>
          <div>
            <small>Last attendance</small>
            <strong>{selected?.lastSeen}</strong>
          </div>
          <div>
            <small>Branch</small>
            <strong>Abeokuta Main</strong>
          </div>
        </div>
      </Modal>
      <Modal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        title="Add a member"
        description="Create an invitation without assigning elevated permissions."
        footer={
          <>
            <Button variant="ghost" onClick={() => setInviteOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                setInviteOpen(false);
                toast("Invitation prepared successfully.");
              }}
            >
              Send invitation
            </Button>
          </>
        }
      >
        <div className="form-grid">
          <Field label="Full name" required />
          <Field label="Email address" type="email" required />
          <Field label="Matric number or staff ID" required />
          <label className="field">
            <span>Member type</span>
            <select>
              <option>Student</option>
              <option>Staff</option>
              <option>Community member</option>
            </select>
          </label>
        </div>
      </Modal>
    </>
  );
}

export function AttendancePage() {
  return isDemoMode ? <DemoAttendancePage /> : <LiveAttendancePage />;
}

function DemoAttendancePage() {
  const { user } = useAuth();
  const canManage = hasPermission(user, "attendance:write");
  const [scanner, setScanner] = useState(false);
  const [scanState, setScanState] = useState<"ready" | "success" | "duplicate">(
    "ready",
  );
  const [sessionOpen, setSessionOpen] = useState(false);
  const toast = useToast();
  return (
    <>
      <PageHeader
        eyebrow="Attendance"
        title="Sunday Worship Service"
        description="Live attendance · Sunday, 30 August 2026 · University Chapel"
        actions={
          canManage ? (
            <Button icon={<QrCode />} onClick={() => setScanner(true)}>
              Open scanner
            </Button>
          ) : (
            <Button icon={<QrCode />} onClick={() => setScanner(true)}>
              Check in
            </Button>
          )
        }
      />
      <div className="attendance-livebar">
        <div>
          <span className="live-pulse" />
          <div>
            <strong>Check-in is open</strong>
            <small>Opened 8:15 AM · Closes 10:15 AM</small>
          </div>
        </div>
        <div>
          <strong>842</strong>
          <small>Total present</small>
        </div>
        <div>
          <strong>64</strong>
          <small>Checked in late</small>
        </div>
        <div>
          <strong>12</strong>
          <small>Manual entries</small>
        </div>
        <Button
          variant="ghost"
          icon={<RefreshCw />}
          onClick={() => toast("Attendance preview refreshed.")}
        >
          Refresh
        </Button>
      </div>
      <div className="attendance-layout">
        <section className="panel panel--wide">
          <PanelHeading
            title="Attendance by time"
            subtitle="Live check-ins at five-minute intervals"
            action={
              <Badge tone="success">
                <Wifi size={12} /> Live
              </Badge>
            }
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  { t: "8:15", v: 12 },
                  { t: "8:30", v: 45 },
                  { t: "8:45", v: 124 },
                  { t: "9:00", v: 256 },
                  { t: "9:15", v: 181 },
                  { t: "9:30", v: 126 },
                  { t: "9:45", v: 72 },
                  { t: "10:00", v: 26 },
                ]}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="var(--border)"
                />
                <XAxis dataKey="t" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} />
                <Tooltip />
                <Bar
                  dataKey="v"
                  fill="var(--purple-500)"
                  radius={[5, 5, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel">
          <PanelHeading title="Check-in methods" subtitle="Current session" />
          <div className="method-chart">
            <ResponsiveContainer width="45%" height={180}>
              <PieChart>
                <Pie
                  data={[
                    { name: "QR scan", value: 68 },
                    { name: "Kiosk", value: 25 },
                    { name: "Manual", value: 7 },
                  ]}
                  dataKey="value"
                  innerRadius={52}
                  outerRadius={76}
                  paddingAngle={3}
                >
                  {["#6d3fa0", "#b996d9", "#d7a72d"].map((color) => (
                    <Cell key={color} fill={color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div>
              <p>
                <span className="legend-dot legend-dot--purple" /> QR scan{" "}
                <strong>68%</strong>
              </p>
              <p>
                <span className="legend-dot legend-dot--lavender" /> Kiosk{" "}
                <strong>25%</strong>
              </p>
              <p>
                <span className="legend-dot legend-dot--gold" /> Manual{" "}
                <strong>7%</strong>
              </p>
            </div>
          </div>
        </section>
      </div>
      <section className="table-panel attendance-table">
        <header>
          <PanelHeading
            title="Recent check-ins"
            subtitle="Personally identifying details are minimized after verification."
            action={
              canManage && (
                <Button
                  variant="secondary"
                  icon={<Plus />}
                  onClick={() => setSessionOpen(true)}
                >
                  Manual entry
                </Button>
              )
            }
          />
        </header>
        <table>
          <thead>
            <tr>
              <th>Member</th>
              <th>Check-in time</th>
              <th>Method</th>
              <th>Result</th>
              <th>Reference</th>
            </tr>
          </thead>
          <tbody>
            {recentAttendance.map((record) => (
              <tr key={record.id}>
                <td>
                  <span className="table-avatar">
                    {record.memberName
                      .split(" ")
                      .map((part) => part[0])
                      .join("")}
                  </span>
                  <span>
                    <strong>{record.memberName}</strong>
                    <small>{record.identifier}</small>
                  </span>
                </td>
                <td>{record.time}</td>
                <td>{record.method.toUpperCase()}</td>
                <td>
                  <Badge
                    tone={record.status === "duplicate" ? "warning" : "success"}
                  >
                    {record.status}
                  </Badge>
                </td>
                <td>ATT-260830-{record.id.toUpperCase()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <Modal
        open={sessionOpen}
        onClose={() => setSessionOpen(false)}
        title="Manual attendance entry"
        description="A reason is required and the action will be recorded in the audit log."
        footer={
          <>
            <Button variant="ghost" onClick={() => setSessionOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                setSessionOpen(false);
                toast("Attendance entry recorded with an audit reference.");
              }}
            >
              Record attendance
            </Button>
          </>
        }
      >
        <div className="form-grid">
          <Field label="Matric number or member ID" required />
          <Field label="Check-in time" type="time" required />
          <label className="field field--full">
            <span>
              Reason <em>Required</em>
            </span>
            <textarea
              required
              placeholder="Explain why a manual entry is needed"
            />
          </label>
        </div>
      </Modal>
      <ScannerModal
        open={scanner}
        state={scanState}
        onState={setScanState}
        onClose={() => {
          setScanner(false);
          setScanState("ready");
        }}
      />
    </>
  );
}

function ScannerModal({
  open,
  state,
  onState,
  onClose,
}: {
  open: boolean;
  state: "ready" | "success" | "duplicate";
  onState: (state: "ready" | "success" | "duplicate") => void;
  onClose: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Attendance scanner"
      description="Camera details are processed only for check-in and are not retained."
    >
      <div className={`scanner scanner--${state}`}>
        <div className="scanner__viewport">
          {state === "ready" ? (
            <>
              <Camera />
              <span className="scan-frame">
                <i />
                <i />
                <i />
                <i />
              </span>
              <p>Position the QR code inside the frame</p>
            </>
          ) : state === "success" ? (
            <>
              <CheckCircle2 />
              <h3>Check-in confirmed</h3>
              <p>Temiloluwa Akin · 09:06</p>
            </>
          ) : (
            <>
              <AlertTriangle />
              <h3>Already checked in</h3>
              <p>This code was accepted at 09:06.</p>
            </>
          )}
        </div>
        <div className="scanner__status">
          <span>
            <Wifi /> Connected
          </span>
          <span>
            <Camera /> Front camera
          </span>
          <strong>842 checked in</strong>
        </div>
        <div className="scanner__actions">
          <Button variant="secondary" onClick={() => onState("duplicate")}>
            Test duplicate
          </Button>
          <Button
            onClick={() => onState(state === "ready" ? "success" : "ready")}
          >
            {state === "ready" ? "Simulate valid scan" : "Scan next person"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export function EventsPage() {
  return isDemoMode ? <DemoEventsPage /> : <LiveEventsPage />;
}

function DemoEventsPage() {
  const { user } = useAuth();
  const canWrite = hasPermission(user, "events:write");
  const [view, setView] = useState<"list" | "calendar">("list");
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<
    (typeof events)[number] | null
  >(null);
  const toast = useToast();
  return (
    <>
      <PageHeader
        eyebrow="Events"
        title="Events and registrations"
        description="Plan chapel gatherings, manage capacity, and track participation."
        actions={
          canWrite && (
            <Button icon={<Plus />} onClick={() => setCreateOpen(true)}>
              Create event
            </Button>
          )
        }
      />
      <div className="filter-bar">
        <SearchField
          value=""
          onChange={() => undefined}
          placeholder="Search events"
        />
        <label>
          <Filter />
          <select aria-label="Filter event visibility">
            <option>All visibility</option>
            <option>Public</option>
            <option>Private</option>
          </select>
        </label>
        <div className="view-toggle">
          <button
            className={view === "list" ? "active" : ""}
            onClick={() => setView("list")}
          >
            List
          </button>
          <button
            className={view === "calendar" ? "active" : ""}
            onClick={() => setView("calendar")}
          >
            Calendar
          </button>
        </div>
      </div>
      {view === "list" ? (
        <div className="event-cards">
          {events.map((event) => (
            <article key={event.id}>
              <div className="event-card__date">
                <strong>
                  {format(new Date(`${event.date}T12:00:00`), "dd")}
                </strong>
                <span>{format(new Date(`${event.date}T12:00:00`), "MMM")}</span>
              </div>
              <div className="event-card__body">
                <div>
                  <Badge
                    tone={event.visibility === "public" ? "success" : "neutral"}
                  >
                    {event.visibility}
                  </Badge>
                  <h2>{event.title}</h2>
                  <p>
                    <Clock3 />{" "}
                    {format(new Date(`${event.date}T12:00:00`), "EEEE, d MMMM")}{" "}
                    · {event.time}
                  </p>
                  <p>
                    <MapPin /> {event.venue}
                  </p>
                </div>
                <div className="event-card__registration">
                  <small>Registration</small>
                  <strong>
                    {event.registered} / {event.capacity}
                  </strong>
                  <span>
                    <i
                      style={{
                        width: `${(event.registered / event.capacity) * 100}%`,
                      }}
                    />
                  </span>
                </div>
                <Button
                  variant="secondary"
                  onClick={() => setSelectedEvent(event)}
                >
                  Manage event
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <CalendarView />
      )}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create event"
        description="Set the essentials now; registration and reminders can be configured next."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Save draft
            </Button>
            <Button
              onClick={() => {
                setCreateOpen(false);
                toast("Event created successfully.");
              }}
            >
              Create event
            </Button>
          </>
        }
      >
        <div className="form-grid">
          <Field className="field--full" label="Event title" required />
          <Field label="Date" type="date" required />
          <Field label="Start time" type="time" required />
          <Field label="Venue" required />
          <Field label="Registration capacity" type="number" />
          <label className="field">
            <span>Visibility</span>
            <select>
              <option>Public</option>
              <option>Members only</option>
              <option>Workers only</option>
            </select>
          </label>
        </div>
      </Modal>
      <Modal
        open={Boolean(selectedEvent)}
        onClose={() => setSelectedEvent(null)}
        title={selectedEvent?.title || "Event"}
        description="Preview event details and registration capacity."
        footer={
          <Button variant="secondary" onClick={() => setSelectedEvent(null)}>
            Close
          </Button>
        }
      >
        <div className="detail-grid">
          <div>
            <small>Date</small>
            <strong>{selectedEvent?.date}</strong>
          </div>
          <div>
            <small>Time</small>
            <strong>{selectedEvent?.time}</strong>
          </div>
          <div>
            <small>Venue</small>
            <strong>{selectedEvent?.venue}</strong>
          </div>
          <div>
            <small>Registration</small>
            <strong>
              {selectedEvent?.registered} / {selectedEvent?.capacity}
            </strong>
          </div>
        </div>
      </Modal>
    </>
  );
}

function CalendarView() {
  const days = Array.from({ length: 35 }, (_, index) => index - 1);
  return (
    <section className="calendar-panel">
      <header>
        <h2>September 2026</h2>
      </header>
      <div className="calendar-weekdays">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div className="calendar-grid">
        {days.map((day, index) => (
          <div className={day < 1 || day > 30 ? "muted" : ""} key={index}>
            <span>{day < 1 ? 31 : day > 30 ? day - 30 : day}</span>
            {day === 6 && <small>Freshers Welcome</small>}
            {day === 12 && <small>Workers Retreat</small>}
            {day === 18 && <small>Evening of Worship</small>}
          </div>
        ))}
      </div>
    </section>
  );
}

const moduleConfigs = {
  workers: {
    eyebrow: "Workers and volunteers",
    title: "People serving with purpose",
    description:
      "Coordinate teams, availability, duty rosters, and development.",
    button: "Create roster",
    icon: <UserCheck />,
    metrics: [
      ["Active workers", "286", "Across 8 service teams"],
      ["Coverage", "94%", "For next Sunday"],
      ["Leave requests", "6", "2 require a decision"],
    ],
    rows: [
      ["Media & Production", "42 workers", "98% covered", "1 open"],
      ["Choir & Worship", "68 workers", "94% covered", "3 open"],
      ["Ushering", "54 workers", "96% covered", "2 open"],
      ["Prayer & Care", "37 workers", "100% covered", "Fully staffed"],
    ],
  },
  finance: {
    eyebrow: "Finance and giving",
    title: "Financial overview",
    description:
      "Privacy-conscious giving, reconciliation, expenses, and reporting.",
    button: "Record transaction",
    icon: <Coins />,
    metrics: [
      ["Income this month", "₦4.82m", "Offerings and designated gifts"],
      ["Expenses", "₦1.46m", "Within approved budget"],
      ["Reconciliation", "96%", "12 records pending"],
    ],
    rows: [
      ["Sunday offering", "24 Aug 2026", "₦842,500", "Reconciled"],
      ["Student support fund", "22 Aug 2026", "₦185,000", "Pending"],
      ["Media equipment service", "19 Aug 2026", "−₦96,000", "Approved"],
      ["Community outreach", "17 Aug 2026", "−₦142,500", "Approved"],
    ],
  },
  communication: {
    eyebrow: "Communication centre",
    title: "Reach the right people clearly",
    description:
      "Draft, approve, schedule, and review targeted chapel communications.",
    button: "Create broadcast",
    icon: <Send />,
    metrics: [
      ["Sent this month", "18,420", "Across all channels"],
      ["Delivery rate", "96.8%", "Email, SMS, and push"],
      ["Scheduled", "4", "Next 7 days"],
    ],
    rows: [
      [
        "Freshers Welcome reminder",
        "Email + Push",
        "2,184 recipients",
        "Scheduled",
      ],
      ["Worker roster update", "Email", "286 recipients", "Delivered"],
      ["Sunday service notice", "SMS + Push", "2,418 recipients", "Delivered"],
      ["Choir rehearsal change", "Push", "68 recipients", "Draft"],
    ],
  },
  assets: {
    eyebrow: "Assets and inventory",
    title: "Asset register",
    description: "Track chapel equipment, custody, stock, and maintenance.",
    button: "Add asset",
    icon: <Package />,
    metrics: [
      ["Registered assets", "328", "Across 6 locations"],
      ["Maintenance due", "8", "Within 30 days"],
      ["Low stock", "5", "Consumable items"],
    ],
    rows: [
      [
        "Sony PXW-Z190 camera",
        "Media control room",
        "In service",
        "Due 14 Sep",
      ],
      ["Yamaha TF3 console", "Main auditorium", "In service", "Due 30 Oct"],
      ["Wireless microphone set", "Equipment store", "Maintenance", "Overdue"],
      ["Communion supplies", "Main store", "Low stock", "12 units"],
    ],
  },
  media: {
    eyebrow: "Sermons and media",
    title: "Media library",
    description:
      "Manage sermons, series, livestreams, and accessible resources.",
    button: "Upload media",
    icon: <Video />,
    metrics: [
      ["Published items", "146", "Audio, video, and documents"],
      ["Plays this month", "8,920", "12% increase"],
      ["Drafts", "7", "3 awaiting captions"],
    ],
    rows: [
      [
        "Steady faith in changing seasons",
        "Pastor Daniel Eze",
        "23 Aug 2026",
        "Published",
      ],
      [
        "Wisdom for the road ahead",
        "Rev. Ada Okoro",
        "16 Aug 2026",
        "Published",
      ],
      ["The courage to serve", "Pastor Daniel Eze", "9 Aug 2026", "Published"],
      [
        "Formed for community",
        "Dr. Tola Adebayo",
        "Scheduled",
        "Needs captions",
      ],
    ],
  },
  cms: {
    eyebrow: "Website CMS",
    title: "Website content",
    description:
      "Keep public chapel information accurate, timely, and accessible.",
    button: "New content",
    icon: <FileText />,
    metrics: [
      ["Published pages", "18", "All public routes healthy"],
      ["Draft changes", "5", "Awaiting review"],
      ["Scheduled", "3", "Next 14 days"],
    ],
    rows: [
      ["Homepage", "Grace Adeyemi", "Today, 8:42 AM", "Published"],
      ["About the Chapel", "Tola Adebayo", "24 Aug 2026", "Published"],
      ["Freshers Welcome article", "Moyo Bello", "26 Aug 2026", "Draft"],
      [
        "September service times",
        "Grace Adeyemi",
        "Publishes 1 Sep",
        "Scheduled",
      ],
    ],
  },
  branches: {
    eyebrow: "Headquarters oversight",
    title: "Chapel branches",
    description:
      "Compare branch health and keep local administration clearly scoped.",
    button: "Add branch",
    icon: <Building2 />,
    metrics: [
      ["Active branches", "2", "Across Chrisland University"],
      ["Total members", "2,684", "42 joined this semester"],
      ["Services this month", "12", "Across all branches"],
    ],
    rows: [
      [
        "Abeokuta Main Chapel",
        "2,418 members",
        "842 last attendance",
        "Healthy",
      ],
      ["Lagos Liaison Chapel", "266 members", "184 last attendance", "Healthy"],
    ],
  },
  audit: {
    eyebrow: "Security and accountability",
    title: "Audit log",
    description:
      "Review authorized administrative actions and sensitive record changes.",
    button: "Export log",
    icon: <ShieldCheck />,
    metrics: [
      ["Events today", "184", "Across 9 modules"],
      ["Sensitive changes", "12", "All have reasons"],
      ["Security alerts", "0", "No action required"],
    ],
    rows: [
      [
        "Grace Adeyemi",
        "Corrected attendance record",
        "Attendance",
        "Today, 9:16 AM",
      ],
      [
        "Tola Adebayo",
        "Approved worker access",
        "Permissions",
        "Today, 8:58 AM",
      ],
      ["System", "Published scheduled event", "CMS", "Today, 8:00 AM"],
      [
        "Moyo Bello",
        "Updated duty availability",
        "Workers",
        "Yesterday, 6:42 PM",
      ],
    ],
  },
  settings: {
    eyebrow: "Account and institution",
    title: "Settings",
    description:
      "Manage profile, notifications, privacy, sessions, and chapel preferences.",
    button: "Save changes",
    icon: <ShieldCheck />,
    metrics: [
      ["Profile completion", "92%", "One item remaining"],
      ["Active sessions", "2", "Windows and Android"],
      ["Policy status", "Accepted", "Version 2.1"],
    ],
    rows: [
      [
        "Profile and identity",
        "Name, contact, and chapel profile",
        "Complete",
        "Open",
      ],
      [
        "Notification preferences",
        "Email, SMS, and push channels",
        "Configured",
        "Open",
      ],
      [
        "Privacy and data requests",
        "Consent, export, and account requests",
        "Available",
        "Open",
      ],
      [
        "Security and sessions",
        "Password, recent logins, active devices",
        "Review recommended",
        "Open",
      ],
    ],
  },
} as const;

export function OperationsPage({
  module,
}: {
  module: keyof typeof moduleConfigs;
}) {
  return isDemoMode ? (
    <DemoOperationsPage module={module} />
  ) : (
    <LiveOperationsPage module={module} />
  );
}

function DemoOperationsPage({
  module,
}: {
  module: keyof typeof moduleConfigs;
}) {
  const { user } = useAuth();
  const config = moduleConfigs[module];
  const writePermissions: Partial<
    Record<keyof typeof moduleConfigs, Permission>
  > = {
    workers: "workers:write",
    finance: "finance:write",
    communication: "communication:write",
    assets: "assets:write",
    media: "media:write",
    cms: "cms:write",
    branches: "branches:manage",
  };
  const canCreate =
    module === "settings" || hasPermission(user, writePermissions[module]);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<{
    first: string;
    second: string;
    third: string;
    fourth: string;
  } | null>(null);
  const exportRows = config.rows.map(([first, second, third, fourth]) => ({
    primary: first,
    secondary: second,
    detail: third,
    status: fourth,
  }));
  const visibleRows = config.rows.filter(
    ([first, second, , fourth], index) =>
      `${first} ${second}`.toLowerCase().includes(search.toLowerCase()) &&
      (!statusFilter ||
        (statusFilter === "attention" &&
          /Pending|Draft|Due|Needs|Overdue|Low/i.test(fourth)) ||
        (statusFilter === "recent" && index < 2)),
  );
  return (
    <>
      <PageHeader
        eyebrow={config.eyebrow}
        title={config.title}
        description={config.description}
        actions={
          module === "audit" || canCreate ? (
            <Button
              icon={module === "audit" ? <Download /> : <Plus />}
              onClick={() =>
                module === "audit"
                  ? downloadCsv("chapelflow-audit-preview.csv", exportRows)
                  : setOpen(true)
              }
            >
              {config.button}
            </Button>
          ) : undefined
        }
      />
      <div className="metric-grid metric-grid--three">
        {config.metrics.map(([label, value, note]) => (
          <article className="metric-card" key={label}>
            <small>{label}</small>
            <strong>{value}</strong>
            <p>{note}</p>
          </article>
        ))}
      </div>
      <div className="filter-bar">
        <SearchField
          value={search}
          onChange={setSearch}
          placeholder={`Search ${config.title.toLowerCase()}`}
        />
        <label>
          <Filter />
          <select
            aria-label="Filter records"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All records</option>
            <option value="attention">Needs attention</option>
            <option value="recent">Recently updated</option>
          </select>
        </label>
        <Button
          variant="ghost"
          icon={<Download />}
          disabled={!visibleRows.length}
          onClick={() =>
            downloadCsv("chapelflow-records-preview.csv", exportRows)
          }
        >
          Export
        </Button>
      </div>
      <section className="module-list">
        <header>
          <span>{config.icon}</span>
          <div>
            <h2>Recent activity</h2>
            <p>Showing the most relevant records for the active branch.</p>
          </div>
        </header>
        {visibleRows.map(([first, second, third, fourth]) => (
          <article key={first}>
            <span className="module-row__icon">{config.icon}</span>
            <div>
              <strong>{first}</strong>
              <small>{second}</small>
            </div>
            <div>
              <strong>{third}</strong>
              <small>
                {module === "finance" ? "Amount" : "Current detail"}
              </small>
            </div>
            <Badge
              tone={
                String(fourth).match(
                  /Healthy|Published|Approved|Reconciled|Complete|Open|staffed/i,
                )
                  ? "success"
                  : String(fourth).match(/Pending|Draft|Due|Needs|Overdue|Low/i)
                    ? "warning"
                    : "neutral"
              }
            >
              {fourth}
            </Badge>
            <button
              className="icon-button"
              aria-label={`Actions for ${first}`}
              onClick={() => setSelected({ first, second, third, fourth })}
            >
              <MoreHorizontal />
            </button>
          </article>
        ))}
      </section>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={config.button}
        description="This workflow is permission-checked and will be recorded where auditability is required."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setOpen(false)}>Close preview</Button>
          </>
        }
      >
        <div className="workflow-placeholder">
          <span>{config.icon}</span>
          <h3>Ready for backend connection</h3>
          <p>
            The production form is isolated behind the typed API service.
            Configure the required endpoint to enable submission without
            changing this interface.
          </p>
        </div>
      </Modal>
      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.first || "Record"}
        description={selected?.second}
        footer={
          <Button variant="secondary" onClick={() => setSelected(null)}>
            Close
          </Button>
        }
      >
        <div className="detail-grid">
          <div>
            <small>Current detail</small>
            <strong>{selected?.third}</strong>
          </div>
          <div>
            <small>Status</small>
            <strong>{selected?.fourth}</strong>
          </div>
        </div>
      </Modal>
    </>
  );
}

export function AnalyticsPage() {
  return isDemoMode ? <DemoAnalyticsPage /> : <LiveAnalyticsPage />;
}

function DemoAnalyticsPage() {
  const toast = useToast();
  const attendanceByLevel = [
    { name: "100", value: 89 },
    { name: "200", value: 82 },
    { name: "300", value: 78 },
    { name: "400", value: 71 },
    { name: "500", value: 68 },
  ];
  return (
    <>
      <PageHeader
        eyebrow="Analytics and reports"
        title="Chapel insights"
        description="Decision support across attendance, engagement, workers, and programmes."
        actions={
          <Button
            variant="secondary"
            icon={<Download />}
            onClick={() =>
              downloadCsv("chapelflow-analytics-preview.csv", attendanceByLevel)
            }
          >
            Export report
          </Button>
        }
      />
      <div className="report-toolbar">
        <label>
          <CalendarDays />
          <span>Date range</span>
          <select>
            <option>This semester</option>
            <option>Last semester</option>
            <option>Custom range</option>
          </select>
        </label>
        <label>
          <Building2 />
          <span>Branch</span>
          <select>
            <option>Abeokuta Main Chapel</option>
            <option>All branches</option>
          </select>
        </label>
        <Button onClick={() => toast("Report filters applied.")}>
          Apply filters
        </Button>
      </div>
      <div className="metric-grid">
        <article className="metric-card">
          <small>Average attendance</small>
          <strong>792</strong>
          <p>
            <ArrowUpRight /> 8.4% vs last semester
          </p>
        </article>
        <article className="metric-card">
          <small>Member consistency</small>
          <strong>76%</strong>
          <p>Attended at least 3 of 4 services</p>
        </article>
        <article className="metric-card">
          <small>First-time attendees</small>
          <strong>184</strong>
          <p>Across the selected period</p>
        </article>
        <article className="metric-card">
          <small>Worker participation</small>
          <strong>91%</strong>
          <p>Accepted assigned duties</p>
        </article>
      </div>
      <div className="analytics-grid">
        <section className="panel panel--wide">
          <PanelHeading
            title="Attendance over time"
            subtitle="Selected semester compared with previous period"
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={attendanceTrend}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="var(--border)"
                />
                <XAxis dataKey="week" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="attendance"
                  stroke="#6d3fa0"
                  fill="#6d3fa022"
                  strokeWidth={3}
                />
                <Line type="monotone" dataKey="attendance" stroke="#d7a72d" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="chart-summary">
            <BarChart3 /> Attendance rose from 718 to 842 over the seven-week
            period, with one short decline in early August.
          </p>
        </section>
        <section className="panel">
          <PanelHeading
            title="Attendance by level"
            subtitle="Share attending this month"
          />
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={attendanceByLevel}>
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip />
                <Bar
                  dataKey="value"
                  fill="var(--purple-500)"
                  radius={[0, 5, 5, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
      <div className="insight-note">
        <AlertTriangle />
        <div>
          <strong>Decision-support indicator</strong>
          <p>
            Thirty-one members have attended fewer than two services this month.
            This pattern may justify a considerate follow-up; it does not
            determine personal commitment or wellbeing.
          </p>
        </div>
        <Link className="button button--secondary" to="/app/members">
          Review cohort
        </Link>
      </div>
    </>
  );
}
