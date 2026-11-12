export const COOKIE_CONSENT_KEY = "chapelflow:cookie-consent-v1";
export const COOKIE_CONSENT_EVENT = "chapelflow:manage-cookies";
export type CookieConsentChoice = "all" | "necessary";

export interface CookieConsentRecord {
  choice: CookieConsentChoice;
  version: 1;
  savedAt: string;
}

export function readCookieConsent(): CookieConsentChoice | null {
  try {
    const raw = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!raw) return null;
    const record: unknown = JSON.parse(raw);
    if (record && typeof record === "object" && "choice" in record) {
      const choice = (record as CookieConsentRecord).choice;
      return choice === "all" || choice === "necessary" ? choice : null;
    }
  } catch {
    // Storage may be unavailable or unreadable.
  }
  return null;
}

export function writeCookieConsent(choice: CookieConsentChoice) {
  const record: CookieConsentRecord = {
    choice,
    version: 1,
    savedAt: new Date().toISOString(),
  };
  try {
    localStorage.setItem(COOKIE_CONSENT_KEY, JSON.stringify(record));
  } catch {
    // Preference stays in memory for this page session.
  }
  return record;
}

export function requestCookiePreferenceReview() {
  window.dispatchEvent(new Event(COOKIE_CONSENT_EVENT));
}

export function isSafeExternalUrl(value: string | undefined | null) {
  const trimmed = value?.trim() ?? "";
  if (!trimmed) return null;
  try {
    const url = new URL(trimmed);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    return url.toString();
  } catch {
    return null;
  }
}
