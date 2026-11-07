import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, EmptyState, ErrorState, LoadingState, Modal, PageHeader, useToast } from "../components/ui";
import { moderationService, type ModerationReason, type ModerationReport, type ModerationStatus, type ModerationTarget } from "../services/chapelflow";
import { useAuth } from "./auth-context";

const reasons: { value: ModerationReason; label: string }[] = [
  { value: "HARASSMENT", label: "Harassment" },
  { value: "BULLYING", label: "Bullying" },
  { value: "SPAM", label: "Spam" },
  { value: "IMPERSONATION", label: "Impersonation" },
  { value: "HATE_SPEECH", label: "Hate speech" },
  { value: "INAPPROPRIATE", label: "Inappropriate content" },
  { value: "PRIVACY", label: "Privacy violation" },
  { value: "OTHER", label: "Other" },
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed. Try again.";
}

export function ReportContentButton({ targetKind, targetId, label = "Report" }: { targetKind: ModerationTarget; targetId: string; label?: string }) {
  const [open, setOpen] = useState(false);
  const toast = useToast();
  const submit = useMutation({
    mutationFn: ({ reason, explanation }: { reason: ModerationReason; explanation: string }) => moderationService.report(targetKind, targetId, reason, explanation),
    onSuccess: () => { setOpen(false); toast("Report sent to the chapel moderation team."); },
  });

  function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    submit.mutate({ reason: String(data.get("reason")) as ModerationReason, explanation: String(data.get("explanation") || "").trim() });
  }

  return <>
    <button type="button" className="button button--ghost" onClick={() => setOpen(true)} aria-label={`${label} content`}><Flag size={16} aria-hidden="true" /> {label}</button>
    <Modal open={open} onClose={() => setOpen(false)} title="Report content" description="Reports are private. The person who posted this will not see your identity." footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button type="submit" form={`report-${targetId}`} loading={submit.isPending}>Send report</Button></>}>
      <form id={`report-${targetId}`} className="form-grid" onSubmit={send}>
        <label className="field field--full"><span>Reason</span><select name="reason" required>{reasons.map((reason) => <option key={reason.value} value={reason.value}>{reason.label}</option>)}</select></label>
        <label className="field field--full"><span>More information (optional)</span><textarea name="explanation" rows={3} maxLength={1000} /></label>
        {submit.isError && <p className="form-error field--full" role="alert">{errorMessage(submit.error)}</p>}
      </form>
    </Modal>
  </>;
}

const moderatorRoles = ["super_admin", "chapel_admin", "chaplain", "student_chaplain", "pastor"];
const statuses: (ModerationStatus | "ALL")[] = ["PENDING", "REVIEWED", "DISMISSED", "ESCALATED", "ALL"];

export function CommunitySafetyPage() {
  const { user } = useAuth();
  const canReview = moderatorRoles.includes(user?.role ?? "");
  const toast = useToast();
  const client = useQueryClient();
  const [status, setStatus] = useState<ModerationStatus | "ALL">("PENDING");
  const [selected, setSelected] = useState<ModerationReport | null>(null);
  const mine = useQuery({ queryKey: ["moderation-mine"], queryFn: async () => (await moderationService.mine()).data });
  const queue = useQuery({ queryKey: ["moderation-queue", status], queryFn: async () => (await moderationService.queue(status)).data, enabled: canReview });
  const act = useMutation({
    mutationFn: ({ report, action, note }: { report: ModerationReport; action: string; note: string }) => moderationService.act(report.id, action, note),
    onSuccess: ({ data }) => {
      setSelected(data);
      toast("Moderation action recorded.");
      void client.invalidateQueries({ queryKey: ["moderation-queue"] });
      void client.invalidateQueries({ queryKey: ["upper-room"] });
    },
  });

  function submitAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    const data = new FormData(event.currentTarget);
    act.mutate({ report: selected, action: String(data.get("action")), note: String(data.get("note") || "").trim() });
  }

  return <>
    <PageHeader eyebrow="Community safety" title="Reports and review" description="Report harmful content and follow the outcome. Authorized chapel staff can review and record actions." />
    <section className="panel"><h2>My reports</h2>{mine.isPending ? <LoadingState label="Loading your reports" /> : mine.isError ? <ErrorState description={errorMessage(mine.error)} onRetry={() => void mine.refetch()} /> : mine.data.length ? <div className="stack-list">{mine.data.map((report) => <article key={report.id}><div><strong>{report.target_kind.replaceAll("_", " ").toLowerCase()} · {report.reason.replaceAll("_", " ").toLowerCase()}</strong><small>Submitted {new Date(report.created_at).toLocaleDateString()}</small></div><span>{report.status.toLowerCase()}</span></article>)}</div> : <EmptyState icon={<ShieldCheck />} title="No reports submitted" description="Use Report beside a post, comment, message, prayer request, or testimony if you need the moderation team to review it." />}</section>
    {canReview && <section className="panel"><header className="panel-heading"><div><p className="eyebrow">Moderator workspace</p><h2>Review queue</h2></div><label className="field"><span>Status</span><select aria-label="Report status" value={status} onChange={(event) => { setStatus(event.target.value as ModerationStatus | "ALL"); setSelected(null); }}>{statuses.map((item) => <option key={item} value={item}>{item.toLowerCase()}</option>)}</select></label></header>
      {queue.isPending ? <LoadingState label="Loading reports" /> : queue.isError ? <ErrorState description={errorMessage(queue.error)} onRetry={() => void queue.refetch()} /> : queue.data.length ? <div className="stack-list">{queue.data.map((report) => <article key={report.id}><div><strong>{report.target_kind.replaceAll("_", " ")} · {report.reason.replaceAll("_", " ")}</strong><small>{report.content_snapshot?.slice(0, 180)} · {new Date(report.created_at).toLocaleString()}</small></div><Button variant="ghost" onClick={() => setSelected(report)}>Review</Button></article>)}</div> : <EmptyState title="No reports in this status" description="New reports will appear here for your chapel branch." />}
    </section>}
    {canReview && <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title="Review report" description="Moderator notes and reporter identity are visible only to authorized reviewers.">
      {selected && <div className="form-grid"><p className="field--full"><strong>Content:</strong> {selected.content_snapshot}</p><p className="field--full"><strong>Reason:</strong> {selected.reason.replaceAll("_", " ")} {selected.explanation && `· ${selected.explanation}`}</p><p className="field--full"><strong>Reporter ID:</strong> {selected.reporter_id || "Unavailable"}</p><p className="field--full"><strong>Assigned moderator:</strong> {selected.assigned_to_id || "Unassigned"}</p><p className="field--full"><strong>Visibility:</strong> {selected.restriction || "Visible"}</p>
        <section className="field--full"><strong>History</strong><ul>{selected.events?.map((entry, index) => <li key={`${entry.created_at}-${index}`}>{entry.action} · {new Date(entry.created_at).toLocaleString()}{entry.note && ` · ${entry.note}`}</li>)}</ul></section>
        <form className="form-grid field--full" onSubmit={submitAction}><label className="field"><span>Action</span><select name="action" required><option value="REVIEW">Mark reviewed</option><option value="DISMISS">Dismiss</option><option value="HIDE">Hide content</option><option value="REMOVE">Remove content</option><option value="RESTORE">Restore content</option><option value="ESCALATE">Escalate</option>{user?.role === "super_admin" && <option value="SUSPEND">Suspend author account</option>}</select></label><label className="field field--full"><span>Moderator note</span><textarea name="note" rows={3} maxLength={2000} placeholder="Required for dismissal, escalation, hide, remove, or suspension" /></label>{act.isError && <p className="form-error field--full" role="alert">{errorMessage(act.error)}</p>}<Button type="submit" loading={act.isPending}>Record action</Button></form>
      </div>}
    </Modal>}
  </>;
}
