import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  History,
  Pause,
  Play,
  ShieldCheck,
  UserRound,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
import {
  adminAttendanceService,
  securityService,
} from "../services/chapelflow";

type Tab = "attendance" | "audit" | "security";

export function AdminOperationsPage() {
  const [tab, setTab] = useState<Tab>("attendance");
  const [correction, setCorrection] = useState<{
    id: string;
    status: string;
  } | null>(null);
  const client = useQueryClient();
  const sessions = useQuery({
    queryKey: ["admin-attendance-sessions"],
    queryFn: async () => (await adminAttendanceService.sessions()).data,
    enabled: tab === "attendance",
  });
  const records = useQuery({
    queryKey: ["admin-attendance-records"],
    queryFn: async () => (await adminAttendanceService.records()).data,
    enabled: tab === "attendance",
  });
  const attempts = useQuery({
    queryKey: ["admin-scan-attempts"],
    queryFn: async () => (await adminAttendanceService.scanAttempts()).data,
    enabled: tab === "attendance",
  });
  const audit = useQuery({
    queryKey: ["admin-audit"],
    queryFn: async () => (await securityService.auditLogs()).data,
    enabled: tab === "audit",
  });
  const activeSessions = useQuery({
    queryKey: ["admin-security-sessions"],
    queryFn: async () => (await securityService.sessions()).data,
    enabled: tab === "security",
  });
  const refreshAttendance = () =>
    void client.invalidateQueries({ queryKey: ["admin-attendance"] });
  const create = useMutation({
    mutationFn: adminAttendanceService.createSession,
    onSuccess: refreshAttendance,
  });
  const transition = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: "pause" | "resume" | "close";
    }) => adminAttendanceService.transition(id, action),
    onSuccess: refreshAttendance,
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
    }) => adminAttendanceService.correct(id, status, reason),
    onSuccess: () => {
      setCorrection(null);
      refreshAttendance();
    },
  });
  const revoke = useMutation({
    mutationFn: securityService.revokeSession,
    onSuccess: () => void activeSessions.refetch(),
  });
  const revokeAll = useMutation({
    mutationFn: securityService.revokeAllSessions,
    onSuccess: () => void activeSessions.refetch(),
  });
  function createSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      label: String(form.get("label")),
      window_opens_at: new Date(String(form.get("opens"))).toISOString(),
      window_closes_at: new Date(String(form.get("closes"))).toISOString(),
    });
  }
  function submitCorrection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!correction) return;
    const form = new FormData(event.currentTarget);
    correct.mutate({ ...correction, reason: String(form.get("reason")) });
  }
  return (
    <div className="motion-feature admin-operations">
      <PageHeader
        eyebrow="Super administration"
        title="Service control room"
        description="Open services, review attendance outcomes, and manage ChapelFlow security from one place."
        actions={
          <Link className="button button--secondary" to="/app/members">
            <UserRound /> Registered students
          </Link>
        }
      />
      <nav
        className="admin-operations__tabs"
        aria-label="Control room sections"
      >
        {(
          [
            ["attendance", "Attendance", CalendarClock],
            ["audit", "Audit trail", History],
            ["security", "Session security", ShieldCheck],
          ] as const
        ).map(([value, label, Icon]) => (
          <button
            type="button"
            key={value}
            className={tab === value ? "is-active" : ""}
            onClick={() => setTab(value)}
          >
            <Icon />
            {label}
          </button>
        ))}
      </nav>
      {tab === "attendance" && (
        <>
          <section className="admin-operations__grid">
            <form className="panel" onSubmit={createSession}>
              <div className="panel-heading">
                <div>
                  <h2>Open a service</h2>
                  <p>Times are enforced by the server, not student devices.</p>
                </div>
              </div>
              <label className="field">
                <span>Service name</span>
                <input name="label" required placeholder="Sunday worship" />
              </label>
              <label className="field">
                <span>Opens</span>
                <input name="opens" type="datetime-local" required />
              </label>
              <label className="field">
                <span>Closes</span>
                <input name="closes" type="datetime-local" required />
              </label>
              <Button type="submit" loading={create.isPending}>
                Open attendance
              </Button>
              {create.isError && <p role="alert">{create.error.message}</p>}
            </form>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Live sessions</h2>
                  <p>
                    Usher QR codes stop immediately when a session pauses or
                    closes.
                  </p>
                </div>
              </div>
              {sessions.isPending ? (
                <LoadingState label="Loading sessions" />
              ) : sessions.isError ? (
                <ErrorState
                  description={sessions.error.message}
                  onRetry={() => void sessions.refetch()}
                />
              ) : sessions.data.length ? (
                <div className="admin-operations__sessions">
                  {sessions.data.map((session) => (
                    <article key={session.id}>
                      <div>
                        <strong>{session.label || "Chapel service"}</strong>
                        <small>{session.record_count} recorded</small>
                      </div>
                      <Badge
                        tone={
                          session.state === "OPEN"
                            ? "success"
                            : session.state === "PAUSED"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {session.state.toLowerCase()}
                      </Badge>
                      <span>
                        {session.state === "OPEN" && (
                          <Button
                            variant="ghost"
                            icon={<Pause />}
                            onClick={() =>
                              transition.mutate({
                                id: session.id,
                                action: "pause",
                              })
                            }
                          >
                            Pause
                          </Button>
                        )}
                        {session.state === "PAUSED" && (
                          <Button
                            variant="ghost"
                            icon={<Play />}
                            onClick={() =>
                              transition.mutate({
                                id: session.id,
                                action: "resume",
                              })
                            }
                          >
                            Resume
                          </Button>
                        )}
                        {session.is_open && (
                          <Button
                            variant="danger"
                            icon={<XCircle />}
                            onClick={() =>
                              transition.mutate({
                                id: session.id,
                                action: "close",
                              })
                            }
                          >
                            Close
                          </Button>
                        )}
                      </span>
                    </article>
                  ))}
                </div>
              ) : (
                <p>No attendance services have been opened.</p>
              )}
            </section>
          </section>
          <section className="table-panel">
            <header>
              <div className="panel-heading">
                <div>
                  <h2>Attendance records</h2>
                  <p>
                    Any correction requires a reason and retains its audit
                    history.
                  </p>
                </div>
              </div>
            </header>
            {records.isPending ? (
              <LoadingState label="Loading attendance records" />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Record</th>
                    <th>Status</th>
                    <th>Checked in</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {records.data?.map((record) => (
                    <tr key={record.id}>
                      <td>{record.member || "Visitor"}</td>
                      <td>
                        <Badge tone="success">{record.status}</Badge>
                      </td>
                      <td>{new Date(record.checked_in_at).toLocaleString()}</td>
                      <td>
                        <Button
                          variant="ghost"
                          onClick={() =>
                            setCorrection({
                              id: record.id,
                              status: record.status,
                            })
                          }
                        >
                          Correct
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section className="table-panel">
            <header>
              <div className="panel-heading">
                <div>
                  <h2>Recent scan outcomes</h2>
                  <p>
                    Tokens are redacted; this shows only safe checkpoint
                    outcomes.
                  </p>
                </div>
              </div>
            </header>
            {attempts.isPending ? (
              <LoadingState label="Loading scan outcomes" />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Result</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {attempts.data?.map((attempt) => (
                    <tr key={attempt.id}>
                      <td>
                        <Badge
                          tone={
                            attempt.result === "recorded"
                              ? "success"
                              : "warning"
                          }
                        >
                          {attempt.result.replaceAll("_", " ")}
                        </Badge>
                      </td>
                      <td>{new Date(attempt.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
      {tab === "audit" && (
        <section className="table-panel">
          <header>
            <div className="panel-heading">
              <div>
                <h2>Audit trail</h2>
                <p>Security and administrative actions are append-only.</p>
              </div>
            </div>
          </header>
          {audit.isPending ? (
            <LoadingState label="Loading audit trail" />
          ) : audit.isError ? (
            <ErrorState
              description={audit.error.message}
              onRetry={() => void audit.refetch()}
            />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Target</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.map((entry) => (
                  <tr key={entry.id}>
                    <td>
                      <strong>{entry.action.replaceAll("_", " ")}</strong>
                    </td>
                    <td>{entry.resource_type}</td>
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
      {tab === "security" && (
        <section className="table-panel">
          <header>
            <div className="panel-heading">
              <div>
                <h2>Active sessions</h2>
                <p>Revoke a device session or terminate all other sessions.</p>
              </div>
              <Button variant="danger" onClick={() => revokeAll.mutate(true)}>
                Log out other devices
              </Button>
            </div>
          </header>
          {activeSessions.isPending ? (
            <LoadingState label="Loading active sessions" />
          ) : activeSessions.isError ? (
            <ErrorState
              description={activeSessions.error.message}
              onRetry={() => void activeSessions.refetch()}
            />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Last active</th>
                  <th>Device</th>
                  <th>Current</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {activeSessions.data.map((session) => (
                  <tr key={session.id}>
                    <td>{new Date(session.lastActiveAt).toLocaleString()}</td>
                    <td>{session.device}</td>
                    <td>
                      {session.current ? "This device" : "Another device"}
                    </td>
                    <td>
                      {!session.current && (
                        <Button
                          variant="ghost"
                          onClick={() => revoke.mutate(session.id)}
                        >
                          Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
      {correction && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={submitCorrection}>
            <header className="modal__header">
              <h2>Correct attendance</h2>
            </header>
            <div className="modal__body">
              <label className="field">
                <span>Status</span>
                <select
                  value={correction.status}
                  onChange={(event) =>
                    setCorrection({ ...correction, status: event.target.value })
                  }
                >
                  <option value="PRESENT">Present</option>
                  <option value="LATE">Late</option>
                  <option value="EXCUSED">Excused</option>
                  <option value="ABSENT">Absent</option>
                </select>
              </label>
              <label className="field">
                <span>Reason</span>
                <textarea name="reason" required maxLength={500} />
              </label>
            </div>
            <footer className="modal__footer">
              <Button
                variant="secondary"
                type="button"
                onClick={() => setCorrection(null)}
              >
                Cancel
              </Button>
              <Button type="submit" loading={correct.isPending}>
                Save correction
              </Button>
            </footer>
          </form>
        </div>
      )}
    </div>
  );
}
