import { describe, expect, it } from "vitest";
import { shouldPlayIntro } from "../components/intro/intro.config";

describe("ChapelFlow introduction policy", () => {
  it("replays on every home-page refresh and skips repeat visits elsewhere", () => {
    expect(shouldPlayIntro("/", "session", false, false)).toBe(true);
    expect(shouldPlayIntro("/", "session", true, false)).toBe(true);
    expect(shouldPlayIntro("/login", "session", true, false)).toBe(false);
  });

  it("does not interrupt protected application routes", () => {
    expect(shouldPlayIntro("/app", "always", false, false)).toBe(false);
    expect(shouldPlayIntro("/usher/attendance", "always", false, false)).toBe(false);
  });

  it("supports persistent and disabled policies", () => {
    expect(shouldPlayIntro("/login", "once", false, true)).toBe(false);
    expect(shouldPlayIntro("/", "disabled", false, false)).toBe(false);
  });
});
