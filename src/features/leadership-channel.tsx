import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "./auth-context";

type Group = {
  id: string; name: string; type: string; branch_id: string; branch_name: string;
  member_count: number; pending_count: number; latest_activity: string | null;
};
type Activity = {
  id: string; name: string; type: string; branch_name: string;
  member_count: number; pending_count: number;
  messages: { id: string; body: string; author: string; created_at: string }[];
  announcements: { id: string; title: string; body: string; published_at: string }[];
  meetings: { id: string; title: string; starts_at: string; location: string }[];
  resources: { id: string; title: string; url: string }[];
  pending_requests: { id: string; name: string; requested_at: string }[];
};
type Reply = { id: string; author: string; body: string; created_at: string };
type Delivery = {
  id: string; recipient_name: string; read_at: string | null; acknowledged_at: string | null;
  delivery_status: string; replies: Reply[];
};
type Notice = {
  id: string; title: string; body: string; audience: string; branch_id: string;
  branch_name: string; sender: string; created_at: string; target_group_ids: string[];
  recipient_count: number; read_at: string | null; acknowledged_at: string | null;
  deliveries?: Delivery[];
};
const stamp = (value: string | null) => value ? new Date(value).toLocaleString() : "—";
const message = (error: unknown) => error instanceof Error ? error.message : "Please try again.";

function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = async () => {
    setLoading(true);
    try {
      const response = await api.get<{ data: T }>(path);
      setData(response.data); setError("");
    } catch (cause) { setError(message(cause)); }
    finally { setLoading(false); }
  };
  useEffect(() => { void reload(); }, [path]);
  return { data, error, loading, reload };
}

export function CommunityOversightPage() {
  const { groupId } = useParams();
  const list = useLoad<Group[]>("/leadership-channel/oversight/");
  const detail = useLoad<Activity>(groupId ? `/leadership-channel/oversight/${encodeURIComponent(groupId)}/` : "/leadership-channel/oversight/");
  if (groupId) return (
    <main className="leadership-page">
      <Link to="/app/community-oversight">← All communities</Link>
      <h1>{detail.data?.name || "Community activity"}</h1>
      {detail.loading && <p>Loading activity…</p>}
      {detail.error && <p role="alert">{detail.error}</p>}
      {detail.data && <>
        <p>{detail.data.branch_name} · {detail.data.member_count} members · {detail.data.pending_count} pending requests</p>
        <section className="panel"><h2>Recent chat</h2>
          {detail.data.messages.length ? detail.data.messages.map(row => <article key={row.id}><strong>{row.author}</strong> <small>{stamp(row.created_at)}</small><p>{row.body}</p></article>) : <p>No messages yet.</p>}
        </section>
        <section className="panel"><h2>Announcements</h2>
          {detail.data.announcements.length ? detail.data.announcements.map(row => <article key={row.id}><strong>{row.title}</strong><p>{row.body}</p><small>{stamp(row.published_at)}</small></article>) : <p>No announcements yet.</p>}
        </section>
        <section className="panel"><h2>Meetings</h2>
          {detail.data.meetings.length ? detail.data.meetings.map(row => <p key={row.id}>{row.title} · {stamp(row.starts_at)} · {row.location}</p>) : <p>No meetings yet.</p>}
        </section>
        <section className="panel"><h2>Resources</h2>
          {detail.data.resources.length ? detail.data.resources.map(row => <p key={row.id}><a href={row.url} target="_blank" rel="noopener noreferrer">{row.title}</a></p>) : <p>No resources yet.</p>}
        </section>
        <section className="panel"><h2>Pending join requests</h2>
          {detail.data.pending_requests.length ? detail.data.pending_requests.map(row => <p key={row.id}>{row.name} · {stamp(row.requested_at)}</p>) : <p>No pending requests.</p>}
        </section>
      </>}
    </main>
  );
  return <main className="leadership-page">
    <h1>Community oversight</h1>
    <p>Read-only activity across the units and fellowships in your scope. Community leaders retain posting and membership controls.</p>
    {list.loading && <p>Loading communities…</p>}
    {list.error && <p role="alert">{list.error}</p>}
    <div className="leadership-grid">{list.data?.map(group => <Link className="panel" key={group.id} to={`/app/community-oversight/${group.id}`}>
      <small>{group.branch_name} · {group.type === "UNIT" ? "Unit" : "Fellowship"}</small>
      <h2>{group.name}</h2>
      <p>{group.member_count} members · {group.pending_count} pending requests</p>
      <small>Latest chat: {stamp(group.latest_activity)}</small>
    </Link>)}</div>
    {list.data?.length === 0 && <p>No active communities in your scope.</p>}
  </main>;
}

export function LeadershipNoticesPage() {
  const { user } = useAuth();
  const canSend = ["super_admin", "chaplain", "student_chaplain"].includes(user?.role || "");
  const [view, setView] = useState<"inbox" | "sent">(canSend ? "sent" : "inbox");
  const [noticeError, setNoticeError] = useState("");
  const [busy, setBusy] = useState(false);
  const notices = useLoad<Notice[]>(`/leadership-channel/notices/?view=${view}`);
  const groups = useLoad<Group[]>("/leadership-channel/oversight/");
  const branches = [...new Map((groups.data || []).map(group => [group.branch_id, group.branch_name])).entries()];
  const [branchId, setBranchId] = useState("");
  const [audience, setAudience] = useState("ALL");
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => { if (!branchId && branches.length) setBranchId(branches[0]![0]); }, [groups.data, branchId]);
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setNoticeError("");
    try {
      await api.post("/leadership-channel/notices/", {
        branch_id: branchId, title: String(data.get("title") || ""),
        body: String(data.get("body") || ""), audience,
        target_group_ids: audience === "SELECTED" ? selected : [],
        email_requested: data.get("email") === "on",
      });
      form.reset(); setSelected([]); setAudience("ALL"); setView("sent");
      await notices.reload();
    } catch (cause) { setNoticeError(message(cause)); }
    finally { setBusy(false); }
  }
  return <main className="leadership-page">
    <h1>Leadership announcements</h1>
    <p>Private instructions for unit and fellowship leaders. These messages never appear in the public announcement feed or student chats.</p>
    <div className="leadership-actions">
      <button className="button button--secondary" onClick={() => setView("inbox")} aria-pressed={view === "inbox"}>Inbox</button>
      {canSend && <button className="button button--secondary" onClick={() => setView("sent")} aria-pressed={view === "sent"}>Sent</button>}
    </div>
    {canSend && <section className="panel">
      <h2>Compose for leaders</h2>
      <form onSubmit={send} className="leadership-form">
        <label>Branch<select value={branchId} onChange={event => { setBranchId(event.target.value); setSelected([]); }} required>
          {branches.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select></label>
        <label>Audience<select value={audience} onChange={event => setAudience(event.target.value)}>
          <option value="ALL">All unit and fellowship leaders</option>
          <option value="UNIT">Unit heads</option>
          <option value="FELLOWSHIP">Fellowship leaders</option>
          <option value="SELECTED">Selected communities</option>
        </select></label>
        {audience === "SELECTED" && <fieldset><legend>Choose communities</legend>
          {groups.data?.filter(group => group.branch_id === branchId).map(group =>
            <label key={group.id}><input type="checkbox" checked={selected.includes(group.id)} onChange={event => setSelected(current => event.target.checked ? [...current, group.id] : current.filter(id => id !== group.id))} /> {group.name}</label>
          )}
        </fieldset>}
        <label>Title<input name="title" maxLength={180} required /></label>
        <label>Message<textarea name="body" rows={5} maxLength={5000} required /></label>
        <label><input type="checkbox" name="email" /> Also email leaders whose notification preferences allow it</label>
        {noticeError && <p role="alert">{noticeError}</p>}
        <button className="button" disabled={busy || !branches.length || (audience === "SELECTED" && !selected.length)}>{busy ? "Sending…" : "Send privately to leaders"}</button>
      </form>
    </section>}
    <section className="panel"><h2>{view === "sent" ? "Sent announcements" : "Leadership inbox"}</h2>
      {notices.loading && <p>Loading…</p>}
      {notices.error && <p role="alert">{notices.error}</p>}
      {notices.data?.map(row => <p key={row.id}><Link to={`/app/leadership-notices/${row.id}`}><strong>{row.title}</strong></Link> · {row.branch_name} · {stamp(row.created_at)}
        {view === "sent" ? ` · ${row.recipient_count} recipients` : row.acknowledged_at ? " · Acknowledged" : row.read_at ? " · Read" : " · Unread"}
      </p>)}
      {notices.data?.length === 0 && <p>No announcements here yet.</p>}
    </section>
  </main>;
}

export function LeadershipNoticePage() {
  const { noticeId } = useParams();
  const notice = useLoad<Notice>(`/leadership-channel/notices/${encodeURIComponent(noticeId || "")}/`);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function acknowledge() {
    if (!noticeId) return;
    setBusy(true);
    try { await api.post(`/leadership-channel/notices/${encodeURIComponent(noticeId)}/`, {}); await notice.reload(); setError(""); }
    catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }
  async function reply(event: FormEvent<HTMLFormElement>, deliveryId?: string) {
    event.preventDefault();
    if (!noticeId || busy) return;
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    setBusy(true);
    try {
      await api.post(`/leadership-channel/notices/${encodeURIComponent(noticeId)}/replies/`, { body, ...(deliveryId ? { delivery_id: deliveryId } : {}) });
      form.reset(); await notice.reload(); setError("");
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }
  return <main className="leadership-page">
    <Link to="/app/leadership-notices">← Leadership announcements</Link>
    {notice.loading && <p>Loading announcement…</p>}
    {notice.error && <p role="alert">{notice.error}</p>}
    {notice.data && <>
      <h1>{notice.data.title}</h1>
      <p>{notice.data.sender} · {notice.data.branch_name} · {stamp(notice.data.created_at)}</p>
      <section className="panel"><p style={{ whiteSpace: "pre-wrap" }}>{notice.data.body}</p></section>
      {notice.data.deliveries?.length === 1 && notice.data.read_at !== null && !notice.data.acknowledged_at &&
        <button className="button" onClick={() => void acknowledge()} disabled={busy}>Acknowledge</button>}
      {error && <p role="alert">{error}</p>}
      <h2>{notice.data.read_at !== null ? "Private conversation" : "Recipients and private replies"}</h2>
      {notice.data.deliveries?.map(delivery => <section className="panel" key={delivery.id}>
        <h3>{delivery.recipient_name}</h3>
        <p>Delivery: {delivery.delivery_status} · Read: {stamp(delivery.read_at)} · Acknowledged: {stamp(delivery.acknowledged_at)}</p>
        {delivery.replies.map(row => <p key={row.id}><strong>{row.author}</strong> · {stamp(row.created_at)}<br />{row.body}</p>)}
        <form onSubmit={event => void reply(event, notice.data?.read_at !== null ? undefined : delivery.id)} className="leadership-form">
          <label>Private reply<textarea name="body" maxLength={2000} rows={3} required /></label>
          <button className="button button--secondary" disabled={busy}>Send reply</button>
        </form>
      </section>)}
    </>}
  </main>;
}
