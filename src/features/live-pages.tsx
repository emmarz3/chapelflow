import {
  AlertTriangle,
  BarChart3,
  CalendarDays,
  ClipboardCheck,
  Download,
  FileText,
  Filter,
  ListFilter,
  LockKeyhole,
  MoreHorizontal,
  Plus,
  QrCode,
  Send,
  ShieldCheck,
  UserCheck,
  Users,
  WifiOff,
  XCircle,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  PageHeader,
  SearchField,
  useToast,
} from "../components/ui";
import { ApiError } from "../lib/api";
import { downloadCsv } from "../lib/export";
import {
  ATTENDANCE_QUEUE_EVENT,
  readPendingAttendance,
} from "../lib/offline-queue";
import {
  analyticsService,
  attendanceService,
  authService,
  dashboardService,
  eventService,
  memberService,
  operationsService,
  privacyService,
  communityService,
  queryKeys,
  type ListRow,
  type OperationsModule,
} from "../services/chapelflow";
import type {
  AttendanceRecord,
  EventSummary,
  Member,
  Permission,
} from "../types/domain";
import { hasPermission, useAuth } from "./auth-context";

function message(error: unknown) {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : "The request could not be completed.";
}

export function LiveDashboardPage() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.dashboard(user?.branchId || ""),
    queryFn: async () =>
      (await dashboardService.get(user?.branchId || "")).data,
    enabled: Boolean(user),
  });
  const communities = useQuery({
    queryKey: queryKeys.communities(),
    queryFn: async () => (await communityService.mine()).data,
    enabled: Boolean(user?.permissions.includes("community:view")),
  });
  if (query.isPending) return <LoadingState label="Loading dashboard" />;
  if (query.isError)
    return (
      <ErrorState
        description={message(query.error)}
        onRetry={() => void query.refetch()}
      />
    );
  const data = query.data;
  return (
    <>
      <PageHeader
        eyebrow={user?.branchName}
        title={`Welcome back, ${user?.name.split(" ")[0] || "member"}.`}
        description="Live information from your authorized chapel workspace."
      />
      <div className="metric-grid">
        {data.metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <small>{metric.label}</small>
            <strong>{metric.value}</strong>
            <p className={metric.trend === "down" ? "trend--warning" : ""}>
              {metric.change}
            </p>
          </article>
        ))}
      </div>
      {communities.data && communities.data.length > 0 && (
        <section className="panel dashboard-community-preview">
          <header className="panel-heading">
            <div>
              <h2>My communities</h2>
              <p>Private updates from your unit and fellowship</p>
            </div>
            <Link className="text-link" to="/app/communities">
              View all communities
            </Link>
          </header>
          <div>
            {communities.data.slice(0, 3).map((community) => (
              <Link
                key={community.id}
                to={`/app/communities/${community.slug}`}
              >
                <span>{community.type === "unit" ? "Unit" : "Fellowship"}</span>
                <strong>{community.name}</strong>
                <small>{community.unreadCount ?? 0} unread</small>
              </Link>
            ))}
          </div>
        </section>
      )}
      <section className="panel">
        <header className="panel-heading">
          <div>
            <h2>Attendance trend</h2>
            <p>Authorized summary for the active branch</p>
          </div>
        </header>
        {data.attendanceTrend.length ? (
          <>
            <div
              className="chart-wrap"
              role="img"
              aria-label="Attendance trend for the selected reporting period"
            >
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.attendanceTrend}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="var(--border)"
                  />
                  <XAxis dataKey="week" />
                  <YAxis />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="attendance"
                    stroke="var(--purple-500)"
                    fill="var(--purple-100)"
                    strokeWidth={3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="chart-summary">
              <BarChart3 /> The chart is a summary of backend-authorized
              attendance totals and does not expose personal records.
            </p>
          </>
        ) : (
          <EmptyState
            title="No attendance trend yet"
            description="Attendance summaries will appear after sessions are recorded for this reporting period."
          />
        )}
      </section>
    </>
  );
}

export function LiveMembersPage() {
  const { user } = useAuth();
  const canWrite = hasPermission(user, "members:write");
  const [queryText, setQueryText] = useState("");
  const [status, setStatus] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [selected, setSelected] = useState<Member | null>(null);
  const toast = useToast();
  const client = useQueryClient();
  const params = {
    search: queryText,
    status: status === "all" ? undefined : status,
    page: 1,
    pageSize: 50,
  };
  const query = useQuery({
    queryKey: queryKeys.members(params),
    queryFn: () => memberService.list(params),
  });
  const create = useMutation({
    mutationFn: (payload: Partial<Member>) => memberService.create(payload),
    onSuccess: () => {
      setCreateOpen(false);
      toast("Member created successfully.");
      void client.invalidateQueries({ queryKey: ["members"] });
    },
  });
  const approve = useMutation({
    mutationFn: (memberId: string) => memberService.approve(memberId),
    onSuccess: () => {
      setSelected(null);
      toast("Student registration approved. The account can now sign in.");
      void client.invalidateQueries({ queryKey: ["members"] });
    },
  });
  const rows = query.data?.data ?? [];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const name = String(values.get("name"));
    create.mutate({
      name,
      email: String(values.get("email")),
      identifier: String(values.get("identifier")),
      programme: String(values.get("programme") || ""),
      level: String(values.get("level") || ""),
      department: String(values.get("department") || ""),
      status: "active",
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="Membership"
        title="Member directory"
        description="Records are scoped by the backend to your active branch and permissions."
        actions={
          <>
            <Button
              variant="secondary"
              icon={<Download />}
              disabled={!rows.length}
              onClick={() =>
                downloadCsv(
                  "chapelflow-members.csv",
                  rows as unknown as Record<string, unknown>[],
                )
              }
            >
              Export
            </Button>
            {canWrite && (
              <Button icon={<Plus />} onClick={() => setCreateOpen(true)}>
                Add member
              </Button>
            )}
          </>
        }
      />
      <div className="filter-bar">
        <SearchField
          value={queryText}
          onChange={setQueryText}
          placeholder="Search name, identifier, or programme"
        />
        <label>
          <ListFilter />
          <select
            aria-label="Member status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending approval</option>
            <option value="active">Active</option>
            <option value="follow_up">Follow-up</option>
            <option value="inactive">Inactive</option>
          </select>
        </label>
        <span>{query.data?.total ?? 0} members</span>
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          description={message(query.error)}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <section className="table-panel">
          <table>
            <caption className="sr-only">Members in the active branch</caption>
            <thead>
              <tr>
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
              {rows.map((member) => (
                <tr key={member.id} onClick={() => setSelected(member)}>
                  <td>
                    <span className="table-avatar">
                      {member.name
                        .split(" ")
                        .map((part) => part[0])
                        .join("")
                        .slice(0, 2)}
                    </span>
                    <span>
                      <strong>{member.name}</strong>
                      <small>{member.identifier}</small>
                    </span>
                  </td>
                  <td>
                    <strong>{member.programme}</strong>
                    <small>{member.level && `Level ${member.level}`}</small>
                  </td>
                  <td>{member.department || "Not assigned"}</td>
                  <td>
                    <Badge
                      tone={
                        member.status === "active"
                          ? "success"
                          : member.status === "pending"
                            ? "warning"
                            : member.status === "follow_up"
                              ? "warning"
                              : "neutral"
                      }
                    >
                      {member.status.replace("_", " ")}
                    </Badge>
                  </td>
                  <td>{member.attendanceRate}%</td>
                  <td>{member.lastSeen || "No attendance"}</td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Open ${member.name}`}
                      onClick={() => setSelected(member)}
                    >
                      <MoreHorizontal />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && (
            <EmptyState
              icon={<Users />}
              title="No member records found"
              description="Adjust the filters or add the first authorized member record."
            />
          )}
        </section>
      )}
      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.name || "Member"}
        description={selected?.identifier}
        footer={
          selected?.status === "pending" && canWrite ? (
            <>
              <Button variant="ghost" onClick={() => setSelected(null)}>
                Review later
              </Button>
              <Button
                loading={approve.isPending}
                onClick={() => selected && approve.mutate(selected.id)}
              >
                Approve student account
              </Button>
            </>
          ) : undefined
        }
      >
        <div className="detail-grid">
          <div>
            <small>Email</small>
            <strong>{selected?.email}</strong>
          </div>
          <div>
            <small>Programme</small>
            <strong>{selected?.programme || "Not provided"}</strong>
          </div>
          <div>
            <small>Attendance rate</small>
            <strong>{selected?.attendanceRate}%</strong>
          </div>
          <div>
            <small>Status</small>
            <strong>{selected?.status.replace("_", " ")}</strong>
          </div>
        </div>
        {approve.isError && (
          <div className="form-error" role="alert">
            {message(approve.error)}
          </div>
        )}
      </Modal>
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Add member"
        description="The backend will validate branch scope, duplicates, and allowed fields."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="live-member-form"
              loading={create.isPending}
            >
              Create member
            </Button>
          </>
        }
      >
        <form id="live-member-form" className="form-grid" onSubmit={submit}>
          <Field name="name" label="Full name" required />
          <Field name="email" label="Email address" type="email" required />
          <Field name="identifier" label="Matric number or staff ID" required />
          <Field name="programme" label="Programme" />
          <Field name="level" label="Academic level" />
          <Field name="department" label="Service team" />
          {create.isError && (
            <div className="form-error field--full" role="alert">
              {message(create.error)}
            </div>
          )}
        </form>
      </Modal>
    </>
  );
}

export function LiveAttendancePage() {
  const { user } = useAuth();
  const canManage = hasPermission(user, "attendance:write");
  const [manualOpen, setManualOpen] = useState(false);
  const [sessionOpen, setSessionOpen] = useState(false);
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [correction, setCorrection] = useState<AttendanceRecord | null>(null);
  const [pendingCount, setPendingCount] = useState(
    () => readPendingAttendance().length,
  );
  const toast = useToast();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.attendance("current"),
    queryFn: async () => (await attendanceService.current()).data,
  });
  const scheduled = useQuery({
    queryKey: ["attendance-sessions", "scheduled"],
    queryFn: async () => (await attendanceService.sessions("scheduled")).data,
    enabled: canManage,
  });
  const manual = useMutation({
    mutationFn: ({
      sessionId,
      identifier,
      reason,
    }: {
      sessionId: string;
      identifier: string;
      reason: string;
    }) =>
      attendanceService.manual({
        sessionId,
        identifier,
        reason,
        idempotencyKey: crypto.randomUUID(),
      }),
    onSuccess: () => {
      setManualOpen(false);
      toast("Attendance recorded with an audit reference.");
      void client.invalidateQueries({ queryKey: ["attendance"] });
    },
  });
  const createSession = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      attendanceService.createSession(payload),
    onSuccess: () => {
      setSessionOpen(false);
      toast("Attendance session scheduled. Activate it when check-in opens.");
      void client.invalidateQueries({ queryKey: ["attendance"] });
      void client.invalidateQueries({ queryKey: ["attendance-sessions"] });
    },
  });
  const activateSession = useMutation({
    mutationFn: (sessionId: string) =>
      attendanceService.activateSession(sessionId),
    onSuccess: () => {
      toast(
        "Attendance session activated. Usher scanners can now check in students.",
      );
      void client.invalidateQueries({ queryKey: ["attendance"] });
      void client.invalidateQueries({ queryKey: ["attendance-sessions"] });
    },
  });
  const closeSession = useMutation({
    mutationFn: () => attendanceService.closeSession(query.data!.session.id),
    onSuccess: () => {
      setCloseConfirmOpen(false);
      toast("Attendance session closed. New scans are now blocked.");
      void client.invalidateQueries({ queryKey: ["attendance"] });
      void client.invalidateQueries({ queryKey: ["attendance-sessions"] });
    },
  });
  const qr = useQuery({
    queryKey: ["attendance-qr", query.data?.session.id],
    queryFn: async () =>
      (await attendanceService.qrCode(query.data!.session.id)).data,
    enabled: qrOpen && Boolean(query.data?.session.id),
    refetchInterval: 45_000,
  });
  const correct = useMutation({
    mutationFn: ({
      id,
      status,
      reason,
    }: {
      id: string;
      status: string;
      reason: string;
    }) => attendanceService.correct(id, { status, reason }),
    onSuccess: () => {
      setCorrection(null);
      toast("Attendance correction saved with an audit reference.");
      void client.invalidateQueries({ queryKey: ["attendance"] });
    },
  });
  useEffect(() => {
    const updatePendingCount = () =>
      setPendingCount(readPendingAttendance().length);
    window.addEventListener(ATTENDANCE_QUEUE_EVENT, updatePendingCount);
    return () =>
      window.removeEventListener(ATTENDANCE_QUEUE_EVENT, updatePendingCount);
  }, []);
  if (query.isPending)
    return <LoadingState label="Loading current attendance session" />;
  if (query.isError)
    return (
      <>
        <PageHeader
          eyebrow="Attendance"
          title="Attendance sessions"
          description="Create or open an attendance session for this branch."
          actions={
            canManage && (
              <Button icon={<Plus />} onClick={() => setSessionOpen(true)}>
                Create session
              </Button>
            )
          }
        />
        {query.error instanceof ApiError &&
        query.error.code === "NO_ACTIVE_SESSION" ? (
          <section className="table-panel">
            <header>
              <div className="panel-heading">
                <div>
                  <h2>Scheduled sessions</h2>
                  <p>
                    Activate one service when ushers are ready to begin
                    scanning.
                  </p>
                </div>
              </div>
            </header>
            {scheduled.isPending ? (
              <LoadingState label="Loading scheduled attendance sessions" />
            ) : scheduled.isError ? (
              <ErrorState
                description={message(scheduled.error)}
                onRetry={() => void scheduled.refetch()}
              />
            ) : scheduled.data.length ? (
              <table>
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Date</th>
                    <th>Check-in window</th>
                    <th>
                      <span className="sr-only">Action</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {scheduled.data.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.title}</strong>
                      </td>
                      <td>{new Date(item.date).toLocaleDateString()}</td>
                      <td>
                        {new Date(item.startsAt).toLocaleTimeString()} –{" "}
                        {new Date(item.endsAt).toLocaleTimeString()}
                      </td>
                      <td>
                        <Button
                          loading={
                            activateSession.isPending &&
                            activateSession.variables === item.id
                          }
                          onClick={() => activateSession.mutate(item.id)}
                        >
                          Activate session
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState
                icon={<CalendarDays />}
                title="No scheduled attendance sessions"
                description="Create the next chapel service before check-in begins."
              />
            )}
            {activateSession.isError && (
              <div className="form-error" role="alert">
                {message(activateSession.error)}
              </div>
            )}
          </section>
        ) : (
          <ErrorState
            description={message(query.error)}
            onRetry={() => void query.refetch()}
          />
        )}
        <SessionModal
          open={sessionOpen}
          loading={createSession.isPending}
          error={createSession.error}
          onClose={() => setSessionOpen(false)}
          onSubmit={(payload) => createSession.mutate(payload)}
        />
      </>
    );
  const { session, records } = query.data;
  function manualSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const identifier = String(
      new FormData(event.currentTarget).get("identifier"),
    );
    const reason = String(new FormData(event.currentTarget).get("reason"));
    if (!navigator.onLine) {
      toast("Connection problem — attendance was not recorded.", "error");
      return;
    }
    manual.mutate({ sessionId: session.id, identifier, reason });
  }
  return (
    <>
      <PageHeader
        eyebrow="Attendance"
        title={session.title}
        description={`${session.status} session · ${new Date(session.opensAt).toLocaleString()}`}
        actions={
          <>
            <Button
              variant="secondary"
              icon={<QrCode />}
              onClick={() => setQrOpen(true)}
            >
              Display QR
            </Button>
            {canManage && (
              <>
                <Button icon={<Plus />} onClick={() => setManualOpen(true)}>
                  Manual entry
                </Button>
                <Button
                  variant="danger"
                  icon={<XCircle />}
                  loading={closeSession.isPending}
                  onClick={() => setCloseConfirmOpen(true)}
                >
                  Close session
                </Button>
              </>
            )}
          </>
        }
      />
      <div className="attendance-livebar">
        <div>
          <span className="live-pulse" />
          <div>
            <strong>Check-in is {session.status}</strong>
            <small>
              Closes {new Date(session.closesAt).toLocaleTimeString()}
            </small>
          </div>
        </div>
        <div>
          <strong>{session.count}</strong>
          <small>Total present</small>
        </div>
        <div>
          <strong>{session.lateCount}</strong>
          <small>Late arrivals</small>
        </div>
        <div>
          <strong>{session.manualCount}</strong>
          <small>Manual entries</small>
        </div>
      </div>
      {pendingCount > 0 && (
        <div className="insight-note">
          <WifiOff />
          <div>
            <strong>{pendingCount} pending offline check-ins</strong>
            <p>
              These records remain on this device until a safe backend
              reconciliation succeeds. Duplicate identifiers are blocked
              locally.
            </p>
          </div>
        </div>
      )}
      <section className="table-panel attendance-table">
        <header>
          <div className="panel-heading">
            <div>
              <h2>Recent check-ins</h2>
              <p>Sensitive identification is shown only to authorized roles.</p>
            </div>
          </div>
        </header>
        <table>
          <thead>
            <tr>
              <th>Member</th>
              <th>Time</th>
              <th>Method</th>
              <th>Result</th>
              <th>Reference</th>
              {canManage && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.id}>
                <td>
                  <strong>{record.memberName}</strong>
                  <small>{record.identifier}</small>
                </td>
                <td>{record.time}</td>
                <td>{record.method}</td>
                <td>
                  <Badge
                    tone={record.status === "duplicate" ? "warning" : "success"}
                  >
                    {record.status}
                  </Badge>
                </td>
                <td>{record.id}</td>
                {canManage && (
                  <td>
                    <Button
                      variant="ghost"
                      onClick={() => setCorrection(record)}
                    >
                      Correct
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!records.length && (
          <EmptyState
            icon={<ClipboardCheck />}
            title="No one has checked in yet"
            description="New verified check-ins will appear here while the session is open."
          />
        )}
      </section>
      <Modal
        open={closeConfirmOpen}
        onClose={() => setCloseConfirmOpen(false)}
        title="Close attendance session?"
        description="Existing attendance records remain available, but all usher devices will be blocked from recording new scans."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCloseConfirmOpen(false)}>
              Keep session active
            </Button>
            <Button
              variant="danger"
              loading={closeSession.isPending}
              onClick={() => closeSession.mutate()}
            >
              Close attendance
            </Button>
          </>
        }
      >
        {closeSession.isError && (
          <div className="form-error" role="alert">
            {message(closeSession.error)}
          </div>
        )}
      </Modal>
      <Modal
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        title="Manual attendance entry"
        description="The backend records the actor, time, and reason for audit review."
        footer={
          <>
            <Button variant="ghost" onClick={() => setManualOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="manual-checkin"
              loading={manual.isPending}
            >
              Record check-in
            </Button>
          </>
        }
      >
        <form id="manual-checkin" onSubmit={manualSubmit} className="form-grid">
          <Field
            className="field--full"
            name="identifier"
            label="Member identifier"
            required
          />
          <label className="field field--full">
            <span>
              Reason <em>Required</em>
            </span>
            <textarea name="reason" required />
          </label>
          {manual.isError && (
            <div className="form-error field--full">
              {message(manual.error)}
            </div>
          )}
        </form>
      </Modal>
      <Modal
        open={qrOpen}
        onClose={() => setQrOpen(false)}
        title="Session QR code"
        description="The code is time-limited and refreshes automatically."
      >
        {qr.isPending ? (
          <LoadingState />
        ) : qr.isError ? (
          <ErrorState
            description={message(qr.error)}
            onRetry={() => void qr.refetch()}
          />
        ) : (
          <div className="qr-display">
            <img
              src={qr.data.imageDataUrl}
              alt="Time-limited attendance QR code"
            />
            <strong>{qr.data.reference}</strong>
            <small>
              Expires {new Date(qr.data.expiresAt).toLocaleTimeString()}
            </small>
          </div>
        )}
      </Modal>
      <CorrectionModal
        record={correction}
        loading={correct.isPending}
        error={correct.error}
        onClose={() => setCorrection(null)}
        onSubmit={(status, reason) =>
          correction && correct.mutate({ id: correction.id, status, reason })
        }
      />
      <SessionModal
        open={sessionOpen}
        loading={createSession.isPending}
        error={createSession.error}
        onClose={() => setSessionOpen(false)}
        onSubmit={(payload) => createSession.mutate(payload)}
      />
    </>
  );
}

function CorrectionModal({
  record,
  loading,
  error,
  onClose,
  onSubmit,
}: {
  record: AttendanceRecord | null;
  loading: boolean;
  error: unknown;
  onClose: () => void;
  onSubmit: (status: string, reason: string) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSubmit(String(data.get("status")), String(data.get("reason")));
  }
  return (
    <Modal
      open={Boolean(record)}
      onClose={onClose}
      title="Correct attendance record"
      description={`${record?.memberName || ""} · ${record?.id || ""}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="correction-form" loading={loading}>
            Save correction
          </Button>
        </>
      }
    >
      <form id="correction-form" className="form-grid" onSubmit={submit}>
        <label className="field">
          <span>Corrected status</span>
          <select name="status" defaultValue={record?.status}>
            <option value="present">Present</option>
            <option value="late">Late</option>
            <option value="excused">Excused absence</option>
          </select>
        </label>
        <label className="field field--full">
          <span>
            Reason <em>Required</em>
          </span>
          <textarea name="reason" required />
        </label>
        {Boolean(error) && (
          <div className="form-error field--full">{message(error)}</div>
        )}
      </form>
    </Modal>
  );
}

function SessionModal({
  open,
  loading,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  loading: boolean;
  error: unknown;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSubmit(Object.fromEntries(data.entries()));
  }
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Create attendance session"
      description="Opening and closing times are enforced by the backend."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            form="attendance-session-form"
            loading={loading}
          >
            Create session
          </Button>
        </>
      }
    >
      <form
        id="attendance-session-form"
        className="form-grid"
        onSubmit={submit}
      >
        <Field
          className="field--full"
          name="title"
          label="Service or event"
          required
        />
        <Field name="venue" label="Venue" required />
        <Field name="date" label="Date" type="date" required />
        <Field name="opensAt" label="Opening time" type="time" required />
        <Field name="closesAt" label="Closing time" type="time" required />
        {Boolean(error) && (
          <div className="form-error field--full">{message(error)}</div>
        )}
      </form>
    </Modal>
  );
}

export function LiveEventsPage() {
  const { user } = useAuth();
  const canWrite = hasPermission(user, "events:write");
  const [search, setSearch] = useState("");
  const [visibility, setVisibility] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [registerEvent, setRegisterEvent] = useState<EventSummary | null>(null);
  const toast = useToast();
  const client = useQueryClient();
  const params = {
    search,
    visibility: visibility || undefined,
    page: 1,
    pageSize: 30,
  };
  const query = useQuery({
    queryKey: queryKeys.events(params),
    queryFn: () => eventService.list(params),
  });
  const create = useMutation({
    mutationFn: (payload: Partial<EventSummary>) =>
      eventService.create(payload),
    onSuccess: () => {
      setCreateOpen(false);
      toast("Event created successfully.");
      void client.invalidateQueries({ queryKey: ["events"] });
    },
  });
  const register = useMutation({
    mutationFn: (eventId: string) => eventService.register(eventId, {}),
    onSuccess: (response) => {
      setRegisterEvent(null);
      toast(
        response.data.waitlisted
          ? "You were added to the waitlist."
          : `Registration confirmed: ${response.data.confirmationCode}`,
      );
    },
  });
  const rows = query.data?.data ?? [];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      title: String(data.get("title")),
      date: String(data.get("date")),
      time: String(data.get("time")),
      venue: String(data.get("venue")),
      capacity: Number(data.get("capacity")),
      visibility: String(data.get("visibility")) as EventSummary["visibility"],
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="Events"
        title="Events and registrations"
        description="Live event data scoped to your branch and visibility permissions."
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
          value={search}
          onChange={setSearch}
          placeholder="Search events"
        />
        <label>
          <Filter />
          <select
            aria-label="Event visibility"
            value={visibility}
            onChange={(event) => setVisibility(event.target.value)}
          >
            <option value="">All visibility</option>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
        </label>
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          description={message(query.error)}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <div className="event-cards">
          {rows.map((event) => (
            <article key={event.id}>
              <div className="event-card__date">
                <strong>{new Date(`${event.date}T12:00:00`).getDate()}</strong>
                <span>
                  {new Date(`${event.date}T12:00:00`).toLocaleString(
                    undefined,
                    { month: "short" },
                  )}
                </span>
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
                    <CalendarDays /> {event.date} · {event.time}
                  </p>
                  <p>{event.venue}</p>
                </div>
                <div className="event-card__registration">
                  <small>Registration</small>
                  <strong>
                    {event.registered} / {event.capacity}
                  </strong>
                  <span>
                    <i
                      style={{
                        width: `${Math.min(100, (event.registered / event.capacity) * 100)}%`,
                      }}
                    />
                  </span>
                </div>
                <Button
                  variant="secondary"
                  onClick={() => setRegisterEvent(event)}
                >
                  {canWrite ? "Open event" : "Register"}
                </Button>
              </div>
            </article>
          ))}
          {!rows.length && (
            <EmptyState
              title="No events found"
              description="Published events will appear here when available to your role."
            />
          )}
        </div>
      )}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create event"
        description="Registration, reminders, and visibility are validated by the backend."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="live-event-form"
              loading={create.isPending}
            >
              Create event
            </Button>
          </>
        }
      >
        <form id="live-event-form" className="form-grid" onSubmit={submit}>
          <Field
            className="field--full"
            name="title"
            label="Event title"
            required
          />
          <Field name="date" label="Date" type="date" required />
          <Field name="time" label="Time" type="time" required />
          <Field name="venue" label="Venue" required />
          <Field
            name="capacity"
            label="Capacity"
            type="number"
            min="1"
            required
          />
          <label className="field">
            <span>Visibility</span>
            <select name="visibility">
              <option value="public">Public</option>
              <option value="private">Members only</option>
            </select>
          </label>
          {create.isError && (
            <div className="form-error field--full">
              {message(create.error)}
            </div>
          )}
        </form>
      </Modal>
      <Modal
        open={Boolean(registerEvent)}
        onClose={() => setRegisterEvent(null)}
        title={canWrite ? "Event details" : "Confirm registration"}
        description={registerEvent?.title}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRegisterEvent(null)}>
              Cancel
            </Button>
            {!canWrite && (
              <Button
                loading={register.isPending}
                onClick={() =>
                  registerEvent && register.mutate(registerEvent.id)
                }
              >
                Confirm registration
              </Button>
            )}
          </>
        }
      >
        <div className="detail-grid">
          <div>
            <small>Date</small>
            <strong>{registerEvent?.date}</strong>
          </div>
          <div>
            <small>Time</small>
            <strong>{registerEvent?.time}</strong>
          </div>
          <div>
            <small>Venue</small>
            <strong>{registerEvent?.venue}</strong>
          </div>
          <div>
            <small>Availability</small>
            <strong>
              {registerEvent
                ? registerEvent.capacity - registerEvent.registered
                : 0}{" "}
              places
            </strong>
          </div>
        </div>
        {register.isError && (
          <div className="form-error">{message(register.error)}</div>
        )}
      </Modal>
    </>
  );
}

const moduleMeta: Record<
  OperationsModule,
  {
    eyebrow: string;
    title: string;
    description: string;
    action: string;
    icon: ReactNode;
  }
> = {
  workers: {
    eyebrow: "Workers and volunteers",
    title: "Worker directory and rosters",
    description: "Assignments, availability, leave, and service history.",
    action: "Create roster item",
    icon: <UserCheck />,
  },
  finance: {
    eyebrow: "Finance and giving",
    title: "Financial records",
    description:
      "Permission-filtered transactions, approvals, and reconciliation.",
    action: "Record transaction",
    icon: <FileText />,
  },
  communication: {
    eyebrow: "Communication centre",
    title: "Broadcasts",
    description: "Draft, confirm, and monitor targeted messages.",
    action: "Create broadcast",
    icon: <Send />,
  },
  assets: {
    eyebrow: "Assets and inventory",
    title: "Asset register",
    description: "Custody, stock movements, condition, and maintenance.",
    action: "Add asset",
    icon: <ListFilter />,
  },
  media: {
    eyebrow: "Sermons and media",
    title: "Media library",
    description: "Accessible audio, video, documents, and livestream content.",
    action: "Add media",
    icon: <FileText />,
  },
  cms: {
    eyebrow: "Website CMS",
    title: "Website content",
    description: "Draft, preview, schedule, and publish public content.",
    action: "Create content",
    icon: <FileText />,
  },
  branches: {
    eyebrow: "Headquarters oversight",
    title: "Branches",
    description: "Branch-scoped configuration and cross-branch oversight.",
    action: "Add branch",
    icon: <Users />,
  },
  audit: {
    eyebrow: "Security and accountability",
    title: "Audit log",
    description: "Authorized, redacted administrative activity.",
    action: "Export log",
    icon: <ShieldCheck />,
  },
  settings: {
    eyebrow: "Account and institution",
    title: "Privacy and account settings",
    description: "Preferences, data requests, password, and active sessions.",
    action: "Save preferences",
    icon: <LockKeyhole />,
  },
};

export function LiveOperationsPage({ module }: { module: OperationsModule }) {
  if (module === "settings") return <LiveSettingsPage />;
  return <LiveModuleOperationsPage module={module} />;
}

function LiveModuleOperationsPage({
  module,
}: {
  module: Exclude<OperationsModule, "settings">;
}) {
  const { user } = useAuth();
  const meta = moduleMeta[module];
  const writePermissions: Partial<Record<OperationsModule, Permission>> = {
    workers: "workers:write",
    finance: "finance:write",
    communication: "communication:write",
    assets: "assets:write",
    media: "media:write",
    cms: "cms:write",
    branches: "branches:manage",
  };
  const canCreate = hasPermission(user, writePermissions[module]);
  const canActOnRecord =
    (module === "workers" && hasPermission(user, "workers:acknowledge")) ||
    (module === "communication" &&
      hasPermission(user, "communication:write")) ||
    (module === "assets" && hasPermission(user, "assets:write")) ||
    (module === "cms" && hasPermission(user, "cms:write"));
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [pendingPayload, setPendingPayload] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [selected, setSelected] = useState<ListRow | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const toast = useToast();
  const client = useQueryClient();
  const params = {
    search,
    status: statusFilter || undefined,
    page: 1,
    pageSize: 40,
  };
  const query = useQuery({
    queryKey: queryKeys.operations(module, params),
    queryFn: () => operationsService.list(module, params),
  });
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      operationsService.create(module, payload),
    onSuccess: () => {
      setOpen(false);
      setConfirm(false);
      toast(`${meta.action} completed.`);
      void client.invalidateQueries({ queryKey: [module] });
    },
  });
  const recordAction = useMutation({
    mutationFn: async (row: ListRow) => {
      if (module === "workers")
        return operationsService.workerAcknowledge(row.id);
      if (module === "communication")
        return operationsService.sendBroadcast(row.id);
      if (module === "assets")
        return operationsService.assetMovement(row.id, { action: "issue" });
      if (module === "cms") return operationsService.publishContent(row.id);
    },
    onSuccess: () => {
      setSelected(null);
      toast("Record action completed.");
      void client.invalidateQueries({ queryKey: [module] });
    },
  });
  const rows = query.data?.data ?? [];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = Object.fromEntries(
      new FormData(event.currentTarget).entries(),
    );
    if (module === "communication" || module === "finance") {
      setPendingPayload(payload);
      setConfirm(true);
      return;
    }
    create.mutate(payload);
  }
  return (
    <>
      <PageHeader
        eyebrow={meta.eyebrow}
        title={meta.title}
        description={meta.description}
        actions={
          module === "audit" ? (
            <Button
              icon={<Download />}
              disabled={!rows.length}
              onClick={() =>
                downloadCsv(
                  "chapelflow-audit.csv",
                  rows as unknown as Record<string, unknown>[],
                )
              }
            >
              {meta.action}
            </Button>
          ) : canCreate ? (
            <Button icon={<Plus />} onClick={() => setOpen(true)}>
              {meta.action}
            </Button>
          ) : undefined
        }
      />
      <div className="filter-bar">
        <SearchField
          value={search}
          onChange={setSearch}
          placeholder={`Search ${meta.title.toLowerCase()}`}
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
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          description={message(query.error)}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <section className="module-list">
          <header>
            <span>{meta.icon}</span>
            <div>
              <h2>Records</h2>
              <p>Data is filtered and authorized by the backend.</p>
            </div>
          </header>
          {rows.map((row) => (
            <article key={row.id}>
              <span className="module-row__icon">{meta.icon}</span>
              <div>
                <strong>{row.primary}</strong>
                <small>{row.secondary}</small>
              </div>
              <div>
                <strong>{row.detail}</strong>
                <small>Current detail</small>
              </div>
              <Badge
                tone={
                  /approved|published|active|healthy|delivered|complete/i.test(
                    row.status,
                  )
                    ? "success"
                    : /pending|draft|due|failed/i.test(row.status)
                      ? "warning"
                      : "neutral"
                }
              >
                {row.status}
              </Badge>
              <button
                className="icon-button"
                aria-label={`Actions for ${row.primary}`}
                onClick={() => setSelected(row)}
              >
                <MoreHorizontal />
              </button>
            </article>
          ))}
          {!rows.length && (
            <EmptyState
              title={`No ${meta.title.toLowerCase()} found`}
              description="Records will appear when the backend returns data for the active scope."
            />
          )}
        </section>
      )}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={meta.action}
        description="Required fields and authorization are validated again by the backend."
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="operation-form"
              loading={create.isPending}
            >
              Continue
            </Button>
          </>
        }
      >
        <form id="operation-form" onSubmit={submit} className="form-grid">
          <Field
            className="field--full"
            name="title"
            label={
              module === "finance"
                ? "Description"
                : module === "assets"
                  ? "Asset name"
                  : module === "communication"
                    ? "Broadcast title"
                    : "Title"
            }
            required
          />
          {module === "communication" && (
            <>
              <label className="field">
                <span>Channel</span>
                <select name="channel">
                  <option>Email</option>
                  <option>SMS</option>
                  <option>Push</option>
                </select>
              </label>
              <label className="field">
                <span>Audience</span>
                <select name="audience">
                  <option>All active members</option>
                  <option>Workers</option>
                  <option>Event participants</option>
                </select>
              </label>
              <label className="field field--full">
                <span>Message</span>
                <textarea name="message" required />
              </label>
            </>
          )}
          {module === "finance" && (
            <>
              <Field
                name="amount"
                label="Amount"
                type="number"
                min="0"
                required
              />
              <label className="field">
                <span>Category</span>
                <select name="category">
                  <option>Offering</option>
                  <option>Donation</option>
                  <option>Expense</option>
                </select>
              </label>
            </>
          )}
          {module !== "communication" && module !== "finance" && (
            <Field
              className="field--full"
              name="detail"
              label="Details"
              required
            />
          )}
          {create.isError && (
            <div className="form-error field--full">
              {message(create.error)}
            </div>
          )}
        </form>
      </Modal>
      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title={
          module === "communication"
            ? "Confirm broadcast audience"
            : "Confirm financial record"
        }
        description="This sensitive action requires an explicit confirmation."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Go back
            </Button>
            <Button
              loading={create.isPending}
              onClick={() =>
                create.mutate({ ...(pendingPayload || {}), confirmed: true })
              }
            >
              Confirm and continue
            </Button>
          </>
        }
      >
        <div className="insight-note">
          <AlertTriangle />
          <div>
            <strong>Review before submitting</strong>
            <p>
              {module === "communication"
                ? "Verify the audience, channel, and message. Large broadcasts cannot be sent with a single unconfirmed action."
                : "Verify the amount, category, and supporting information. The backend will preserve the audit trail."}
            </p>
          </div>
        </div>
      </Modal>
      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.primary || "Record"}
        description={selected?.secondary}
        footer={
          <>
            <Button variant="ghost" onClick={() => setSelected(null)}>
              Close
            </Button>
            {selected &&
              canActOnRecord &&
              ["workers", "communication", "assets", "cms"].includes(
                module,
              ) && (
                <Button
                  loading={recordAction.isPending}
                  onClick={() => recordAction.mutate(selected)}
                >
                  {module === "workers"
                    ? "Acknowledge assignment"
                    : module === "communication"
                      ? "Confirm and send"
                      : module === "assets"
                        ? "Record issue"
                        : "Publish content"}
                </Button>
              )}
          </>
        }
      >
        <div className="detail-grid">
          <div>
            <small>Current detail</small>
            <strong>{selected?.detail}</strong>
          </div>
          <div>
            <small>Status</small>
            <strong>{selected?.status}</strong>
          </div>
          <div>
            <small>Reference</small>
            <strong>{selected?.id}</strong>
          </div>
          <div>
            <small>Module</small>
            <strong>{module}</strong>
          </div>
        </div>
        {module === "cms" && (
          <div className="cms-preview">
            <small>Content preview</small>
            <h2>{selected?.primary}</h2>
            <p>{selected?.detail}</p>
          </div>
        )}
        {recordAction.isError && (
          <div className="form-error">{message(recordAction.error)}</div>
        )}
      </Modal>
    </>
  );
}

function LiveSettingsPage() {
  const toast = useToast();
  const query = useQuery({
    queryKey: ["privacy-preferences"],
    queryFn: async () => (await privacyService.preferences()).data,
  });
  const update = useMutation({
    mutationFn: (payload: Record<string, boolean>) =>
      privacyService.updatePreferences(payload),
    onSuccess: () => toast("Privacy preferences updated."),
  });
  const exportRequest = useMutation({
    mutationFn: () => privacyService.requestExport(),
    onSuccess: (response) =>
      toast(`Data request submitted: ${response.data.requestId}`),
  });
  const deleteRequest = useMutation({
    mutationFn: (reason: string) => privacyService.requestDeletion(reason),
    onSuccess: (response) =>
      toast(`Account request submitted: ${response.data.requestId}`),
  });
  const [deleteOpen, setDeleteOpen] = useState(false);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    update.mutate({
      email: data.has("email"),
      sms: data.has("sms"),
      push: data.has("push"),
      analytics: data.has("analytics"),
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="Account and institution"
        title="Privacy and account settings"
        description="Control optional communications, data requests, and account security."
      />
      <div className="settings-grid">
        <section className="panel">
          <header className="panel-heading">
            <div>
              <h2>Communication preferences</h2>
              <p>Essential service messages cannot be disabled.</p>
            </div>
          </header>
          {query.isPending ? (
            <LoadingState />
          ) : query.isError ? (
            <ErrorState
              description={message(query.error)}
              onRetry={() => void query.refetch()}
            />
          ) : (
            <form className="preference-form" onSubmit={submit}>
              <label>
                <span>
                  <strong>Email updates</strong>
                  <small>Programmes and chapel announcements</small>
                </span>
                <input
                  name="email"
                  type="checkbox"
                  defaultChecked={query.data.email}
                />
              </label>
              <label>
                <span>
                  <strong>SMS updates</strong>
                  <small>Time-sensitive service notices</small>
                </span>
                <input
                  name="sms"
                  type="checkbox"
                  defaultChecked={query.data.sms}
                />
              </label>
              <label>
                <span>
                  <strong>Push notifications</strong>
                  <small>In-app and device updates</small>
                </span>
                <input
                  name="push"
                  type="checkbox"
                  defaultChecked={query.data.push}
                />
              </label>
              <label>
                <span>
                  <strong>Optional analytics</strong>
                  <small>Help improve the ChapelFlow experience</small>
                </span>
                <input
                  name="analytics"
                  type="checkbox"
                  defaultChecked={query.data.analytics}
                />
              </label>
              <Button type="submit" loading={update.isPending}>
                Save preferences
              </Button>
            </form>
          )}
        </section>
        <section className="panel">
          <header className="panel-heading">
            <div>
              <h2>Your data and account</h2>
              <p>
                Requests are reviewed according to institutional retention
                policy.
              </p>
            </div>
          </header>
          <div className="settings-actions">
            <article>
              <span>
                <Download />
              </span>
              <div>
                <strong>Request a copy of your data</strong>
                <p>Receive an export of eligible ChapelFlow records.</p>
              </div>
              <Button
                variant="secondary"
                loading={exportRequest.isPending}
                onClick={() => exportRequest.mutate()}
              >
                Request
              </Button>
            </article>
            <article>
              <span>
                <ShieldCheck />
              </span>
              <div>
                <strong>Review privacy policy</strong>
                <p>See how chapel information is handled.</p>
              </div>
              <a className="button button--secondary" href="/privacy">
                Open policy
              </a>
            </article>
            <article>
              <span>
                <LockKeyhole />
              </span>
              <div>
                <strong>Request account deletion</strong>
                <p>Some records may be retained where policy requires it.</p>
              </div>
              <Button variant="secondary" onClick={() => setDeleteOpen(true)}>
                Request
              </Button>
            </article>
          </div>
        </section>
        <LiveSecurityPanel />
      </div>
      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Request account deletion"
        description="This submits a review request; it does not immediately erase institutional records."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deleteRequest.isPending}
              onClick={() =>
                deleteRequest.mutate(
                  "User requested account deletion through ChapelFlow.",
                )
              }
            >
              Submit request
            </Button>
          </>
        }
      >
        <div className="insight-note">
          <AlertTriangle />
          <div>
            <strong>Review the consequences</strong>
            <p>
              You may lose access to your chapel profile and saved content.
              Attendance or financial records may be retained when institutional
              policy requires them.
            </p>
          </div>
        </div>
      </Modal>
    </>
  );
}

function LiveSecurityPanel() {
  const [passwordOpen, setPasswordOpen] = useState(false);
  const toast = useToast();
  const client = useQueryClient();
  const sessions = useQuery({
    queryKey: ["account-sessions"],
    queryFn: async () => (await authService.sessions()).data,
  });
  const revoke = useMutation({
    mutationFn: (id: string) => authService.revokeSession(id),
    onSuccess: () => {
      toast("Session signed out.");
      void client.invalidateQueries({ queryKey: ["account-sessions"] });
    },
  });
  const password = useMutation({
    mutationFn: ({
      currentPassword,
      nextPassword,
    }: {
      currentPassword: string;
      nextPassword: string;
    }) => authService.changePassword(currentPassword, nextPassword),
    onSuccess: () => {
      setPasswordOpen(false);
      toast("Password changed successfully.");
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const currentPassword = String(data.get("currentPassword"));
    const nextPassword = String(data.get("nextPassword"));
    const confirmation = String(data.get("confirmation"));
    if (nextPassword !== confirmation) return;
    password.mutate({ currentPassword, nextPassword });
  }
  return (
    <section className="panel settings-security">
      <header className="panel-heading">
        <div>
          <h2>Password and active sessions</h2>
          <p>Review devices with access to your ChapelFlow account.</p>
        </div>
        <Button variant="secondary" onClick={() => setPasswordOpen(true)}>
          Change password
        </Button>
      </header>
      {sessions.isPending ? (
        <LoadingState />
      ) : sessions.isError ? (
        <ErrorState
          description={message(sessions.error)}
          onRetry={() => void sessions.refetch()}
        />
      ) : (
        <div className="session-list">
          {sessions.data.map((session) => (
            <article key={session.id}>
              <span>
                <LockKeyhole />
              </span>
              <div>
                <strong>{session.device}</strong>
                <p>
                  {session.current
                    ? "Current session"
                    : `Last active ${new Date(session.lastActiveAt).toLocaleString()}`}
                </p>
              </div>
              {session.current ? (
                <Badge tone="success">Current</Badge>
              ) : (
                <Button
                  variant="ghost"
                  loading={revoke.isPending}
                  onClick={() => revoke.mutate(session.id)}
                >
                  Sign out
                </Button>
              )}
            </article>
          ))}
          {!sessions.data.length && (
            <EmptyState
              title="No active sessions returned"
              description="The backend did not return any current device sessions."
            />
          )}
        </div>
      )}
      <Modal
        open={passwordOpen}
        onClose={() => setPasswordOpen(false)}
        title="Change password"
        description="Changing your password may revoke other active sessions."
        footer={
          <>
            <Button variant="ghost" onClick={() => setPasswordOpen(false)}>
              Cancel
            </Button>
            <Button
              form="change-password-form"
              type="submit"
              loading={password.isPending}
            >
              Change password
            </Button>
          </>
        }
      >
        <form id="change-password-form" className="form-grid" onSubmit={submit}>
          <Field
            className="field--full"
            name="currentPassword"
            label="Current password"
            type="password"
            required
          />
          <Field
            name="nextPassword"
            label="New password"
            type="password"
            minLength={8}
            required
          />
          <Field
            name="confirmation"
            label="Confirm password"
            type="password"
            minLength={8}
            required
          />
          {password.isError && (
            <div className="form-error field--full">
              {message(password.error)}
            </div>
          )}
        </form>
      </Modal>
    </section>
  );
}

export function LiveAnalyticsPage() {
  const [range, setRange] = useState("semester");
  const query = useQuery({
    queryKey: queryKeys.analytics({ range }),
    queryFn: async () => (await analyticsService.get({ range })).data,
  });
  return (
    <>
      <PageHeader
        eyebrow="Analytics and reports"
        title="Chapel insights"
        description="Backend-generated summaries with privacy-respecting decision support."
        actions={
          query.data && (
            <Button
              variant="secondary"
              icon={<Download />}
              onClick={() =>
                downloadCsv(
                  "chapelflow-analytics.csv",
                  query.data.metrics as unknown as Record<string, unknown>[],
                )
              }
            >
              Export report
            </Button>
          )
        }
      />
      <div className="report-toolbar">
        <label>
          <CalendarDays />
          <span>Date range</span>
          <select
            value={range}
            onChange={(event) => setRange(event.target.value)}
          >
            <option value="semester">This semester</option>
            <option value="previous_semester">Last semester</option>
            <option value="year">Academic year</option>
          </select>
        </label>
      </div>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          description={message(query.error)}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <>
          <div className="metric-grid">
            {query.data.metrics.map((metric) => (
              <article className="metric-card" key={metric.label}>
                <small>{metric.label}</small>
                <strong>{metric.value}</strong>
                <p>{metric.note}</p>
              </article>
            ))}
          </div>
          <div className="analytics-grid">
            <section className="panel panel--wide">
              <header className="panel-heading">
                <div>
                  <h2>Attendance over time</h2>
                  <p>Selected reporting period</p>
                </div>
              </header>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={query.data.attendanceTrend}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" />
                    <YAxis />
                    <Tooltip />
                    <Area
                      dataKey="attendance"
                      stroke="var(--purple-500)"
                      fill="var(--purple-100)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </section>
            <section className="panel">
              <header className="panel-heading">
                <div>
                  <h2>Attendance by level</h2>
                  <p>Authorized aggregated values</p>
                </div>
              </header>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart layout="vertical" data={query.data.byLevel}>
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" />
                    <Tooltip />
                    <Bar dataKey="value" fill="var(--purple-500)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
          </div>
          <div className="insight-note">
            <AlertTriangle />
            <div>
              <strong>Decision support only</strong>
              <p>
                Patterns may guide considerate follow-up but must not be treated
                as judgments about an individual.
              </p>
            </div>
          </div>
        </>
      )}
    </>
  );
}
