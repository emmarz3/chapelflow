import { ProfilePhotoEditor } from "./profile-photo";
import QRCode from "qrcode";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Camera,
  CheckCircle2,
  QrCode,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, ErrorState, LoadingState, PageHeader, useToast } from "../components/ui";
import { attendanceService, authService, notificationService, studentContentService } from "../services/chapelflow";
import { useAuth } from "./auth-context";
import { isStudentMember } from "../lib/permissions";

function displayDate(value?: string | null) {
  if (!value) return "Time will be confirmed by the chapel.";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Time will be confirmed by the chapel."
    : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function StudentJoinCommunityPage() {
  const toast = useToast();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["student-join-requests"], queryFn: async () => (await studentContentService.joinRequests()).data });
  const request = useMutation({ mutationFn: ({ group, message }: { group: string; message: string }) => studentContentService.requestJoin(group, message), onSuccess: () => { toast("Join request sent to the community leader."); void client.invalidateQueries({ queryKey: ["student-join-requests"] }); } });
  if (query.isPending) return <LoadingState label="Loading chapel communities" />;
  if (query.isError) return <ErrorState description={query.error.message} onRetry={() => void query.refetch()} />;
  const { groups, memberships, current_fellowship: currentFellowship, requests } = query.data;
  const fellowships = groups.filter((group) => group.type === "FELLOWSHIP");
  const units = groups.filter((group) => group.type === "UNIT");
  const activeGroupIds = new Set(memberships.map((membership) => membership.id));
  const requestByGroup = new Map(requests.map((item) => [item.group_id, item]));
  const activeFellowship = memberships.find((membership) => membership.type === "FELLOWSHIP");
  const pendingFellowship = requests.find((item) => item.type === "FELLOWSHIP" && item.status === "PENDING");
  const currentFellowshipId = currentFellowship?.id ?? activeFellowship?.id;
  const selectedFellowshipId = currentFellowshipId ?? pendingFellowship?.group_id;
  const fellowshipLockMessage = selectedFellowshipId
    ? "You can join one Fellowship. Your Chapel Unit choices stay open separately."
    : "";
  const sendRequest = (group: string, message: string) => { request.reset(); request.mutate({ group, message }); };

  return <div className="student-workspace student-join-community">
    <PageHeader eyebrow="Chapel communities" title="Find your communities" description="Choose a Fellowship and Chapel Units through separate request paths. You can belong to a Fellowship and join Units too; each request goes to that community’s leaders." />
    <JoinPathSection title="Fellowships" description="Choose one Fellowship. Your Chapel Unit choices are independent." empty="There are no active Fellowships available right now." groups={fellowships} requestByGroup={requestByGroup} activeGroupIds={activeGroupIds} currentFellowshipId={currentFellowshipId} selectedFellowshipId={selectedFellowshipId} lockMessage={fellowshipLockMessage} pendingGroupId={request.variables?.group} failedGroupId={request.isError ? request.variables?.group : undefined} requestPending={request.isPending} requestError={request.isError ? request.error.message : ""} onRequest={sendRequest} />
    <JoinPathSection title="Chapel Units" description="Units have their own join path, so you can request a Unit even when you belong to a Fellowship." empty="There are no active Chapel Units available right now." groups={units} requestByGroup={requestByGroup} activeGroupIds={activeGroupIds} pendingGroupId={request.variables?.group} failedGroupId={request.isError ? request.variables?.group : undefined} requestPending={request.isPending} requestError={request.isError ? request.error.message : ""} onRequest={sendRequest} />
    <section className="panel"><header className="panel-heading"><div><h2>Your requests</h2><p>Each community leader reviews requests for their own Fellowship or Unit.</p></div></header>{requests.length ? <div className="stack-list">{requests.map((item) => <article key={item.id}><div><strong>{item.group}</strong><small>{item.type === "FELLOWSHIP" ? "Fellowship" : "Chapel Unit"}</small></div><Badge tone={item.status === "APPROVED" ? "success" : item.status === "REJECTED" ? "danger" : "warning"}>{item.status.toLowerCase()}</Badge></article>)}</div> : <p className="empty-copy">You have not sent a join request.</p>}</section>
  </div>;
}

type JoinGroup = { id: string; name: string; type: "FELLOWSHIP" | "UNIT"; description: string };
type JoinRequest = { id: string; group_id: string; group: string; type: "FELLOWSHIP" | "UNIT"; status: "PENDING" | "APPROVED" | "REJECTED"; message: string; requested_at: string };

function JoinPathSection({ title, description, empty, groups, requestByGroup, activeGroupIds, currentFellowshipId, selectedFellowshipId, lockMessage, pendingGroupId, failedGroupId, requestPending, requestError, onRequest }: {
  title: string;
  description: string;
  empty: string;
  groups: JoinGroup[];
  requestByGroup: Map<string, JoinRequest>;
  activeGroupIds: Set<string>;
  currentFellowshipId?: string;
  selectedFellowshipId?: string;
  lockMessage?: string;
  pendingGroupId?: string;
  failedGroupId?: string;
  requestPending: boolean;
  requestError: string;
  onRequest: (group: string, message: string) => void;
}) {
  return <section className="student-join-path">
    <header className="student-join-path__heading"><div><p className="eyebrow">{title === "Fellowships" ? "Belong together" : "Serve together"}</p><h2>{title}</h2><p>{description}</p></div><span>{groups.length} {groups.length === 1 ? "group" : "groups"}</span></header>
    {groups.length ? <div className="student-join-path__grid">{groups.map((group) => {
      const groupRequest = requestByGroup.get(group.id);
      const isMember = activeGroupIds.has(group.id) || (group.type === "FELLOWSHIP" && currentFellowshipId === group.id);
      const isSelectedPending = groupRequest?.status === "PENDING";
      const isLocked = group.type === "FELLOWSHIP" && Boolean(selectedFellowshipId) && selectedFellowshipId !== group.id;
      const isSubmitting = requestPending && pendingGroupId === group.id;
      return <article className="panel student-join-group" key={group.id}>
        <header><div><p className="eyebrow">{group.type === "FELLOWSHIP" ? "Fellowship" : "Chapel Unit"}</p><h3>{group.name}</h3></div>{isMember ? <Badge tone="success">Member</Badge> : groupRequest && <Badge tone={groupRequest.status === "REJECTED" ? "danger" : groupRequest.status === "APPROVED" ? "success" : "warning"}>{groupRequest.status === "PENDING" ? "Request pending" : groupRequest.status.toLowerCase()}</Badge>}</header>
        <p>{group.description || `Connect, grow, and serve with the ${group.type === "FELLOWSHIP" ? "fellowship" : "unit"}.`}</p>
        {isLocked ? <p className="student-join-group__notice">{lockMessage}</p> : isMember ? <p className="student-join-group__notice">You are already part of this community. Its updates are available from your Communities page.</p> : isSelectedPending ? <p className="student-join-group__notice">Your request is with the community leaders. You can still request a {group.type === "FELLOWSHIP" ? "Chapel Unit" : "Fellowship"} separately.</p> : <form className="student-join-group__form" onSubmit={(event) => { event.preventDefault(); onRequest(group.id, String(new FormData(event.currentTarget).get("message") || "")); }}>
          <label className="field"><span>Optional note to the leaders</span><textarea name="message" rows={2} maxLength={500} /></label>
          {requestError && failedGroupId === group.id && <p className="form-error" role="alert">{requestError}</p>}
          <Button type="submit" loading={isSubmitting} disabled={requestPending && !isSubmitting}>{groupRequest?.status === "REJECTED" || groupRequest?.status === "APPROVED" ? "Request again" : "Request to join"}</Button>
        </form>}
      </article>;
    })}</div> : <div className="student-join-path__empty">{empty}</div>}
  </section>;
}

export function StudentAttendanceHistoryPage() {
  const history = useQuery({ queryKey: ["attendance-history", "me"], queryFn: async () => (await attendanceService.history()).data });
  if (history.isPending) return <LoadingState label="Loading your attendance history" />;
  if (history.isError) return <ErrorState description={history.error.message} onRetry={() => void history.refetch()} />;
  return <><PageHeader eyebrow="Personal record" title="My attendance" description="This is your private chapel-service attendance history." /><section className="panel student-history-panel">{history.data.length ? history.data.map((record) => <article key={`${record.recorded_at}-${record.title}`}><CheckCircle2 /><div><strong>{record.title}</strong><small>{displayDate(record.recorded_at)}</small></div><Badge tone="success">{record.status}</Badge></article>) : <p className="empty-copy">You have no completed attendance records yet.</p>}</section></>;
}

export function StudentNotificationsPage() {
  const client = useQueryClient();
  const notifications = useInfiniteQuery({
    queryKey: ["notifications", "all"],
    initialPageParam: 1,
    queryFn: async ({ pageParam }) => (await notificationService.list(pageParam)).data,
    getNextPageParam: (lastPage, pages) => lastPage.hasMore ? pages.length + 1 : undefined,
  });
  const markRead = useMutation({ mutationFn: notificationService.markRead, onSuccess: () => {
    void client.invalidateQueries({ queryKey: ["notifications"] });
    void client.invalidateQueries({ queryKey: ["notification-unread-count"] });
  } });
  if (notifications.isPending) return <LoadingState label="Loading your notifications" />;
  if (notifications.isError) return <ErrorState description={notifications.error.message} onRetry={() => void notifications.refetch()} />;
  const items = notifications.data.pages.flatMap((page) => page.items);
  return <><PageHeader eyebrow="Personal updates" title="Notifications" description="Updates sent to your ChapelFlow account and assigned communities." actions={<Link className="button button--secondary" to="/app/notification-settings">Notification settings</Link>} /><section className="panel student-history-panel">{items.length ? items.map((item) => <article key={item.id}><Bell /><div><Link to={item.href || "/app"} onClick={() => { if (!item.read_at) markRead.mutate(item.id); }}><strong>{item.title}</strong></Link><small>{item.body}</small><small>{displayDate(item.created_at)}</small></div>{!item.read_at && <button className="text-link" disabled={markRead.isPending} onClick={() => markRead.mutate(item.id)}>Mark read</button>}</article>) : <p className="empty-copy">You have no notifications.</p>}{notifications.hasNextPage && <Button type="button" variant="secondary" loading={notifications.isFetchingNextPage} onClick={() => void notifications.fetchNextPage()}>Load more</Button>}</section></>;
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
    if (!current || password.length < 8) {
      setNotice("Enter your current password and a new password with at least 8 characters.");
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
  return <><PageHeader eyebrow="Personal account" title="Profile and security" description="Your academic identity is protected by the chapel office." /><ProfilePhotoEditor /><div className="student-content-grid"><section className="panel"><header className="panel-heading"><div><h2>Your account</h2><p>Contact details shown to ChapelFlow.</p></div></header><dl className="student-profile-list"><div><dt>Name</dt><dd>{user?.name}</dd></div><div><dt>Email</dt><dd>{profileEmail}</dd></div><div><dt>Phone</dt><dd>{profile.data.phone_number || "Not recorded"}</dd></div><div><dt>Role</dt><dd>Student</dd></div></dl><p className="empty-copy">Use Edit profile to change your contact and emergency details. Matric number, programme, department, level, roles, and attendance records are protected. Contact the chapel office to correct them.</p></section><section className="panel"><header className="panel-heading"><div><h2>Change password</h2><p>Use a unique password you do not reuse elsewhere.</p></div></header><form className="student-password-form" onSubmit={(event) => void changePassword(event)}><label>Current password<input name="current" type="password" autoComplete="current-password" /></label><label>New password<input name="password" type="password" autoComplete="new-password" minLength={8} /></label>{notice && <p className="form-note">{notice}</p>}<button className="button button--primary" disabled={saving}>{saving ? "Saving…" : "Update password"}</button></form></section></div></>;
}
