import type { EventSummary, Member, Permission, Role, User } from "../types/domain";
import { buildDemoUser } from "./permissions";

type Row = Record<string, unknown>;
type Envelope = {
  data: unknown;
  pagination?: { current_page: number; page_size: number; count: number };
};
export type DjangoTransport = (
  path: string,
  init?: RequestInit,
) => Promise<unknown>;

const row = (value: unknown): Row =>
  value && typeof value === "object" ? (value as Row) : {};
const str = (value: unknown) => (value == null ? "" : String(value));
const list = (value: unknown): Row[] =>
  Array.isArray(value) ? value.map(row) : [];
const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});

export class UnsupportedDjangoOperation extends Error {}
function unsupported(message: string): never {
  throw new UnsupportedDjangoOperation(message);
}

function role(value: unknown): Role {
  const roles: Record<string, Role> = {
    SUPER_ADMIN: "super_admin",
    CHAPEL_ADMIN: "chapel_admin",
    CHAPLAIN: "chaplain",
    STUDENT_CHAPLAIN: "student_chaplain",
    UNIT_HEAD: "unit_leader",
    UNIT_LEADER: "unit_leader",
    FELLOWSHIP_LEADER: "fellowship_leader",
    MINISTRY_GROUP_LEADER: "unit_leader",
    ATTENDANCE_USHER: "attendance_usher",
    PASTOR: "pastor",
    VOLUNTEER: "worker",
    MEMBER: "member",
  };
  return roles[str(value).toUpperCase()] ?? "member";
}

function user(value: Row): User {
  const mappedRole = role(value.role);
  const communityValue = str(value.community).toUpperCase();
  const community = communityValue === "STAFF"
    ? "staff"
    : communityValue === "GUEST"
      ? "guest"
      : "student";
  const fallback = buildDemoUser(mappedRole);
  const grantMap: Record<string, Permission[]> = {
    "members.view": ["members:read"],
    "members.create": ["members:write"],
    "members.update": ["members:write"],
    "members.delete": ["members:write"],
    "attendance.view": ["attendance:read"],
    "attendance.create": ["attendance:write"],
    "attendance.manage_devices": ["attendance:manual"],
    "events.view": ["events:read"],
    "events.create": ["events:write"],
    "events.update": ["events:write"],
    "events.delete": ["events:write"],
    "finance.view": ["finance:read"],
    "finance.create": ["finance:write"],
    "finance.update": ["finance:write"],
    "communications.create": ["communication:write"],
    "communications.update": ["communication:write"],
    "communications.send": ["communication:write", "chapel:announce"],
    "audit.view": ["audit:read"],
    "reports.view": ["analytics:read"],
    "reports.export": ["analytics:read"],
    "groups.view": ["community:view"],
    "groups.create": ["community:manage"],
    "groups.update": ["community:manage"],
    "groups.manage_members": ["community:manage"],
    "volunteers.view": ["workers:read"],
    "volunteers.create": ["workers:write"],
    "volunteers.assign": ["workers:write"],
  };
  const grants = Array.isArray(value.effective_permissions)
    ? value.effective_permissions.map(str)
    : [];
  const basePermissions = grants.includes("*")
    ? fallback.permissions
    : Array.from(new Set(["dashboard:view" as Permission, ...grants.flatMap((grant) => grantMap[grant] ?? [])]));
  const permissions = Array.from(new Set([
    ...basePermissions,
    ...(value.inventory_access === true ? ["assets:read" as Permission, "assets:write" as Permission] : []),
    ...(value.media_access === true ? ["media:write" as Permission] : []),
  ]));
  const name =
    str(value.full_name) ||
    `${str(value.first_name)} ${str(value.last_name)}`.trim();
  return {
    ...fallback,
    id: str(value.id),
    name: name || fallback.name,
    email: str(value.email),
    role: mappedRole,
    roles: [mappedRole],
    permissions,
    branchId: str(value.branch),
    branchName: "",
    initials: (name || fallback.name)
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join(""),
    mfaRequired: value.mfa_required === true,
    passwordChangeRequired: Boolean(value.password_change_required),
    community,
  };
}

function upperRoomPost(value: Row) {
  return {
    id: str(value.id),
    caption: str(value.caption),
    createdAt: str(value.created_at),
    updatedAt: str(value.updated_at),
    authorName: str(value.author_name),
    media: list(value.media).map((media) => ({
      id: str(media.id),
      url: str(media.url),
      mediaType: str(media.media_type).toUpperCase() === "VIDEO" ? "VIDEO" as const : "IMAGE" as const,
      position: Number(media.position || 0),
    })),
    likeCount: Number(value.like_count || 0),
    commentCount: Number(value.comment_count || 0),
    isLiked: Boolean(value.is_liked),
  };
}

function upperRoomComment(value: Row) {
  return {
    id: str(value.id),
    body: str(value.body),
    createdAt: str(value.created_at),
    authorName: str(value.author_name),
    isAuthor: Boolean(value.is_author),
  };
}

function member(value: Row): Member {
  return {
    id: str(value.id),
    name: str(value.full_name),
    identifier: str(value.matric_no || value.user_matric_no),
    email: str(value.email),
    programme: str(value.department_name),
    level: str(value.academic_level),
    department: str(value.department_name),
    status:
      value.membership_status === "ACTIVE"
        ? "active"
        : value.membership_status === "PENDING"
          ? "pending"
          : "inactive",
    attendanceRate: null,
    lastSeen: "",
  };
}

function event(value: Row): EventSummary {
  const start = new Date(str(value.start_time));
  const schedules = list(value.schedules);
  const nextSchedule = schedules.find((schedule) => schedule.is_cancelled !== true) ?? null;
  return {
    id: str(value.id),
    scheduleId: nextSchedule ? str(nextSchedule.id) : null,
    title: str(value.title),
    date: str(value.start_time).slice(0, 10),
    time: Number.isNaN(start.getTime())
      ? ""
      : start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    venue: str(value.location_name || "Venue to be confirmed"),
    registered: Number(value.registration_count ?? 0),
    capacity: Number(value.capacity ?? 0),
    visibility: value.is_public ? "public" : "private",
  };
}

function paged(response: Envelope, transform: (value: Row) => unknown) {
  return {
    data: list(response.data).map(transform),
    page: response.pagination?.current_page ?? 1,
    pageSize: response.pagination?.page_size ?? 25,
    total: response.pagination?.count ?? list(response.data).length,
  };
}

function operationRow(value: Row) {
  return {
    id: str(value.id),
    primary: str(value.primary || value.name || value.title || value.description),
    secondary: str(value.secondary || value.category || value.branch),
    detail: str(value.detail || value.details || value.amount),
    status: str(value.status),
    contentType: str(value.content_type),
    slug: str(value.slug),
    mediaUrl: str(value.media_url),
    coverImageUrl: str(value.cover_image_url),
    authorName: str(value.author_name),
    publishAt: value.publish_at ? str(value.publish_at) : null,
    publishedAt: value.published_at ? str(value.published_at) : null,
    rejectionReason: str(value.rejection_reason),
    categoryName: str(value.category_name),
    locationName: str(value.location_name),
    assetTag: str(value.asset_tag),
    serialNumber: str(value.serial_number),
    trackingMode: str(value.tracking_mode),
    quantityOnHand: Number(value.quantity_on_hand ?? 0),
    reorderLevel: Number(value.reorder_level ?? 0),
    unitOfMeasure: str(value.unit_of_measure),
    condition: str(value.condition),
    custodianName: str(value.custodian_name),
    nextMaintenanceAt: value.next_maintenance_at ? str(value.next_maintenance_at) : null,
    lowStock: Boolean(value.low_stock),
  };
}

function givingEntry(value: Row) {
  return {
    id: str(value.id),
    categoryName: str(value.category_name || value.category),
    amount: str(value.amount),
    currency: str(value.currency || "NGN"),
    source: str(value.source),
    status: str(value.status),
    givenAt: str(value.given_at),
    note: str(value.note),
  };
}

function volunteerProfile(value: Row) {
  return {
    id: str(value.id),
    memberId: str(value.member),
    memberName: str(value.member_name || value.member),
    skills: str(value.skills),
    status: str(value.status),
    isActive: Boolean(value.is_active),
  };
}

function volunteerAssignment(value: Row) {
  return {
    id: str(value.id),
    volunteerName: str(value.volunteer_name || value.volunteer),
    eventTitle: str(value.event_title),
    groupName: str(value.group_name),
    role: str(value.role),
    status: str(value.status),
    notes: str(value.notes),
    hoursLogged: str(value.hours_logged),
  };
}

function prayerEntry(value: Row) {
  return {
    id: str(value.id),
    category: str(value.category),
    details: str(value.details),
    privacyLevel: str(value.privacy_level),
    status: str(value.status),
    createdAt: str(value.created_at),
  };
}

function pastoralCaseEntry(value: Row) {
  return {
    id: str(value.id),
    category: str(value.category),
    summary: str(value.summary),
    priority: str(value.priority),
    status: str(value.status),
    nextFollowUpDate: value.next_follow_up_date ? str(value.next_follow_up_date) : null,
    createdAt: str(value.created_at),
  };
}

function testimonyEntry(value: Row) {
  return {
    id: str(value.id),
    title: str(value.title),
    details: str(value.details),
    consentToPublish: Boolean(value.consent_to_publish),
    status: str(value.status),
    rejectionReason: str(value.rejection_reason),
    createdAt: str(value.created_at),
  };
}

export async function djangoRequest(
  path: string,
  init: RequestInit,
  request: DjangoTransport,
): Promise<unknown> {
  const url = new URL(path, "http://chapelflow.local");
  const route = url.pathname;
  const method = init.method ?? "GET";
  const body = typeof init.body === "string" ? row(JSON.parse(init.body)) : {};
  const call = async (target: string, options = init) =>
    (await request(target, options)) as Envelope;
  const query = new URLSearchParams(url.search);
  if (query.has("pageSize")) {
    query.set("page_size", query.get("pageSize")!);
    query.delete("pageSize");
  }
  if (route === "/members" && query.has("status")) {
    query.set("membership_status", query.get("status")!.toUpperCase());
    query.delete("status");
  }
  if (route === "/members" && query.has("branchId")) {
    query.set("branch", query.get("branchId")!);
    query.delete("branchId");
  }
  const suffix = query.size ? `?${query}` : "";

  if (route === "/auth/me")
    return { data: user(row((await call("/auth/me/")).data)) };
  if (route === "/auth/login") {
    const response = await call(
      "/auth/login/",
      json("POST", {
        [str(body.identifier).includes("@") ? "email" : "matric_no"]:
          body.identifier,
        password: body.password,
        ...(body.otp ? { otp: body.otp } : {}),
      }),
    );
    return { data: user(row(row(response.data).user)) };
  }
  if (route === "/auth/logout") return call("/auth/logout/", json("POST", {}));
  if (route === "/auth/register") {
    if (!body.acceptedPolicies)
      unsupported("Accept the privacy policy and terms before registering.");
    const registrationType = str(body.memberType || "Student");
    const community = registrationType === "Staff"
      ? "STAFF"
      : registrationType === "Guest"
        ? "GUEST"
        : "STUDENT";
    await call(
      "/auth/register/",
      json("POST", {
        email: body.email,
        password: body.password,
        first_name: body.firstName,
        last_name: body.lastName,
        phone_number: body.phone,
        community,
        ...(community === "STUDENT"
          ? { matric_no: body.identifier, academic_level: body.level }
          : {}),
      }),
    );
    return { data: { verificationRequired: false, approvalRequired: false } };
  }
  if (route === "/auth/setup/super-admin")
    return call("/auth/setup/super-admin/", json("POST", body));
  if (route === "/auth/change-password")
    return call(
      "/auth/change-password/",
      json("POST", {
        old_password: body.currentPassword,
        new_password: body.password,
      }),
    );
  if (route === "/account/profile/photo" && method === "POST")
    return call("/auth/profile/photo/", init);
  if (route === "/account/profile")
    return call("/auth/profile/", method === "PATCH" ? json("PATCH", body) : undefined);
  if (route === "/uploads" && method === "POST")
    return call("/uploads/upload/", init);
  if (route === "/social/posts") {
    const response = await call("/social/posts/", init);
    if (method === "POST") return { data: upperRoomPost(row(response.data)) };
    const feed = row(response.data);
    return {
      data: {
        items: list(feed.items).map(upperRoomPost),
        page: Number(feed.page || 1),
        hasMore: Boolean(feed.has_more),
      },
    };
  }
  const socialPost = route.match(/^\/social\/posts\/([^/]+)$/);
  if (socialPost && method === "DELETE")
    return call(`/social/posts/${encodeURIComponent(socialPost[1]!)}/`, { method: "DELETE" });
  const socialLike = route.match(/^\/social\/posts\/([^/]+)\/like$/);
  if (socialLike && method === "POST") {
    const response = await call(`/social/posts/${encodeURIComponent(socialLike[1]!)}/like/`, json("POST", {}));
    const liked = row(response.data);
    return { data: { liked: Boolean(liked.liked), likeCount: Number(liked.like_count || 0) } };
  }
  const socialComments = route.match(/^\/social\/posts\/([^/]+)\/comments$/);
  if (socialComments) {
    const response = await call(
      `/social/posts/${encodeURIComponent(socialComments[1]!)}/comments/`,
      method === "POST" ? json("POST", { body: body.body }) : init,
    );
    if (method === "POST") return { data: upperRoomComment(row(response.data)) };
    return { data: list(response.data).map(upperRoomComment) };
  }
  const socialComment = route.match(/^\/social\/posts\/([^/]+)\/comments\/([^/]+)$/);
  if (socialComment && method === "DELETE")
    return call(`/social/posts/${encodeURIComponent(socialComment[1]!)}/comments/${encodeURIComponent(socialComment[2]!)}/`, { method: "DELETE" });
  if (route === "/student/announcements")
    return call("/communications/announcements/me/");
  if (route === "/student/join-requests")
    return call("/group-join-requests/me/", method === "POST" ? json("POST", body) : init);
  if (route === "/auth/forgot-password")
    return call(
      "/auth/password-reset/",
      json("POST", { email: body.identifier }),
    );
  if (route === "/auth/reset-password")
    return call(
      "/auth/password-reset/confirm/",
      json("POST", {
        uid: body.uid,
        token: body.token,
        new_password: body.password,
      }),
    );
  if (route.startsWith("/auth/mfa/")) return call(`${route}/`, init);

  if (/^\/public\/content\/[^/]+$/.test(route)) return call(`${route}/${suffix}`);
  if (/^\/public\/(events|sermons|news|gallery)\/[^/]+$/.test(route))
    return call(`${route}/${suffix}`);

  if (route === "/branches" && method === "GET") {
    return paged(await call(`/operations/branches/${suffix}`), operationRow);
  }
  if (route === "/members" && method === "GET")
    return paged(await call(`/members/${suffix}`), member);
  if (/^\/members\/[^/]+$/.test(route) && method === "PATCH") {
    const payload: Row = {
      ...(body.email === undefined ? {} : { email: body.email }),
    };
    if (body.name !== undefined) {
      const [first, ...rest] = str(body.name).trim().split(/\s+/);
      payload.first_name = first;
      payload.last_name = rest.join(" ");
    }
    return {
      data: member(row((await call(`${route}/`, json("PATCH", payload))).data)),
    };
  }
  if (route === "/events/public" && method === "GET")
    return paged(await call(`/events/public/${suffix}`), event);
  if (route === "/events" && method === "GET")
    return paged(await call(`/events/${suffix}`), event);
  if (route === "/events" && method === "POST") {
    const start = new Date(`${str(body.date)}T${str(body.time)}`);
    const end = new Date(`${str(body.date)}T${str(body.endTime)}`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()))
      unsupported("Enter a valid event date and time.");
    const response = await call(
      "/events/",
      json("POST", {
        title: body.title,
        description: body.description || "",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        venue_name: body.venue,
        is_public: body.visibility !== "private",
        requires_registration: true,
        capacity: body.capacity ? Number(body.capacity) : null,
      }),
    );
    return { data: event(row(response.data)) };
  }
  const eventRegistration = route.match(/^\/events\/([^/]+)\/registrations$/);
  if (eventRegistration && method === "POST")
    return call(`/events/${encodeURIComponent(eventRegistration[1]!)}/register/`, json("POST", {}));
  const eventCancellation = route.match(/^\/events\/([^/]+)\/registrations\/me$/);
  if (eventCancellation && method === "DELETE")
    return call(`/events/${encodeURIComponent(eventCancellation[1]!)}/registration/`, { method: "DELETE" });
  if (route === "/giving/checkout" && method === "POST") {
    const response = await call("/giving/checkout/", json("POST", {
      giving_type: body.givingType,
      amount: body.amount,
      note: body.note || "",
      terms_accepted: body.termsAccepted === true,
    }));
    const checkout = row(response.data);
    return {
      data: {
        authorizationUrl: str(checkout.authorization_url),
        reference: str(checkout.reference),
      },
    };
  }
  if (route === "/giving/checkout/verify" && method === "POST") {
    const response = await call("/giving/checkout/verify/", json("POST", { reference: body.reference }));
    const verification = row(response.data);
    return {
      data: {
        reference: str(verification.reference),
        status: str(verification.status) as "PENDING" | "SUCCESSFUL" | "FAILED" | "REFUNDED",
        amount: str(verification.amount),
        currency: str(verification.currency),
        givingRecorded: Boolean(verification.giving_recorded),
      },
    };
  }
  if (route === "/finance/dashboard" && method === "GET") {
    const dashboard = row((await call("/dashboard/")).data);
    const pledge = row(dashboard.pledge_summary);
    return {
      data: {
        totalGiving: str(dashboard.total_giving),
        givingCount: Number(dashboard.giving_count ?? 0),
        uniqueContributors: Number(dashboard.unique_contributors ?? 0),
        paymentPending: Number(dashboard.payment_pending ?? 0),
        paymentFailed: Number(dashboard.payment_failed ?? 0),
        byCategory: list(dashboard.by_category).map((category) => ({
          name: str(category.category__name || "Uncategorised"),
          total: str(category.total),
        })),
        pledgeSummary: {
          totalPledged: str(pledge.total_pledged),
          totalFulfilled: str(pledge.total_fulfilled),
          totalRemaining: str(pledge.total_remaining),
        },
      },
    };
  }
  if (route === "/finance/giving") {
    const response = await call("/giving/", method === "POST" ? json("POST", body) : init);
    if (method === "GET") return paged(response, givingEntry);
    return { data: givingEntry(row(response.data)) };
  }
  if (route === "/finance/categories" && method === "GET") {
    const response = await call("/giving-categories/");
    return { data: list(response.data).map((category) => ({ id: str(category.id), name: str(category.name) })) };
  }
  if (route === "/volunteers/profiles" && method === "GET")
    return paged(await call(`/volunteers/profiles/${suffix}`), volunteerProfile);
  if (route === "/volunteers/profiles" && method === "POST") {
    const response = await call("/volunteers/profiles/", json("POST", {
      member: body.member,
      skills: typeof body.skills === "string"
        ? body.skills.split(",").map((skill) => skill.trim()).filter(Boolean)
        : body.skills ?? [],
      availability_notes: body.availabilityNotes ?? "",
    }));
    return { data: volunteerProfile(row(response.data)) };
  }
  if (route === "/volunteers/assignments" && method === "GET")
    return paged(await call("/volunteers/assignments/"), volunteerAssignment);
  if (route === "/volunteers/assignments" && method === "POST") {
    const response = await call("/volunteers/assignments/", json("POST", body));
    return { data: volunteerAssignment(row(response.data)) };
  }
  const volunteerAction = route.match(/^\/volunteers\/assignments\/([^/]+)\/(confirm|complete)$/);
  if (volunteerAction && method === "POST") {
    const response = await call(
      `/volunteers/assignments/${encodeURIComponent(volunteerAction[1]!)}/${volunteerAction[2]!}/`,
      json("POST", body),
    );
    return { data: volunteerAssignment(row(response.data)) };
  }
  if (route === "/care/prayers") {
    const response = await call("/prayer/requests/", method === "POST" ? json("POST", {
      category: body.category,
      details: body.details,
      privacy_level: body.privacyLevel,
    }) : init);
    if (method === "GET") return paged(response, prayerEntry);
    return { data: prayerEntry(row(response.data)) };
  }
  if (route === "/care/pastoral-cases" && method === "GET")
    return paged(await call("/pastoral/cases/"), pastoralCaseEntry);
  const pastoralCaseUpdate = route.match(/^\/care\/pastoral-cases\/([^/]+)$/);
  if (pastoralCaseUpdate && method === "PATCH") {
    const response = await call(`/pastoral/cases/${encodeURIComponent(pastoralCaseUpdate[1]!)}/`, json("PATCH", {
      status: body.status,
      closure_reason: body.closureReason || "",
    }));
    return { data: pastoralCaseEntry(row(response.data)) };
  }
  if (route === "/care/counselling-requests" && method === "POST") {
    const response = await call("/pastoral/counselling-requests/", json("POST", {
      summary: body.summary,
      preferred_date: body.preferredDate || null,
    }));
    return { data: pastoralCaseEntry(row(response.data)) };
  }
  if (route === "/care/testimonies") {
    const response = await call("/prayer/testimonies/", method === "POST" ? json("POST", {
      title: body.title,
      details: body.details,
      consent_to_publish: Boolean(body.consentToPublish),
    }) : init);
    if (method === "GET") return paged(response, testimonyEntry);
    return { data: testimonyEntry(row(response.data)) };
  }
  const testimonyReview = route.match(/^\/care\/testimonies\/([^/]+)\/(approve|reject)$/);
  if (testimonyReview && method === "POST") {
    const response = await call(
      `/prayer/testimonies/${encodeURIComponent(testimonyReview[1]!)}/${testimonyReview[2]!}/`,
      json("POST", testimonyReview[2] === "reject" ? { reason: body.reason } : {}),
    );
    return { data: testimonyEntry(row(response.data)) };
  }
  if (route === "/attendance/pass") return call("/attendance/pass/");
  if (route === "/attendance/identity-pass")
    return call("/attendance/identity-pass/");
  if (route === "/attendance/history/me")
    return call("/attendance/history/me/");
  if (route === "/attendance/checkpoint/token")
    return call("/attendance/checkpoint/token/");
  if (route === "/attendance/student-scan" && method === "POST")
    return call(
      "/attendance/student-scan/",
      json("POST", { token: body.token }),
    );
  const attendanceSessions = async (branchId: string) => {
    const response = await call(`/attendance/sessions/?branch=${encodeURIComponent(branchId)}&page_size=100`);
    return list(response.data).map((session) => {
      const opensAt = str(session.window_opens_at || session.opened_at);
      const closesAt = session.window_closes_at ? str(session.window_closes_at) : null;
      const startsInFuture = Boolean(opensAt && new Date(opensAt).getTime() > Date.now());
      const closed = session.is_open !== true || str(session.state).toUpperCase() === "CLOSED";
      const status = closed ? "closed" : str(session.state).toUpperCase() === "PAUSED" ? "paused" : startsInFuture ? "scheduled" : "active";
      return {
        id: str(session.id),
        title: str(session.label || "Chapel service"),
        venue: str(session.venue),
        startsAt: opensAt,
        endsAt: closesAt,
        status,
        isOpen: session.is_open === true,
        createdAt: str(session.opened_at),
        recordCount: Number(session.record_count || 0),
        raw: session,
      };
    });
  };
  if (route === "/attendance/sessions" && method === "GET") {
    const branchId = query.get("branch") || "";
    if (!branchId) unsupported("Assign a chapel branch to this account before viewing attendance sessions.");
    const sessions = await attendanceSessions(branchId);
    return { data: sessions.map((session) => ({
      id: session.id, title: session.title, venue: session.venue, startsAt: session.startsAt,
      endsAt: session.endsAt, status: session.status, isOpen: session.isOpen,
      createdAt: session.createdAt,
    })) };
  }
  if (route === "/attendance/sessions/current" && method === "GET") {
    const branchId = query.get("branch") || "";
    if (!branchId) unsupported("Assign a chapel branch to this account before viewing attendance sessions.");
    const sessions = await attendanceSessions(branchId);
    const now = Date.now();
    const current = sessions.find((session) => {
      if (!session.isOpen || str(session.raw.state).toUpperCase() !== "OPEN") return false;
      const opensAt = session.startsAt ? new Date(session.startsAt).getTime() : 0;
      const closesAt = session.endsAt ? new Date(session.endsAt).getTime() : Number.POSITIVE_INFINITY;
      return opensAt <= now && now <= closesAt;
    });
    const summaries = sessions.map((session) => ({
      id: session.id, title: session.title, venue: session.venue, startsAt: session.startsAt,
      endsAt: session.endsAt, status: session.status, isOpen: session.isOpen,
      createdAt: session.createdAt,
    }));
    if (!current) return { data: { session: null, records: [], sessions: summaries } };
    const branchMembers = await call(`/members/?branch=${encodeURIComponent(branchId)}&page_size=100`);
    const members = new Map(list(branchMembers.data).map((item) => [str(item.id), member(item)]));
    const recordsResponse = await call(`/attendance/records/?session=${encodeURIComponent(current.id)}&page_size=100`);
    const records = list(recordsResponse.data).map((record) => {
      const person = members.get(str(record.member));
      const method = str(record.method).toUpperCase();
      return {
        id: str(record.id),
        memberName: person?.name || (record.visitor ? "Visitor" : "Member"),
        identifier: person?.identifier || str(record.member || record.visitor),
        time: record.checked_in_at ? new Date(str(record.checked_in_at)).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "",
        method: method === "QR_CODE" ? "qr" : method === "KIOSK" ? "kiosk" : "manual",
        status: str(record.status).toLowerCase(),
      };
    });
    const raw = current.raw;
    return {
      data: {
        session: {
          id: current.id,
          title: current.title,
          venue: current.venue,
          status: "open",
          opensAt: current.startsAt,
          closesAt: current.endsAt,
          count: Number(raw.record_count || records.length),
          lateCount: records.filter((record) => record.status === "late").length,
          manualCount: records.filter((record) => record.method === "manual").length,
        },
        records,
        sessions: summaries,
      },
    };
  }
  if (route === "/attendance/sessions" && method === "POST") {
    const branchId = str(body.branchId || body.branch);
    if (!branchId) unsupported("Assign a chapel branch to this account before creating an attendance session.");
    const opensAt = new Date(`${str(body.date)}T${str(body.opensAt)}`);
    const closesAt = new Date(`${str(body.date)}T${str(body.closesAt)}`);
    if (Number.isNaN(opensAt.getTime()) || Number.isNaN(closesAt.getTime())) unsupported("Enter a valid attendance date and time.");
    return call("/attendance/sessions/", json("POST", {
      branch: branchId,
      label: body.title,
      venue: body.venue,
      window_opens_at: opensAt.toISOString(),
      window_closes_at: closesAt.toISOString(),
    }));
  }
  if (route === "/attendance/manual" && method === "POST") {
    const branchId = str(body.branchId);
    const memberResponse = await call(`/members/?branch=${encodeURIComponent(branchId)}&search=${encodeURIComponent(str(body.identifier))}&page_size=100`);
    const identifier = str(body.identifier).trim().toLowerCase();
    const match = list(memberResponse.data).find((candidate) =>
      str(candidate.matric_no).toLowerCase() === identifier || str(candidate.email).toLowerCase() === identifier,
    );
    if (!match) unsupported("No member with that email or matriculation number was found in your branch.");
    return call("/attendance/manual/", json("POST", { member_id: match.id, session_id: body.sessionId }));
  }
  const attendanceClose = route.match(/^\/attendance\/sessions\/([^/]+)\/close$/);
  if (attendanceClose && (method === "POST" || method === "PATCH"))
    return call(`/attendance/sessions/${encodeURIComponent(attendanceClose[1]!)}/close/`, json("POST", {}));
  const attendanceCorrection = route.match(/^\/attendance\/records\/([^/]+)$/);
  if (attendanceCorrection && method === "PATCH")
    return call(`/attendance/records/${encodeURIComponent(attendanceCorrection[1]!)}/correct/`, json("POST", {
      status: str(body.status).toUpperCase(),
      reason: body.reason,
    }));
  if (route === "/institutional-accounts" && method === "GET")
    return call("/auth/institutional-accounts/");
  if (route === "/institutional-accounts" && method === "POST")
    return call("/auth/institutional-accounts/", json("POST", body));
  if (route === "/chapel-groups" && method === "GET")
    return call(`/groups-catalog/${suffix}`);
  if (route === "/chapel-groups/bootstrap-groups" && method === "POST")
    return call("/groups-catalog/bootstrap-chapel-groups/", json("POST", {}));
  if (/^\/institutional-accounts\/[^/]+$/.test(route) && method === "PATCH")
    return call(`/auth${route}/`, json("PATCH", body));
  if (
    /^\/institutional-accounts\/[^/]+\/password-reset$/.test(route) &&
    method === "POST"
  )
    return call(`/auth${route}/`, json("POST", {}));
  if (route === "/admin/attendance/sessions" && method === "GET")
    return call("/attendance/sessions/");
  if (route === "/admin/attendance/sessions" && method === "POST")
    return call("/attendance/sessions/", json("POST", body));
  if (
    /^\/admin\/attendance\/sessions\/[^/]+\/(pause|resume|close)$/.test(
      route,
    ) &&
    method === "POST"
  ) {
    const [, id, action] = route.match(
      /^\/admin\/attendance\/sessions\/([^/]+)\/(pause|resume|close)$/,
    )!;
    return call(
      `/attendance/sessions/${encodeURIComponent(id!)}/${action!}/`,
      json("POST", body),
    );
  }
  if (route === "/admin/attendance/records")
    return call("/attendance/records/");
  if (
    /^\/admin\/attendance\/records\/[^/]+\/correct$/.test(route) &&
    method === "POST"
  ) {
    const id = route.split("/")[4];
    return call(
      `/attendance/records/${encodeURIComponent(id!)}/correct/`,
      json("POST", body),
    );
  }
  if (route === "/admin/attendance/scan-attempts")
    return call("/attendance/scan-attempts/");
  if (route === "/admin/audit-logs") return call("/audit/logs/");
  if (route === "/auth/sessions") {
    const response = await call("/auth/sessions/");
    return {
      data: list(response.data).map((session) => ({
        id: str(session.jti),
        device: "Signed-in device",
        lastActiveAt: str(session.created_at),
        current: session.is_current === true,
      })),
    };
  }
  const revokeSession = route.match(/^\/auth\/sessions\/([^/]+)$/);
  if (revokeSession && method === "DELETE")
    return call("/auth/sessions/revoke/", json("POST", { jti: decodeURIComponent(revokeSession[1]!) }));
  if (route === "/auth/sessions/revoke" && method === "POST")
    return call("/auth/sessions/revoke/", json("POST", body));
  if (route === "/auth/sessions/revoke-all" && method === "POST")
    return call("/auth/sessions/revoke-all/", json("POST", body));
  if (route === "/communities") return call("/community-memberships/");
  if (route === "/communities/leadership/directory")
    return call("/community-memberships/leadership-directory/");
  const communityMessages = route.match(/^\/communities\/([^/]+)\/messages$/);
  if (communityMessages)
    return call(
      `/community-memberships/${encodeURIComponent(communityMessages[1]!)}/messages/${suffix}`,
      method === "POST" ? json("POST", { body: body.body }) : init,
    );
  const communityResources = route.match(/^\/communities\/([^/]+)\/resources$/);
  if (communityResources)
    return call(
      `/community-memberships/${encodeURIComponent(communityResources[1]!)}/resources/${suffix}`,
      method === "POST" ? json("POST", body) : init,
    );
  const communityAnnouncements = route.match(/^\/communities\/([^/]+)\/announcements$/);
  if (communityAnnouncements)
    return call(
      `/community-memberships/${encodeURIComponent(communityAnnouncements[1]!)}/announcements/${suffix}`,
      method === "POST" ? json("POST", body) : init,
    );
  const communityEvents = route.match(/^\/communities\/([^/]+)\/events$/);
  if (communityEvents)
    return call(
      `/community-memberships/${encodeURIComponent(communityEvents[1]!)}/meetings/${suffix}`,
      method === "POST" ? json("POST", {
        title: body.title, description: body.description, venue: body.venue,
        starts_at: body.startsAt, ends_at: body.endsAt,
      }) : init,
    );
  const communityMemberUpdate = route.match(/^\/communities\/([^/]+)\/members\/([^/]+)$/);
  if (communityMemberUpdate && method === "PATCH")
    return call(
      `/community-memberships/${encodeURIComponent(communityMemberUpdate[1]!)}/members/${encodeURIComponent(communityMemberUpdate[2]!)}/`,
      json("PATCH", body),
    );
  const communityMembers = route.match(/^\/communities\/([^/]+)\/members$/);
  if (communityMembers)
    return call(`/community-memberships/${encodeURIComponent(communityMembers[1]!)}/members/${suffix}`);
  if (/^\/communities\/[^/]+\/read$/.test(route) && method === "POST")
    return { data: null };
  if (/^\/communities\/[^/]+$/.test(route))
    return call(
      `/community-memberships/${encodeURIComponent(route.split("/").at(-1)!)}/`,
    );
  if (route === "/notifications" && method === "GET") {
    const response = await call(`/notifications/${suffix}`);
    return {
      data: list(response.data).map((notification) => ({
        id: str(notification.id),
        title: str(notification.title),
        body: str(notification.body),
        read_at: notification.read_at ?? null,
        created_at: str(notification.created_at),
        community_id: null,
        type: str(notification.channel),
        href: null,
      })),
    };
  }
  if (/^\/notifications\/[^/]+\/read$/.test(route))
    return call(
      `/notifications/${encodeURIComponent(route.split("/")[2]!)}/mark-read/`,
      json("POST", {}),
    );
  if (route === "/account/privacy-preferences" && method === "GET") {
    const response = await call("/communications/preferences/me/");
    const preference = row(response.data);
    return {
      data: {
        email: Boolean(preference.email_enabled),
        sms: Boolean(preference.sms_enabled),
        push: Boolean(preference.push_enabled),
        analytics: false,
      },
    };
  }
  if (route === "/account/privacy-preferences" && method === "PATCH")
    return call(
      "/communications/preferences/me/",
      json("PATCH", {
        email_enabled: body.email,
        sms_enabled: body.sms,
        push_enabled: body.push,
      }),
    );
  if (route === "/dashboard") {
    const dashboardRole = query.get("role");
    const endpoint = ["super_admin", "chapel_admin"].includes(dashboardRole ?? "")
      ? "/dashboard/admin/"
      : dashboardRole === "pastor"
        ? "/dashboard/pastor/"
        : dashboardRole === "treasurer"
          ? "/dashboard/finance/"
          : "/dashboard/member/";
    const dashboard = row((await call(endpoint)).data);
    const metrics = Object.entries(dashboard)
      .flatMap(([section, value]) => {
        if (typeof value === "number") return [[section, value] as const];
        return Object.entries(row(value))
          .filter((entry): entry is [string, number] => typeof entry[1] === "number")
          .map(([label, metric]) => [`${section} ${label}`, metric] as const);
      })
      .slice(0, 8)
      .map(([label, value]) => ({
        label: label.replaceAll("_", " "),
        value: Number(value).toLocaleString(),
        change: "",
        trend: "neutral" as const,
      }));
    return { data: { metrics, attendanceTrend: [] } };
  }
  if (route === "/role-workspace") return call("/dashboard/operations/");
  if (route === "/role/memberships" && method === "GET")
    return call(`/community-memberships/${suffix}`);
  if (/^\/role\/memberships\/[^/]+$/.test(route) && method === "PATCH")
    return call(`/community-memberships/${encodeURIComponent(route.split("/").at(-1)!)}/`, json("PATCH", body));
  if (route === "/role/announcements")
    return call("/communications/announcements/", method === "POST" ? json("POST", body) : init);
  if (route === "/role/reports")
    return call("/reports/jobs/", method === "POST" ? json("POST", body) : init);
  if (route === "/role/assignments") return call("/volunteers/assignments/");
  if (route === "/role/follow-ups") return call("/pastoral/cases/");
  if (route === "/role/join-requests") return call("/group-join-requests/", init);
  if (/^\/role\/join-requests\/[^/]+\/(approve|reject)$/.test(route) && method === "POST") {
    const [, id, action] = route.match(/^\/role\/join-requests\/([^/]+)\/(approve|reject)$/)!;
    return call(`/group-join-requests/${encodeURIComponent(id!)}/${action!}/`, json("POST", {}));
  }
  if (route === "/role/tasks") return call("/group-tasks/", method === "POST" ? json("POST", body) : init);
  if (/^\/role\/tasks\/[^/]+$/.test(route) && method === "PATCH")
    return call(`/group-tasks/${encodeURIComponent(route.split("/").at(-1)!)}/`, json("PATCH", body));
  if (route === "/role/meetings") return call("/group-meetings/", method === "POST" ? json("POST", body) : init);
  if (/^\/role\/meetings\/[^/]+\/attendance$/.test(route)) {
    const id = route.split("/")[3]!;
    return call(`/group-meetings/${encodeURIComponent(id)}/attendance/`, method === "POST" ? json("POST", body) : init);
  }
  if (route === "/assets/alerts" && method === "GET") {
    const response = await call("/operations/assets/alerts/");
    const alerts = row(response.data);
    return {
      data: {
        lowStock: list(alerts.low_stock).map(operationRow),
        maintenanceDue: list(alerts.maintenance_due).map((entry) => {
          const maintenance = row(entry);
          return {
            id: str(maintenance.id),
            assetId: str(maintenance.asset),
            title: str(maintenance.title),
            details: str(maintenance.details),
            dueAt: str(maintenance.due_at),
            status: str(maintenance.status),
          };
        }),
      },
    };
  }

  const operationRoutes: Record<string, string> = {
    "/worker-assignments": "/operations/workers/",
    "/rosters": "/operations/workers/",
    "/finance/transactions": "/operations/finance/",
    "/communications/broadcasts": "/operations/communication/",
    "/assets": "/operations/assets/",
    "/media": "/operations/media/",
    "/cms/content": "/operations/cms/",
    "/branches": "/operations/branches/",
  };
  const operationTarget = operationRoutes[route];
  if (operationTarget) {
    const response = await call(
      `${operationTarget}${method === "GET" ? suffix : ""}`,
      method === "POST" ? json("POST", body) : init,
    );
    if (method === "GET") return paged(response, operationRow);
    return { data: operationRow(row(response.data)) };
  }
  const workerAcknowledge = route.match(/^\/worker-assignments\/([^/]+)\/acknowledge$/);
  if (workerAcknowledge && method === "POST")
    return call(`/operations/workers/${encodeURIComponent(workerAcknowledge[1]!)}/acknowledge/`, json("POST", {}));
  if (route === "/worker-leave-requests" && method === "POST")
    return call("/operations/worker-leave-requests/", json("POST", body));
  const broadcastSend = route.match(/^\/communications\/broadcasts\/([^/]+)\/send$/);
  if (broadcastSend && method === "POST")
    return call(`/operations/communication/${encodeURIComponent(broadcastSend[1]!)}/send/`, json("POST", {}));
  const assetMovement = route.match(/^\/assets\/([^/]+)\/movements$/);
  if (assetMovement && method === "POST")
    return call(`/operations/assets/${encodeURIComponent(assetMovement[1]!)}/movement/`, json("POST", body));
  const assetHistory = route.match(/^\/assets\/([^/]+)\/history$/);
  if (assetHistory && method === "GET") {
    const response = row((await call(
      `/operations/assets/${encodeURIComponent(assetHistory[1]!)}/history/`,
    )).data);
    return {
      data: {
        movements: list(response.movements).map((movement) => ({
          id: str(movement.id),
          type: str(movement.movement_type),
          quantityChange: Number(movement.quantity_change ?? 0),
          quantityAfter: Number(movement.quantity_after ?? 0),
          reason: str(movement.reason),
          createdAt: str(movement.created_at),
        })),
        maintenance: list(response.maintenance).map((maintenance) => ({
          id: str(maintenance.id),
          title: str(maintenance.title),
          dueAt: str(maintenance.due_at),
          status: str(maintenance.status),
          completedAt: maintenance.completed_at ? str(maintenance.completed_at) : null,
        })),
      },
    };
  }
  const contentPublish = route.match(/^\/cms\/content\/([^/]+)\/publish$/);
  if (contentPublish && method === "POST")
    return call(`/operations/cms/${encodeURIComponent(contentPublish[1]!)}/publish/`, json("POST", {}));
  const contentWorkflow = route.match(
    /^\/cms\/content\/([^/]+)\/(submit|approve|reject|publish|archive)$/,
  );
  if (contentWorkflow && method === "POST") {
    const response = await call(
      `/operations/cms/${encodeURIComponent(contentWorkflow[1]!)}/${contentWorkflow[2]}/`,
      json("POST", body),
    );
    return { data: operationRow(row(response.data)) };
  }
  if (route === "/audit-events" && method === "GET") {
    const response = await call(`/audit/logs/${suffix}`);
    return paged(response, (entry) => ({
      id: str(entry.id),
      primary: str(entry.action).replaceAll("_", " "),
      secondary: str(entry.resource_type),
      detail: str(entry.resource_id || entry.created_at),
      status: "RECORDED",
    }));
  }
  if (route === "/analytics/overview" && method === "GET")
    return call(`/analytics/overview/${suffix}`);
  if (route === "/account/data-export-requests" && method === "POST")
    return call("/account/data-export-requests/", json("POST", body));
  if (route === "/account/deletion-requests" && method === "POST")
    return call("/account/deletion-requests/", json("POST", body));
  unsupported(
    "This feature is not available in the connected Django backend yet.",
  );
}
