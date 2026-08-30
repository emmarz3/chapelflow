export const roles = [
  "super_admin",
  "chapel_admin",
  "chaplain",
  "student_chaplain",
  "treasurer",
  "chapel_official",
  "pastor",
  "worker",
  "attendance_usher",
  "member",
] as const;

export type Role = (typeof roles)[number];
export type ServerPermission =
  | "dashboard:view"
  | "members:read"
  | "members:write"
  | "attendance:read"
  | "attendance:write"
  | "attendance:scan"
  | "attendance:manual"
  | "community:view"
  | "community:view_all"
  | "community:manage"
  | "leadership:view"
  | "leadership:manage"
  | "chapel:announce";

const permissions: Record<Role, ServerPermission[]> = {
  super_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "attendance:scan",
    "attendance:manual",
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
    "community:view",
    "community:view_all",
    "leadership:view",
    "chapel:announce",
  ],
  student_chaplain: [
    "dashboard:view",
    "members:read",
    "attendance:read",
    "community:view",
    "community:view_all",
    "leadership:view",
    "chapel:announce",
  ],
  treasurer: [
    "dashboard:view",
    "attendance:read",
    "community:view",
    "leadership:view",
  ],
  chapel_official: [
    "dashboard:view",
    "attendance:read",
    "community:view",
    "leadership:view",
  ],
  pastor: [
    "dashboard:view",
    "attendance:read",
    "community:view",
    "community:view_all",
    "leadership:view",
  ],
  worker: ["dashboard:view", "attendance:read", "community:view"],
  attendance_usher: ["attendance:read", "attendance:scan", "attendance:manual"],
  member: ["dashboard:view", "attendance:read", "community:view"],
};

export function permissionsFor(role: Role) {
  return permissions[role];
}

export function roleHasPermission(role: Role, permission: ServerPermission) {
  return permissions[role].includes(permission);
}

export function rolesHavePermission(
  userRoles: Role[],
  permission: ServerPermission,
) {
  return userRoles.some((role) => roleHasPermission(role, permission));
}
