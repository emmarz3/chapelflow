import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, CalendarDays, FileText, HeartHandshake, ListTodo, Megaphone, UsersRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { downloadCsv } from "../lib/export";
import { Badge, Button, EmptyState, ErrorState, Field, LoadingState, PageHeader, useToast } from "../components/ui";
import { roleWorkspaceService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

type Row = Record<string, unknown>;
const value = (row: Row, key: string) => String(row[key] ?? "");
const rows = (data: unknown) => (Array.isArray(data) ? data as Row[] : []);
const error = (reason: unknown) => reason instanceof Error ? reason.message : "The request could not be completed.";

function Metric({ label, value: metric }: { label: string; value: number }) {
  return <article className="metric-card"><small>{label}</small><strong>{metric.toLocaleString()}</strong></article>;
}

export function RoleOperationsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const client = useQueryClient();
  const [meetingId, setMeetingId] = useState("");
  const summary = useQuery({ queryKey: ["role-workspace"], queryFn: async () => (await roleWorkspaceService.summary()).data });
  const memberships = useQuery({ queryKey: ["role-memberships"], queryFn: async () => (await roleWorkspaceService.memberships()).data, enabled: user?.role === "unit_leader" || user?.role === "fellowship_leader" });
  const joinRequests = useQuery({ queryKey: ["role-join-requests"], queryFn: async () => (await roleWorkspaceService.joinRequests()).data, enabled: user?.role === "unit_leader" || user?.role === "fellowship_leader" });
  const tasks = useQuery({ queryKey: ["role-tasks"], queryFn: async () => (await roleWorkspaceService.tasks()).data, enabled: user?.role === "unit_leader" || user?.role === "fellowship_leader" });
  const meetings = useQuery({ queryKey: ["role-meetings"], queryFn: async () => (await roleWorkspaceService.meetings()).data, enabled: user?.role === "unit_leader" || user?.role === "fellowship_leader" });
  const meetingAttendance = useQuery({ queryKey: ["role-meeting-attendance", meetingId], queryFn: async () => (await roleWorkspaceService.meetingAttendance(meetingId)).data, enabled: Boolean(meetingId) && (user?.role === "unit_leader" || user?.role === "fellowship_leader") });
  const announcements = useQuery({ queryKey: ["role-announcements"], queryFn: async () => (await roleWorkspaceService.announcements()).data });
  const assignments = useQuery({ queryKey: ["role-assignments"], queryFn: async () => (await roleWorkspaceService.assignments()).data, enabled: user?.permissions.includes("workers:read") });
  const followUps = useQuery({ queryKey: ["role-followups"], queryFn: async () => (await roleWorkspaceService.followUps()).data, enabled: user?.role === "chaplain" });
  const setMembership = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) => roleWorkspaceService.updateMembership(id, isActive),
    onSuccess: () => { toast("Membership updated."); void client.invalidateQueries({ queryKey: ["role-memberships"] }); },
  });
  const resolveRequest = useMutation({ mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) => roleWorkspaceService.resolveJoinRequest(id, action), onSuccess: () => { toast("Join request updated."); void client.invalidateQueries({ queryKey: ["role-join-requests"] }); void client.invalidateQueries({ queryKey: ["role-memberships"] }); } });
  const createTask = useMutation({ mutationFn: roleWorkspaceService.createTask, onSuccess: () => { toast("Task created."); void client.invalidateQueries({ queryKey: ["role-tasks"] }); } });
  const updateTask = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => roleWorkspaceService.updateTask(id, { status }), onSuccess: () => { toast("Task updated."); void client.invalidateQueries({ queryKey: ["role-tasks"] }); } });
  const createMeeting = useMutation({ mutationFn: roleWorkspaceService.createMeeting, onSuccess: () => { toast("Meeting scheduled."); void client.invalidateQueries({ queryKey: ["role-meetings"] }); } });
  const markAttendance = useMutation({ mutationFn: ({ meeting, member }: { meeting: string; member: string }) => roleWorkspaceService.markMeetingAttendance(meeting, member), onSuccess: () => { toast("Meeting attendance recorded."); void client.invalidateQueries({ queryKey: ["role-meeting-attendance", meetingId] }); } });
  const createAnnouncement = useMutation({
    mutationFn: roleWorkspaceService.createAnnouncement,
    onSuccess: () => { toast("Announcement saved as a draft."); void client.invalidateQueries({ queryKey: ["role-announcements"] }); },
  });
  const createReport = useMutation({
    mutationFn: roleWorkspaceService.createReport,
    onSuccess: () => { toast("Report queued. It will appear here when ready."); void client.invalidateQueries({ queryKey: ["role-reports"] }); },
  });

  if (summary.isPending) return <LoadingState label="Loading your operational workspace" />;
  if (summary.isError) return <ErrorState description={error(summary.error)} onRetry={() => void summary.refetch()} />;
  const data = summary.data;
  const leader = user?.role === "unit_leader" || user?.role === "fellowship_leader";
  const chaplain = user?.role === "chaplain" || user?.role === "student_chaplain";
  const heading = user?.role === "chaplain" ? "Chaplain operations" : user?.role === "student_chaplain" ? "Student Chapel operations" : user?.role === "unit_leader" ? "Unit operations" : "Fellowship operations";

  function submitAnnouncement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const groupId = String(form.get("group") || "");
    createAnnouncement.mutate({
      branch: data.branch_id,
      title: String(form.get("title") || ""),
      body: String(form.get("body") || ""),
      audience_type: groupId ? "CUSTOM" : "EVERYONE",
      target_groups: groupId ? [groupId] : [],
      channels: ["IN_APP"],
      publish_at: new Date().toISOString(),
    });
  }

  return <>
    <PageHeader eyebrow="Authorized operational workspace" title={heading} description="Every list and action is checked again by the Django role and scope policy." />
    <section className="metric-grid">
      <Metric label={leader ? "Active members" : "Active students"} value={data.metrics.active_students} />
      <Metric label={leader ? "Assigned communities" : "Active communities"} value={data.metrics.groups} />
      <Metric label="Open attendance sessions" value={data.metrics.open_sessions} />
      <Metric label="Attendance today" value={data.metrics.attendance_today} />
      <Metric label="Reports in progress" value={data.metrics.pending_reports} />
    </section>

    {chaplain && <section className="panel"><header className="panel-heading"><div><h2>Live attendance monitoring</h2><p>Open service windows and confirmed check-ins. Attendance controls remain restricted to authorized session administrators.</p></div><Activity /></header>{data.live_sessions.length ? <div className="stack-list">{data.live_sessions.map((session) => <article key={session.id}><div><strong>{session.label}</strong><small>{session.check_ins} confirmed check-ins</small></div><Badge tone={session.state === "OPEN" ? "success" : "warning"}>{session.state.toLowerCase()}</Badge></article>)}</div> : <EmptyState title="No open attendance session" description="Live service activity will appear here when an authorized administrator opens a session." />}</section>}

    <section className="panel">
      <header className="panel-heading"><div><h2>{leader ? "My community scope" : "Chapel communities"}</h2><p>{leader ? "Only the unit or fellowship assigned to your account is shown." : "University chapel communities available within your authorized scope."}</p></div><UsersRound /></header>
      {data.groups.length ? <div className="role-workspace-grid">{data.groups.map((group) => <article key={group.id} className="role-workspace-card"><UsersRound /><div><h2>{group.name}</h2><p>{group.type.toLowerCase()} · {group.active_members} active members</p></div></article>)}</div> : <EmptyState title="No community assignment" description="A Super Admin must assign your unit or fellowship before leader operations can begin." />}
    </section>

    {leader && <section className="panel">
      <header className="panel-heading"><div><h2>Member register</h2><p>Activate or archive existing members in your assigned community. The server prevents changes outside your group.</p></div><UsersRound /></header>
      {memberships.isPending ? <LoadingState label="Loading member register" /> : memberships.isError ? <ErrorState description={error(memberships.error)} /> : rows(memberships.data).length ? <div className="table-wrap"><table><thead><tr><th>Member</th><th>Community</th><th>Role</th><th>Status</th><th /></tr></thead><tbody>{rows(memberships.data).map((item) => <tr key={value(item, "id")}><td><strong>{value(item, "member_name") || "Student"}</strong><br /><small>{value(item, "member_identifier")}</small></td><td>{value(item, "group_name")}</td><td>{value(item, "role").replaceAll("_", " ")}</td><td><Badge tone={item.is_active ? "success" : "warning"}>{item.is_active ? "Active" : "Archived"}</Badge></td><td><Button variant="ghost" disabled={setMembership.isPending} onClick={() => setMembership.mutate({ id: value(item, "id"), isActive: !Boolean(item.is_active) })}>{item.is_active ? "Archive" : "Restore"}</Button></td></tr>)}</tbody></table></div> : <EmptyState title="No members yet" description="Membership records will appear here as students join your assigned community." />}
    </section>}

    {leader && <section className="role-workspace-grid">
      <section className="panel"><header className="panel-heading"><div><h2>Join requests</h2><p>Approval creates the member record for this community only.</p></div><UsersRound /></header>{joinRequests.isPending ? <LoadingState label="Loading requests" /> : joinRequests.isError ? <ErrorState description={error(joinRequests.error)} /> : rows(joinRequests.data).filter((item) => value(item, "status") === "PENDING").length ? <div className="stack-list">{rows(joinRequests.data).filter((item) => value(item, "status") === "PENDING").map((item) => <article key={value(item, "id")}><div><strong>{value(item, "member_name")}</strong><small>{value(item, "message") || "No message supplied"}</small></div><span><Button variant="secondary" loading={resolveRequest.isPending} onClick={() => resolveRequest.mutate({ id: value(item, "id"), action: "approve" })}>Approve</Button><Button variant="ghost" disabled={resolveRequest.isPending} onClick={() => resolveRequest.mutate({ id: value(item, "id"), action: "reject" })}>Reject</Button></span></article>)}</div> : <EmptyState title="No pending requests" description="New requests from students will appear here." />}</section>
      <section className="panel"><header className="panel-heading"><div><h2>Group tasks</h2><p>Keep follow-up and service preparation visible to the leadership team.</p></div><ListTodo /></header><form className="form-grid" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const group = String(form.get("group") || ""); if (group) createTask.mutate({ group, title: form.get("title"), description: form.get("description"), assignee: form.get("assignee") || null, due_at: form.get("due_at") ? new Date(String(form.get("due_at"))).toISOString() : null }); }}><label className="field"><span>Community</span><select name="group" required defaultValue=""><option value="" disabled>Select community</option>{data.groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><Field name="title" label="Task" required /><label className="field"><span>Assign to</span><select name="assignee" defaultValue=""><option value="">Leadership team</option>{rows(memberships.data).filter((member) => Boolean(member.is_active)).map((member) => <option key={value(member, "member")} value={value(member, "member")}>{value(member, "member_name")}</option>)}</select></label><Field name="due_at" label="Due" type="datetime-local" /><label className="field field--full"><span>Note</span><textarea name="description" rows={2} /></label><Button type="submit" loading={createTask.isPending}>Add task</Button></form>{tasks.data && <div className="stack-list">{rows(tasks.data).slice(0, 5).map((item) => <article key={value(item, "id")}><strong>{value(item, "title")}</strong><Button variant="ghost" disabled={updateTask.isPending || value(item, "status") === "COMPLETE"} onClick={() => updateTask.mutate({ id: value(item, "id"), status: "COMPLETE" })}>{value(item, "status") === "COMPLETE" ? "Complete" : "Mark complete"}</Button></article>)}</div>}<Button variant="ghost" onClick={() => { if (!downloadCsv("community-tasks.csv", rows(tasks.data).map((task) => ({ task: value(task, "title"), status: value(task, "status"), assignee: value(task, "assignee_name"), due: value(task, "due_at") })))) toast("There are no tasks to export."); }}>Export my community tasks</Button></section>
      <section className="panel"><header className="panel-heading"><div><h2>Meetings and attendance</h2><p>Schedule a community meeting and record its attendance register.</p></div><CalendarDays /></header><form className="form-grid" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const group = String(form.get("group") || ""); if (group) createMeeting.mutate({ group, title: form.get("title"), starts_at: new Date(String(form.get("starts_at"))).toISOString(), location: form.get("location"), agenda: form.get("agenda") }); }}><label className="field"><span>Community</span><select name="group" required defaultValue=""><option value="" disabled>Select community</option>{data.groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><Field name="title" label="Meeting title" required /><Field name="starts_at" label="Starts" type="datetime-local" required /><Field name="location" label="Location" /><label className="field field--full"><span>Agenda</span><textarea name="agenda" rows={2} /></label><Button type="submit" loading={createMeeting.isPending}>Schedule meeting</Button></form>{meetings.data && <><label className="field"><span>Attendance register</span><select value={meetingId} onChange={(event) => setMeetingId(event.target.value)}><option value="">Choose a meeting</option>{rows(meetings.data).map((meeting) => <option key={value(meeting, "id")} value={value(meeting, "id")}>{value(meeting, "title")}</option>)}</select></label>{meetingId && <form className="form-grid" onSubmit={(event) => { event.preventDefault(); const member = String(new FormData(event.currentTarget).get("member") || ""); if (member) markAttendance.mutate({ meeting: meetingId, member }); }}><label className="field"><span>Member present</span><select name="member" required defaultValue=""><option value="" disabled>Select member</option>{rows(memberships.data).filter((member) => Boolean(member.is_active)).map((member) => <option key={value(member, "member")} value={value(member, "member")}>{value(member, "member_name")}</option>)}</select></label><Button type="submit" loading={markAttendance.isPending}>Mark present</Button></form>}{meetingAttendance.data && <SimpleList pending={meetingAttendance.isPending} failure={meetingAttendance.isError ? error(meetingAttendance.error) : ""} rows={rows(meetingAttendance.data)} primary="member_name" secondary="present" empty="No attendance marked for this meeting." />}</>} </section>
    </section>}

    <section className="role-workspace-grid">
      <section className="panel"><header className="panel-heading"><div><h2>Scoped announcement</h2><p>Create a draft for your community or chapel-wide scope. Sending remains an explicit later action.</p></div><Megaphone /></header><form className="form-grid" onSubmit={submitAnnouncement}><Field name="title" label="Title" required /><label className="field"><span>Audience</span><select name="group" defaultValue=""><option value="">All allowed students</option>{data.groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><label className="field field--full"><span>Message</span><textarea name="body" rows={4} required /></label>{createAnnouncement.isError && <p className="form-error">{error(createAnnouncement.error)}</p>}<Button type="submit" loading={createAnnouncement.isPending}>Save draft</Button></form></section>
      <section className="panel"><header className="panel-heading"><div><h2>{leader ? "Community snapshot" : "Report queue"}</h2><p>{leader ? "Your live member and service metrics above are limited to the assigned community." : "Request an export for data within your authorized scope."}</p></div><FileText /></header>{leader ? <EmptyState title="Scoped data, no branch export" description="Leaders cannot export wider chapel data. Use the member register and live community metrics for approved reporting." /> : <form className="form-grid" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); createReport.mutate({ branch: data.branch_id, report_type: form.get("type"), export_format: "CSV", filters: {} }); }}><label className="field"><span>Report</span><select name="type" defaultValue="ATTENDANCE"><option value="MEMBERSHIP">Membership</option><option value="ATTENDANCE">Attendance</option><option value="EVENTS">Events</option><option value="VOLUNTEERS">Volunteers</option></select></label>{createReport.isError && <p className="form-error">{error(createReport.error)}</p>}<Button type="submit" loading={createReport.isPending}>Queue CSV report</Button></form>}</section>
    </section>

    <section className="role-workspace-grid">
      <section className="panel"><header className="panel-heading"><div><h2>Recent announcements</h2><p>Draft and delivery progress in your current scope.</p></div><Megaphone /></header><SimpleList pending={announcements.isPending} failure={announcements.isError ? error(announcements.error) : ""} rows={rows(announcements.data)} primary="title" secondary="status" empty="No announcements have been created yet." /></section>
      <section className="panel"><header className="panel-heading"><div><h2>{chaplain ? "Follow-up queue" : "Duty roster"}</h2><p>{chaplain ? "Chaplain-only pastoral case summaries; student chaplains receive aggregate counts only." : "Volunteer assignments in your authorized scope."}</p></div>{chaplain ? <HeartHandshake /> : <Activity />}</header>{chaplain && user?.role === "student_chaplain" ? <EmptyState title="Safeguarded pastoral access" description="Student Chaplains can coordinate operations without accessing private pastoral cases." /> : <SimpleList pending={chaplain ? followUps.isPending : assignments.isPending} failure={chaplain && followUps.isError ? error(followUps.error) : !chaplain && assignments.isError ? error(assignments.error) : ""} rows={chaplain ? rows(followUps.data) : rows(assignments.data)} primary={chaplain ? "summary" : "role"} secondary={chaplain ? "status" : "status"} empty={chaplain ? "No follow-up cases are open." : "No duty assignments are scheduled."} />}</section>
    </section>
  </>;
}

function SimpleList({ pending, failure, rows: entries, primary, secondary, empty }: { pending: boolean; failure: string; rows: Row[]; primary: string; secondary: string; empty: string }) {
  if (pending) return <LoadingState label="Loading" />;
  if (failure) return <ErrorState description={failure} />;
  if (!entries.length) return <EmptyState title="Nothing to show" description={empty} />;
  return <div className="stack-list">{entries.slice(0, 6).map((entry) => <article key={value(entry, "id")}><strong>{value(entry, primary) || "Untitled record"}</strong><Badge>{value(entry, secondary).replaceAll("_", " ") || "Recorded"}</Badge></article>)}</div>;
}
