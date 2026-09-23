import { describe, expect, it } from "vitest";
import {
  DEFAULT_HOMEPAGE,
  calendarItems,
  countdownParts,
  formatClock,
  googleCalendarUrl,
  icsFor,
  nextLastFriday,
  nextWeekly,
  resolveHomepage,
  safeHref,
  serviceStart,
  upcomingEvents,
  verseOfTheDay,
  visibleServices,
  type HomepageContent,
} from "../lib/homepage-content";

// Monday 21 Sep 2026, 12:00 in Lagos (UTC+1).
const NOW = Date.UTC(2026, 8, 21, 11, 0);
const service = (id: string) => DEFAULT_HOMEPAGE.services.find((s) => s.id === id)!;

describe("resolveHomepage", () => {
  it("returns the defaults when nothing has been saved", () => {
    expect(resolveHomepage(null)).toEqual(DEFAULT_HOMEPAGE);
    expect(resolveHomepage({})).toEqual(DEFAULT_HOMEPAGE);
  });

  it("keeps deliberately emptied lists but fills fields added after a save", () => {
    const stored = { ...structuredClone(DEFAULT_HOMEPAGE), units: [] } as Partial<HomepageContent>;
    delete (stored as { contact?: unknown }).contact;
    const resolved = resolveHomepage(stored);
    expect(resolved.units).toEqual([]);
    expect(resolved.contact.address).toBe(DEFAULT_HOMEPAGE.contact.address);
  });

  it("does not mutate the shared defaults", () => {
    const first = resolveHomepage(null);
    first.units.pop();
    expect(resolveHomepage(null).units).toHaveLength(DEFAULT_HOMEPAGE.units.length);
  });
});

describe("West Africa Time scheduling", () => {
  it("finds the next Wednesday 5pm service", () => {
    const start = nextWeekly(3, "17:00", NOW)!;
    expect(new Date(start).toISOString()).toBe("2026-09-23T16:00:00.000Z");
  });

  it("rolls to next week once today's service has started", () => {
    const wednesdayEvening = Date.UTC(2026, 8, 23, 17, 0);
    expect(new Date(nextWeekly(3, "17:00", wednesdayEvening)!).toISOString()).toBe("2026-09-30T16:00:00.000Z");
  });

  it("finds the last Friday of the month", () => {
    expect(new Date(nextLastFriday("22:00", NOW)!).toISOString()).toBe("2026-09-25T21:00:00.000Z");
    const afterIt = Date.UTC(2026, 8, 26, 10, 0);
    expect(new Date(nextLastFriday("22:00", afterIt)!).toISOString()).toBe("2026-10-30T21:00:00.000Z");
  });

  it("hides one-off services once their date has passed", () => {
    const vigil = { ...service("svc-semester-vigil") };
    expect(serviceStart(vigil, NOW)).not.toBeNull();
    expect(serviceStart(vigil, Date.UTC(2026, 9, 20))).toBeNull();
    expect(visibleServices([vigil], "vigil", Date.UTC(2026, 9, 20))).toHaveLength(0);
  });

  it("formats clock times", () => {
    expect(formatClock("00:05")).toBe("12:05 AM");
    expect(formatClock("17:30")).toBe("5:30 PM");
  });

  it("splits a countdown into padded parts", () => {
    expect(countdownParts(NOW + (2 * 86400 + 3 * 3600 + 4 * 60 + 5) * 1000, NOW)).toEqual({ days: "02", hours: "03", minutes: "04", seconds: "05" });
    expect(countdownParts(NOW - 5000, NOW).seconds).toBe("00");
  });
});

describe("events", () => {
  const today = new Date(2026, 8, 21, 9);

  it("orders upcoming events, adds sign-ups to places taken and hides past ones", () => {
    const events = [
      ...DEFAULT_HOMEPAGE.events,
      { ...DEFAULT_HOMEPAGE.events[0]!, id: "past", startDate: "2026-01-01", endDate: "" },
    ];
    const rows = upcomingEvents(events, { "evt-freshers-retreat": 5 }, today);
    expect(rows.map((r) => r.event.id)).toEqual(["evt-choir-rehearsal", "evt-freshers-retreat", "evt-leadership-conference", "evt-community-outreach"]);
    expect(rows[1]!.taken).toBe(79);
    expect(rows[1]!.full).toBe(false);
  });

  it("marks an event full when capacity is reached and skips hidden events", () => {
    const rows = upcomingEvents(DEFAULT_HOMEPAGE.events.map((e) => (e.id === "evt-community-outreach" ? { ...e, capacity: 40 } : { ...e, active: e.id === "evt-community-outreach" })), { "evt-community-outreach": 9 }, today);
    expect(rows).toHaveLength(1);
    expect(rows[0]!.full).toBe(true);
  });
});

describe("calendar", () => {
  it("lists services and events for a date in time order", () => {
    // Sunday 20 Sep 2026
    const items = calendarItems(new Date(2026, 8, 20, 12), "all", DEFAULT_HOMEPAGE);
    expect(items.map((i) => i.title)).toEqual(["Walking in Covenant Promise", "Renewed in Spirit"]);
    // Tuesday: weekly choir rehearsal; Friday 25 Sep is the last Friday
    expect(calendarItems(new Date(2026, 8, 22, 12), "all", DEFAULT_HOMEPAGE)[0]!.type).toBe("event");
    expect(calendarItems(new Date(2026, 8, 25, 12), "vigil", DEFAULT_HOMEPAGE)[0]!.title).toBe("Night of Encounter");
    expect(calendarItems(new Date(2026, 8, 18, 12), "vigil", DEFAULT_HOMEPAGE)).toHaveLength(0);
  });

  it("shows multi-day events on every day of their range", () => {
    for (const day of [9, 10, 11]) expect(calendarItems(new Date(2026, 9, day, 12), "event", DEFAULT_HOMEPAGE)[0]?.title).toBe("Freshers' Welcome Retreat");
    expect(calendarItems(new Date(2026, 9, 12, 12), "event", DEFAULT_HOMEPAGE).find((i) => i.title.includes("Freshers"))).toBeUndefined();
  });

  it("ignores hidden services", () => {
    const hidden = { services: DEFAULT_HOMEPAGE.services.map((s) => ({ ...s, active: false })), events: [] };
    expect(calendarItems(new Date(2026, 8, 20, 12), "all", hidden)).toHaveLength(0);
  });
});

describe("verse of the day", () => {
  it("is stable for a day, changes the next day and handles an empty list", () => {
    const verses = DEFAULT_HOMEPAGE.verse.verses;
    const a = verseOfTheDay(verses, new Date(2026, 8, 21, 8));
    expect(verseOfTheDay(verses, new Date(2026, 8, 21, 22))).toEqual(a);
    expect(verseOfTheDay(verses, new Date(2026, 8, 22, 8))).not.toEqual(a);
    expect(verseOfTheDay([], new Date())).toBeNull();
  });
});

describe("add to calendar", () => {
  const meta = { siteName: "Chrisland University Chapel", contact: { ...DEFAULT_HOMEPAGE.contact } };

  it("builds a recurring Google Calendar link", () => {
    const url = new URL(googleCalendarUrl(service("svc-midweek-fellowship"), meta, NOW));
    expect(url.searchParams.get("dates")).toBe("20260923T160000Z/20260923T173000Z");
    expect(url.searchParams.get("recur")).toBe("RRULE:FREQ=WEEKLY");
  });

  it("builds a valid, escaped ICS file", () => {
    const ics = icsFor({ ...service("svc-night-of-encounter"), title: "Night; of, Encounter" }, meta, NOW);
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain("RRULE:FREQ=MONTHLY;BYDAY=-1FR");
    expect(ics).toContain("SUMMARY:Night\\; of\\, Encounter");
    expect(ics.split("\r\n").at(-1)).toBe("END:VCALENDAR");
  });

  it("returns nothing for a finished one-off service", () => {
    expect(icsFor(service("svc-semester-vigil"), meta, Date.UTC(2027, 0, 1))).toBe("");
  });
});

describe("safeHref", () => {
  it.each([
    ["https://example.com/a", "https://example.com/a"],
    ["/events", "/events"],
    ["#schedule", "#schedule"],
    ["javascript:alert(1)", ""],
    ["//evil.example", ""],
    ["data:text/html,x", ""],
    ["", ""],
  ])("%s", (input, expected) => expect(safeHref(input)).toBe(expected));
});
