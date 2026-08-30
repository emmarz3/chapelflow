import { API_BASE_URL, api } from "../lib/api";
import { isDemoMode } from "../lib/fixtures";
import type {
  AttendanceRecord,
  AttendancePass,
  AttendanceScanResult,
  EventSummary,
  Member,
  PagedResponse,
  CommunitySummary,
  CommunityDetail,
  CommunityMessage,
  CommunityAnnouncement,
  CommunityEvent,
  CommunityMember,
  LeadershipDirectoryEntry,
} from "../types/domain";

export type QueryParams = Record<string, string | number | boolean | undefined>;
export interface ListRow {
  id: string;
  primary: string;
  secondary: string;
  detail: string;
  status: string;
}
export interface DashboardPayload {
  metrics: {
    label: string;
    value: string;
    change: string;
    trend: "up" | "down" | "neutral";
  }[];
  attendanceTrend: { week: string; attendance: number }[];
}
export interface AttendancePayload {
  session: {
    id: string;
    title: string;
    status: "scheduled" | "open" | "closed";
    opensAt: string;
    closesAt: string;
    count: number;
    lateCount: number;
    manualCount: number;
  };
  records: AttendanceRecord[];
}
export interface AttendanceSessionSummary {
  id: string;
  title: string;
  serviceType: string;
  date: string;
  startsAt: string;
  endsAt: string;
  status: "scheduled" | "active" | "closed";
  createdAt: string;
}
export interface AnalyticsPayload {
  metrics: { label: string; value: string; note: string }[];
  attendanceTrend: { week: string; attendance: number }[];
  byLevel: { name: string; value: number }[];
}
export interface PublicContentPayload {
  slug: string;
  eyebrow?: string;
  title: string;
  description?: string;
  sections: {
    id: string;
    heading?: string;
    body: string;
    imageUrl?: string;
    imageAlt?: string;
    action?: { label: string; href: string };
  }[];
  updatedAt: string;
}

const demoAttendancePass: AttendancePass = {
  student: {
    name: "Favour Okafor",
    identifier: "CU/24/CSC/108",
    programme: "Computer Science",
    level: "200",
    photoUrl: null,
  },
  passStatus: "active",
  session: null,
  token: null,
  imageDataUrl: null,
  expiresAt: null,
};

const demoAttendanceHistory = [
  {
    title: "Sunday Worship Service",
    date: "2026-08-23T09:00:00.000Z",
    recorded_at: "2026-08-23T09:06:00.000Z",
    status: "present",
  },
];
export type OperationsModule =
  | "workers"
  | "finance"
  | "communication"
  | "assets"
  | "media"
  | "cms"
  | "branches"
  | "audit"
  | "settings";

function queryString(params: QueryParams = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  const result = search.toString();
  return result ? `?${result}` : "";
}

function unavailable<T>(capability: string): Promise<T> {
  return Promise.reject(
    new Error(
      `${capability} is not available until its backend contract is configured.`,
    ),
  );
}

export const queryKeys = {
  dashboard: (branchId: string) => ["dashboard", branchId] as const,
  members: (params: QueryParams) => ["members", params] as const,
  attendance: (sessionId: string) => ["attendance", sessionId] as const,
  events: (params: QueryParams) => ["events", params] as const,
  operations: (module: OperationsModule, params: QueryParams) =>
    [module, params] as const,
  analytics: (params: QueryParams) => ["analytics", params] as const,
  communities: () => ["communities"] as const,
  community: (slug: string) => ["communities", slug] as const,
};

export const authService = {
  register: (payload: Record<string, unknown>) =>
    api.post<{
      data: { verificationRequired: boolean; approvalRequired?: boolean };
    }>("/auth/register", payload),
  verifyEmail: (token: string) =>
    api.post<{ data: { verified: boolean } }>("/auth/verify-email", { token }),
  verifyOtp: (identifier: string, code: string) =>
    api.post<{ data: { verified: boolean } }>("/auth/verify-otp", {
      identifier,
      code,
    }),
  forgotPassword: (identifier: string) =>
    api.post<void>("/auth/forgot-password", { identifier }),
  resetPassword: (token: string, password: string) =>
    api.post<void>("/auth/reset-password", { token, password }),
  changePassword: (currentPassword: string, password: string) =>
    api.post<void>("/auth/change-password", { currentPassword, password }),
  sessions: () =>
    api.get<{
      data: {
        id: string;
        device: string;
        location?: string;
        lastActiveAt: string;
        current: boolean;
      }[];
    }>("/auth/sessions"),
  revokeSession: (sessionId: string) =>
    api.delete<void>(`/auth/sessions/${encodeURIComponent(sessionId)}`),
  setupPassword: (token: string, password: string) =>
    api.post<void>("/auth/setup-password", { token, password }),
};

const demoCommunities: CommunitySummary[] = [
  {
    id: "11111111-1111-4111-a111-111111111111",
    name: "Music",
    slug: "music",
    type: "unit",
    description: "Worship, rehearsal, and music ministry coordination.",
    status: "active",
    requires_approval: true,
    members_can_post: true,
    chat_enabled: true,
    membership_status: "active",
    unreadCount: 4,
    member_count: 84,
    pending_count: 6,
  },
  {
    id: "22222222-2222-4222-a222-222222222222",
    name: "Love Campus Fellowship",
    slug: "love-campus-fellowship",
    type: "campus_fellowship",
    description:
      "A private fellowship workspace for meetings, care, and campus discipleship.",
    status: "active",
    requires_approval: true,
    members_can_post: true,
    chat_enabled: true,
    membership_status: "active",
    unreadCount: 2,
    member_count: 112,
    pending_count: 0,
  },
];

export const communityService = {
  publicList: (type?: CommunitySummary["type"]) =>
    isDemoMode
      ? Promise.resolve({
          data: demoCommunities.filter(
            (community) => !type || community.type === type,
          ),
        })
      : api.get<{ data: CommunitySummary[] }>(
          `/public/communities${queryString({ type })}`,
        ),
  mine: () =>
    isDemoMode
      ? Promise.resolve({ data: demoCommunities })
      : api.get<{ data: CommunitySummary[] }>("/communities"),
  get: (slug: string) =>
    isDemoMode
      ? Promise.resolve({
          data: {
            ...demoCommunities.find((community) => community.slug === slug)!,
            membershipStatus: "active" as const,
            memberCount: slug === "music" ? 84 : 112,
            access: { isLeader: false, canPost: true, canManage: false },
            leaders: [
              {
                position:
                  slug === "music" ? "Head of Music" : "Fellowship Leader",
                name:
                  slug === "music"
                    ? "Olaoti Mofiyinfoluwa"
                    : "Dada Mofopefoluwa",
              },
            ],
            pinnedAnnouncement: null,
            nextEvent: null,
          } as CommunityDetail,
        })
      : api.get<{ data: CommunityDetail }>(
          `/communities/${encodeURIComponent(slug)}`,
        ),
  messages: (slug: string, search = "") =>
    isDemoMode
      ? Promise.resolve({ data: [] as CommunityMessage[] })
      : api.get<{ data: CommunityMessage[] }>(
          `/communities/${encodeURIComponent(slug)}/messages${queryString({ search })}`,
        ),
  sendMessage: (slug: string, body: string, replyToId?: string) =>
    api.post<{ data: CommunityMessage }>(
      `/communities/${encodeURIComponent(slug)}/messages`,
      { body, replyToId },
    ),
  markRead: (slug: string) =>
    api.post<void>(`/communities/${encodeURIComponent(slug)}/read`),
  announcements: (slug: string) =>
    api.get<{ data: CommunityAnnouncement[] }>(
      `/communities/${encodeURIComponent(slug)}/announcements`,
    ),
  createAnnouncement: (slug: string, payload: Record<string, unknown>) =>
    api.post<{ data: { id: string } }>(
      `/communities/${encodeURIComponent(slug)}/announcements`,
      payload,
    ),
  events: (slug: string) =>
    api.get<{ data: CommunityEvent[] }>(
      `/communities/${encodeURIComponent(slug)}/events`,
    ),
  createEvent: (slug: string, payload: Record<string, unknown>) =>
    api.post<{ data: { id: string } }>(
      `/communities/${encodeURIComponent(slug)}/events`,
      payload,
    ),
  members: (slug: string, status?: string) =>
    api.get<{ data: CommunityMember[] }>(
      `/communities/${encodeURIComponent(slug)}/members${queryString({ status })}`,
    ),
  updateMembership: (slug: string, membershipId: string, status: string) =>
    api.patch<{ data: { id: string; status: string } }>(
      `/communities/${encodeURIComponent(slug)}/members/${encodeURIComponent(membershipId)}`,
      { status },
    ),
  leadership: () =>
    api.get<{ data: LeadershipDirectoryEntry[] }>(
      "/communities/leadership/directory",
    ),
  streamUrl: (slug: string) =>
    `${API_BASE_URL}/communities/${encodeURIComponent(slug)}/stream`,
};

export const communityAdminService = {
  list: () => api.get<{ data: CommunitySummary[] }>("/admin/communities"),
  create: (payload: Record<string, unknown>) =>
    api.post<{ data: CommunitySummary }>("/admin/communities", payload),
  update: (id: string, payload: Record<string, unknown>) =>
    api.patch<{ data: CommunitySummary }>(
      `/admin/communities/${encodeURIComponent(id)}`,
      payload,
    ),
  leadership: () =>
    api.get<{ data: Record<string, unknown>[] }>("/admin/leadership"),
  positions: () =>
    api.get<{
      data: { id: string; name: string; scope_type: "global" | "community" }[];
    }>("/admin/leadership/positions"),
  assignLeader: (payload: Record<string, unknown>) =>
    api.post<{ data: { id: string } }>("/admin/leadership/assign", payload),
  provisionAccount: (payload: Record<string, unknown>) =>
    api.post<{
      data: { userId: string; setupPath: string; expiresInHours: number };
    }>("/admin/accounts", payload),
};

export const notificationService = {
  list: () =>
    isDemoMode
      ? Promise.resolve({
          data: [
            {
              id: "demo-community-notification",
              community_id: demoCommunities[0]!.id,
              type: "community.announcement",
              title: "Music",
              body: "Friday rehearsal begins at 5:00 PM.",
              href: "/app/communities/music?tab=announcements",
              read_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        })
      : api.get<{
          data: {
            id: string;
            community_id: string | null;
            type: string;
            title: string;
            body: string;
            href: string | null;
            read_at: string | null;
            created_at: string;
          }[];
        }>("/notifications"),
  markRead: (id: string) =>
    api.patch<void>(`/notifications/${encodeURIComponent(id)}/read`, {}),
};

export const dashboardService = {
  get: (branchId: string) =>
    api.get<{ data: DashboardPayload }>(
      `/dashboard${queryString({ branchId })}`,
    ),
};
export const memberService = {
  list: (params: QueryParams) =>
    api.get<PagedResponse<Member>>(`/members${queryString(params)}`),
  create: (payload: Partial<Member>) =>
    api.post<{ data: Member }>("/members", payload),
  update: (id: string, payload: Partial<Member>) =>
    api.patch<{ data: Member }>(`/members/${encodeURIComponent(id)}`, payload),
  archive: (id: string) =>
    api.post<void>(`/members/${encodeURIComponent(id)}/archive`),
  restore: (id: string) =>
    api.post<void>(`/members/${encodeURIComponent(id)}/restore`),
  approve: (id: string) =>
    api.post<{ data: { id: string; status: "active" } }>(
      `/members/${encodeURIComponent(id)}/approve`,
    ),
};
export const attendanceService = {
  current: () =>
    api.get<{ data: AttendancePayload }>("/attendance/sessions/current"),
  createSession: (payload: Record<string, unknown>) =>
    api.post<{ data: AttendancePayload["session"] }>(
      "/attendance/sessions",
      payload,
    ),
  qrCode: (sessionId: string) =>
    api.get<{
      data: { imageDataUrl: string; expiresAt: string; reference: string };
    }>(`/attendance/sessions/${encodeURIComponent(sessionId)}/qr`),
  checkIn: (
    sessionId: string,
    payload: {
      qrToken?: string;
      memberIdentifier?: string;
      method: "qr" | "manual" | "kiosk";
    },
  ) =>
    api.post<{ data: AttendanceRecord }>(
      `/attendance/sessions/${encodeURIComponent(sessionId)}/check-ins`,
      payload,
    ),
  correct: (recordId: string, payload: { status: string; reason: string }) =>
    api.patch<{ data: AttendanceRecord }>(
      `/attendance/records/${encodeURIComponent(recordId)}`,
      payload,
    ),
  pass: () =>
    isDemoMode
      ? Promise.resolve({ data: demoAttendancePass })
      : api.get<{ data: AttendancePass }>("/attendance/pass"),
  history: () =>
    isDemoMode
      ? Promise.resolve({ data: demoAttendanceHistory })
      : api.get<{
          data: {
            title: string;
            date: string;
            recorded_at: string;
            status: string;
          }[];
        }>("/attendance/history/me"),
  activeScannerSession: () =>
    api.get<{
      data: null | {
        session: AttendancePayload["session"];
        recent: AttendanceRecord[];
      };
    }>("/attendance/sessions/active"),
  sessions: (status?: AttendanceSessionSummary["status"]) =>
    api.get<{ data: AttendanceSessionSummary[] }>(
      `/attendance/sessions${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  scan: (payload: {
    token: string;
    sessionId: string;
    idempotencyKey: string;
  }) => api.post<{ data: AttendanceScanResult }>("/attendance/scan", payload),
  manual: (payload: {
    identifier: string;
    sessionId: string;
    reason: string;
    idempotencyKey: string;
  }) => api.post<{ data: AttendanceScanResult }>("/attendance/manual", payload),
  activateSession: (sessionId: string) =>
    api.patch<{ data: { id: string; status: "active" } }>(
      `/attendance/sessions/${encodeURIComponent(sessionId)}/activate`,
      {},
    ),
  closeSession: (sessionId: string) =>
    api.patch<{ data: { id: string; status: "closed" } }>(
      `/attendance/sessions/${encodeURIComponent(sessionId)}/close`,
      {},
    ),
};
export const eventService = {
  list: (params: QueryParams) =>
    api.get<PagedResponse<EventSummary>>(`/events${queryString(params)}`),
  create: (payload: Partial<EventSummary>) =>
    api.post<{ data: EventSummary }>("/events", payload),
  register: (eventId: string, answers: Record<string, unknown>) =>
    api.post<{ data: { confirmationCode: string; waitlisted: boolean } }>(
      `/events/${encodeURIComponent(eventId)}/registrations`,
      answers,
    ),
  cancelRegistration: (eventId: string) =>
    api.delete<void>(`/events/${encodeURIComponent(eventId)}/registrations/me`),
};

const modulePaths: Record<OperationsModule, string> = {
  workers: "/worker-assignments",
  finance: "/finance/transactions",
  communication: "/communications/broadcasts",
  assets: "/assets",
  media: "/media",
  cms: "/cms/content",
  branches: "/branches",
  audit: "/audit-events",
  settings: "/settings",
};
const moduleCreatePaths: Record<OperationsModule, string> = {
  ...modulePaths,
  workers: "/rosters",
};
export const operationsService = {
  list: (module: OperationsModule, params: QueryParams) =>
    api.get<PagedResponse<ListRow>>(
      `${modulePaths[module]}${queryString(params)}`,
    ),
  create: <T extends Record<string, unknown>>(
    module: OperationsModule,
    payload: T,
  ) => api.post<{ data: ListRow }>(moduleCreatePaths[module], payload),
  workerAcknowledge: (assignmentId: string) =>
    api.post<void>(
      `/worker-assignments/${encodeURIComponent(assignmentId)}/acknowledge`,
    ),
  workerLeave: (payload: Record<string, unknown>) =>
    api.post<void>("/worker-leave-requests", payload),
  sendBroadcast: (broadcastId: string) =>
    api.post<void>(
      `/communications/broadcasts/${encodeURIComponent(broadcastId)}/send`,
    ),
  assetMovement: (assetId: string, payload: Record<string, unknown>) =>
    api.post<void>(`/assets/${encodeURIComponent(assetId)}/movements`, payload),
  publishContent: (contentId: string) =>
    api.post<void>(`/cms/content/${encodeURIComponent(contentId)}/publish`),
};
export const analyticsService = {
  get: (params: QueryParams) =>
    api.get<{ data: AnalyticsPayload }>(
      `/analytics/overview${queryString(params)}`,
    ),
};
export const publicService = {
  content: (slug: string) =>
    api.get<{ data: PublicContentPayload }>(
      `/public/content/${encodeURIComponent(slug)}`,
    ),
  detail: (kind: "events" | "sermons" | "news", id: string) =>
    api.get<{ data: PublicContentPayload }>(
      `/public/${kind}/${encodeURIComponent(id)}`,
    ),
};
export const privacyService = {
  preferences: () =>
    api.get<{
      data: { email: boolean; sms: boolean; push: boolean; analytics: boolean };
    }>("/account/privacy-preferences"),
  updatePreferences: (payload: Record<string, boolean>) =>
    api.patch<void>("/account/privacy-preferences", payload),
  requestExport: () =>
    api.post<{ data: { requestId: string } }>("/account/data-export-requests"),
  requestDeletion: (reason: string) =>
    api.post<{ data: { requestId: string } }>("/account/deletion-requests", {
      reason,
    }),
};

export function requireApiMode<T>(
  capability: string,
  action: () => Promise<T>,
  demoResult?: T,
): Promise<T> {
  if (!isDemoMode) return action();
  if (demoResult !== undefined) return Promise.resolve(demoResult);
  return unavailable<T>(capability);
}
