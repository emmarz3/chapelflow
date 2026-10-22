export type IntroMode = "always" | "session" | "once" | "disabled";
export type IntroStage =
  | "anticipation"
  | "mark"
  | "wordmark"
  | "brandHold"
  | "transitionToInstitution"
  | "institution"
  | "institutionHold"
  | "transitionToApplication";

export const INTRO_CONFIG = {
  enabled: true,
  mode: "session" as IntroMode,
  storageKey: "chapelflow:intro-seen",
  replayOnHomeRefresh: true,
  skipPathPrefixes: ["/app", "/kiosk", "/usher", "/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/verify-otp", "/change-password-required", "/setup/admin", "/access-denied", "/offline", "/404"],
  brand: {
    useTagline: false,
    chapelFlowAsset: "/chapelflow-brand.jpg",
    institutionAsset: "/chrisland-university-chapel.png",
  },
  timing: {
    anticipation: 600,
    mark: 1200,
    wordmark: 800,
    brandHold: 700,
    transitionToInstitution: 1000,
    institution: 900,
    institutionHold: 600,
    transitionToApplication: 1000,
  },
} as const;

export const INTRO_SEQUENCE: { stage: IntroStage; duration: number }[] = [
  { stage: "anticipation", duration: INTRO_CONFIG.timing.anticipation },
  { stage: "mark", duration: INTRO_CONFIG.timing.mark },
  { stage: "wordmark", duration: INTRO_CONFIG.timing.wordmark },
  { stage: "brandHold", duration: INTRO_CONFIG.timing.brandHold },
  {
    stage: "transitionToInstitution",
    duration: INTRO_CONFIG.timing.transitionToInstitution,
  },
  { stage: "institution", duration: INTRO_CONFIG.timing.institution },
  {
    stage: "institutionHold",
    duration: INTRO_CONFIG.timing.institutionHold,
  },
  {
    stage: "transitionToApplication",
    duration: INTRO_CONFIG.timing.transitionToApplication,
  },
];

export const REDUCED_MOTION_SEQUENCE: { stage: IntroStage; duration: number }[] = [
  { stage: "brandHold", duration: 300 },
  { stage: "institution", duration: 280 },
  { stage: "transitionToApplication", duration: 320 },
];

export function shouldPlayIntro(
  pathname: string,
  mode: IntroMode,
  sessionSeen: boolean,
  permanentlySeen: boolean,
) {
  if (!INTRO_CONFIG.enabled || mode === "disabled") return false;
  if (INTRO_CONFIG.skipPathPrefixes.some((prefix) => pathname.startsWith(prefix))) {
    return false;
  }
  if (pathname === "/" && INTRO_CONFIG.replayOnHomeRefresh) return true;
  if (mode === "session" && sessionSeen) return false;
  if (mode === "once" && permanentlySeen) return false;
  return true;
}
