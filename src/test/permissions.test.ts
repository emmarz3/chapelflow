import { describe, expect, it } from "vitest";
import { buildDemoUser, hasPermission } from "../lib/permissions";

describe("role permissions", () => {
  it("keeps member access scoped to personal portal features", () => {
    const member = buildDemoUser("member");
    expect(hasPermission(member, "attendance:read")).toBe(true);
    expect(hasPermission(member, "members:read")).toBe(false);
    expect(hasPermission(member, "finance:read")).toBe(false);
    expect(hasPermission(member, "media:write")).toBe(false);
  });

  it("separates read-only ministry access from mutation permissions", () => {
    const pastor = buildDemoUser("pastor");
    const worker = buildDemoUser("worker");
    expect(hasPermission(pastor, "members:read")).toBe(true);
    expect(hasPermission(pastor, "members:write")).toBe(false);
    expect(hasPermission(pastor, "workers:write")).toBe(false);
    expect(hasPermission(worker, "workers:acknowledge")).toBe(true);
    expect(hasPermission(worker, "workers:write")).toBe(false);
  });

  it("allows headquarters administrators to manage branches and audit records", () => {
    const administrator = buildDemoUser("super_admin");
    expect(hasPermission(administrator, "branches:manage")).toBe(true);
    expect(hasPermission(administrator, "audit:read")).toBe(true);
  });
});
