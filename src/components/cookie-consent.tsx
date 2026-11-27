import { Cookie } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  COOKIE_CONSENT_EVENT,
  readCookieConsent,
  writeCookieConsent,
  type CookieConsentChoice,
} from "../lib/cookie-consent";

export function CookieConsent() {
  const [choice, setChoice] = useState<CookieConsentChoice | null>(readCookieConsent);
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    const open = () => setReviewing(true);
    window.addEventListener(COOKIE_CONSENT_EVENT, open);
    return () => window.removeEventListener(COOKIE_CONSENT_EVENT, open);
  }, []);

  const save = (nextChoice: CookieConsentChoice) => {
    writeCookieConsent(nextChoice);
    setChoice(nextChoice);
    setReviewing(false);
  };

  if (import.meta.env.VITE_E2E_TEST === "true" && !reviewing) return null;
  if (choice && !reviewing) return null;

  return (
    <section className="cookie-consent" role="region" aria-labelledby="cookie-consent-title" tabIndex={-1}>
      <Cookie aria-hidden="true" />
      <div>
        <h2 id="cookie-consent-title">Your privacy, your choice</h2>
        <p>ChapelFlow uses essential cookies for secure sign-in and reliable service. Optional analytics and marketing cookies are not active in this version.</p>
        <Link to="/cookies">Read the Cookie Policy</Link>
      </div>
      <div className="cookie-consent__actions">
        <button className="button button--secondary" type="button" onClick={() => save("necessary")}>Use necessary only</button>
        <button className="button button--primary" type="button" onClick={() => save("all")}>Accept cookies</button>
      </div>
    </section>
  );
}
