import type { Permission, Role, User } from "../types/domain";

const rolePermissions: Record<Role, Permission[]> = {
  super_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "attendance:scan",
    "attendance:manual",
    "events:read",
    "events:write",
    "finance:read",
    "finance:write",
    "communication:write",
    "workers:read",
    "workers:write",
    "workers:acknowledge",
    "media:write",
    "cms:write",
    "analytics:read",
    "branches:manage",
    "audit:read",
    "settings:manage",
    "community:view",
    "community:view_all",
    "community:manage",
    "leadership:view",
    "leadership:manage",
    "chapel:announce",
  ],
  chapel_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "attendance:scan",
    "attendance:manual",
    "events:read",
    "events:write",
    "finance:read",
    "finance:write",
    "communication:write",
    "workers:read",
    "workers:write",
    "workers:acknowledge",
    "media:write",
    "cms:write",
    "analytics:read",
    "audit:read",
    "community:view",
    "community:view_all",
    "community:manage",
    "leadership:view",
    "leadership:manage",
    "chapel:announce",
  ],
  chaplain: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "communication:write",
    "analytics:read",
    "community:view",
    "community:view_all",
    "leadership:view",
    "chapel:announce",
  ],
  student_chaplain: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "communication:write",
    "community:view",
    "community:view_all",
    "leadership:view",
    "chapel:announce",
  ],
  unit_leader: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "community:view",
  ],
  fellowship_leader: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "community:view",
  ],
  treasurer: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "finance:read",
    "finance:write",
    "community:view",
    "leadership:view",
  ],
  chapel_official: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "community:view",
    "leadership:view",
  ],
  pastor: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "events:read",
    "events:write",
    "workers:read",
    "analytics:read",
    "media:write",
    "community:view",
    "community:view_all",
    "leadership:view",
  ],
  worker: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "workers:read",
    "workers:acknowledge",
    "community:view",
  ],
  attendance_usher: ["attendance:read", "attendance:scan", "attendance:manual"],
  member: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "community:view",
  ],
};

const operationalWorkspaceRoles = new Set<Role>([
  "chaplain",
  "student_chaplain",
  "unit_leader",
  "fellowship_leader",
]);

export function getAccountMenuItem(role: Role) {
  if (role === "member")
    return { label: "Profile and security", path: "/app/profile/edit" };
  if (role === "super_admin" || role === "chapel_admin")
    return { label: "Profile and settings", path: "/app/settings" };
  if (operationalWorkspaceRoles.has(role))
    return { label: "Operational workspace", path: "/app/operations" };
  if (role === "attendance_usher")
    return { label: "Attendance scanner", path: "/usher/attendance" };
  return { label: "Account overview", path: "/app" };
}

export function getMobilePrimaryItem(role: Role) {
  if (role === "member")
    return { label: "Chapel Pass", path: "/app/chapel-pass" };
  if (role === "super_admin" || role === "chapel_admin")
    return { label: "Attendance", path: "/app/attendance" };
  if (operationalWorkspaceRoles.has(role))
    return { label: "Operations", path: "/app/operations" };
  if (role === "attendance_usher")
    return { label: "Scanner", path: "/usher/attendance" };
  return { label: "Overview", path: "/app" };
}

export function hasPermission(user: User | null, permission?: Permission) {
  return !permission || Boolean(user?.permissions.includes(permission));
}

export function isStudentMember(user: User | null | undefined) {
  return user?.role === "member" && user.community !== "staff" && user.community !== "guest";
}

export function getAuthenticatedHomePath(user: User | null | undefined) {
  if (user?.role === "attendance_usher") return "/usher/attendance";
  if (isStudentMember(user)) return "/app/chapel-pass";
  return "/app";
}

export function buildDemoUser(role: Role): User {
  const names: Record<Role, string> = {
    super_admin: "Dr. Tola Adebayo",
    chapel_admin: "Grace Adeyemi",
    chaplain: "Chaplain Emmanuel Adekunle",
    student_chaplain: "Akintobi Oluwabori Favour",
    unit_leader: "Unit Leader",
    fellowship_leader: "Fellowship Leader",
    treasurer: "Olutanwa Esther",
    chapel_official: "Chapel Official",
    pastor: "Pastor Daniel Eze",
    worker: "Moyo Bello",
    attendance_usher: "Attendance Usher 01",
    member: "Favour Okafor",
  };
  const name = names[role];
  return {
    id: `demo-${role}`,
    name,
    email: `${name.toLowerCase().replaceAll(" ", ".")}@example.edu.ng`,
    role,
    roles: [role],
    branchId: "abeokuta-main",
    branchName: "Abeokuta Main Chapel",
    permissions: rolePermissions[role],
    initials: name
      .split(" ")
      .slice(0, 2)
      .map((part) => part[0])
      .join(""),
  };
}
