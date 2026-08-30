export type Role =
  | "super_admin"
  | "chapel_admin"
  | "chaplain"
  | "student_chaplain"
  | "treasurer"
  | "chapel_official"
  | "pastor"
  | "worker"
  | "attendance_usher"
  | "member";

export type Permission =
  | "dashboard:view"
  | "members:read"
  | "members:write"
  | "attendance:read"
  | "attendance:write"
  | "attendance:scan"
  | "attendance:manual"
  | "events:read"
  | "events:write"
  | "finance:read"
  | "finance:write"
  | "communication:write"
  | "workers:read"
  | "workers:write"
  | "workers:acknowledge"
  | "assets:read"
  | "assets:write"
  | "media:write"
  | "cms:write"
  | "analytics:read"
  | "branches:manage"
  | "audit:read"
  | "settings:manage"
  | "community:view"
  | "community:view_all"
  | "community:manage"
  | "leadership:view"
  | "leadership:manage"
  | "chapel:announce";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  roles: Role[];
  branchId: string;
  branchName: string;
  permissions: Permission[];
  initials: string;
}

export interface ApiErrorShape {
  code: string;
  message: string;
  fieldErrors?: Record<string, string[]>;
  requestId?: string;
  status: number;
}

export interface PagedResponse<T> {
  data: T[];
  page: number;
  pageSize: number;
  total: number;
}
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface Member {
  id: string;
  name: string;
  identifier: string;
  email: string;
  programme: string;
  level: string;
  department: string;
  status: "pending" | "active" | "follow_up" | "inactive";
  attendanceRate: number;
  lastSeen: string;
}

export interface AttendanceRecord {
  id: string;
  memberName: string;
  identifier: string;
  time: string;
  method: "qr" | "manual" | "kiosk";
  status: "present" | "late" | "duplicate";
}

export interface AttendancePass {
  student: {
    name: string;
    identifier: string;
    programme: string | null;
    level: string | null;
    photoUrl: string | null;
  };
  passStatus: "active" | "revoked" | "inactive";
  session: { id: string; title: string } | null;
  token: string | null;
  imageDataUrl: string | null;
  expiresAt: string | null;
}

export interface AttendanceScanResult {
  result: "recorded" | "duplicate";
  record: {
    id: string;
    recordedAt: string;
    student: {
      name: string;
      identifier: string;
      programme: string | null;
      level: string | null;
    };
    session: { id: string; title: string };
  };
}

export interface EventSummary {
  id: string;
  title: string;
  date: string;
  time: string;
  venue: string;
  registered: number;
  capacity: number;
  visibility: "public" | "private";
}

export interface Metric {
  label: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
}

export type CommunityType =
  "unit" | "campus_fellowship" | "hostel_fellowship" | "other";

export type MembershipStatus =
  "pending" | "active" | "rejected" | "suspended" | "left";

export interface CommunitySummary {
  id: string;
  name: string;
  slug: string;
  type: CommunityType;
  description: string;
  status: "active" | "inactive";
  requires_approval: boolean;
  members_can_post: boolean;
  chat_enabled: boolean;
  membership_status?: MembershipStatus | null;
  is_leader?: boolean;
  unreadCount?: number;
  member_count?: number;
  pending_count?: number;
}

export interface CommunityDetail extends CommunitySummary {
  membershipStatus: MembershipStatus | null;
  memberCount: number;
  access: { isLeader: boolean; canPost: boolean; canManage: boolean };
  leaders: { position: string; name: string }[];
  pinnedAnnouncement: CommunityAnnouncement | null;
  nextEvent: CommunityEvent | null;
}

export interface CommunityMessage {
  id: string;
  body: string;
  reply_to_id: string | null;
  pinned: boolean;
  created_at: string;
  edited_at: string | null;
  sender_id: string;
  sender_name: string;
}

export interface CommunityAnnouncement {
  id: string;
  title: string;
  content: string;
  pinned: boolean;
  priority: "normal" | "important" | "urgent";
  published_at: string;
  expires_at?: string | null;
  author_name: string;
}

export interface CommunityEvent {
  id: string;
  title: string;
  description: string;
  venue: string;
  starts_at: string;
  ends_at: string;
  status: "upcoming" | "ongoing" | "completed" | "cancelled";
}

export interface CommunityMember {
  id: string;
  user_id: string;
  name: string;
  identifier: string | null;
  programme: string | null;
  level: string | null;
  status: MembershipStatus;
  is_primary: boolean;
  joined_at: string;
}

export interface LeadershipDirectoryEntry {
  position: string;
  leader_name: string | null;
  community_name: string | null;
  community_slug: string | null;
  community_type: CommunityType | null;
  starts_at: string | null;
  ends_at: string | null;
}
