import {
  CalendarHeart,
  Coins,
  HandHeart,
  HeartHandshake,
  Plus,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  Modal,
  PageHeader,
  useToast,
} from "../components/ui";
import { ApiError } from "../lib/api";
import { hasPermission, useAuth } from "./auth-context";
import {
  careService,
  financeService,
  isAssignableVolunteer,
  memberService,
  queryKeys,
  volunteerService,
} from "../services/chapelflow";

function message(error: unknown) {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : "The request could not be completed.";
}

function naira(value: string) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function localDateTimeInput(value: Date) {
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <article className="metric-card"><small>{label}</small><strong>{value}</strong><p>{detail}</p></article>;
}

export function FinanceWorkspacePage() {
  const client = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const dashboard = useQuery({ queryKey: queryKeys.financeDashboard(), queryFn: async () => (await financeService.dashboard()).data });
  const giving = useQuery({ queryKey: ["finance-giving"], queryFn: financeService.giving });
  const categories = useQuery({ queryKey: ["finance-categories"], queryFn: financeService.categories });
  const record = useMutation({
    mutationFn: financeService.recordGiving,
    onSuccess: () => {
      toast("Giving record saved.");
      setOpen(false);
      void client.invalidateQueries({ queryKey: queryKeys.financeDashboard() });
      void client.invalidateQueries({ queryKey: ["finance-giving"] });
    },
  });
  if (dashboard.isPending) return <LoadingState label="Loading financial overview" />;
  if (dashboard.isError) return <ErrorState description={message(dashboard.error)} onRetry={() => void dashboard.refetch()} />;
  const summary = dashboard.data;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    record.mutate({
      category: String(form.get("category")),
      amount: Number(form.get("amount")),
      source: String(form.get("source")),
      note: String(form.get("note") || ""),
    });
  }
  return <>
    <PageHeader eyebrow="Restricted financial workspace" title="Giving and reconciliation" description="Only authorized finance roles can view or record branch financial data." actions={<Button icon={<Plus />} onClick={() => setOpen(true)}>Record giving</Button>} />
    <section className="metric-grid metric-grid--three">
      <Metric label="Giving this period" value={naira(summary.totalGiving)} detail={`${summary.givingCount} confirmed record${summary.givingCount === 1 ? "" : "s"}`} />
      <Metric label="Contributors" value={summary.uniqueContributors} detail="Member names remain out of this overview" />
      <Metric label="Payment exceptions" value={summary.paymentPending + summary.paymentFailed} detail={`${summary.paymentPending} pending · ${summary.paymentFailed} failed`} />
    </section>
    <section className="ministry-workspace-grid">
      <section className="panel">
        <header className="panel-heading"><div><p className="eyebrow">Category ledger</p><h2>Giving allocation</h2><p>Confirmed records only. Payment and donor identifiers are not exposed here.</p></div><Coins /></header>
        {summary.byCategory.length ? <div className="stack-list">{summary.byCategory.map((item) => <article key={item.name}><div><strong>{item.name}</strong><small>Confirmed giving</small></div><strong>{naira(item.total)}</strong></article>)}</div> : <EmptyState title="No confirmed giving yet" description="Category totals will appear after finance records are confirmed." />}
      </section>
      <section className="panel">
        <header className="panel-heading"><div><p className="eyebrow">Pledges</p><h2>Commitment position</h2><p>Use the reconciliation workflow for corrections; confirmed records are immutable.</p></div><ShieldCheck /></header>
        <div className="inventory-ledger"><div><small>Pledged</small><strong>{naira(summary.pledgeSummary.totalPledged)}</strong></div><div><small>Fulfilled</small><strong>{naira(summary.pledgeSummary.totalFulfilled)}</strong></div><div><small>Remaining</small><strong>{naira(summary.pledgeSummary.totalRemaining)}</strong></div></div>
      </section>
    </section>
    <section className="panel">
      <header className="panel-heading"><div><h2>Recent financial records</h2><p>Each result is scope-filtered by the Django finance policy.</p></div></header>
      {giving.isPending ? <LoadingState label="Loading financial records" /> : giving.isError ? <ErrorState description={message(giving.error)} onRetry={() => void giving.refetch()} /> : giving.data.data.length ? <div className="table-wrap"><table><thead><tr><th>Category</th><th>Amount</th><th>Source</th><th>Recorded</th><th>Status</th></tr></thead><tbody>{giving.data.data.map((entry) => <tr key={entry.id}><td><strong>{entry.categoryName}</strong>{entry.note && <small>{entry.note}</small>}</td><td>{naira(entry.amount)}</td><td>{entry.source.replaceAll("_", " ")}</td><td>{entry.givenAt ? new Date(entry.givenAt).toLocaleDateString() : "—"}</td><td><Badge tone={entry.status === "CONFIRMED" ? "success" : "warning"}>{entry.status.toLowerCase()}</Badge></td></tr>)}</tbody></table></div> : <EmptyState title="No financial records" description="Authorized staff can record a confirmed offline giving entry." />}
    </section>
    <Modal open={open} onClose={() => setOpen(false)} title="Record offline giving" description="This creates a confirmed audit-trailed record. Do not use it for gateway payments." footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" form="giving-form" loading={record.isPending}>Save record</Button></>}>
      <form id="giving-form" className="form-grid" onSubmit={submit}>
        <label className="field"><span>Category</span><select name="category" required defaultValue=""><option value="" disabled>Select category</option>{categories.data?.data.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
        <Field name="amount" label="Amount (NGN)" type="number" min="1" step="0.01" required />
        <label className="field"><span>Source</span><select name="source" defaultValue="OFFLINE"><option value="OFFLINE">Offline / cash</option><option value="BANK_TRANSFER">Bank transfer</option><option value="CHECK">Cheque</option></select></label>
        <Field className="field--full" name="note" label="Reference note" maxLength={500} />
        {record.isError && <p className="form-error field--full">{message(record.error)}</p>}
      </form>
    </Modal>
  </>;
}

export function VolunteerWorkspacePage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const [completion, setCompletion] = useState<{ id: string; volunteerName: string } | null>(null);
  const [assignmentOpen, setAssignmentOpen] = useState(false);
  const [shiftStartsAt, setShiftStartsAt] = useState(() => localDateTimeInput(new Date()));
  const [shiftEndsAt, setShiftEndsAt] = useState(() => localDateTimeInput(new Date(Date.now() + 24 * 60 * 60 * 1000)));
  const [shiftEndEdited, setShiftEndEdited] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const profiles = useQuery({
    queryKey: ["volunteer-profiles", user?.branchId],
    queryFn: async () => {
      const first = await volunteerService.profiles({ page: 1, pageSize: 100 });
      const all = [...first.data];
      let page = 2;
      while (all.length < first.total) {
        const response = await volunteerService.profiles({ page, pageSize: 100 });
        all.push(...response.data);
        page += 1;
      }
      return { ...first, data: all, total: all.length };
    },
  });
  const assignments = useQuery({ queryKey: queryKeys.volunteerAssignments(), queryFn: volunteerService.assignments });
  const canUpdate = hasPermission(user, "workers:write");
  const confirm = useMutation({ mutationFn: volunteerService.confirm, onSuccess: () => { toast("Volunteer assignment confirmed."); void client.invalidateQueries({ queryKey: queryKeys.volunteerAssignments() }); } });
  const complete = useMutation({ mutationFn: ({ id, hours }: { id: string; hours: number }) => volunteerService.complete(id, hours), onSuccess: () => { toast("Service hours recorded."); setCompletion(null); void client.invalidateQueries({ queryKey: queryKeys.volunteerAssignments() }); } });
  const createAssignment = useMutation({ mutationFn: volunteerService.createAssignment, onSuccess: () => { toast("Duty assignment created. It is awaiting confirmation."); setAssignmentOpen(false); void client.invalidateQueries({ queryKey: queryKeys.volunteerAssignments() }); } });
  function openAssignmentForm() {
    const start = new Date();
    setShiftStartsAt(localDateTimeInput(start));
    setShiftEndsAt(localDateTimeInput(new Date(start.getTime() + 24 * 60 * 60 * 1000)));
    setShiftEndEdited(false);
    setAssignmentOpen(true);
  }
  function changeShiftStart(value: string) {
    setShiftStartsAt(value);
    if (shiftEndEdited) return;
    const start = new Date(value);
    if (!Number.isNaN(start.getTime()))
      setShiftEndsAt(localDateTimeInput(new Date(start.getTime() + 24 * 60 * 60 * 1000)));
  }
  const members = useQuery({
    queryKey: ["volunteer-profile-members", user?.branchId],
    enabled: profileOpen,
    queryFn: async () => {
      const all = [] as Awaited<ReturnType<typeof memberService.list>>["data"];
      let page = 1;
      let total = 0;
      do {
        const response = await memberService.list({ page, pageSize: 100 });
        all.push(...response.data);
        total = response.total;
        page += 1;
      } while (all.length < total);
      return all;
    },
  });
  const createProfile = useMutation({
    mutationFn: volunteerService.createProfile,
    onSuccess: () => {
      toast("Volunteer profile created.");
      setProfileOpen(false);
      void client.invalidateQueries({ queryKey: ["volunteer-profiles"] });
    },
  });
  if (profiles.isPending || assignments.isPending) return <LoadingState label="Loading volunteer roster" />;
  if (profiles.isError) return <ErrorState description={message(profiles.error)} onRetry={() => void profiles.refetch()} />;
  if (assignments.isError) return <ErrorState description={message(assignments.error)} onRetry={() => void assignments.refetch()} />;
  const active = profiles.data.data.filter(isAssignableVolunteer).length;
  const awaiting = assignments.data.data.filter((assignment) => assignment.status === "PENDING").length;
  return <>
    <PageHeader eyebrow="Volunteer operations" title="Duty roster" description="Assignments, conflicts, availability and service history remain validated by the server." actions={canUpdate ? <><Button variant="secondary" icon={<Plus />} onClick={() => setProfileOpen(true)}>Add volunteer</Button><Button icon={<Plus />} onClick={openAssignmentForm}>Assign duty</Button></> : undefined} />
    <section className="metric-grid metric-grid--three"><Metric label="Active volunteers" value={active} detail="Approved service profiles" /><Metric label="Assignments awaiting response" value={awaiting} detail="Confirm only after availability checks" /><Metric label="Completed assignments" value={assignments.data.data.filter((assignment) => assignment.status === "COMPLETED").length} detail="Recorded service history" /></section>
    <section className="ministry-workspace-grid">
      <section className="panel"><header className="panel-heading"><div><p className="eyebrow">People ready to serve</p><h2>Volunteer profiles</h2><p>Skills and availability are used to protect roster coverage.</p></div><UsersRound /></header>{profiles.data.data.length ? <div className="stack-list">{profiles.data.data.slice(0, 8).map((profile) => <article key={profile.id}><div><strong>{profile.memberName}</strong><small>{profile.skills || "Skills to be confirmed"}</small></div><Badge tone={profile.isActive ? "success" : "warning"}>{profile.status.toLowerCase()}</Badge></article>)}</div> : <EmptyState title="No volunteer profiles" description="Create approved volunteer profiles before assigning service duties." />}</section>
      <section className="panel"><header className="panel-heading"><div><p className="eyebrow">Roster rules</p><h2>Assignment guardrails</h2><p>The backend rejects conflicts, unavailable windows and cross-branch assignments.</p></div><ShieldCheck /></header><div className="ministry-rule-list"><p>Only authorized teams can create or change assignments.</p><p>Confirmed assignments preserve a response time and service history.</p><p>Completed duties require an hours record.</p></div></section>
    </section>
    <section className="panel"><header className="panel-heading"><div><h2>Current assignments</h2><p>All changes use the controlled assignment lifecycle.</p></div></header>{assignments.data.data.length ? <div className="table-wrap"><table><thead><tr><th>Volunteer</th><th>Duty</th><th>Service</th><th>Status</th><th /></tr></thead><tbody>{assignments.data.data.map((assignment) => <tr key={assignment.id}><td>{assignment.volunteerName}</td><td><strong>{assignment.role.replaceAll("_", " ")}</strong>{assignment.notes && <small>{assignment.notes}</small>}</td><td>{assignment.eventTitle || assignment.groupName || "General duty"}</td><td><Badge tone={assignment.status === "CONFIRMED" || assignment.status === "COMPLETED" ? "success" : assignment.status === "PENDING" ? "warning" : "neutral"}>{assignment.status.toLowerCase()}</Badge></td><td>{canUpdate && assignment.status === "PENDING" && <Button variant="ghost" loading={confirm.isPending} onClick={() => confirm.mutate(assignment.id)}>Confirm</Button>}{canUpdate && assignment.status === "CONFIRMED" && <Button variant="ghost" loading={complete.isPending} onClick={() => setCompletion({ id: assignment.id, volunteerName: assignment.volunteerName })}>Record completion</Button>}</td></tr>)}</tbody></table></div> : <EmptyState title="No assignments scheduled" description="Create a duty assignment after a volunteer and service schedule are ready." />}</section>
    <Modal open={Boolean(completion)} onClose={() => setCompletion(null)} title="Record completed duty" description={completion ? `Record the actual service time for ${completion.volunteerName}.` : ""} footer={<><Button variant="ghost" onClick={() => setCompletion(null)}>Cancel</Button><Button type="submit" form="completion-form" loading={complete.isPending}>Save completion</Button></>}><form id="completion-form" className="form-grid" onSubmit={(event) => { event.preventDefault(); if (!completion) return; const hours = Number(new FormData(event.currentTarget).get("hours")); if (Number.isFinite(hours) && hours > 0) complete.mutate({ id: completion.id, hours }); }}><Field name="hours" label="Actual service hours" type="number" min="0.25" step="0.25" required />{complete.isError && <p className="form-error field--full">{message(complete.error)}</p>}</form></Modal>
    <Modal
      open={assignmentOpen}
      onClose={() => setAssignmentOpen(false)}
      title="Assign volunteer duty"
      description="Set the duty window. The assignment begins pending and grants usher checkpoint access only after confirmation."
      footer={<><Button variant="ghost" onClick={() => setAssignmentOpen(false)}>Cancel</Button><Button type="submit" form="assignment-form" loading={createAssignment.isPending}>Create assignment</Button></>}
    >
      <form id="assignment-form" className="form-grid" onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        const start = new Date(shiftStartsAt);
        const end = new Date(shiftEndsAt);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) {
          toast("Shift end must be after shift start.", "error");
          return;
        }
        createAssignment.mutate({
          volunteer: String(form.get("volunteer")),
          role: String(form.get("role")),
          notes: String(form.get("notes") || ""),
          shift_starts_at: start.toISOString(),
          shift_ends_at: end.toISOString(),
        });
      }}>
        <label className="field field--full"><span>Volunteer</span><select name="volunteer" required defaultValue="" disabled={!profiles.data.data.some(isAssignableVolunteer)}><option value="" disabled>Select an active volunteer</option>{profiles.data.data.filter(isAssignableVolunteer).map((profile) => <option key={profile.id} value={profile.id}>{profile.memberName}</option>)}</select>{!profiles.data.data.some(isAssignableVolunteer) && <EmptyState title="No approved volunteers yet" description="Add a volunteer first." action={<Button type="button" variant="secondary" onClick={() => { setAssignmentOpen(false); setProfileOpen(true); }}>Add a volunteer</Button>} />}</label>
        <label className="field"><span>Duty</span><select name="role" defaultValue="OTHER"><option value="USHER">Usher</option><option value="CHOIR">Choir</option><option value="MEDIA">Media</option><option value="SECURITY">Security</option><option value="TECHNICAL">Technical</option><option value="PROTOCOL">Protocol</option><option value="OTHER">Other</option></select></label>
        <Field name="shift_starts_at" label="Shift starts" type="datetime-local" value={shiftStartsAt} onChange={(event) => changeShiftStart(event.target.value)} required />
        <Field name="shift_ends_at" label="Shift ends" type="datetime-local" value={shiftEndsAt} min={shiftStartsAt} onChange={(event) => { setShiftEndsAt(event.target.value); setShiftEndEdited(true); }} required />
        <Field name="notes" label="Duty note" maxLength={255} />
        {createAssignment.isError && <p className="form-error field--full">{message(createAssignment.error)}</p>}
      </form>
    </Modal>
    <Modal open={profileOpen} onClose={() => setProfileOpen(false)} title="Add volunteer" description="Create a service profile for a registered member." footer={<><Button variant="ghost" onClick={() => setProfileOpen(false)}>Cancel</Button><Button type="submit" form="volunteer-profile-form" loading={createProfile.isPending}>Create profile</Button></>}><form id="volunteer-profile-form" className="form-grid" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); createProfile.mutate({ member: String(form.get("member")), skills: String(form.get("skills") || ""), availabilityNotes: String(form.get("availability") || "") }); }}><label className="field field--full"><span>Member</span><select name="member" required defaultValue=""><option value="" disabled>{members.isPending ? "Loading registered members…" : "Select a member"}</option>{(members.data || []).map((member) => { const existingProfile = profiles.data.data.some((profile) => profile.memberId === member.id); return <option key={member.id} value={member.id} disabled={existingProfile}>{member.name} · {member.identifier || member.email}{existingProfile ? " · already a volunteer" : ""}</option>; })}</select></label><Field name="skills" label="Skills" placeholder="Ushering, media, sound" /><Field name="availability" label="Availability" placeholder="e.g. Sunday mornings" />{members.isError && <p className="form-error field--full">{message(members.error)}</p>}{createProfile.isError && <p className="form-error field--full">{message(createProfile.error)}</p>}</form></Modal>
  </>;
}

export function CareWorkspacePage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const [prayerOpen, setPrayerOpen] = useState(false);
  const [counsellingOpen, setCounsellingOpen] = useState(false);
  const [testimonyOpen, setTestimonyOpen] = useState(false);
  const [rejectingTestimony, setRejectingTestimony] = useState<string | null>(null);
  const [editingCase, setEditingCase] = useState<string | null>(null);
  const prayers = useQuery({ queryKey: ["care-prayers"], queryFn: careService.prayers });
  const cases = useQuery({ queryKey: ["care-cases"], queryFn: careService.counsellingRequests });
  const testimonies = useQuery({ queryKey: ["care-testimonies"], queryFn: careService.testimonies });
  const requestPrayer = useMutation({ mutationFn: careService.submitPrayer, onSuccess: () => { toast("Prayer request submitted securely."); setPrayerOpen(false); void client.invalidateQueries({ queryKey: ["care-prayers"] }); } });
  const requestCounselling = useMutation({ mutationFn: careService.requestCounselling, onSuccess: () => { toast("Counselling request sent to the pastoral team."); setCounsellingOpen(false); void client.invalidateQueries({ queryKey: ["care-cases"] }); } });
  const updateCase = useMutation({ mutationFn: ({ id, status, closureReason }: { id: string; status: string; closureReason?: string }) => careService.updateCounsellingCase(id, { status, closureReason }), onSuccess: () => { toast("Pastoral case updated."); setEditingCase(null); void client.invalidateQueries({ queryKey: ["care-cases"] }); } });
  const submitTestimony = useMutation({ mutationFn: careService.submitTestimony, onSuccess: () => { toast("Testimony submitted for pastoral review."); setTestimonyOpen(false); void client.invalidateQueries({ queryKey: ["care-testimonies"] }); } });
  const approveTestimony = useMutation({ mutationFn: careService.approveTestimony, onSuccess: () => { toast("Testimony approved for sharing."); void client.invalidateQueries({ queryKey: ["care-testimonies"] }); } });
  const rejectTestimony = useMutation({ mutationFn: ({ id, reason }: { id: string; reason: string }) => careService.rejectTestimony(id, reason), onSuccess: () => { toast("Testimony review recorded."); setRejectingTestimony(null); void client.invalidateQueries({ queryKey: ["care-testimonies"] }); } });
  const canReviewCare = ["chaplain", "student_chaplain", "pastor", "chapel_admin", "super_admin"].includes(user?.role ?? "");
  function submitPrayer(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); requestPrayer.mutate({ category: String(form.get("category")), details: String(form.get("details")), privacyLevel: String(form.get("privacyLevel")) as "PRIVATE" | "PASTORAL" }); }
  function submitCounselling(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); requestCounselling.mutate({ summary: String(form.get("summary")), preferredDate: String(form.get("preferredDate") || "") || undefined }); }
  function submitTestimonyForm(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); submitTestimony.mutate({ title: String(form.get("title")), details: String(form.get("details")), consentToPublish: form.get("consentToPublish") === "on" }); }
  return <>
    <PageHeader eyebrow={canReviewCare ? "Confidential pastoral workspace" : "Private chapel care"} title={canReviewCare ? "Prayer and care queue" : "Prayer and counselling"} description={canReviewCare ? "Sensitive requests are access-logged and remain limited to authorized pastoral staff." : "Ask for prayer or confidential counselling. Your request is never shown in a general community feed."} actions={<><Button variant="secondary" onClick={() => setTestimonyOpen(true)}>Share testimony</Button><Button variant="secondary" icon={<CalendarHeart />} onClick={() => setCounsellingOpen(true)}>Request counselling</Button><Button icon={<Plus />} onClick={() => setPrayerOpen(true)}>Request prayer</Button></>} />
    <section className="ministry-workspace-grid">
      <section className="panel"><header className="panel-heading"><div><p className="eyebrow">Prayer</p><h2>{canReviewCare ? "Requests in your care scope" : "My prayer requests"}</h2><p>Private requests remain private. Wider sharing always requires pastoral review and consent.</p></div><HandHeart /></header>{prayers.isPending ? <LoadingState label="Loading prayer requests" /> : prayers.isError ? <ErrorState description={message(prayers.error)} onRetry={() => void prayers.refetch()} /> : prayers.data.data.length ? <div className="stack-list">{prayers.data.data.map((prayer) => <article key={prayer.id}><div><strong>{prayer.category.replaceAll("_", " ")}</strong><small>{prayer.details}</small></div><span><Badge tone={prayer.privacyLevel === "PRIVATE" ? "purple" : "warning"}>{prayer.privacyLevel.toLowerCase()}</Badge><Badge tone={prayer.status === "ANSWERED" || prayer.status === "CLOSED" ? "success" : "neutral"}>{prayer.status.toLowerCase()}</Badge></span></article>)}</div> : <EmptyState title="No prayer requests yet" description="Use “Request prayer” when you would like the chapel team to stand with you." />}</section>
      <section className="panel"><header className="panel-heading"><div><p className="eyebrow">Counselling</p><h2>{canReviewCare ? "Pastoral follow-up queue" : "My counselling requests"}</h2><p>Requests create a confidential pastoral case, not a public appointment entry.</p></div><HeartHandshake /></header>{cases.isPending ? <LoadingState label="Loading counselling requests" /> : cases.isError ? <ErrorState description={message(cases.error)} onRetry={() => void cases.refetch()} /> : cases.data.data.length ? <div className="stack-list">{cases.data.data.map((careCase) => <article key={careCase.id}><div><strong>{careCase.category.replaceAll("_", " ")}</strong><small>{canReviewCare ? careCase.summary : "Your confidential request is with the pastoral team."}</small></div><span><Badge tone={careCase.priority === "URGENT" || careCase.priority === "HIGH" ? "danger" : "warning"}>{careCase.status.toLowerCase()}</Badge>{canReviewCare && careCase.status !== "CLOSED" && <Button variant="ghost" onClick={() => setEditingCase(careCase.id)}>Update case</Button>}</span></article>)}</div> : <EmptyState title="No counselling requests" description="A counselling request is shared only with authorized pastoral staff." />}</section>
    </section>
    <section className="panel"><header className="panel-heading"><div><p className="eyebrow">Testimony moderation</p><h2>{canReviewCare ? "Review queue" : "My testimony submissions"}</h2><p>Nothing is published automatically. Pastoral approval and the member’s explicit consent are both required.</p></div><HeartHandshake /></header>{testimonies.isPending ? <LoadingState label="Loading testimony submissions" /> : testimonies.isError ? <ErrorState description={message(testimonies.error)} onRetry={() => void testimonies.refetch()} /> : testimonies.data.data.length ? <div className="stack-list">{testimonies.data.data.map((testimony) => <article key={testimony.id}><div><strong>{testimony.title}</strong><small>{canReviewCare ? testimony.details : testimony.status === "REJECTED" ? testimony.rejectionReason || "This submission was not approved." : "Your submission is awaiting pastoral review."}</small></div><span><Badge tone={testimony.status === "APPROVED" ? "success" : testimony.status === "REJECTED" ? "danger" : "warning"}>{testimony.status.toLowerCase()}</Badge>{canReviewCare && testimony.status === "PENDING" && <><Button variant="ghost" loading={approveTestimony.isPending} onClick={() => approveTestimony.mutate(testimony.id)}>Approve</Button><Button variant="ghost" onClick={() => setRejectingTestimony(testimony.id)}>Reject</Button></>}</span></article>)}</div> : <EmptyState title="No testimony submissions" description="Share an answer to prayer when you are ready; pastoral review protects your story." />}</section>
    <Modal open={prayerOpen} onClose={() => setPrayerOpen(false)} title="Request prayer" description="Choose private for you and assigned pastoral staff, or pastoral for the authorized chapel care team." footer={<><Button variant="ghost" onClick={() => setPrayerOpen(false)}>Cancel</Button><Button type="submit" form="prayer-request-form" loading={requestPrayer.isPending}>Submit request</Button></>}><form id="prayer-request-form" className="form-grid" onSubmit={submitPrayer}><label className="field"><span>Category</span><select name="category" defaultValue="OTHER"><option value="HEALING">Healing</option><option value="FAMILY">Family</option><option value="FINANCIAL">Financial</option><option value="SPIRITUAL">Spiritual growth</option><option value="THANKSGIVING">Thanksgiving</option><option value="OTHER">Other</option></select></label><label className="field"><span>Privacy</span><select name="privacyLevel" defaultValue="PRIVATE"><option value="PRIVATE">Private</option><option value="PASTORAL">Pastoral team</option></select></label><label className="field field--full"><span>How can we pray?</span><textarea name="details" rows={5} required /></label>{requestPrayer.isError && <p className="form-error field--full">{message(requestPrayer.error)}</p>}</form></Modal>
    <Modal open={counsellingOpen} onClose={() => setCounsellingOpen(false)} title="Request counselling" description="Describe what support you need. A pastoral leader will arrange the next safe step with you." footer={<><Button variant="ghost" onClick={() => setCounsellingOpen(false)}>Cancel</Button><Button type="submit" form="counselling-request-form" loading={requestCounselling.isPending}>Send confidential request</Button></>}><form id="counselling-request-form" className="form-grid" onSubmit={submitCounselling}><Field name="preferredDate" label="Preferred follow-up date" type="date" /><label className="field field--full"><span>What support do you need?</span><textarea name="summary" rows={5} required /></label>{requestCounselling.isError && <p className="form-error field--full">{message(requestCounselling.error)}</p>}</form></Modal>
    <Modal open={Boolean(editingCase)} onClose={() => setEditingCase(null)} title="Update pastoral case" description="Status changes are audit-trailed. Closing a case requires a pastoral reason." footer={<><Button variant="ghost" onClick={() => setEditingCase(null)}>Cancel</Button><Button type="submit" form="pastoral-case-form" loading={updateCase.isPending}>Save update</Button></>}><form id="pastoral-case-form" className="form-grid" onSubmit={(event) => { event.preventDefault(); if (!editingCase) return; const form = new FormData(event.currentTarget); const status = String(form.get("status")); updateCase.mutate({ id: editingCase, status, closureReason: String(form.get("closureReason") || "") }); }}><label className="field"><span>Status</span><select name="status" defaultValue="IN_PROGRESS"><option value="OPEN">Open</option><option value="IN_PROGRESS">In progress</option><option value="FOLLOW_UP">Follow up</option><option value="RESOLVED">Resolved</option><option value="CLOSED">Closed</option></select></label><label className="field field--full"><span>Closure reason (required when closing)</span><textarea name="closureReason" rows={3} /></label>{updateCase.isError && <p className="form-error field--full">{message(updateCase.error)}</p>}</form></Modal>
    <Modal open={testimonyOpen} onClose={() => setTestimonyOpen(false)} title="Share a testimony" description="Your testimony remains private unless you tick consent and a pastoral reviewer approves it." footer={<><Button variant="ghost" onClick={() => setTestimonyOpen(false)}>Cancel</Button><Button type="submit" form="testimony-form" loading={submitTestimony.isPending}>Submit for review</Button></>}><form id="testimony-form" className="form-grid" onSubmit={submitTestimonyForm}><Field className="field--full" name="title" label="Short title" maxLength={180} required /><label className="field field--full"><span>Your testimony</span><textarea name="details" rows={5} required /></label><label className="field field--full checkbox-field"><input name="consentToPublish" type="checkbox" /><span>I consent to this testimony being shared only after pastoral approval.</span></label>{submitTestimony.isError && <p className="form-error field--full">{message(submitTestimony.error)}</p>}</form></Modal>
    <Modal open={Boolean(rejectingTestimony)} onClose={() => setRejectingTestimony(null)} title="Decline testimony" description="Give a clear pastoral reason. It is shown only to the member who submitted it." footer={<><Button variant="ghost" onClick={() => setRejectingTestimony(null)}>Cancel</Button><Button type="submit" form="testimony-rejection-form" loading={rejectTestimony.isPending}>Record decision</Button></>}><form id="testimony-rejection-form" className="form-grid" onSubmit={(event) => { event.preventDefault(); if (!rejectingTestimony) return; const reason = String(new FormData(event.currentTarget).get("reason") || "").trim(); if (reason) rejectTestimony.mutate({ id: rejectingTestimony, reason }); }}><label className="field field--full"><span>Reason</span><textarea name="reason" rows={4} required /></label>{rejectTestimony.isError && <p className="form-error field--full">{message(rejectTestimony.error)}</p>}</form></Modal>
  </>;
}
