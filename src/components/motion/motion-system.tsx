import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  useEffect,
  useLayoutEffect,
  useState,
  type RefObject,
} from "react";

gsap.registerPlugin(ScrollTrigger);

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
    const root = rootRef.current;
    if (pathname !== "/" || !root || prefersReducedMotion()) return;
    const home = root.querySelector<HTMLElement>(".cuc-home");
    const hero = home?.querySelector<HTMLElement>(".cuc-home__hero");
    if (!home || !hero) return;
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
        const revealAtScroll = (
          triggerSelector: string,
          targetSelectors: string[],
          direction: "up" | "left" | "right" = "up",
        ) => {
          const trigger = home.querySelector<HTMLElement>(triggerSelector);
          const targets = targetSelectors
            .map((selector) => home.querySelector<HTMLElement>(selector))
            .filter((target): target is HTMLElement => Boolean(target));
          if (!trigger || !targets.length) return;

          const from =
            direction === "left"
              ? { autoAlpha: 0, x: -20 }
              : direction === "right"
                ? { autoAlpha: 0, x: 20 }
                : { autoAlpha: 0, y: 12 };
          const to =
            direction === "left" || direction === "right"
              ? { autoAlpha: 1, x: 0 }
              : { autoAlpha: 1, y: 0 };

          gsap.fromTo(targets, from, {
            ...to,
            duration: 0.58,
            stagger: targets.length > 1 ? 0.08 : 0,
            ease: "power3.out",
            clearProps: "opacity,visibility,transform",
            scrollTrigger: {
              trigger,
              start: "top 84%",
              once: true,
            },
          });
        };

        revealAtScroll(".cuc-home__daily-verse", [
          ".cuc-home__daily-verse blockquote",
          ".cuc-home__daily-verse-reference",
        ]);
        revealAtScroll(".cuc-home__worship", [
          ".cuc-home__worship > div",
          ".cuc-home__service-link",
          ".cuc-home__schedule-note",
        ]);

        const revealPair = (
          triggerSelector: string,
          firstSelector: string,
          secondSelector: string,
        ) => {
          const trigger = home.querySelector<HTMLElement>(triggerSelector);
          const first = home.querySelector<HTMLElement>(firstSelector);
          const second = home.querySelector<HTMLElement>(secondSelector);
          if (!trigger || !first || !second) return;
          const timeline = gsap.timeline({
            defaults: {
              duration: 0.62,
              ease: "power3.out",
              clearProps: "opacity,visibility,transform",
            },
            scrollTrigger: { trigger, start: "top 82%", once: true },
          });
          timeline
            .fromTo(first, { autoAlpha: 0, x: -18 }, { autoAlpha: 1, x: 0 }, 0)
            .fromTo(second, { autoAlpha: 0, x: 18 }, { autoAlpha: 1, x: 0 }, 0.08);
        };

        revealPair(
          ".cuc-home__belonging",
          ".cuc-home__belonging > div:first-child",
          ".cuc-home__photo-rail",
        );
        revealPair(
          ".cuc-home__chaplain",
          ".cuc-home__chaplain-photo",
          ".cuc-home__chaplain > div:nth-child(2)",
        );
        revealPair(
          ".cuc-home__attendance",
          ".cuc-home__attendance > div:first-child",
          ".cuc-home__attendance-art",
        );

        revealAtScroll(".cuc-home__closing", [
          ".cuc-home__closing-copy",
          ".cuc-home__closing-media",
        ], "up");
      }, home);
    };
    const intro = document.querySelector(".cf-intro");
    if (intro) window.addEventListener("chapelflow:intro-complete", reveal, { once: true });
    else reveal();
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
