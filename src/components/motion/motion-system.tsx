import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { useLocation } from "react-router-dom";

if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
  gsap.registerPlugin(ScrollTrigger);
}

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

function animateMetricValues(root: HTMLElement) {
  const values = root.querySelectorAll<HTMLElement>(
    ".metric-card > strong, .service-status > div > strong",
  );
  values.forEach((element) => {
    if (element.dataset.motionCounted === "true") return;
    const original = element.textContent?.trim() ?? "";
    const match = original.match(/^([\d,.]+)(%)?$/);
    if (!match) return;
    const target = Number(match[1]?.replaceAll(",", ""));
    if (!Number.isFinite(target)) return;
    element.dataset.motionCounted = "true";
    const state = { value: 0 };
    gsap.to(state, {
      value: target,
      duration: Math.min(0.8, 0.42 + target / 4_000),
      ease: MOTION.ease.smooth,
      onUpdate: () => {
        element.textContent = `${Math.round(state.value).toLocaleString("en-GB")}${match[2] ?? ""}`;
      },
    });
  });
}

function revealPortalContent(root: HTMLElement) {
  const candidates = Array.from(
    root.querySelectorAll<HTMLElement>(
      ".page-header, .service-status, .member-hero, .chapel-pass, .metric-card, .panel, .table-panel, .module-list, .calendar-panel, .attendance-livebar, .insight-note, .workflow-placeholder, .error-state, .empty-state",
    ),
  ).filter((element) => element.dataset.motionRevealed !== "true");
  if (!candidates.length) return;
  candidates.forEach((element) => {
    element.dataset.motionRevealed = "true";
  });
  gsap.fromTo(
    candidates.slice(0, 18),
    { autoAlpha: 0, y: MOTION.distance.md, scale: 0.992 },
    {
      autoAlpha: 1,
      y: 0,
      scale: 1,
      duration: MOTION.duration.normal,
      stagger: 0.035,
      ease: MOTION.ease.enter,
      clearProps: "opacity,visibility,transform",
    },
  );

  const rows = Array.from(root.querySelectorAll<HTMLElement>("tbody tr"))
    .filter((row) => row.dataset.motionRevealed !== "true")
    .slice(0, 12);
  rows.forEach((row) => {
    row.dataset.motionRevealed = "true";
  });
  if (rows.length) {
    gsap.fromTo(
      rows,
      { autoAlpha: 0, y: 7 },
      {
        autoAlpha: 1,
        y: 0,
        duration: MOTION.duration.fast,
        stagger: 0.025,
        ease: MOTION.ease.standard,
        clearProps: "opacity,visibility,transform",
      },
    );
  }
  animateMetricValues(root);
}

export function usePortalMotion(
  contentRef: RefObject<HTMLElement | null>,
  sidebarRef: RefObject<HTMLElement | null>,
  pathname: string,
) {
  useLayoutEffect(() => {
    const content = contentRef.current;
    if (!content || prefersReducedMotion()) return;
    const context = gsap.context(() => revealPortalContent(content), content);
    const observer = new MutationObserver(() => revealPortalContent(content));
    observer.observe(content, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      context.revert();
    };
  }, [contentRef, pathname]);

  useLayoutEffect(() => {
    const sidebar = sidebarRef.current;
    if (!sidebar || prefersReducedMotion()) return;
    const context = gsap.context(() => {
      const timeline = gsap.timeline({ defaults: { ease: MOTION.ease.enter } });
      timeline
        .fromTo(
          ".sidebar__brand",
          { autoAlpha: 0, x: -8 },
          { autoAlpha: 1, x: 0, duration: MOTION.duration.normal },
        )
        .fromTo(
          ".nav-group",
          { autoAlpha: 0, x: -8 },
          {
            autoAlpha: 1,
            x: 0,
            duration: MOTION.duration.fast,
            stagger: 0.045,
          },
          "-=0.2",
        );
    }, sidebar);
    return () => context.revert();
  }, [sidebarRef]);

  useLayoutEffect(() => {
    const active = sidebarRef.current?.querySelector<HTMLElement>(
      ".nav-group a.active",
    );
    if (!active || prefersReducedMotion()) return;
    gsap.fromTo(
      active,
      { x: -4, backgroundColor: "rgba(255,255,255,0.04)" },
      {
        x: 0,
        backgroundColor: "rgba(255,255,255,0.11)",
        duration: MOTION.duration.fast,
        ease: MOTION.ease.standard,
        clearProps: "transform,backgroundColor",
      },
    );
  }, [pathname, sidebarRef]);
}

export function useAuthMotion(
  rootRef: RefObject<HTMLElement | null>,
  pathname: string,
) {
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root || prefersReducedMotion()) return;
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
          ".auth-card > *, .auth-main > .auth-back",
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
    if (!root || prefersReducedMotion()) return;
    const contexts: ReturnType<typeof gsap.context>[] = [];
    const triggers: ScrollTrigger[] = [];
    const animatedTargets = new Set<HTMLElement>();
    let introFinished = !document.querySelector(".cf-intro");

    const animateHero = () => {
      introFinished = true;
      const hero = root.querySelector<HTMLElement>(".hero");
      if (!hero || hero.dataset.motionHero === "true") return;
      hero.dataset.motionHero = "true";
      const context = gsap.context(() => {
        gsap
          .timeline({ defaults: { ease: MOTION.ease.enter } })
          .fromTo(
            ".hero__content > *",
            { autoAlpha: 0, y: 18 },
            {
              autoAlpha: 1,
              y: 0,
              duration: MOTION.duration.medium,
              stagger: 0.065,
            },
          )
          .fromTo(
            ".service-ribbon",
            { autoAlpha: 0, y: 16 },
            { autoAlpha: 1, y: 0, duration: MOTION.duration.normal },
            "-=0.28",
          );
      }, hero);
      contexts.push(context);
    };

    if (!introFinished) {
      window.addEventListener("chapelflow:intro-complete", animateHero, {
        once: true,
      });
    } else {
      animateHero();
    }

    const prepareSections = () => {
      if (introFinished) animateHero();
      const sections = Array.from(
        root.querySelectorAll<HTMLElement>(
          ".section, .livestream-strip, .content-page > header, .content-page > .section",
        ),
      ).filter((section) => section.dataset.motionScroll !== "true");
      sections.forEach((section) => {
        section.dataset.motionScroll = "true";
        const targets = section.querySelectorAll<HTMLElement>(
          ".section-heading, .welcome__copy, .public-event-grid > article, .sermon-feature__visual, .sermon-feature > div:last-child, .ministry-grid > article, .info-sections > section, .detail-feature > *",
        );
        const elements = targets.length
          ? Array.from(targets).slice(0, 10)
          : [section];
        elements.forEach((element) => animatedTargets.add(element));
        gsap.set(elements, { autoAlpha: 0, y: 20 });
        const trigger = ScrollTrigger.create({
          trigger: section,
          start: "top 88%",
          once: true,
          onEnter: () => {
            gsap.to(elements, {
              autoAlpha: 1,
              y: 0,
              duration: MOTION.duration.medium,
              stagger: 0.045,
              ease: MOTION.ease.enter,
              clearProps: "opacity,visibility,transform",
            });
          },
        });
        triggers.push(trigger);
      });
    };

    prepareSections();
    const observer = new MutationObserver(prepareSections);
    observer.observe(root, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      window.removeEventListener("chapelflow:intro-complete", animateHero);
      triggers.forEach((trigger) => trigger.kill());
      contexts.forEach((context) => context.revert());
      gsap.set(Array.from(animatedTargets), {
        clearProps: "opacity,visibility,transform",
      });
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

export function RouteMotionLayer() {
  const location = useLocation();
  const rootRef = useRef<HTMLDivElement>(null);
  const previousPath = useRef(location.pathname);

  useLayoutEffect(() => {
    if (previousPath.current === location.pathname) return;
    previousPath.current = location.pathname;
    const root = rootRef.current;
    if (!root || prefersReducedMotion()) return;
    const context = gsap.context(() => {
      gsap
        .timeline()
        .set(root, { display: "block" })
        .fromTo(
          root,
          { xPercent: -118, skewX: -8 },
          {
            xPercent: 118,
            skewX: 8,
            duration: 0.52,
            ease: MOTION.ease.exit,
          },
        )
        .set(root, { display: "none", clearProps: "transform" });
    }, root);
    return () => context.revert();
  }, [location.pathname]);

  return (
    <div className="route-motion-wave" ref={rootRef} aria-hidden="true">
      <span />
    </div>
  );
}
