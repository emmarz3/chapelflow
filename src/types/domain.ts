export type Role =
  "super_admin" | "chapel_admin" | "pastor" | "worker" | "member";

export type Permission =
  | "dashboard:view"
  | "members:read"
  | "members:write"
  | "attendance:read"
  | "attendance:write"
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
  | "settings:manage";

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
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
  status: "active" | "follow_up" | "inactive";
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
