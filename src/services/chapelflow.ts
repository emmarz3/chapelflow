import { api } from "../lib/api";
import { isDemoMode } from "../lib/fixtures";
import type {
  AttendanceRecord,
  EventSummary,
  Member,
  PagedResponse,
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
};

export const authService = {
  register: (payload: Record<string, unknown>) =>
    api.post<{ data: { verificationRequired: boolean } }>(
      "/auth/register",
      payload,
    ),
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
