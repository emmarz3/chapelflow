import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { resolveHomepage, type HomepageContent } from "../../lib/homepage-content";
import { homepageService } from "../../services/chapelflow";

export const HOMEPAGE_QUERY_KEY = ["public-homepage"] as const;

/**
 * Public homepage content. While the first request is in flight `content` is
 * null so callers can show a placeholder instead of flashing default names;
 * if the request fails the built-in defaults are used so the site never breaks.
 */
export function usePublicHomepage(): {
  content: HomepageContent | null;
  counts: Record<string, number>;
  isPending: boolean;
} {
  const query = useQuery({
    queryKey: HOMEPAGE_QUERY_KEY,
    queryFn: async () => (await homepageService.get()).data,
    staleTime: 60_000,
    retry: 0,
  });
  const content = useMemo(
    () => (query.isPending ? null : resolveHomepage(query.data?.content)),
    [query.isPending, query.data],
  );
  return { content, counts: query.data?.counts ?? {}, isPending: query.isPending };
}

export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}

const REGISTERED_KEY = "chapelflow:homepage-registered-v1";

function loadRegistered(): Set<string> {
  try {
    const raw: unknown = JSON.parse(localStorage.getItem(REGISTERED_KEY) || "[]");
    return new Set(Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : []);
  } catch {
    return new Set();
  }
}

/** Remembers, per browser, which programmes and units this visitor already signed up for. */
export function useRegistered() {
  const [registered, setRegistered] = useState<Set<string>>(loadRegistered);
  const remember = (key: string) => {
    setRegistered((current) => {
      const next = new Set(current).add(key);
      try {
        localStorage.setItem(REGISTERED_KEY, JSON.stringify([...next]));
      } catch {
        // Storage can be unavailable; the button still reflects this visit.
      }
      return next;
    });
  };
  return { registered, remember };
}
