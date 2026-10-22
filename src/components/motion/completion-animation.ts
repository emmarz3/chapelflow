import { gsap } from "gsap";
import { useCallback, useEffect, useRef } from "react";

function prefersReducedMotion() {
  if (import.meta.env.MODE === "test") return true;
  return (
    typeof window === "undefined" ||
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function useCompletionAnimation() {
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => () => cleanupRef.current?.(), []);

  const playRegister = useCallback((root: HTMLElement | null) => {
    cleanupRef.current?.();
    if (!root || prefersReducedMotion()) return;

    let context: ReturnType<typeof gsap.context> | undefined;
    let timeline: gsap.core.Timeline | undefined;
    const cleanup = () => {
      timeline?.kill();
      context?.revert();
      cleanupRef.current = null;
    };

    context = gsap.context(() => {
      const figure = root.querySelector<HTMLElement>(".completion-figure--register");
      const halo = root.querySelector<HTMLElement>(".completion-figure__halo");
      const content = root.querySelectorAll<HTMLElement>(
        ".completion-success__content > *",
      );
      if (!figure) return;

      gsap.set(figure, { autoAlpha: 0, scale: 0.78, rotateX: -24, rotateY: 22, y: 18 });
      gsap.set(content, { autoAlpha: 0, y: 12 });
      if (halo) gsap.set(halo, { autoAlpha: 0, scale: 0.7 });

      timeline = gsap.timeline({ onComplete: cleanup });
      timeline
        .to(figure, { autoAlpha: 1, duration: 0.12, ease: "power1.out" })
        .to(
          figure,
          {
            scale: 1,
            rotateX: 0,
            rotateY: -8,
            y: -3,
            duration: 0.42,
            ease: "back.out(1.7)",
          },
          "<",
        )
        .to(figure, { rotateY: 0, y: 0, duration: 0.18, ease: "power2.out" })
        .to(halo, { autoAlpha: 0.7, scale: 1.12, duration: 0.25, ease: "power2.out" }, "-=0.36")
        .to(halo, { autoAlpha: 0, scale: 1.42, duration: 0.3, ease: "power1.out" })
        .to(content, { autoAlpha: 1, y: 0, duration: 0.3, stagger: 0.07, ease: "power2.out" }, "-=0.34");

      const check = root.querySelector<SVGPathElement>(".completion-figure__check");
      if (check) {
        const length =
          typeof check.getTotalLength === "function" ? check.getTotalLength() : 40;
        gsap.set(check, { strokeDasharray: length, strokeDashoffset: length });
        timeline.to(check, { strokeDashoffset: 0, duration: 0.28, ease: "power2.out" }, "-=0.44");
      }
    }, root);

    cleanupRef.current = cleanup;
  }, []);

  return { playRegister };
}
