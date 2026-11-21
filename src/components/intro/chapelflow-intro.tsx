import { gsap } from "gsap";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
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
    if (
      typeof window === "undefined" ||
      import.meta.env.MODE === "test" ||
      user
    )
      return false;
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
        .fromTo(
          ".cf-intro__mark",
          { autoAlpha: 0, y: 12 },
          { autoAlpha: 1, y: 0, duration: 0.5, ease: "power2.out" },
          0.1,
        )
        .fromTo(
          ".cf-intro__mark-draw",
          { strokeDashoffset: 1 },
          {
            strokeDashoffset: 0,
            duration: 0.65,
            stagger: 0.08,
            ease: "power2.inOut",
          },
          0.15,
        )
        .fromTo(
          ".cf-intro__mark-fill",
          { autoAlpha: 0 },
          { autoAlpha: 1, duration: 0.35, stagger: 0.04 },
          0.5,
        )
        .fromTo(
          ".cf-intro__wordmark",
          { autoAlpha: 0, y: 16 },
          { autoAlpha: 1, y: 0, duration: 0.5, ease: "power3.out" },
          0.6,
        )
        .fromTo(
          ".cf-intro__tagline",
          { autoAlpha: 0, y: 8 },
          { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out" },
          0.85,
        )
        .fromTo(
          ".cf-intro__rule",
          { scaleX: 0 },
          { scaleX: 1, duration: 1.2, ease: "power2.inOut" },
          0.15,
        )
        .set(".cf-intro__wipe", { visibility: "visible", xPercent: -130 }, 1.6)
        .to(
          ".cf-intro__wipe",
          { xPercent: 0, duration: 0.5, ease: "power3.inOut" },
          1.6,
        )
        .set(".cf-intro__brand-scene", { autoAlpha: 0 }, 2.1)
        .set(".cf-intro__chapel-scene", { autoAlpha: 1 }, 2.1)
        .to(
          ".cf-intro__wipe",
          { xPercent: 130, duration: 0.55, ease: "power3.inOut" },
          2.12,
        )
        .fromTo(
          ".cf-intro__chapel-logo",
          { autoAlpha: 0, y: 14 },
          { autoAlpha: 1, y: 0, duration: 0.45, ease: "power2.out" },
          2.25,
        )
        .fromTo(
          ".cf-intro__chapel-copy",
          { autoAlpha: 0, y: 10 },
          { autoAlpha: 1, y: 0, duration: 0.4, ease: "power2.out" },
          2.45,
        )
        .to(
          overlay,
          { yPercent: -100, duration: 0.65, ease: "power3.inOut" },
          3.25,
        );
    }, overlay);

    const onLogoError = () => {
      if (active) finish();
    };
    const onLogoLoad = () => window.clearTimeout(logoTimeout);
    logo.addEventListener("error", onLogoError);
    logo.addEventListener("load", onLogoLoad);
    if (logo.complete) {
      if (!logo.naturalWidth) onLogoError();
    } else {
      logoTimeout = window.setTimeout(onLogoError, INTRO_CONFIG.maxLogoWaitMs);
    }
    const onMotionChange = () => {
      if (reducedMotion.matches) finish();
    };
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
    if (visible && (location.pathname !== initialPathname.current || user))
      finish();
  }, [finish, location.pathname, user, visible]);

  if (!visible) return null;

  return (
    <div className="cf-intro" ref={overlayRef} role="presentation">
      <div className="cf-intro__brand-scene" aria-hidden="true">
        <div className="cf-intro__edge" aria-hidden="true" />
        <div className="cf-intro__brand-lockup">
          <p className="cf-intro__eyebrow">Chrisland University Chapel</p>
          <svg
            className="cf-intro__mark"
            viewBox="0 0 240 220"
            aria-hidden="true"
          >
            <path
              className="cf-intro__mark-fill"
              d="M18 173 C53 143 83 147 119 170 C157 194 197 197 225 166 C209 211 165 220 119 194 C78 171 49 160 18 185 Z"
              fill="#4c266a"
            />
            <path
              className="cf-intro__mark-draw"
              d="M52 151 V82 L120 31 L188 82 V118"
              fill="none"
              stroke="#4c266a"
              strokeWidth="16"
              strokeLinecap="square"
              strokeLinejoin="round"
              pathLength="1"
              strokeDasharray="1"
            />
            <path
              className="cf-intro__mark-fill"
              d="M96 168 V114 C96 98 107 87 120 87 C133 87 144 98 144 114 V168"
              fill="#4c266a"
            />
            <path
              className="cf-intro__mark-fill"
              d="M120 106 V147 M108 119 H132"
              fill="none"
              stroke="#fff"
              strokeWidth="7"
              strokeLinecap="square"
            />
            <path
              className="cf-intro__mark-draw"
              d="M120 4 V31 M108 16 H132"
              fill="none"
              stroke="#4c266a"
              strokeWidth="7"
              strokeLinecap="square"
              pathLength="1"
              strokeDasharray="1"
            />
            <path
              className="cf-intro__mark-fill"
              d="M184 132 C208 112 229 119 234 121 C216 119 202 128 202 143 C202 158 216 166 234 162 C222 181 184 183 174 157 C169 146 174 138 184 132 Z"
              fill="#4c266a"
            />
          </svg>
          <p className="cf-intro__wordmark">
            <span>Chapel</span>
            <strong>Flow</strong>
          </p>
          <p className="cf-intro__tagline">Faith. Community. Connection.</p>
          <span className="cf-intro__rule" />
        </div>
      </div>
      <div className="cf-intro__chapel-scene">
        <div className="cf-intro__edge" aria-hidden="true" />
        <div className="cf-intro__chapel-lockup">
          <p className="cf-intro__chapel-kicker">
            Rooted in faith · Growing together
          </p>
          <div className="cf-intro__chapel-emblem">
            <img
              ref={logoRef}
              className="cf-intro__chapel-logo"
              src={INTRO_CONFIG.brand.institutionAsset}
              alt="Chrisland University Chapel logo"
              fetchPriority="high"
            />
          </div>
          <p className="cf-intro__chapel-copy">
            A place to belong<span>.</span>
          </p>
        </div>
      </div>
      <div className="cf-intro__wipe" aria-hidden="true" />
      <button className="cf-intro__skip" type="button" onClick={finish}>
        Skip intro
      </button>
    </div>
  );
}
