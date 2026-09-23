/**
 * Public homepage content model.
 *
 * The Super Admin edits one JSON document (see `apps/operations/homepage_schema.py`
 * on the Django side, which validates the same shape). Until a first save the
 * API returns `content: null` and the defaults below are rendered, so the
 * homepage is never empty. Everything here is pure and unit-tested.
 */

export type ServiceType = "sunday" | "midweek" | "vigil";
export type ServiceRule = "weekly" | "lastfri" | "date";
export type CalendarKind = ServiceType | "event";
export type UnitIcon =
  | "music"
  | "door"
  | "camera"
  | "flame"
  | "smile"
  | "shield"
  | "heart"
  | "book"
  | "users"
  | "mic"
  | "megaphone"
  | "star";

export const UNIT_ICONS: UnitIcon[] = [
  "music",
  "door",
  "camera",
  "flame",
  "smile",
  "shield",
  "heart",
  "book",
  "users",
  "mic",
  "megaphone",
  "star",
];

export interface HomepageAnnouncement {
  id: string;
  text: string;
  linkLabel: string;
  linkHref: string;
  active: boolean;
}
export interface HomepageService {
  id: string;
  type: ServiceType;
  title: string;
  venue: string;
  minister: string;
  /** 24-hour HH:MM in West Africa Time. */
  time: string;
  duration: number;
  rule: ServiceRule;
  /** 0 = Sunday … 6 = Saturday; used by the weekly rule. */
  weekday: number;
  /** YYYY-MM-DD; used by the one-off rule. */
  date: string;
  active: boolean;
}
export interface HomepageEvent {
  id: string;
  category: string;
  title: string;
  repeat: "none" | "weekly";
  weekday: number;
  startDate: string;
  endDate: string;
  /** 24-hour HH:MM start, used for ordering and the calendar. */
  startTime: string;
  /** Human-readable time text shown on the card. */
  time: string;
  venue: string;
  cta: "Register" | "RSVP";
  capacity: number | null;
  taken: number;
  active: boolean;
}
export interface HomepageSermon {
  id: string;
  series: string;
  title: string;
  speaker: string;
  date: string;
  duration: string;
  videoUrl: string;
  audioUrl: string;
  downloadUrl: string;
  imageUrl: string;
  active: boolean;
}
export interface HomepageUnit {
  id: string;
  name: string;
  icon: UnitIcon;
  description: string;
  meeting: string;
  active: boolean;
}
export interface HomepageGalleryItem {
  id: string;
  title: string;
  subtitle: string;
  imageUrl: string;
  active: boolean;
}
export interface HomepageVerse {
  id: string;
  text: string;
  reference: string;
  translation: string;
  note: string;
}
export interface HomepageSectionCopy {
  enabled: boolean;
  eyebrow: string;
  title: string;
  description: string;
}
export type HomepageSectionKey =
  | "schedule"
  | "events"
  | "sermons"
  | "ministries"
  | "calendar"
  | "gallery";

export interface HomepageContent {
  siteName: string;
  hero: {
    eyebrow: string;
    titleLead: string;
    titleAccent: string;
    lede: string;
    primaryLabel: string;
    primaryHref: string;
    secondaryLabel: string;
    secondaryHref: string;
    imageUrl: string;
    imageCaption: string;
    stats: { value: string; label: string }[];
  };
  sections: Record<HomepageSectionKey, HomepageSectionCopy>;
  belonging: {
    eyebrow: string;
    title: string;
    body: string;
    quote: string;
    pillars: { title: string; detail: string }[];
  };
  closing: { eyebrow: string; title: string; body: string; ctaLabel: string };
  countdown: { enabled: boolean; serviceId: string };
  verse: { enabled: boolean; verses: HomepageVerse[] };
  announcements: HomepageAnnouncement[];
  services: HomepageService[];
  events: HomepageEvent[];
  sermons: HomepageSermon[];
  units: HomepageUnit[];
  gallery: HomepageGalleryItem[];
  contact: {
    address: string;
    email: string;
    phone: string;
    facebook: string;
    x: string;
    instagram: string;
    youtube: string;
  };
}

/** Shape returned by the homepage API. */
export interface HomepageResponse {
  content: HomepageContent | null;
  version: number;
  updatedAt: string | null;
  counts: Record<string, number>;
}

/* -------------------------------------------------------------------------- */
/* Defaults                                                                   */
/* -------------------------------------------------------------------------- */

const verse = (
  id: string,
  text: string,
  reference: string,
  note: string,
): HomepageVerse => ({ id, text, reference, translation: "KJV", note });

export const DEFAULT_VERSES: HomepageVerse[] = [
  verse("v-psalm-119-105", "Thy word is a lamp unto my feet, and a light unto my path.", "Psalm 119:105", "You don't need the whole map tonight, only enough light for the next step. Read one passage before you make today's plans."),
  verse("v-proverbs-3-5", "Trust in the LORD with all thine heart; and lean not unto thine own understanding. In all thy ways acknowledge him, and he shall direct thy paths.", "Proverbs 3:5–6", "Your own understanding is a useful tool but a poor master. Bring today's decisions to God first, then move."),
  verse("v-isaiah-40-31", "But they that wait upon the LORD shall renew their strength; they shall mount up with wings as eagles; they shall run, and not be weary; and they shall walk, and not faint.", "Isaiah 40:31", "Waiting is not wasted time; it is where strength is renewed. Rest in prayer today, then run your race."),
  verse("v-philippians-4-13", "I can do all things through Christ which strengtheneth me.", "Philippians 4:13", "This is not a promise of an easy day, but of enough strength for the one you have. Name the thing you're dreading and ask for that strength."),
  verse("v-jeremiah-29-11", "For I know the thoughts that I think toward you, saith the LORD, thoughts of peace, and not of evil, to give you an expected end.", "Jeremiah 29:11", "God's plans for you are bigger than this semester's results. Hold your goals loosely and his purposes firmly."),
  verse("v-joshua-1-9", "Have not I commanded thee? Be strong and of a good courage; be not afraid, neither be thou dismayed: for the LORD thy God is with thee whithersoever thou goest.", "Joshua 1:9", "Courage is not the absence of fear; it is moving forward because you are not alone. Take the step you have been putting off."),
  verse("v-psalm-46-1", "God is our refuge and strength, a very present help in trouble.", "Psalm 46:1", "When everything feels unsteady, start with who is near. Say a one-line prayer before you open the next message or the next textbook."),
  verse("v-romans-12-2", "And be not conformed to this world: but be ye transformed by the renewing of your mind, that ye may prove what is that good, and acceptable, and perfect, will of God.", "Romans 12:2", "Renewal is daily, like charging a phone. Feed your mind something worth becoming today."),
  verse("v-matthew-11-28", "Come unto me, all ye that labour and are heavy laden, and I will give you rest.", "Matthew 11:28", "Come with the tiredness you have been hiding. Rest here isn't laziness; it is trust."),
  verse("v-2-timothy-1-7", "For God hath not given us the spirit of fear; but of power, and of love, and of a sound mind.", "2 Timothy 1:7", "Anxiety is loud, but it is not your identity. Ask for power, love and a clear mind, and take one calm step."),
  verse("v-colossians-3-23", "And whatsoever ye do, do it heartily, as to the Lord, and not unto men;", "Colossians 3:23", "Assignments, chores, rehearsals: all of it can be worship when done for the Lord. Do one small task well today."),
  verse("v-james-1-5", "If any of you lack wisdom, let him ask of God, that giveth to all men liberally, and upbraideth not; and it shall be given him.", "James 1:5", "Wisdom is not reserved for the clever; it is asked for. Bring the question you're stuck on and ask plainly."),
  verse("v-psalm-23-1", "The LORD is my shepherd; I shall not want.", "Psalm 23:1", "Lacking nothing doesn't mean having everything; it means being led by someone who knows what you need. Trust the Shepherd with today's list."),
  verse("v-1-thess-5-16", "Rejoice evermore. Pray without ceasing. In every thing give thanks: for this is the will of God in Christ Jesus concerning you.", "1 Thessalonians 5:16–18", "Joy, prayer and thanks are habits before they are feelings. Write down three things to thank God for."),
  verse("v-hebrews-11-1", "Now faith is the substance of things hoped for, the evidence of things not seen.", "Hebrews 11:1", "Faith is confidence in what you cannot yet see. Pray about one hope today as though it is already on the way."),
];

export const DEFAULT_HOMEPAGE: HomepageContent = {
  siteName: "Chrisland University Chapel",
  hero: {
    eyebrow: "Chrisland University Chapel",
    titleLead: "Where faith becomes",
    titleAccent: "community.",
    lede: "One beautiful place to worship, belong, grow, and stay connected to chapel life at CUC.",
    primaryLabel: "Create your ChapelFlow account",
    primaryHref: "/register",
    secondaryLabel: "Explore ChapelFlow",
    secondaryHref: "/about",
    imageUrl: "/chapel-hero.png",
    imageCaption: "“A deeper faith. A stronger community.”",
    stats: [
      { value: "2,500+", label: "Students connected" },
      { value: "20+", label: "Chapel communities" },
      { value: "48", label: "Programmes yearly" },
    ],
  },
  sections: {
    schedule: { enabled: true, eyebrow: "Plan your visit", title: "Service Schedule", description: "" },
    events: { enabled: true, eyebrow: "What's coming up", title: "Upcoming Events", description: "Retreats, conferences, outreaches and rehearsals. Save your place before it fills up." },
    sermons: { enabled: true, eyebrow: "Latest messages", title: "Recent Sermons", description: "Catch up on what you missed, or listen again on your way to lectures." },
    ministries: { enabled: true, eyebrow: "Get involved", title: "Ministries & Units", description: "Belonging starts with serving. Find the team that fits your gifts and join it this semester." },
    calendar: { enabled: true, eyebrow: "Vigils & events", title: "Chapel Calendar", description: "Filter by service type, then select a day to see times and venues." },
    gallery: { enabled: true, eyebrow: "Highlights", title: "Moments of Grace", description: "A look back at services, retreats and outreaches from the past year." },
  },
  belonging: {
    eyebrow: "One chapel · one community · one flow",
    title: "A richer campus life, rooted in purpose.",
    body: "ChapelFlow is the digital home for worship, fellowship, service, and spiritual growth at Chrisland University Chapel.",
    quote: "“Faith is lived best when it is lived together.”",
    pillars: [
      { title: "Worship together", detail: "Services and shared moments" },
      { title: "Belong deeply", detail: "Units and fellowships" },
      { title: "Grow in faith", detail: "Sermons and resources" },
      { title: "Serve with purpose", detail: "Community and leadership" },
    ],
  },
  closing: {
    eyebrow: "Chrisland University Chapel",
    title: "Stay connected to everything happening at CUC.",
    body: "Join ChapelFlow and become part of a growing community of faith, purpose, and impact.",
    ctaLabel: "Join the chapel community",
  },
  countdown: { enabled: true, serviceId: "svc-midweek-fellowship" },
  verse: { enabled: true, verses: DEFAULT_VERSES },
  announcements: [
    { id: "ann-service-moved", text: "Service moved to Chapel Hall B: this Sunday's 11:30 AM worship", linkLabel: "See schedule", linkHref: "#schedule", active: true },
    { id: "ann-exam-week", text: "Exam-week schedule: extra prayer hours 6:00 to 8:00 AM in Chapel Hall A, Mon to Fri", linkLabel: "View calendar", linkHref: "#calendar", active: true },
    { id: "ann-freshers-retreat", text: "Freshers' Welcome Retreat registration closes Friday, 2 October", linkLabel: "Register", linkHref: "#events", active: true },
  ],
  services: [
    { id: "svc-sunday-first", type: "sunday", title: "Walking in Covenant Promise", venue: "Main Auditorium", minister: "Rev. Dr. Emmanuel Adeyemi", time: "09:00", duration: 120, rule: "weekly", weekday: 0, date: "", active: true },
    { id: "svc-sunday-second", type: "sunday", title: "Renewed in Spirit", venue: "Chapel Hall B", minister: "Pastor Ruth Okonkwo", time: "11:30", duration: 120, rule: "weekly", weekday: 0, date: "", active: true },
    { id: "svc-midweek-fellowship", type: "midweek", title: "Midweek Fellowship", venue: "Main Auditorium", minister: "Chaplaincy Team", time: "17:00", duration: 90, rule: "weekly", weekday: 3, date: "", active: true },
    { id: "svc-bible-study", type: "midweek", title: "Bible Study Hour", venue: "Chapel Hall A", minister: "Bible Study Team", time: "16:00", duration: 60, rule: "weekly", weekday: 4, date: "", active: true },
    { id: "svc-night-of-encounter", type: "vigil", title: "Night of Encounter", venue: "Main Auditorium", minister: "Prayer Team & Chaplaincy", time: "22:00", duration: 240, rule: "lastfri", weekday: 5, date: "", active: true },
    { id: "svc-semester-vigil", type: "vigil", title: "Semester Prayer & Fasting Vigil", venue: "Main Auditorium", minister: "Rev. Dr. Emmanuel Adeyemi", time: "22:00", duration: 300, rule: "date", weekday: 5, date: "2026-10-16", active: true },
    { id: "svc-carol-vigil", type: "vigil", title: "Carol Night Vigil", venue: "Main Auditorium", minister: "Choir & Chaplaincy", time: "21:00", duration: 180, rule: "date", weekday: 5, date: "2026-12-18", active: true },
  ],
  events: [
    { id: "evt-freshers-retreat", category: "Retreat", title: "Freshers' Welcome Retreat", repeat: "none", weekday: 0, startDate: "2026-10-09", endDate: "2026-10-11", startTime: "16:00", time: "Fri 4:00 PM to Sun 2:00 PM", venue: "Chapel Retreat Grounds", cta: "Register", capacity: 120, taken: 74, active: true },
    { id: "evt-leadership-conference", category: "Conference", title: "Leadership & Faith Conference", repeat: "none", weekday: 0, startDate: "2026-10-24", endDate: "", startTime: "09:00", time: "9:00 AM to 4:00 PM", venue: "Main Auditorium", cta: "Register", capacity: 400, taken: 212, active: true },
    { id: "evt-community-outreach", category: "Outreach", title: "Owode-Ede Community Outreach", repeat: "none", weekday: 0, startDate: "2026-11-07", endDate: "", startTime: "08:00", time: "8:00 AM to 2:00 PM", venue: "Owode-Ede community", cta: "RSVP", capacity: 80, taken: 31, active: true },
    { id: "evt-choir-rehearsal", category: "Choir Rehearsal", title: "Open Choir Rehearsal", repeat: "weekly", weekday: 2, startDate: "", endDate: "", startTime: "18:00", time: "6:00 PM to 8:00 PM", venue: "Music Room, Chapel Annex", cta: "RSVP", capacity: null, taken: 0, active: true },
  ],
  sermons: [
    { id: "srm-covenant-promise", series: "Covenant Series", title: "Walking in Covenant Promise", speaker: "Rev. Dr. Emmanuel Adeyemi", date: "2026-09-13", duration: "42:18", videoUrl: "", audioUrl: "", downloadUrl: "", imageUrl: "", active: true },
    { id: "srm-renewed-in-spirit", series: "Spirit & Life", title: "Renewed in Spirit", speaker: "Pastor Ruth Okonkwo", date: "2026-09-06", duration: "38:05", videoUrl: "", audioUrl: "", downloadUrl: "", imageUrl: "", active: true },
    { id: "srm-discipline-of-rest", series: "Campus Faith", title: "The Discipline of Rest", speaker: "Chaplain Grace Ogunleye", date: "2026-08-30", duration: "35:47", videoUrl: "", audioUrl: "", downloadUrl: "", imageUrl: "", active: true },
  ],
  units: [
    { id: "unit-choir", name: "Choir", icon: "music", description: "Lead the congregation in worship through song. All voice parts welcome; auditions each semester.", meeting: "Rehearsals: Tuesdays, 6:00 PM", active: true },
    { id: "unit-ushering", name: "Ushering", icon: "door", description: "Welcome, seat and care for everyone who walks through the chapel doors.", meeting: "Serving: Sundays and special services", active: true },
    { id: "unit-media", name: "Media", icon: "camera", description: "Run sound, lights, livestream and photography, and keep the sermon archive current.", meeting: "Training: Saturdays, 10:00 AM", active: true },
    { id: "unit-prayer", name: "Prayer Team", icon: "flame", description: "Intercede for students, staff and the nation, and cover every service and vigil in prayer.", meeting: "Meets: Wednesdays, 6:00 AM", active: true },
    { id: "unit-drama", name: "Drama", icon: "smile", description: "Tell gospel stories on stage for services, outreaches and the Christmas and Easter productions.", meeting: "Rehearsals: Fridays, 5:00 PM", active: true },
    { id: "unit-protocol", name: "Protocol", icon: "shield", description: "Host guests and keep programmes on time so every service runs smoothly.", meeting: "Briefings: Saturdays, 4:00 PM", active: true },
  ],
  gallery: [
    { id: "gal-convocation", title: "Convocation Service", subtitle: "July 2026", imageUrl: "", active: true },
    { id: "gal-baptism", title: "Baptism Sunday", subtitle: "June 2026", imageUrl: "", active: true },
    { id: "gal-encounter", title: "Night of Encounter", subtitle: "Monthly vigil", imageUrl: "", active: true },
    { id: "gal-choir-anniversary", title: "Choir Anniversary", subtitle: "May 2026", imageUrl: "", active: true },
    { id: "gal-outreach", title: "Owode-Ede Community Outreach", subtitle: "November 2025", imageUrl: "", active: true },
    { id: "gal-thanksgiving", title: "Thanksgiving Service", subtitle: "December 2025", imageUrl: "", active: true },
    { id: "gal-leadership", title: "Leadership Conference", subtitle: "October 2025", imageUrl: "", active: true },
  ],
  // Contact channels are left for the Super Admin to confirm: the address
  // matches the public footer, but no unverified phone, email or social
  // account is ever published by default.
  contact: {
    address: "Chrisland University, Owode-Ede Road, Abeokuta, Ogun State",
    email: "",
    phone: "",
    facebook: "",
    x: "",
    instagram: "",
    youtube: "",
  },
};

/**
 * Combine stored content with defaults. Objects are merged key by key so a
 * document saved before a field existed still renders; arrays are taken
 * verbatim, because an emptied list is a deliberate choice by the admin.
 */
export function resolveHomepage(stored: Partial<HomepageContent> | null | undefined): HomepageContent {
  if (!stored || typeof stored !== "object" || !Object.keys(stored).length)
    return structuredClone(DEFAULT_HOMEPAGE);
  const d = DEFAULT_HOMEPAGE;
  const sections = { ...d.sections };
  for (const key of Object.keys(d.sections) as HomepageSectionKey[])
    sections[key] = { ...d.sections[key], ...(stored.sections?.[key] ?? {}) };
  return {
    siteName: stored.siteName || d.siteName,
    hero: { ...d.hero, ...(stored.hero ?? {}), stats: stored.hero?.stats ?? d.hero.stats },
    sections,
    belonging: { ...d.belonging, ...(stored.belonging ?? {}), pillars: stored.belonging?.pillars ?? d.belonging.pillars },
    closing: { ...d.closing, ...(stored.closing ?? {}) },
    countdown: { ...d.countdown, ...(stored.countdown ?? {}) },
    verse: {
      enabled: stored.verse?.enabled ?? d.verse.enabled,
      verses: stored.verse?.verses ?? d.verse.verses,
    },
    announcements: stored.announcements ?? d.announcements,
    services: stored.services ?? d.services,
    events: stored.events ?? d.events,
    sermons: stored.sermons ?? d.sermons,
    units: stored.units ?? d.units,
    gallery: stored.gallery ?? d.gallery,
    contact: { ...d.contact, ...(stored.contact ?? {}) },
  };
}

export function newId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-3)}`;
}

/* -------------------------------------------------------------------------- */
/* Time helpers. Chapel time is West Africa Time (UTC+1, no daylight saving). */
/* -------------------------------------------------------------------------- */

const HOUR = 3_600_000;
export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export const MON3 = MONTHS.map((m) => m.slice(0, 3));
export const DOW3 = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const pad = (n: number) => String(n).padStart(2, "0");
export const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export function parseClock(value: string): [number, number] {
  const [h = "0", m = "0"] = value.split(":");
  return [Number(h) || 0, Number(m) || 0];
}

/** "17:30" → "5:30 PM" */
export function formatClock(value: string) {
  const [h, m] = parseClock(value);
  const hour = h % 12 || 12;
  return `${hour}:${pad(m)} ${h < 12 ? "AM" : "PM"}`;
}
const shortTime = (value: string) => formatClock(value).replace(/ (AM|PM)/, (_, a: string) => a.toLowerCase());

const utcFromWat = (y: number, mo: number, d: number, h: number, mi: number) =>
  Date.UTC(y, mo, d, h, mi) - HOUR;
const watNow = (now: number) => new Date(now + HOUR);

export function nextWeekly(weekday: number, time: string, now = Date.now()): number | null {
  const [h, mi] = parseClock(time);
  const w = watNow(now);
  for (let i = 0; i < 9; i++) {
    const t = utcFromWat(w.getUTCFullYear(), w.getUTCMonth(), w.getUTCDate() + i, h, mi);
    if (new Date(t + HOUR).getUTCDay() === weekday && t > now) return t;
  }
  return null;
}

export function nextLastFriday(time: string, now = Date.now()): number | null {
  const [h, mi] = parseClock(time);
  const w = watNow(now);
  for (let off = 0; off < 3; off++) {
    const y = w.getUTCFullYear();
    const m = w.getUTCMonth() + off;
    const last = new Date(Date.UTC(y, m + 1, 0));
    const back = (last.getUTCDay() - 5 + 7) % 7;
    const t = utcFromWat(y, m, last.getUTCDate() - back, h, mi);
    if (t > now) return t;
  }
  return null;
}

export function serviceStart(service: HomepageService, now = Date.now()): number | null {
  if (service.rule === "weekly") return nextWeekly(service.weekday, service.time, now);
  if (service.rule === "lastfri") return nextLastFriday(service.time, now);
  if (!service.date) return null;
  const [y, mo, d] = service.date.split("-").map(Number) as [number, number, number];
  const [h, mi] = parseClock(service.time);
  const t = utcFromWat(y, mo - 1, d, h, mi);
  return t > now ? t : null;
}

/** Card label for the "when" of a service, e.g. "Wed · 5:00 PM". */
export function serviceWhen(service: HomepageService) {
  const time = formatClock(service.time);
  if (service.rule === "lastfri") return `Last Fri · ${time}`;
  if (service.rule === "date") {
    const [, mo, d] = service.date.split("-").map(Number) as [number, number, number];
    return `${d} ${MON3[mo - 1]} · ${time}`;
  }
  return service.type === "sunday" ? time : `${DOW3[service.weekday]} · ${time}`;
}

export function countdownParts(target: number | null, now = Date.now()) {
  const s = Math.max(0, Math.floor(((target ?? now) - now) / 1000));
  return {
    days: pad(Math.floor(s / 86400)),
    hours: pad(Math.floor((s % 86400) / 3600)),
    minutes: pad(Math.floor((s % 3600) / 60)),
    seconds: pad(s % 60),
  };
}

/** Services still worth listing (finished one-off dates are hidden). */
export function visibleServices(services: HomepageService[], type: ServiceType, now = Date.now()) {
  return services.filter((s) => s.active && s.type === type && (s.rule !== "date" || serviceStart(s, now)));
}

export function countdownService(content: HomepageContent): HomepageService | null {
  if (!content.countdown.enabled) return null;
  const active = content.services.filter((s) => s.active);
  return active.find((s) => s.id === content.countdown.serviceId) ?? null;
}

/* -------------------------------------------------------------------------- */
/* Events                                                                     */
/* -------------------------------------------------------------------------- */

function nextWeeklyDate(weekday: number, from: Date) {
  const d = new Date(from);
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + ((weekday - d.getDay() + 7) % 7));
  return d;
}

export interface UpcomingEvent {
  event: HomepageEvent;
  date: Date;
  taken: number;
  full: boolean;
}

/** Upcoming events ordered by their next occurrence, with live registration counts. */
export function upcomingEvents(
  events: HomepageEvent[],
  counts: Record<string, number> = {},
  now = new Date(),
): UpcomingEvent[] {
  const today = ymd(now);
  const rows: UpcomingEvent[] = [];
  for (const event of events) {
    if (!event.active) continue;
    let date: Date;
    if (event.repeat === "weekly") date = nextWeeklyDate(event.weekday, now);
    else {
      if (!event.startDate || (event.endDate || event.startDate) < today) continue;
      const [y, m, d] = event.startDate.split("-").map(Number) as [number, number, number];
      date = new Date(y, m - 1, d, 12);
    }
    const taken = (event.taken || 0) + (counts[event.id] ?? 0);
    rows.push({ event, date, taken, full: Boolean(event.capacity) && taken >= (event.capacity as number) });
  }
  return rows.sort((a, b) => a.date.getTime() - b.date.getTime());
}

/* -------------------------------------------------------------------------- */
/* Calendar                                                                   */
/* -------------------------------------------------------------------------- */

export const CALENDAR_LABELS: Record<CalendarKind, string> = {
  sunday: "Sunday Worship",
  midweek: "Midweek Service",
  vigil: "Special Vigil",
  event: "Event or Outreach",
};

export interface CalendarItem {
  type: CalendarKind;
  title: string;
  time: string;
  short: string;
  venue: string;
  minutes: number;
}

const isLastOfMonth = (d: Date) =>
  new Date(d.getFullYear(), d.getMonth(), d.getDate() + 7).getMonth() !== d.getMonth();

export function calendarItems(
  d: Date,
  filter: CalendarKind | "all",
  content: Pick<HomepageContent, "services" | "events">,
): CalendarItem[] {
  const out: CalendarItem[] = [];
  const dow = d.getDay();
  const key = ymd(d);
  for (const s of content.services) {
    if (!s.active) continue;
    const hit =
      s.rule === "weekly" ? s.weekday === dow : s.rule === "lastfri" ? dow === 5 && isLastOfMonth(d) : s.date === key;
    if (!hit) continue;
    const [h, m] = parseClock(s.time);
    out.push({ type: s.type, title: s.title, time: formatClock(s.time), short: shortTime(s.time), venue: s.venue, minutes: h * 60 + m });
  }
  for (const e of content.events) {
    if (!e.active) continue;
    const hit =
      e.repeat === "weekly" ? e.weekday === dow : Boolean(e.startDate) && key >= e.startDate && key <= (e.endDate || e.startDate);
    if (!hit) continue;
    const [h, m] = parseClock(e.startTime);
    out.push({ type: "event", title: e.title, time: formatClock(e.startTime), short: shortTime(e.startTime), venue: e.venue, minutes: h * 60 + m });
  }
  out.sort((a, b) => a.minutes - b.minutes);
  return filter === "all" ? out : out.filter((item) => item.type === filter);
}

/* -------------------------------------------------------------------------- */
/* Verse of the day                                                           */
/* -------------------------------------------------------------------------- */

export function verseOfTheDay(verses: HomepageVerse[], now = new Date()): HomepageVerse | null {
  if (!verses.length) return null;
  const dayNumber = Math.floor((now.getTime() - now.getTimezoneOffset() * 60000) / 86_400_000);
  return verses[dayNumber % verses.length] ?? null;
}

/* -------------------------------------------------------------------------- */
/* Add-to-calendar                                                            */
/* -------------------------------------------------------------------------- */

const fmtUtc = (t: number) => new Date(t).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
const rrule = (s: HomepageService) =>
  s.rule === "weekly" ? "RRULE:FREQ=WEEKLY" : s.rule === "lastfri" ? "RRULE:FREQ=MONTHLY;BYDAY=-1FR" : "";
const place = (s: HomepageService, content: Pick<HomepageContent, "siteName" | "contact">) =>
  `${s.venue}, ${content.contact.address || content.siteName}`;

export function googleCalendarUrl(
  s: HomepageService,
  content: Pick<HomepageContent, "siteName" | "contact">,
  now = Date.now(),
) {
  const start = serviceStart(s, now);
  if (!start) return "";
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: `${s.title} · ${content.siteName}`,
    dates: `${fmtUtc(start)}/${fmtUtc(start + s.duration * 60_000)}`,
    location: place(s, content),
    details: s.minister ? `With ${s.minister}. ${content.siteName}.` : content.siteName,
  });
  const recurrence = rrule(s);
  if (recurrence) params.set("recur", recurrence);
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

const icsEscape = (value: string) => value.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

export function icsFor(
  s: HomepageService,
  content: Pick<HomepageContent, "siteName" | "contact">,
  now = Date.now(),
): string {
  const start = serviceStart(s, now);
  if (!start) return "";
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//ChapelFlow//Schedule//EN",
    "BEGIN:VEVENT",
    `UID:${s.id}-${fmtUtc(start)}@chapelflow`,
    `DTSTAMP:${fmtUtc(now)}`,
    `DTSTART:${fmtUtc(start)}`,
    `DTEND:${fmtUtc(start + s.duration * 60_000)}`,
    `SUMMARY:${icsEscape(`${s.title} - ${content.siteName}`)}`,
    `LOCATION:${icsEscape(place(s, content))}`,
    `DESCRIPTION:${icsEscape(s.minister ? `With ${s.minister}` : content.siteName)}`,
  ];
  const recurrence = rrule(s);
  if (recurrence) lines.push(recurrence);
  lines.push("END:VEVENT", "END:VCALENDAR");
  return lines.join("\r\n");
}

/** `# anchor`, `/path` and `https://` targets are all allowed by the backend. */
export const isExternalHref = (href: string) => /^https?:\/\//i.test(href);
export const isAnchorHref = (href: string) => href.startsWith("#");
/** Defence in depth: never render a link whose scheme is not http(s), a path or an anchor. */
export function safeHref(href: string | undefined | null) {
  if (!href) return "";
  return /^(https?:\/\/|\/(?!\/)|#)/i.test(href) ? href : "";
}
