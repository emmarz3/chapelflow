import { BRAND_ASSETS } from "../../lib/brand-assets";

export type IntroMode = "always" | "session" | "once" | "disabled";

export const INTRO_CONFIG = {
  enabled: true,
  mode: "session" as IntroMode,
  storageKey: "chapelflow:intro-seen",
  brand: {
    institutionAsset: BRAND_ASSETS.institutionLogo,
  },
  maxLogoWaitMs: 3000,
} as const;

export function shouldPlayIntro(
  pathname: string,
  mode: IntroMode,
  sessionSeen: boolean,
  permanentlySeen: boolean,
) {
  if (!INTRO_CONFIG.enabled || mode === "disabled") return false;
  if (pathname !== "/") return false;
  if (mode === "session" && sessionSeen) return false;
  if (mode === "once" && permanentlySeen) return false;
  return true;
}
