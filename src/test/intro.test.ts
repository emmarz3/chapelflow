import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { INTRO_CONFIG, shouldPlayIntro } from "../components/intro/intro.config";
import { BRAND_ASSETS, brandFallbackFor } from "../lib/brand-assets";

describe("ChapelFlow introduction policy", () => {
  it("plays once per session on the homepage", () => {
    expect(shouldPlayIntro("/", "session", false, false)).toBe(true);
    expect(shouldPlayIntro("/", "session", true, false)).toBe(false);
    expect(shouldPlayIntro("/about", "session", false, false)).toBe(false);
  });

  it("does not interrupt protected application routes", () => {
    expect(shouldPlayIntro("/app", "always", false, false)).toBe(false);
    expect(shouldPlayIntro("/usher/attendance", "always", false, false)).toBe(false);
  });

  it("supports persistent and disabled policies", () => {
    expect(shouldPlayIntro("/", "once", false, true)).toBe(false);
    expect(shouldPlayIntro("/", "disabled", false, false)).toBe(false);
  });

  it("ships a real chapel logo instead of a Git LFS pointer", () => {
    expect(INTRO_CONFIG.brand.institutionAsset).toBe(BRAND_ASSETS.institutionLogo);
    expect(brandFallbackFor(BRAND_ASSETS.institutionLogo)).toBe(BRAND_ASSETS.institutionLogo);
    const logo = readFileSync(resolve("public", INTRO_CONFIG.brand.institutionAsset.slice(1)), "utf8");
    const embeddedPng = logo.match(/data:image\/png;base64,([A-Za-z0-9+/=]+)/)?.[1];
    expect(embeddedPng).toBeTruthy();
    const image = Buffer.from(embeddedPng ?? "", "base64");
    expect(image.subarray(0, 8)).toEqual(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  });
});
