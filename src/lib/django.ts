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
    "volunteers.assign": ["workers:write"],
  };
  const grants = list(value.effective_permissions).map(str);
  const permissions = grants.includes("*")
    ? fallback.permissions
    : Array.from(new Set(["dashboard:view" as Permission, ...grants.flatMap((grant) => grantMap[grant] ?? [])]));
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
    mfaRequired: Boolean(value.mfa_required),
    passwordChangeRequired: Boolean(value.password_change_required),
  };
}

function member(value: Row): Member {
  return {
    id: str(value.id),
    name: str(value.full_name),
    identifier: str(value.matric_no || value.user_matric_no),
    email: str(value.email),
    programme: str(value.department_name),
    level: "",
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
  return {
    id: str(value.id),
    title: str(value.title),
    date: str(value.start_time).slice(0, 10),
    time: Number.isNaN(start.getTime())
      ? ""
      : start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    venue: str(value.location_name || value.location),
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
  if (query.has("status")) {
    query.set("membership_status", query.get("status")!.toUpperCase());
    query.delete("status");
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
    await call(
      "/auth/register/",
      json("POST", {
        email: body.email,
        password: body.password,
        matric_no: body.identifier,
        first_name: body.firstName,
        last_name: body.lastName,
        phone_number: body.phone,
        community: body.memberType === "Staff" ? "STAFF" : "STUDENT",
      }),
    );
    return { data: { verificationRequired: false, approvalRequired: false } };
  }
  if (route === "/auth/change-password")
    return call(
      "/auth/change-password/",
      json("POST", {
        old_password: body.currentPassword,
        new_password: body.password,
      }),
    );
  if (route === "/account/profile")
    return call("/auth/profile/", method === "PATCH" ? json("PATCH", body) : undefined);
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

  if (/^\/public\/content\/[^/]+$/.test(route)) return call(`${route}/`);

  if (route === "/branches" && method === "GET") {
    const response = await call(`/branches/${suffix}`);
    return {
      data: list(response.data).map((branch) => ({
        id: str(branch.id),
        name: str(branch.name),
      })),
    };
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
  if (route === "/events" && method === "GET")
    return paged(await call(`/events/${suffix}`), event);
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
  if (route === "/institutional-accounts" && method === "GET")
    return call("/auth/institutional-accounts/");
  if (route === "/institutional-accounts" && method === "POST")
    return call("/auth/institutional-accounts/", json("POST", body));
  if (route === "/chapel-groups") return call("/groups-catalog/");
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
  if (route === "/auth/sessions") return call("/auth/sessions/");
  if (route === "/auth/sessions/revoke" && method === "POST")
    return call("/auth/sessions/revoke/", json("POST", body));
  if (route === "/auth/sessions/revoke-all" && method === "POST")
    return call("/auth/sessions/revoke-all/", json("POST", body));
  if (route === "/communities") return call("/community-memberships/");
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
    const metrics = Object.entries(row((await call("/dashboard/member/")).data))
      .filter(([, value]) => typeof value === "number")
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
  unsupported(
    "This feature is not available in the connected Django backend yet.",
  );
}
