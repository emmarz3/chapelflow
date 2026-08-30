import {
  BellRing,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Crown,
  Megaphone,
  MessageSquareText,
  Plus,
  Search,
  Send,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
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
import { isDemoMode } from "../lib/fixtures";
import {
  communityAdminService,
  communityService,
  memberService,
  queryKeys,
} from "../services/chapelflow";
import type {
  CommunityAnnouncement,
  CommunityEvent,
  CommunityMember,
  CommunityMessage,
  CommunitySummary,
  LeadershipDirectoryEntry,
} from "../types/domain";
import { useAuth } from "./auth-context";

function errorMessage(error: unknown) {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : "The request could not be completed.";
}

function communityTypeLabel(type: CommunitySummary["type"]) {
  return type === "campus_fellowship"
    ? "Campus fellowship"
    : type === "hostel_fellowship"
      ? "Hostel fellowship"
      : type === "unit"
        ? "Chapel unit"
        : "Community";
}

export function CommunitiesPage() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: queryKeys.communities(),
    queryFn: async () => (await communityService.mine()).data,
  });
  if (query.isPending) return <LoadingState label="Loading your communities" />;
  if (query.isError)
    return (
      <ErrorState
        description={errorMessage(query.error)}
        onRetry={() => void query.refetch()}
      />
    );
  return (
    <>
      <PageHeader
        eyebrow="Private community workspaces"
        title="My communities"
        description="Announcements, conversations, meetings, and leadership updates from the groups you belong to."
        actions={
          user?.permissions.includes("community:manage") ? (
            <Link
              className="button button--secondary"
              to="/app/admin/communities"
            >
              <ShieldCheck /> Manage communities
            </Link>
          ) : undefined
        }
      />
      {query.data.length ? (
        <div className="community-ledger">
          {query.data.map((community) => (
            <Link
              className="community-ledger__row"
              key={community.id}
              to={`/app/communities/${community.slug}`}
            >
              <span
                className={`community-ledger__mark community-ledger__mark--${community.type}`}
              >
                {community.type === "unit" ? <Users /> : <BellRing />}
              </span>
              <span className="community-ledger__identity">
                <small>{communityTypeLabel(community.type)}</small>
                <strong>{community.name}</strong>
                <span>{community.description}</span>
              </span>
              <span className="community-ledger__status">
                {community.is_leader && <Badge tone="purple">Leadership</Badge>}
                {community.membership_status && (
                  <Badge
                    tone={
                      community.membership_status === "active"
                        ? "success"
                        : "warning"
                    }
                  >
                    {community.membership_status}
                  </Badge>
                )}
              </span>
              <span className="community-ledger__unread">
                <strong>{community.unreadCount ?? 0}</strong>
                <small>unread</small>
              </span>
              <ChevronRight />
            </Link>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Users />}
          title="No community memberships yet"
          description="Your approved chapel unit and fellowship memberships will appear here."
        />
      )}
      <section className="community-directory-link panel">
        <div>
          <small>Chapel organization</small>
          <h2>Meet the current student leadership</h2>
          <p>View unit, fellowship, hostel, and global office assignments.</p>
        </div>
        <Link className="button button--secondary" to="/app/leadership">
          Open leadership directory <ChevronRight />
        </Link>
      </section>
    </>
  );
}

const workspaceTabs = [
  ["overview", "Overview"],
  ["announcements", "Announcements"],
  ["chat", "Chat"],
  ["events", "Events"],
  ["members", "Members"],
  ["leadership", "Leadership"],
] as const;

export function CommunityWorkspacePage() {
  const { slug = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "overview";
  const client = useQueryClient();
  const detail = useQuery({
    queryKey: queryKeys.community(slug),
    queryFn: async () => (await communityService.get(slug)).data,
  });

  useEffect(() => {
    if (isDemoMode || !slug || !detail.data) return;
    const stream = new EventSource(communityService.streamUrl(slug), {
      withCredentials: true,
    });
    const refresh = () => {
      void client.invalidateQueries({ queryKey: queryKeys.community(slug) });
      void client.invalidateQueries({ queryKey: ["community-messages", slug] });
      void client.invalidateQueries({
        queryKey: ["community-announcements", slug],
      });
      void client.invalidateQueries({ queryKey: ["community-events", slug] });
    };
    stream.addEventListener("message.created", refresh);
    stream.addEventListener("announcement.created", refresh);
    stream.addEventListener("event.created", refresh);
    return () => stream.close();
  }, [client, detail.data, slug]);

  if (detail.isPending)
    return <LoadingState label="Opening community workspace" />;
  if (detail.isError)
    return (
      <ErrorState
        description={errorMessage(detail.error)}
        onRetry={() => void detail.refetch()}
      />
    );
  const community = detail.data;
  return (
    <div className="community-workspace">
      <header className="community-hero">
        <div className="community-hero__rail">
          <small>{communityTypeLabel(community.type)}</small>
          <strong>{community.memberCount}</strong>
          <span>approved members</span>
        </div>
        <div>
          <p className="eyebrow">Private ChapelFlow workspace</p>
          <h1>{community.name}</h1>
          <p>{community.description}</p>
          <div className="tag-row">
            {community.access.isLeader && (
              <Badge tone="purple">Leadership workspace</Badge>
            )}
            <Badge tone="success">
              {community.membershipStatus || "oversight"}
            </Badge>
          </div>
        </div>
      </header>
      <nav className="community-tabs" aria-label="Community workspace sections">
        {workspaceTabs.map(([value, label]) => (
          <button
            className={tab === value ? "active" : ""}
            key={value}
            onClick={() =>
              setParams(value === "overview" ? {} : { tab: value })
            }
          >
            {label}
          </button>
        ))}
      </nav>
      {tab === "overview" && <CommunityOverview community={community} />}
      {tab === "announcements" && (
        <AnnouncementsPanel
          slug={slug}
          canManage={community.access.canManage}
        />
      )}
      {tab === "chat" && (
        <CommunityChat slug={slug} canPost={community.access.canPost} />
      )}
      {tab === "events" && (
        <CommunityEventsPanel
          slug={slug}
          canManage={community.access.canManage}
        />
      )}
      {tab === "members" &&
        (community.access.canManage ? (
          <CommunityMembersPanel slug={slug} />
        ) : (
          <EmptyState
            icon={<ShieldCheck />}
            title="Member directory is restricted"
            description="Community leaders manage membership details and approvals."
          />
        ))}
      {tab === "leadership" && (
        <section className="leadership-stack">
          {community.leaders.map((leader) => (
            <article key={`${leader.position}-${leader.name}`}>
              <Crown />
              <div>
                <small>{leader.position}</small>
                <strong>{leader.name}</strong>
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

function CommunityOverview({
  community,
}: {
  community: Awaited<ReturnType<typeof communityService.get>>["data"];
}) {
  return (
    <div className="community-overview-grid">
      <section className="panel community-overview-grid__wide">
        <header className="panel-heading">
          <div>
            <p className="eyebrow">Pinned update</p>
            <h2>
              {community.pinnedAnnouncement?.title || "No pinned announcement"}
            </h2>
          </div>
        </header>
        <p>
          {community.pinnedAnnouncement?.content ||
            "Leaders can pin an important update here for every approved member."}
        </p>
        <Link className="text-link" to="?tab=announcements">
          Open announcements <ChevronRight />
        </Link>
      </section>
      <section className="panel">
        <p className="eyebrow">Next gathering</p>
        {community.nextEvent ? (
          <>
            <h2>{community.nextEvent.title}</h2>
            <p>{new Date(community.nextEvent.starts_at).toLocaleString()}</p>
            <strong>{community.nextEvent.venue}</strong>
          </>
        ) : (
          <EmptyState
            icon={<CalendarDays />}
            title="No meeting scheduled"
            description="The next community event will appear here."
          />
        )}
      </section>
      <section className="panel community-leader-preview">
        <p className="eyebrow">Leadership</p>
        {community.leaders.map((leader) => (
          <div key={`${leader.position}-${leader.name}`}>
            <span>
              <Crown />
            </span>
            <p>
              <small>{leader.position}</small>
              <strong>{leader.name}</strong>
            </p>
          </div>
        ))}
      </section>
    </div>
  );
}

function CommunityChat({ slug, canPost }: { slug: string; canPost: boolean }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["community-messages", slug, search],
    queryFn: async () => (await communityService.messages(slug, search)).data,
  });
  const send = useMutation({
    mutationFn: (body: string) => communityService.sendMessage(slug, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["community-messages", slug] });
    },
  });
  useEffect(() => {
    if (query.data && !isDemoMode) void communityService.markRead(slug);
  }, [query.data, slug]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = String(new FormData(form).get("body") || "").trim();
    if (!body) return;
    send.mutate(body, { onSuccess: () => form.reset() });
  }
  return (
    <section className="community-chat">
      <header>
        <div>
          <h2>Community conversation</h2>
          <p>Visible only to authorized members.</p>
        </div>
        <label className="community-chat__search">
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search messages"
          />
        </label>
      </header>
      <div className="community-chat__messages" aria-live="polite">
        {query.isPending ? (
          <LoadingState label="Loading messages" />
        ) : query.isError ? (
          <ErrorState
            description={errorMessage(query.error)}
            onRetry={() => void query.refetch()}
          />
        ) : query.data.length ? (
          query.data.map((message: CommunityMessage) => (
            <article
              className={
                message.sender_id === user?.id
                  ? "community-message community-message--own"
                  : "community-message"
              }
              key={message.id}
            >
              <span>
                {message.sender_name
                  .split(/\s+/)
                  .slice(0, 2)
                  .map((part) => part[0])
                  .join("")}
              </span>
              <div>
                <header>
                  <strong>{message.sender_name}</strong>
                  <time>
                    {new Date(message.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </header>
                <p>{message.body}</p>
              </div>
            </article>
          ))
        ) : (
          <EmptyState
            icon={<MessageSquareText />}
            title="The conversation is ready"
            description="The first community message will appear here."
          />
        )}
      </div>
      {canPost ? (
        <form className="community-chat__composer" onSubmit={submit}>
          <label>
            <span className="sr-only">Message</span>
            <textarea
              name="body"
              maxLength={4000}
              placeholder="Write a message to the community"
              required
            />
          </label>
          <Button type="submit" icon={<Send />} loading={send.isPending}>
            Send
          </Button>
          {send.isError && (
            <div className="form-error" role="alert">
              {errorMessage(send.error)}
            </div>
          )}
        </form>
      ) : (
        <div className="community-chat__locked">
          <ShieldCheck /> This community is currently leader-broadcast only.
        </div>
      )}
    </section>
  );
}

function AnnouncementsPanel({
  slug,
  canManage,
}: {
  slug: string;
  canManage: boolean;
}) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({
    queryKey: ["community-announcements", slug],
    queryFn: async () => (await communityService.announcements(slug)).data,
  });
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      communityService.createAnnouncement(slug, payload),
    onSuccess: () => {
      setOpen(false);
      toast("Announcement published.");
      void client.invalidateQueries({
        queryKey: ["community-announcements", slug],
      });
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    create.mutate({
      title: values.get("title"),
      content: values.get("content"),
      priority: values.get("priority"),
      pinned: values.get("pinned") === "on",
    });
  }
  return (
    <section className="community-section">
      <header>
        <div>
          <p className="eyebrow">Official channel</p>
          <h2>Announcements</h2>
        </div>
        {canManage && (
          <Button icon={<Megaphone />} onClick={() => setOpen(true)}>
            New announcement
          </Button>
        )}
      </header>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          description={errorMessage(query.error)}
          onRetry={() => void query.refetch()}
        />
      ) : query.data.length ? (
        <div className="announcement-stack">
          {query.data.map((item: CommunityAnnouncement) => (
            <article key={item.id}>
              <div>
                <Badge
                  tone={
                    item.priority === "urgent"
                      ? "danger"
                      : item.priority === "important"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {item.priority}
                </Badge>
                {item.pinned && <Badge tone="purple">Pinned</Badge>}
              </div>
              <h3>{item.title}</h3>
              <p>{item.content}</p>
              <small>
                {item.author_name} ·{" "}
                {new Date(item.published_at).toLocaleString()}
              </small>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Megaphone />}
          title="No announcements yet"
          description="Official community updates will appear here."
        />
      )}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Publish announcement"
        description="Every approved community member will be notified."
      >
        <form className="modal-form" onSubmit={submit}>
          <Field name="title" label="Title" required />
          <label className="field">
            <span>Message</span>
            <textarea name="content" rows={5} maxLength={10000} required />
          </label>
          <label className="field">
            <span>Priority</span>
            <select name="priority">
              <option value="normal">Normal</option>
              <option value="important">Important</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
          <label className="check-label">
            <input name="pinned" type="checkbox" /> Pin this announcement
          </label>
          {create.isError && (
            <div className="form-error">{errorMessage(create.error)}</div>
          )}
          <Button type="submit" loading={create.isPending}>
            Publish announcement
          </Button>
        </form>
      </Modal>
    </section>
  );
}

function CommunityEventsPanel({
  slug,
  canManage,
}: {
  slug: string;
  canManage: boolean;
}) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({
    queryKey: ["community-events", slug],
    queryFn: async () => (await communityService.events(slug)).data,
  });
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      communityService.createEvent(slug, payload),
    onSuccess: () => {
      setOpen(false);
      toast("Community event scheduled.");
      void client.invalidateQueries({ queryKey: ["community-events", slug] });
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      title: data.get("title"),
      description: data.get("description"),
      venue: data.get("venue"),
      startsAt: new Date(String(data.get("startsAt"))).toISOString(),
      endsAt: new Date(String(data.get("endsAt"))).toISOString(),
    });
  }
  return (
    <section className="community-section">
      <header>
        <div>
          <p className="eyebrow">Calendar</p>
          <h2>Meetings and activities</h2>
        </div>
        {canManage && (
          <Button icon={<Plus />} onClick={() => setOpen(true)}>
            Schedule event
          </Button>
        )}
      </header>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState description={errorMessage(query.error)} />
      ) : query.data.length ? (
        <div className="community-event-grid">
          {query.data.map((event: CommunityEvent) => (
            <article key={event.id}>
              <time>
                <strong>
                  {new Date(event.starts_at).toLocaleDateString([], {
                    day: "2-digit",
                  })}
                </strong>
                <span>
                  {new Date(event.starts_at).toLocaleDateString([], {
                    month: "short",
                  })}
                </span>
              </time>
              <div>
                <Badge
                  tone={event.status === "cancelled" ? "danger" : "success"}
                >
                  {event.status}
                </Badge>
                <h3>{event.title}</h3>
                <p>{event.description}</p>
                <small>
                  {new Date(event.starts_at).toLocaleString()} · {event.venue}
                </small>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<CalendarDays />}
          title="No activities scheduled"
          description="Meetings, rehearsals, and fellowship events will appear here."
        />
      )}
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Schedule community event"
      >
        <form className="modal-form" onSubmit={submit}>
          <Field name="title" label="Event title" required />
          <Field name="venue" label="Venue" required />
          <div className="form-grid">
            <Field
              name="startsAt"
              label="Starts"
              type="datetime-local"
              required
            />
            <Field name="endsAt" label="Ends" type="datetime-local" required />
          </div>
          <label className="field">
            <span>Description</span>
            <textarea name="description" rows={4} />
          </label>
          {create.isError && (
            <div className="form-error">{errorMessage(create.error)}</div>
          )}
          <Button type="submit" loading={create.isPending}>
            Schedule event
          </Button>
        </form>
      </Modal>
    </section>
  );
}

function CommunityMembersPanel({ slug }: { slug: string }) {
  const client = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("pending");
  const query = useQuery({
    queryKey: ["community-members", slug, status],
    queryFn: async () => (await communityService.members(slug, status)).data,
  });
  const update = useMutation({
    mutationFn: ({ id, next }: { id: string; next: string }) =>
      communityService.updateMembership(slug, id, next),
    onSuccess: () => {
      toast("Membership updated.");
      void client.invalidateQueries({ queryKey: ["community-members", slug] });
    },
  });
  return (
    <section className="community-section">
      <header>
        <div>
          <p className="eyebrow">Leadership access</p>
          <h2>Community members</h2>
        </div>
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="pending">Pending requests</option>
          <option value="active">Approved members</option>
          <option value="suspended">Suspended</option>
        </select>
      </header>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState description={errorMessage(query.error)} />
      ) : query.data.length ? (
        <div className="community-member-list">
          {query.data.map((member: CommunityMember) => (
            <article key={member.id}>
              <span>
                {member.name
                  .split(/\s+/)
                  .slice(0, 2)
                  .map((part) => part[0])
                  .join("")}
              </span>
              <div>
                <strong>{member.name}</strong>
                <small>
                  {member.identifier || "No student identifier"} ·{" "}
                  {member.programme || "Programme not provided"}
                </small>
              </div>
              <Badge tone={member.status === "active" ? "success" : "warning"}>
                {member.status}
              </Badge>
              {member.status === "pending" && (
                <div>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      update.mutate({ id: member.id, next: "active" })
                    }
                  >
                    Approve
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() =>
                      update.mutate({ id: member.id, next: "rejected" })
                    }
                  >
                    Reject
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<UserCheck />}
          title={`No ${status} memberships`}
          description="Membership records matching this status will appear here."
        />
      )}
    </section>
  );
}

export function LeadershipDirectoryPage() {
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["leadership-directory"],
    queryFn: async () => (await communityService.leadership()).data,
  });
  const entries = useMemo(
    () =>
      query.data?.filter((entry) =>
        `${entry.position} ${entry.leader_name} ${entry.community_name}`
          .toLowerCase()
          .includes(search.toLowerCase()),
      ) ?? [],
    [query.data, search],
  );
  if (query.isPending)
    return <LoadingState label="Loading leadership directory" />;
  if (query.isError)
    return (
      <ErrorState
        description={errorMessage(query.error)}
        onRetry={() => void query.refetch()}
      />
    );
  const grouped = entries.reduce<Record<string, LeadershipDirectoryEntry[]>>(
    (groups, entry) => {
      const key = entry.community_name || "Chapel-wide offices";
      (groups[key] ??= []).push(entry);
      return groups;
    },
    {},
  );
  return (
    <>
      <PageHeader
        eyebrow="Current appointments"
        title="Chapel leadership"
        description="Active offices and community leadership assignments. Private contact and account details are never shown."
        actions={
          <SearchField
            value={search}
            onChange={setSearch}
            placeholder="Search leadership"
          />
        }
      />
      <div className="leadership-directory">
        {Object.entries(grouped).map(([group, leaders]) => (
          <section key={group}>
            <header>
              <small>
                {leaders[0]?.community_type
                  ? communityTypeLabel(leaders[0].community_type)
                  : "Organization"}
              </small>
              <h2>{group}</h2>
            </header>
            {leaders.map((leader: LeadershipDirectoryEntry) => (
              <article key={`${leader.position}-${leader.leader_name}`}>
                <Crown />
                <div>
                  <small>{leader.position}</small>
                  <strong>{leader.leader_name || "Vacant"}</strong>
                </div>
                {leader.leader_name ? (
                  <CheckCircle2 />
                ) : (
                  <Badge tone="warning">Unassigned</Badge>
                )}
              </article>
            ))}
          </section>
        ))}
      </div>
    </>
  );
}

export function CommunityAdminPage() {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("all");
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({
    queryKey: ["admin-communities"],
    queryFn: async () => (await communityAdminService.list()).data,
  });
  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      communityAdminService.create(payload),
    onSuccess: () => {
      setOpen(false);
      toast("Community created.");
      void client.invalidateQueries({ queryKey: ["admin-communities"] });
    },
  });
  const updateStatus = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: "active" | "inactive";
    }) => communityAdminService.update(id, { status }),
    onSuccess: () => {
      toast("Community status updated.");
      void client.invalidateQueries({ queryKey: ["admin-communities"] });
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      name: data.get("name"),
      slug: data.get("slug"),
      type: data.get("type"),
      description: data.get("description"),
      requiresApproval: data.get("requiresApproval") === "on",
      membersCanPost: data.get("membersCanPost") === "on",
      chatEnabled: data.get("chatEnabled") === "on",
    });
  }
  const rows =
    query.data?.filter(
      (community) => filter === "all" || community.type === filter,
    ) ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Super administration"
        title="Community management"
        description="Manage reusable unit and fellowship workspaces, membership rules, and communication settings."
        actions={
          <Button icon={<Plus />} onClick={() => setOpen(true)}>
            Create community
          </Button>
        }
      />
      <div className="admin-community-summary">
        <article>
          <span>
            <Users />
          </span>
          <div>
            <strong>{query.data?.length ?? 0}</strong>
            <small>Communities</small>
          </div>
        </article>
        <article>
          <span>
            <UserCheck />
          </span>
          <div>
            <strong>
              {query.data?.reduce(
                (sum, item) => sum + Number(item.member_count ?? 0),
                0,
              ) ?? 0}
            </strong>
            <small>Approved memberships</small>
          </div>
        </article>
        <article>
          <span>
            <BellRing />
          </span>
          <div>
            <strong>
              {query.data?.reduce(
                (sum, item) => sum + Number(item.pending_count ?? 0),
                0,
              ) ?? 0}
            </strong>
            <small>Pending requests</small>
          </div>
        </article>
      </div>
      <section className="table-panel">
        <header>
          <div className="panel-heading">
            <div>
              <h2>Units and fellowships</h2>
              <p>Database-managed community configuration</p>
            </div>
            <select
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              <option value="all">All types</option>
              <option value="unit">Units</option>
              <option value="campus_fellowship">Campus fellowships</option>
              <option value="hostel_fellowship">Hostel fellowships</option>
            </select>
          </div>
        </header>
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState description={errorMessage(query.error)} />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Community</th>
                <th>Type</th>
                <th>Members</th>
                <th>Pending</th>
                <th>Posting</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((community) => (
                <tr key={community.id}>
                  <td>
                    <strong>{community.name}</strong>
                    <small>/{community.slug}</small>
                  </td>
                  <td>{communityTypeLabel(community.type)}</td>
                  <td>{community.member_count ?? 0}</td>
                  <td>{community.pending_count ?? 0}</td>
                  <td>
                    {community.members_can_post
                      ? "Member chat"
                      : "Broadcast only"}
                  </td>
                  <td>
                    <Badge
                      tone={
                        community.status === "active" ? "success" : "danger"
                      }
                    >
                      {community.status}
                    </Badge>
                  </td>
                  <td>
                    <Button
                      variant="ghost"
                      disabled={updateStatus.isPending}
                      onClick={() =>
                        updateStatus.mutate({
                          id: community.id,
                          status:
                            community.status === "active"
                              ? "inactive"
                              : "active",
                        })
                      }
                    >
                      {community.status === "active"
                        ? "Deactivate"
                        : "Activate"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Create community"
        description="This creates one reusable private workspace and conversation channel."
      >
        <form className="modal-form" onSubmit={submit}>
          <div className="form-grid">
            <Field name="name" label="Community name" required />
            <Field
              name="slug"
              label="URL slug"
              pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
              required
            />
          </div>
          <label className="field">
            <span>Type</span>
            <select name="type">
              <option value="unit">Chapel unit</option>
              <option value="campus_fellowship">Campus fellowship</option>
              <option value="hostel_fellowship">Hostel fellowship</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="field">
            <span>Description</span>
            <textarea name="description" rows={4} />
          </label>
          <label className="check-label">
            <input name="requiresApproval" type="checkbox" defaultChecked />{" "}
            Membership requires approval
          </label>
          <label className="check-label">
            <input name="membersCanPost" type="checkbox" defaultChecked />{" "}
            Members can post in chat
          </label>
          <label className="check-label">
            <input name="chatEnabled" type="checkbox" defaultChecked /> Chat
            enabled
          </label>
          {create.isError && (
            <div className="form-error">{errorMessage(create.error)}</div>
          )}
          <Button type="submit" loading={create.isPending}>
            Create community
          </Button>
        </form>
      </Modal>
    </>
  );
}

export function LeadershipAdminPage() {
  const [assignOpen, setAssignOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [setupPath, setSetupPath] = useState("");
  const client = useQueryClient();
  const toast = useToast();
  const assignments = useQuery({
    queryKey: ["admin-leadership"],
    queryFn: async () => (await communityAdminService.leadership()).data,
  });
  const positions = useQuery({
    queryKey: ["leadership-positions"],
    queryFn: async () => (await communityAdminService.positions()).data,
  });
  const communities = useQuery({
    queryKey: ["admin-communities"],
    queryFn: async () => (await communityAdminService.list()).data,
  });
  const members = useQuery({
    queryKey: ["members", "leadership-assignment"],
    queryFn: async () =>
      (await memberService.list({ page: 1, pageSize: 100, status: "active" }))
        .data,
  });
  const assign = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      communityAdminService.assignLeader(payload),
    onSuccess: () => {
      setAssignOpen(false);
      toast("Leadership assignment updated.");
      void client.invalidateQueries({ queryKey: ["admin-leadership"] });
    },
  });
  const provision = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      communityAdminService.provisionAccount(payload),
    onSuccess: (response) => {
      setSetupPath(response.data.setupPath);
      toast("Leader account provisioned securely.");
    },
  });
  function submitAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    assign.mutate({
      positionId: data.get("positionId"),
      communityId: data.get("communityId") || null,
      userId: data.get("userId") || null,
      assigneeName: data.get("userId") ? null : data.get("assigneeName"),
    });
  }
  function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const globalRole = String(data.get("globalRole") || "");
    provision.mutate({
      username: data.get("username"),
      email: data.get("email"),
      name: data.get("name"),
      primaryRole: "member",
      globalRoles: globalRole ? [globalRole] : [],
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="Super administration"
        title="Leadership and accounts"
        description="Transfer time-bound offices, link leaders to workspaces, and issue single-use account setup links."
        actions={
          <>
            <Button
              variant="secondary"
              icon={<UserCheck />}
              onClick={() => setAccountOpen(true)}
            >
              Provision account
            </Button>
            <Button icon={<Crown />} onClick={() => setAssignOpen(true)}>
              Assign leadership
            </Button>
          </>
        }
      />
      <section className="table-panel">
        <header>
          <div className="panel-heading">
            <div>
              <h2>Leadership assignments</h2>
              <p>Historical assignments remain available after transfer.</p>
            </div>
          </div>
        </header>
        {assignments.isPending ? (
          <LoadingState />
        ) : assignments.isError ? (
          <ErrorState description={errorMessage(assignments.error)} />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Position</th>
                <th>Leader</th>
                <th>Scope</th>
                <th>Started</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {assignments.data.map((item) => (
                <tr key={String(item.id)}>
                  <td>
                    <strong>{String(item.position)}</strong>
                  </td>
                  <td>{String(item.leader_name || "Vacant")}</td>
                  <td>{String(item.community_name || "Chapel-wide")}</td>
                  <td>
                    {new Date(String(item.starts_at)).toLocaleDateString()}
                  </td>
                  <td>
                    <Badge tone={item.active ? "success" : "neutral"}>
                      {item.active ? "Active" : "Ended"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <Modal
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        title="Assign or transfer leadership"
        description="An existing active assignment for this position and scope will end automatically."
      >
        <form className="modal-form" onSubmit={submitAssignment}>
          <label className="field">
            <span>Position</span>
            <select name="positionId" required>
              <option value="">Select position</option>
              {positions.data?.map((position) => (
                <option key={position.id} value={position.id}>
                  {position.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Community scope</span>
            <select name="communityId">
              <option value="">Chapel-wide office</option>
              {communities.data?.map((community) => (
                <option key={community.id} value={community.id}>
                  {community.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Existing ChapelFlow account</span>
            <select name="userId">
              <option value="">Link by name only</option>
              {members.data?.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name} · {member.identifier}
                </option>
              ))}
            </select>
          </label>
          <Field
            name="assigneeName"
            label="Leader's full name (when no account is linked)"
          />
          {assign.isError && (
            <div className="form-error">{errorMessage(assign.error)}</div>
          )}
          <Button type="submit" loading={assign.isPending}>
            Save assignment
          </Button>
        </form>
      </Modal>
      <Modal
        open={accountOpen}
        onClose={() => {
          setAccountOpen(false);
          setSetupPath("");
        }}
        title="Provision leader account"
        description="No password is generated or stored in source code. The setup link works once and expires after 24 hours."
      >
        {setupPath ? (
          <div className="account-setup-result">
            <CheckCircle2 />
            <h3>Account ready for secure setup</h3>
            <p>Share this path through an approved private channel:</p>
            <code>{setupPath}</code>
            <Button
              onClick={() =>
                navigator.clipboard.writeText(
                  `${window.location.origin}${setupPath}`,
                )
              }
            >
              Copy setup link
            </Button>
          </div>
        ) : (
          <form className="modal-form" onSubmit={submitAccount}>
            <Field name="name" label="Full name" required />
            <div className="form-grid">
              <Field name="username" label="Username" required />
              <Field name="email" label="Email" type="email" required />
            </div>
            <label className="field">
              <span>Global office access</span>
              <select name="globalRole">
                <option value="">No global role</option>
                <option value="chaplain">Chaplain</option>
                <option value="student_chaplain">Student Chaplain</option>
                <option value="treasurer">Treasurer</option>
                <option value="chapel_official">Chapel Official</option>
              </select>
            </label>
            {provision.isError && (
              <div className="form-error">{errorMessage(provision.error)}</div>
            )}
            <Button type="submit" loading={provision.isPending}>
              Create secure setup link
            </Button>
          </form>
        )}
      </Modal>
    </>
  );
}
