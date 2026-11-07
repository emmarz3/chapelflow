import { describe, expect, it } from "vitest";
import { isAssignableVolunteer, type VolunteerProfileEntry } from "../services/chapelflow";

const profile = (status: string, isActive: boolean): VolunteerProfileEntry => ({
  id: "profile-1",
  memberId: "member-1",
  memberName: "Ada Server",
  skills: "ushering",
  status,
  isActive,
});

describe("volunteer duty dropdown eligibility", () => {
  it("includes a newly created active profile", () => {
    const created = profile("ACTIVE", true);
    expect([created].filter(isAssignableVolunteer)).toEqual([created]);
  });

  it("excludes a pending profile", () => {
    expect([profile("PENDING", false)].filter(isAssignableVolunteer)).toEqual([]);
  });
});
