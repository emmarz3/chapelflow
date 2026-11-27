type LayoutShiftEntry = PerformanceEntry & {
  value?: number;
  hadRecentInput?: boolean;
};

type EventTimingEntry = PerformanceEntry & {
  duration: number;
  interactionId?: number;
};

let diagnosticsEnabled = false;
let initialized = false;
let largestContentfulPaint = 0;
let cumulativeLayoutShift = 0;
let longestInteractionCandidate = 0;
let longTaskTotal = 0;
let reportSent = false;
const observers: PerformanceObserver[] = [];

function observeEntries(
  type: string,
  onEntries: (entries: PerformanceEntry[]) => void,
) {
  if (typeof PerformanceObserver === "undefined") return;
  try {
    const observer = new PerformanceObserver((list) => onEntries(list.getEntries()));
    observer.observe({ type, buffered: true });
    observers.push(observer);
  } catch {
    // This performance entry type is not supported in this browser.
  }
}

export function markAppPerformance(name: string) {
  if (typeof performance === "undefined" || typeof performance.mark !== "function") return;
  const markName = `chapelflow:${name}`;
  performance.mark(markName);
  if (!diagnosticsEnabled) return;
  const start = performance.getEntriesByName("chapelflow:app_bootstrap", "mark")[0];
  const end = performance.getEntriesByName(markName, "mark").at(-1);
  if (start && end && end.startTime >= start.startTime) {
    console.info("[ChapelFlow performance]", {
      milestone: name,
      elapsedFromBootstrapMs: Math.round(end.startTime - start.startTime),
    });
  }
}

function buildPerformanceReport() {
  const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
  const paints = performance.getEntriesByType("paint");
  const firstContentfulPaint = paints.find((entry) => entry.name === "first-contentful-paint");
  const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
  const scriptResources = resources.filter((entry) => entry.initiatorType === "script");
  const styleResources = resources.filter((entry) => entry.initiatorType === "link" && /\.css(?:\?|$)/i.test(entry.name));

  return {
    navigation: navigation
      ? {
          domContentLoadedMs: Math.round(navigation.domContentLoadedEventEnd),
          loadEventMs: Math.round(navigation.loadEventEnd),
          responseMs: Math.round(navigation.responseEnd),
          transferBytes: navigation.transferSize || null,
        }
      : null,
    firstContentfulPaintMs: firstContentfulPaint ? Math.round(firstContentfulPaint.startTime) : null,
    largestContentfulPaintMs: largestContentfulPaint ? Math.round(largestContentfulPaint) : null,
    cumulativeLayoutShift: Number(cumulativeLayoutShift.toFixed(4)),
    longestInteractionCandidateMs: Math.round(longestInteractionCandidate),
    longTaskTotalMs: Math.round(longTaskTotal),
    resources: {
      scriptCount: scriptResources.length,
      scriptEncodedBytes: scriptResources.reduce((sum, entry) => sum + (entry.encodedBodySize || 0), 0),
      stylesheetCount: styleResources.length,
      stylesheetEncodedBytes: styleResources.reduce((sum, entry) => sum + (entry.encodedBodySize || 0), 0),
    },
  };
}

function reportPerformance() {
  if (!diagnosticsEnabled || reportSent) return;
  reportSent = true;
  console.info("[ChapelFlow performance report]", buildPerformanceReport());
  for (const observer of observers) observer.disconnect();
  observers.length = 0;
}

export function initializeClientPerformanceDiagnostics() {
  if (initialized || typeof window === "undefined" || typeof performance === "undefined") return;
  initialized = true;
  diagnosticsEnabled =
    import.meta.env.DEV ||
    new URLSearchParams(window.location.search).get("perf") === "1";

  markAppPerformance("app_bootstrap");
  if (!diagnosticsEnabled) return;

  observeEntries("largest-contentful-paint", (entries) => {
    for (const entry of entries) largestContentfulPaint = Math.max(largestContentfulPaint, entry.startTime);
  });
  observeEntries("layout-shift", (entries) => {
    for (const entry of entries) {
      const shift = entry as LayoutShiftEntry;
      if (!shift.hadRecentInput) cumulativeLayoutShift += shift.value || 0;
    }
  });
  observeEntries("event", (entries) => {
    for (const entry of entries) {
      const event = entry as EventTimingEntry;
      longestInteractionCandidate = Math.max(longestInteractionCandidate, event.duration || 0);
    }
  });
  observeEntries("longtask", (entries) => {
    for (const entry of entries) longTaskTotal += entry.duration;
  });

  const reportWhenHidden = () => {
    if (document.visibilityState === "hidden") reportPerformance();
  };
  document.addEventListener("visibilitychange", reportWhenHidden);
  // Emit a usable diagnostic snapshot during a test session without requiring navigation away.
  window.setTimeout(reportPerformance, 15_000);
  window.addEventListener("pagehide", reportPerformance, { once: true });
}
