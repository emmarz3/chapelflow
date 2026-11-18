import { useLayoutEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

function scrollElementToTop(element: Element | null) {
  if (!element || !("scrollTo" in element)) return;
  (element as HTMLElement).scrollTo({ top: 0, left: 0, behavior: "auto" });
}

export function RouteScrollManager() {
  const { pathname, hash } = useLocation();
  const navigationType = useNavigationType();

  useLayoutEffect(() => {
    if ("scrollRestoration" in window.history) {
      window.history.scrollRestoration = "manual";
    }
    if (hash) {
      const id = decodeURIComponent(hash.replace(/^#/, ""));
      if (id) {
        const target = document.getElementById(id);
        if (target) {
          target.scrollIntoView({ behavior: "auto", block: "start" });
          return;
        }
      }
    }
    if (navigationType === "POP") return;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    scrollElementToTop(document.getElementById("main-content"));
    scrollElementToTop(document.getElementById("portal-content"));
    document
      .querySelectorAll(".auth-main, .public-shell, .portal-main")
      .forEach((element) => scrollElementToTop(element));
  }, [pathname, hash, navigationType]);

  return null;
}
