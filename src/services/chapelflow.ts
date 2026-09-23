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
  CommunityResource,
  CommunityMember,
  LeadershipDirectoryEntry,
  Role,
} from "../types/domain";

export type QueryParams = Record<string, string | number | boolean | undefined>;
export interface ListRow {
  id: string;
  primary: string;
  secondary: string;
  detail: string;
  status: string;
  contentType?: string;
  slug?: string;
  mediaUrl?: string;
  coverImageUrl?: string;
  authorName?: string;
  publishAt?: string | null;
  publishedAt?: string | null;
  rejectionReason?: string;
  categoryName?: string;
  locationName?: string;
  assetTag?: string;
  serialNumber?: string;
  trackingMode?: string;
  quantityOnHand?: number;
  reorderLevel?: number;
  unitOfMeasure?: string;
  condition?: string;
  custodianName?: string;
  nextMaintenanceAt?: string | null;
  lowStock?: boolean;
}
export interface AssetHistoryPayload {
  movements: {
    id: string;
    type: string;
    quantityChange: number;
    quantityAfter: number;
    reason: string;
    createdAt: string;
  }[];
  maintenance: {
    id: string;
    title: string;
    dueAt: string;
    status: string;
    completedAt: string | null;
  }[];
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
export interface RoleWorkspacePayload {
  role: string;
  branch_id: string | null;
  groups: { id: string; name: string; type: string; active_members: number }[];
  metrics: {
    active_students: number;
    groups: number;
    open_sessions: number;
    attendance_today: number;
    pending_reports: number;
  };
  live_sessions: { id: string; label: string; state: string; opens_at: string; closes_at: string | null; check_ins: number }[];
}
export interface InventoryAlertsPayload {
  lowStock: ListRow[];
  maintenanceDue: {
    id: string;
    assetId: string;
    title: string;
    details: string;
    dueAt: string;
    status: string;
  }[];
}
export interface FinanceDashboardPayload {
  totalGiving: string;
  givingCount: number;
  uniqueContributors: number;
  paymentPending: number;
  paymentFailed: number;
  byCategory: { name: string; total: string }[];
  pledgeSummary: { totalPledged: string; totalFulfilled: string; totalRemaining: string };
}
export interface GivingEntry {
  id: string;
  categoryName: string;
  amount: string;
  currency: string;
  source: string;
  status: string;
  givenAt: string;
  note: string;
}
export interface VolunteerProfileEntry {
  id: string;
  memberId: string;
  memberName: string;
  skills: string;
  status: string;
  isActive: boolean;
}
export interface VolunteerAssignmentEntry {
  id: string;
  volunteerName: string;
  eventTitle: string;
  groupName: string;
  role: string;
  status: string;
  notes: string;
  hoursLogged: string;
}
export interface PrayerEntry {
  id: string;
  category: string;
  details: string;
  privacyLevel: string;
  status: string;
  createdAt: string;
}
export interface PastoralCaseEntry {
  id: string;
  category: string;
  summary: string;
  priority: string;
  status: string;
  nextFollowUpDate: string | null;
  createdAt: string;
}
export interface TestimonyEntry {
  id: string;
  title: string;
  details: string;
  consentToPublish: boolean;
  status: string;
  rejectionReason: string;
  createdAt: string;
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
    mediaType?: "image" | "video";
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
  inventoryAlerts: () => ["inventory-alerts"] as const,
  financeDashboard: () => ["finance-dashboard"] as const,
  volunteerAssignments: () => ["volunteer-assignments"] as const,
  care: () => ["care"] as const,
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
  resetPassword: (token: string, password: string, uid?: string) =>
    api.post<void>("/auth/reset-password", {
      token,
      password,
      ...(uid ? { uid } : {}),
    }),
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
  studentProfile: () =>
    api.get<{ data: StudentProfile }>("/account/profile"),
  updateStudentProfile: (payload: Partial<StudentProfile>) =>
    api.patch<{ data: StudentProfile }>("/account/profile", payload),
  uploadStudentProfilePhoto: (file: File) => {
    const body = new FormData();
    body.set("file", file);
    return api.postForm<{ data: StudentProfile }>("/account/profile/photo", body);
  },
};

export interface StudentProfile {
  email: string;
  phone_number: string;
  address: string;
  photo_url: string;
  date_of_birth: string | null;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  matric_no: string;
  department: string | null;
  role: string;
}

export interface UploadResult {
  id: string;
  file_url: string;
  content_type: string;
  size_bytes: number;
}

export interface UpperRoomMedia {
  id: string;
  url: string;
  mediaType: "IMAGE" | "VIDEO";
  position: number;
}

export interface UpperRoomPost {
  id: string;
  caption: string;
  createdAt: string;
  updatedAt: string;
  authorName: string;
  media: UpperRoomMedia[];
  likeCount: number;
  commentCount: number;
  isLiked: boolean;
}

export interface UpperRoomComment {
  id: string;
  body: string;
  createdAt: string;
  authorName: string;
  isAuthor: boolean;
}

export const uploadService = {
  upload: (file: File, category: "MEDIA_CONTENT") => {
    const body = new FormData();
    body.set("file", file);
    body.set("category", category);
    return api.postForm<{ data: UploadResult }>("/uploads", body);
  },
};

export const upperRoomService = {
  feed: (page = 1) => api.get<{ data: { items: UpperRoomPost[]; page: number; hasMore: boolean } }>(`/social/posts${queryString({ page, pageSize: 15 })}`),
  createPost: (caption: string, files: File[]) => {
    const body = new FormData();
    body.set("caption", caption);
    files.forEach((file) => body.append("files", file));
    return api.postForm<{ data: UpperRoomPost }>("/social/posts", body);
  },
  deletePost: (postId: string) => api.delete<void>(`/social/posts/${encodeURIComponent(postId)}`),
  toggleLike: (postId: string) => api.post<{ data: { liked: boolean; likeCount: number } }>(`/social/posts/${encodeURIComponent(postId)}/like`),
  comments: (postId: string) => api.get<{ data: UpperRoomComment[] }>(`/social/posts/${encodeURIComponent(postId)}/comments`),
  createComment: (postId: string, body: string) => api.post<{ data: UpperRoomComment }>(`/social/posts/${encodeURIComponent(postId)}/comments`, { body }),
  deleteComment: (postId: string, commentId: string) => api.delete<void>(`/social/posts/${encodeURIComponent(postId)}/comments/${encodeURIComponent(commentId)}`),
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
  resources: (slug: string) =>
    api.get<{ data: CommunityResource[] }>(
      `/communities/${encodeURIComponent(slug)}/resources`,
    ),
  addResource: (slug: string, payload: { title: string; url: string; description?: string }) =>
    api.post<{ data: CommunityResource }>(
      `/communities/${encodeURIComponent(slug)}/resources`, payload,
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
  get: (branchId: string, role: Role) =>
    api.get<{ data: DashboardPayload }>(
      `/dashboard${queryString({ branchId, role })}`,
    ),
};

/** Role-scoped operational endpoints. Django applies scope again server-side. */
export const roleWorkspaceService = {
  summary: () => api.get<{ data: RoleWorkspacePayload }>("/role-workspace"),
  memberships: () => api.get<{ data: Record<string, unknown>[] }>("/role/memberships"),
  updateMembership: (id: string, is_active: boolean) =>
    api.patch<{ data: Record<string, unknown> }>(`/role/memberships/${encodeURIComponent(id)}`, { is_active }),
  announcements: () => api.get<{ data: Record<string, unknown>[] }>("/role/announcements"),
  createAnnouncement: (payload: Record<string, unknown>) =>
    api.post<{ data: Record<string, unknown> }>("/role/announcements", payload),
  reports: () => api.get<{ data: Record<string, unknown>[] }>("/role/reports"),
  createReport: (payload: Record<string, unknown>) =>
    api.post<{ data: Record<string, unknown> }>("/role/reports", payload),
  assignments: () => api.get<{ data: Record<string, unknown>[] }>("/role/assignments"),
  followUps: () => api.get<{ data: Record<string, unknown>[] }>("/role/follow-ups"),
  joinRequests: () => api.get<{ data: Record<string, unknown>[] }>("/role/join-requests"),
  resolveJoinRequest: (id: string, action: "approve" | "reject") => api.post<{ data: Record<string, unknown> }>(`/role/join-requests/${encodeURIComponent(id)}/${action}`, {}),
  tasks: () => api.get<{ data: Record<string, unknown>[] }>("/role/tasks"),
  createTask: (payload: Record<string, unknown>) => api.post<{ data: Record<string, unknown> }>("/role/tasks", payload),
  updateTask: (id: string, payload: Record<string, unknown>) => api.patch<{ data: Record<string, unknown> }>(`/role/tasks/${encodeURIComponent(id)}`, payload),
  meetings: () => api.get<{ data: Record<string, unknown>[] }>("/role/meetings"),
  createMeeting: (payload: Record<string, unknown>) => api.post<{ data: Record<string, unknown> }>("/role/meetings", payload),
  meetingAttendance: (id: string) => api.get<{ data: Record<string, unknown>[] }>(`/role/meetings/${encodeURIComponent(id)}/attendance`),
  markMeetingAttendance: (id: string, member: string, present = true) => api.post<{ data: Record<string, unknown> }>(`/role/meetings/${encodeURIComponent(id)}/attendance`, { member, present }),
};

/** Inventory exceptions are available only to Chapel Protocol and Chapel leadership. */
export const inventoryService = {
  alerts: () => api.get<{ data: InventoryAlertsPayload }>("/assets/alerts"),
};
export const financeService = {
  dashboard: () => api.get<{ data: FinanceDashboardPayload }>("/finance/dashboard"),
  giving: () => api.get<PagedResponse<GivingEntry>>("/finance/giving"),
  categories: () => api.get<{ data: { id: string; name: string }[] }>("/finance/categories"),
  recordGiving: (payload: { category: string; amount: number; source: string; note?: string }) =>
    api.post<{ data: GivingEntry }>("/finance/giving", payload),
};

export type PersonalGivingType = "OFFERING" | "TITHE";

export interface PaystackCheckout {
  authorizationUrl: string;
  reference: string;
}

export interface PaystackVerification {
  reference: string;
  status: "PENDING" | "SUCCESSFUL" | "FAILED" | "REFUNDED";
  amount: string;
  currency: string;
  givingRecorded: boolean;
}

/** Personal giving is available to signed-in ChapelFlow accounts only. */
export const givingService = {
  beginPaystackCheckout: (payload: {
    givingType: PersonalGivingType;
    amount: string;
    note?: string;
    termsAccepted: boolean;
  }) => api.post<{ data: PaystackCheckout }>("/giving/checkout", payload),
  verifyPaystackCheckout: (reference: string) =>
    api.post<{ data: PaystackVerification }>("/giving/checkout/verify", { reference }),
};
export const volunteerService = {
  profiles: () => api.get<PagedResponse<VolunteerProfileEntry>>("/volunteers/profiles"),
  assignments: () => api.get<PagedResponse<VolunteerAssignmentEntry>>("/volunteers/assignments"),
  createAssignment: (payload: { volunteer: string; role: string; notes?: string }) =>
    api.post<{ data: VolunteerAssignmentEntry }>("/volunteers/assignments", payload),
  confirm: (id: string) => api.post<{ data: VolunteerAssignmentEntry }>(`/volunteers/assignments/${encodeURIComponent(id)}/confirm`),
  complete: (id: string, hoursLogged: number) => api.post<{ data: VolunteerAssignmentEntry }>(`/volunteers/assignments/${encodeURIComponent(id)}/complete`, { hours_logged: hoursLogged }),
};
export const careService = {
  prayers: () => api.get<PagedResponse<PrayerEntry>>("/care/prayers"),
  submitPrayer: (payload: { category: string; details: string; privacyLevel: "PRIVATE" | "PASTORAL" }) =>
    api.post<{ data: PrayerEntry }>("/care/prayers", payload),
  counsellingRequests: () => api.get<PagedResponse<PastoralCaseEntry>>("/care/pastoral-cases"),
  updateCounsellingCase: (id: string, payload: { status: string; closureReason?: string }) =>
    api.patch<{ data: PastoralCaseEntry }>(`/care/pastoral-cases/${encodeURIComponent(id)}`, payload),
  requestCounselling: (payload: { summary: string; preferredDate?: string }) =>
    api.post<{ data: PastoralCaseEntry }>("/care/counselling-requests", payload),
  testimonies: () => api.get<PagedResponse<TestimonyEntry>>("/care/testimonies"),
  submitTestimony: (payload: { title: string; details: string; consentToPublish: boolean }) =>
    api.post<{ data: TestimonyEntry }>("/care/testimonies", payload),
  approveTestimony: (id: string) =>
    api.post<{ data: TestimonyEntry }>(`/care/testimonies/${encodeURIComponent(id)}/approve`),
  rejectTestimony: (id: string, reason: string) =>
    api.post<{ data: TestimonyEntry }>(`/care/testimonies/${encodeURIComponent(id)}/reject`, { reason }),
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
  identityPass: () =>
    api.get<{ data: { token: string; issued_at: string } }>(
      "/attendance/identity-pass",
    ),
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
  usherCheckpoint: () =>
    api.get<{
      data: {
        checkpoint_id: string;
        checkpoint_name: string;
        successful_scans: number;
        token: string;
        expires_at: string;
        rotation_seconds: number;
        session: { id: string; label: string; state: string; window_opens_at?: string | null; window_closes_at?: string | null };
      };
    }>("/attendance/checkpoint/token"),
  studentScan: (token: string) =>
    api.post<{
      data: { result: "recorded" | "duplicate"; record: AttendanceRecord };
      message?: string;
    }>("/attendance/student-scan", { token }),
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
export const institutionalAccountService = {
  list: () =>
    api.get<{ data: InstitutionalAccount[] }>("/institutional-accounts"),
  create: (
    payload: Omit<InstitutionalAccount, "id" | "is_active"> & {
      password: string;
    },
  ) =>
    api.post<{ data: InstitutionalAccount }>(
      "/institutional-accounts",
      payload,
    ),
  update: (id: string, payload: Partial<InstitutionalAccount>) =>
    api.patch<{ data: InstitutionalAccount }>(
      `/institutional-accounts/${encodeURIComponent(id)}`,
      payload,
    ),
  resetPassword: (id: string) =>
    api.post<{
      data: {
        temporary_password: string;
        password_change_required: boolean;
      };
    }>(
      `/institutional-accounts/${encodeURIComponent(id)}/password-reset`,
    ),
};

export const chapelGroupService = {
  list: () =>
    api.get<{
      data: Array<{
        id: string;
        name: string;
        group_type: string;
        is_active: boolean;
      }>;
    }>("/chapel-groups"),
};

export interface InstitutionalAccount {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number?: string;
  role:
    | "CHAPLAIN"
    | "STUDENT_CHAPLAIN"
    | "UNIT_HEAD"
    | "FELLOWSHIP_LEADER"
    | "ATTENDANCE_USHER";
  branch?: string | null;
  institutional_group?: string | null;
  is_active: boolean;
  password_change_required?: boolean;
}

export interface AdminAttendanceSession {
  id: string;
  label: string;
  state: "OPEN" | "PAUSED" | "CLOSED";
  is_open: boolean;
  opened_at: string;
  window_opens_at: string | null;
  window_closes_at: string | null;
  record_count: number;
}

export interface AdminAuditLog {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface AdminAttendanceRecord {
  id: string;
  member: string | null;
  status: string;
  checked_in_at: string;
}

export const adminAttendanceService = {
  sessions: () =>
    api.get<{ data: AdminAttendanceSession[] }>("/admin/attendance/sessions"),
  createSession: (
    payload: Pick<
      AdminAttendanceSession,
      "label" | "window_opens_at" | "window_closes_at"
    >,
  ) =>
    api.post<{ data: AdminAttendanceSession }>(
      "/admin/attendance/sessions",
      payload,
    ),
  transition: (id: string, action: "pause" | "resume" | "close") =>
    api.post<{ data: AdminAttendanceSession }>(
      `/admin/attendance/sessions/${encodeURIComponent(id)}/${action}`,
    ),
  records: () =>
    api.get<{ data: AdminAttendanceRecord[] }>("/admin/attendance/records"),
  correct: (id: string, status: string, reason: string) =>
    api.post<{ data: AdminAttendanceRecord }>(
      `/admin/attendance/records/${encodeURIComponent(id)}/correct`,
      { status, reason },
    ),
  scanAttempts: () =>
    api.get<{
      data: Array<{
        id: string;
        result: string;
        created_at: string;
        session: string | null;
      }>;
    }>("/admin/attendance/scan-attempts"),
};

export const securityService = {
  auditLogs: () => api.get<{ data: AdminAuditLog[] }>("/admin/audit-logs"),
  sessions: () =>
    api.get<{
      data: Array<{ id: string; device: string; lastActiveAt: string; current: boolean }>;
    }>("/auth/sessions"),
  revokeSession: (jti: string) =>
    api.post<void>("/auth/sessions/revoke", { jti }),
  revokeAllSessions: (keepCurrent: boolean) =>
    api.post<void>("/auth/sessions/revoke-all", { keep_current: keepCurrent }),
};
export const eventService = {
  list: (params: QueryParams) =>
    api.get<PagedResponse<EventSummary>>(`/events${queryString(params)}`),
  create: (payload: Partial<EventSummary>) =>
    api.post<{ data: EventSummary }>("/events", payload),
  register: (eventId: string, answers: Record<string, unknown> = {}) =>
    api.post<{ data: { id: string; status: "CONFIRMED" | "WAITLISTED" | "CANCELLED" } }>(
      `/events/${encodeURIComponent(eventId)}/registrations`,
      answers,
    ),
  cancelRegistration: (eventId: string) =>
    api.delete<void>(`/events/${encodeURIComponent(eventId)}/registrations/me`),
};
export const accountContentService = {
  announcements: () => api.get<{ data: { id: string; title: string; body: string; published_at: string }[] }>("/student/announcements"),
};
export const studentContentService = {
  announcements: accountContentService.announcements,
  joinRequests: () => api.get<{ data: { groups: { id: string; name: string; type: string; description: string }[]; requests: { id: string; group: string; status: string; message: string; requested_at: string }[] } }>("/student/join-requests"),
  requestJoin: (group: string, message: string) => api.post<{ data: { id: string; status: string } }>("/student/join-requests", { group, message }),
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
  assetHistory: (assetId: string) =>
    api.get<{ data: AssetHistoryPayload }>(
      `/assets/${encodeURIComponent(assetId)}/history`,
    ),
  publishContent: (contentId: string) =>
    api.post<void>(`/cms/content/${encodeURIComponent(contentId)}/publish`),
  contentWorkflow: (
    contentId: string,
    action: "submit" | "approve" | "reject" | "publish" | "archive",
    payload: Record<string, unknown> = {},
  ) =>
    api.post<{ data: ListRow }>(
      `/cms/content/${encodeURIComponent(contentId)}/${action}`,
      payload,
    ),
};
export const analyticsService = {
  get: (params: QueryParams) =>
    api.get<{ data: AnalyticsPayload }>(
      `/analytics/overview${queryString(params)}`,
    ),
};
export const publicService = {
  content: (slug: string, search = "") =>
    api.get<{ data: PublicContentPayload }>(
      `/public/content/${encodeURIComponent(slug)}${queryString({ search })}`,
    ),
  detail: (kind: "events" | "sermons" | "news" | "gallery", id: string) =>
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
