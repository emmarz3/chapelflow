import type { Permission, Role, User } from "../types/domain";

const rolePermissions: Record<Role, Permission[]> = {
  super_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "events:read",
    "events:write",
    "finance:read",
    "finance:write",
    "communication:write",
    "workers:read",
    "workers:write",
    "workers:acknowledge",
    "assets:read",
    "assets:write",
    "media:write",
    "cms:write",
    "analytics:read",
    "branches:manage",
    "audit:read",
    "settings:manage",
  ],
  chapel_admin: [
    "dashboard:view",
    "members:read",
    "members:write",
    "attendance:read",
    "attendance:write",
    "events:read",
    "events:write",
    "finance:read",
    "finance:write",
    "communication:write",
    "workers:read",
    "workers:write",
    "workers:acknowledge",
    "assets:read",
    "assets:write",
    "media:write",
    "cms:write",
    "analytics:read",
    "audit:read",
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
  ],
  worker: [
    "dashboard:view",
    "attendance:read",
    "events:read",
    "workers:read",
    "workers:acknowledge",
  ],
  member: ["dashboard:view", "attendance:read", "events:read"],
};

export function hasPermission(user: User | null, permission?: Permission) {
  return !permission || Boolean(user?.permissions.includes(permission));
}

export function buildDemoUser(role: Role): User {
  const names: Record<Role, string> = {
    super_admin: "Dr. Tola Adebayo",
    chapel_admin: "Grace Adeyemi",
    pastor: "Pastor Daniel Eze",
    worker: "Moyo Bello",
    member: "Favour Okafor",
  };
  const name = names[role];
  return {
    id: `demo-${role}`,
    name,
    email: `${name.toLowerCase().replaceAll(" ", ".")}@example.edu.ng`,
    role,
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
