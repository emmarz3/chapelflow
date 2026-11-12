import { gsap } from "gsap";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../../features/auth-context";
import { INTRO_CONFIG, shouldPlayIntro } from "./intro.config";

function storageHas(kind: "sessionStorage" | "localStorage", key: string) {
  try {
    return window[kind].getItem(key) === "1";
  } catch {
    return false;
  }
}

export function ChapelFlowIntro() {
  const location = useLocation();
  const { user } = useAuth();
  const initialPathname = useRef(location.pathname);
  const finished = useRef(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLImageElement>(null);
  const [visible, setVisible] = useState(() => {
    if (typeof window === "undefined" || import.meta.env.MODE === "test" || user) return false;
    return shouldPlayIntro(
      window.location.pathname,
      INTRO_CONFIG.mode,
      storageHas("sessionStorage", INTRO_CONFIG.storageKey),
      storageHas("localStorage", INTRO_CONFIG.storageKey),
    );
  });

  const finish = useCallback(() => {
    if (finished.current) return;
    finished.current = true;
    document.documentElement.removeAttribute("data-intro-entry");
    window.dispatchEvent(new CustomEvent("chapelflow:intro-complete"));
    setVisible(false);
  }, []);

  useLayoutEffect(() => {
    if (!visible) {
      document.documentElement.removeAttribute("data-intro-entry");
      return;
    }
    const overlay = overlayRef.current;
    const logo = logoRef.current;
    if (!overlay || !logo) return;

    document.body.classList.add("cf-intro-active");
    try {
      if (INTRO_CONFIG.mode === "session") {
        window.sessionStorage.setItem(INTRO_CONFIG.storageKey, "1");
      } else if (INTRO_CONFIG.mode === "once") {
        window.localStorage.setItem(INTRO_CONFIG.storageKey, "1");
      }
    } catch {
      // Browser storage may be unavailable; the intro still finishes.
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (reducedMotion.matches) {
      finish();
      return () => document.body.classList.remove("cf-intro-active");
    }

    let active = true;
    let logoTimeout = 0;
    const context = gsap.context(() => {
      const timeline = gsap.timeline({ onComplete: finish });
      timeline
        .set(".cf-intro__brand-scene", { autoAlpha: 1 }, 0)
        .fromTo(".cf-intro__mark", { autoAlpha: 0, scale: 0.95 }, { autoAlpha: 1, scale: 1, duration: 0.45, ease: "power3.out" }, 0.12)
        .fromTo(".cf-intro__mark-draw", { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: 0.85, stagger: 0.12, ease: "power2.inOut" }, 0.24)
        .fromTo(".cf-intro__mark-fill", { autoAlpha: 0, scale: 0.92 }, { autoAlpha: 1, scale: 1, duration: 0.42, stagger: 0.08, ease: "power3.out" }, 0.68)
        .fromTo(".cf-intro__wordmark", { autoAlpha: 0, y: 18 }, { autoAlpha: 1, y: 0, duration: 0.55, ease: "power3.out" }, 1.05)
        .set(".cf-intro__wipe", { visibility: "visible", xPercent: -101 }, 1.94)
        .fromTo(".cf-intro__wipe", { xPercent: -101 }, { xPercent: 0, duration: 0.55, ease: "power3.inOut" }, 1.95)
        .set(".cf-intro__brand-scene", { autoAlpha: 0 }, 2.5)
        .set(".cf-intro__chapel-scene", { autoAlpha: 1 }, 2.5)
        .to(".cf-intro__wipe", { xPercent: 101, duration: 0.64, ease: "power3.inOut" }, 2.51)
        .fromTo(".cf-intro__chapel-logo", { autoAlpha: 0, y: 14, scale: 0.97 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.62, ease: "power3.out" }, 2.7)
        .to(overlay, { clipPath: "inset(0 0 100% 0)", duration: 0.68, ease: "power3.inOut" }, 3.68);
    }, overlay);

    const onLogoError = () => { if (active) finish(); };
    const onLogoLoad = () => window.clearTimeout(logoTimeout);
    logo.addEventListener("error", onLogoError);
    logo.addEventListener("load", onLogoLoad);
    if (logo.complete) {
      if (!logo.naturalWidth) onLogoError();
    } else {
      logoTimeout = window.setTimeout(onLogoError, INTRO_CONFIG.maxLogoWaitMs);
    }
    const onMotionChange = () => { if (reducedMotion.matches) finish(); };
    reducedMotion.addEventListener("change", onMotionChange);

    return () => {
      active = false;
      window.clearTimeout(logoTimeout);
      logo.removeEventListener("error", onLogoError);
      logo.removeEventListener("load", onLogoLoad);
      reducedMotion.removeEventListener("change", onMotionChange);
      context.revert();
      document.body.classList.remove("cf-intro-active");
    };
  }, [finish, visible]);

  useEffect(() => {
    if (visible && (location.pathname !== initialPathname.current || user)) finish();
  }, [finish, location.pathname, user, visible]);

  if (!visible) return null;

  return (
    <div className="cf-intro" ref={overlayRef} role="presentation">
      <div className="cf-intro__brand-scene" aria-hidden="true">
        <div className="cf-intro__brand-lockup">
          <svg className="cf-intro__mark" viewBox="0 0 240 220" aria-hidden="true">
            <defs>
              <linearGradient id="cf-intro-gradient" x1="0" y1="1" x2="1" y2="0">
                <stop offset="0" stopColor="#4c1798" />
                <stop offset="0.52" stopColor="#6d2dce" />
                <stop offset="1" stopColor="#1685ee" />
              </linearGradient>
            </defs>
            <path className="cf-intro__mark-fill" d="M18 173 C53 143 83 147 119 170 C157 194 197 197 225 166 C209 211 165 220 119 194 C78 171 49 160 18 185 Z" fill="url(#cf-intro-gradient)" />
            <path className="cf-intro__mark-draw" d="M52 151 V82 L120 31 L188 82 V118" fill="none" stroke="url(#cf-intro-gradient)" strokeWidth="16" strokeLinecap="square" strokeLinejoin="round" pathLength="1" strokeDasharray="1" />
            <path className="cf-intro__mark-fill" d="M96 168 V114 C96 98 107 87 120 87 C133 87 144 98 144 114 V168" fill="url(#cf-intro-gradient)" />
            <path className="cf-intro__mark-fill" d="M120 106 V147 M108 119 H132" fill="none" stroke="#fff" strokeWidth="7" strokeLinecap="square" />
            <path className="cf-intro__mark-draw" d="M120 4 V31 M108 16 H132" fill="none" stroke="#4c1798" strokeWidth="7" strokeLinecap="square" pathLength="1" strokeDasharray="1" />
            <path className="cf-intro__mark-fill" d="M184 132 C208 112 229 119 234 121 C216 119 202 128 202 143 C202 158 216 166 234 162 C222 181 184 183 174 157 C169 146 174 138 184 132 Z" fill="url(#cf-intro-gradient)" />
          </svg>
          <p className="cf-intro__wordmark"><span>Chapel</span><strong>Flow</strong></p>
        </div>
      </div>
      <div className="cf-intro__chapel-scene">
        <img ref={logoRef} className="cf-intro__chapel-logo" src={INTRO_CONFIG.brand.institutionAsset} alt="Chrisland University Chapel logo" fetchPriority="high" />
      </div>
      <div className="cf-intro__wipe" aria-hidden="true" />
      <button className="cf-intro__skip" type="button" onClick={finish}>Skip intro</button>
    </div>
  );
}
