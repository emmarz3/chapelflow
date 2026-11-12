import { gsap } from "gsap";
import {
  useEffect,
  useLayoutEffect,
  useState,
  type RefObject,
} from "react";
export const MOTION = {
  duration: {
    micro: 0.16,
    fast: 0.24,
    normal: 0.4,
    medium: 0.55,
    slow: 0.8,
  },
  ease: {
    standard: "power2.out",
    smooth: "power3.out",
    enter: "power4.out",
    exit: "power2.inOut",
  },
  distance: { xs: 4, sm: 8, md: 16, lg: 28 },
} as const;

function prefersReducedMotion() {
  if (import.meta.env.MODE === "test") return true;
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function useReducedMotionPreference() {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}


export function useAuthMotion(
  rootRef: RefObject<HTMLElement | null>,
  pathname: string,
) {
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root || pathname === "/login" || prefersReducedMotion()) return;
    const context = gsap.context(() => {
      const timeline = gsap.timeline({ defaults: { ease: MOTION.ease.enter } });
      timeline
        .fromTo(
          ".auth-visual .brand, .auth-visual blockquote, .auth-visual > p",
          { autoAlpha: 0, y: 12 },
          {
            autoAlpha: 1,
            y: 0,
            duration: MOTION.duration.medium,
            stagger: 0.06,
          },
        )
        .fromTo(
          ".auth-card > *:not(.completion-figure), .auth-main > .auth-back",
          { autoAlpha: 0, y: 12 },
          {
            autoAlpha: 1,
            y: 0,
            duration: MOTION.duration.normal,
            stagger: 0.035,
          },
          "-=0.32",
        );
    }, root);
    return () => context.revert();
  }, [pathname, rootRef]);
}

export function usePublicMotion(
  rootRef: RefObject<HTMLElement | null>,
  pathname: string,
) {
  useLayoutEffect(() => {
    if (pathname !== "/" || prefersReducedMotion() || !document.querySelector(".cf-intro")) return;
    const hero = rootRef.current?.querySelector<HTMLElement>(".cuc-home__hero");
    if (!hero) return;
    let context: ReturnType<typeof gsap.context> | undefined;
    const reveal = () => {
      if (context) return;
      context = gsap.context(() => {
        gsap
          .timeline({ defaults: { ease: "power3.out" } })
          .fromTo(
            ".cuc-home__hero-image",
            { autoAlpha: 0.75 },
            { autoAlpha: 1, duration: 0.65, clearProps: "opacity,visibility" },
            0,
          )
          .fromTo(
            ".cuc-home__hero-copy > *",
            { autoAlpha: 0, y: 16 },
            {
              autoAlpha: 1,
              y: 0,
              duration: 0.58,
              stagger: 0.07,
              clearProps: "opacity,visibility,transform",
            },
            0.12,
          );
      }, hero);
    };
    window.addEventListener("chapelflow:intro-complete", reveal, { once: true });
    return () => {
      window.removeEventListener("chapelflow:intro-complete", reveal);
      context?.revert();
    };
  }, [pathname, rootRef]);
}

export function useFeatureMotion(
  rootRef: RefObject<HTMLElement | null>,
  dependency: unknown,
) {
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root || prefersReducedMotion()) return;
    const context = gsap.context(() => {
      const targets = root.querySelectorAll<HTMLElement>(
        ":scope > *, .chapel-pass__body > *, .scanner-panel, .scanner-activity",
      );
      targets.forEach((target) => {
        target.dataset.motionRevealed = "true";
      });
      gsap.fromTo(
        targets,
        { autoAlpha: 0, y: 14, scale: 0.994 },
        {
          autoAlpha: 1,
          y: 0,
          scale: 1,
          duration: MOTION.duration.normal,
          stagger: 0.045,
          ease: MOTION.ease.enter,
          clearProps: "opacity,visibility,transform",
        },
      );
    }, root);
    return () => context.revert();
  }, [dependency, rootRef]);
}
