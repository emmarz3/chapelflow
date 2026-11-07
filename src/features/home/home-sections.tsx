import {
  ArrowRight,
  CalendarPlus,
  Camera,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  Headphones,
  MapPin,
  Play,
  UserRound,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useToast } from "../../components/ui";
import {
  CALENDAR_LABELS,
  DOW3,
  MONTHS,
  MON3,
  calendarItems,
  googleCalendarUrl,
  icsFor,
  serviceWhen,
  upcomingEvents,
  visibleServices,
  ymd,
  type CalendarKind,
  type HomepageContent,
  type HomepageSectionKey,
  type HomepageSermon,
  type ServiceType,
} from "../../lib/homepage-content";
import { UNIT_ICON_COMPONENTS } from "./home-icons";
import type { RequestTarget } from "./request-modal";
import { SmartLink } from "./smart-link";

const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function SectionHead({ content, id }: { content: HomepageContent; id: HomepageSectionKey }) {
  const copy = content.sections[id];
  return (
    <div className="hp-head">
      {copy.eyebrow && <p className="cuc-home__eyebrow">{copy.eyebrow}</p>}
      <h2>{copy.title}</h2>
      {copy.description && <p>{copy.description}</p>}
    </div>
  );
}

/* ------------------------------ Schedule --------------------------------- */

const SERVICE_TABS: { type: ServiceType; label: string }[] = [
  { type: "sunday", label: "Sunday Worship" },
  { type: "midweek", label: "Midweek Service" },
  { type: "vigil", label: "Special Vigils" },
];

export function ScheduleSection({ content }: { content: HomepageContent }) {
  const [tab, setTab] = useState<ServiceType>(() =>
    SERVICE_TABS.find((t) => content.services.some((s) => s.active && s.type === t.type))?.type ?? "sunday",
  );
  const toast = useToast();
  const services = visibleServices(content.services, tab);

  const downloadIcs = (id: string) => {
    const service = content.services.find((s) => s.id === id);
    const data = service ? icsFor(service, content) : "";
    if (!service || !data) return toast("This service has no upcoming date to add.", "error");
    const url = URL.createObjectURL(new Blob([data], { type: "text/calendar;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${service.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.ics`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 4000);
    toast("Calendar file created. Open it to add the service to Apple Calendar.");
  };

  return (
    <section className="hp-section hp-section--alt" id="schedule">
      <div className="hp-wrap">
        <SectionHead content={content} id="schedule" />
        <div className="hp-tabs-wrap">
          <div className="hp-tabs" role="tablist" aria-label="Service type">
            {SERVICE_TABS.map((t) => (
              <button
                key={t.type}
                type="button"
                role="tab"
                aria-selected={tab === t.type}
                className="hp-tab"
                onClick={() => setTab(t.type)}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="hp-sched" role="tabpanel" aria-live="polite">
          {services.length ? (
            services.map((s) => {
              const gcal = googleCalendarUrl(s, content);
              return (
                <article className="hp-card hp-svc" key={s.id}>
                  <div className="hp-svc__top">
                    <span className="hp-chip">{SERVICE_TABS.find((t) => t.type === s.type)?.label}</span>
                    <span className="hp-svc__time">{serviceWhen(s)}</span>
                  </div>
                  <h3>{s.title}</h3>
                  <p className="hp-meta"><MapPin aria-hidden="true" />{s.venue}</p>
                  {s.minister && <p className="hp-meta"><UserRound aria-hidden="true" />{s.minister}</p>}
                  <div className="hp-svc__btns">
                    {gcal && (
                      <a className="hp-mini" href={gcal} target="_blank" rel="noopener noreferrer">
                        <CalendarPlus aria-hidden="true" />Google Cal
                      </a>
                    )}
                    <button type="button" className="hp-mini" onClick={() => downloadIcs(s.id)}>
                      <CalendarPlus aria-hidden="true" />Apple Cal
                    </button>
                  </div>
                </article>
              );
            })
          ) : (
            <p className="hp-empty hp-empty--wide">No services in this category right now. Check the calendar below.</p>
          )}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------- Events --------------------------------- */

export function EventsSection({
  content,
  counts,
  onRequest,
  registered,
}: {
  content: HomepageContent;
  counts: Record<string, number>;
  onRequest: (target: RequestTarget) => void;
  registered: Set<string>;
}) {
  const rows = upcomingEvents(content.events, counts);
  return (
    <section className="hp-section" id="events">
      <div className="hp-wrap">
        <SectionHead content={content} id="events" />
        {rows.length ? (
          <div className="hp-events">
            {rows.map(({ event, date, taken, full }) => {
              const key = `event:${event.id}`;
              const done = registered.has(key);
              const pct = event.capacity ? Math.min(100, Math.round((taken / event.capacity) * 100)) : 0;
              return (
                <article className="hp-card hp-event" key={event.id}>
                  <div className="hp-event__top">
                    <div className="hp-date">
                      <b>{String(date.getDate()).padStart(2, "0")}</b>
                      <span>{MON3[date.getMonth()]}</span>
                    </div>
                    <span className="hp-chip">{event.category}</span>
                  </div>
                  <h3>{event.title}</h3>
                  <p className="hp-meta"><Clock3 aria-hidden="true" />{event.time}</p>
                  <p className="hp-meta"><MapPin aria-hidden="true" />{event.venue}</p>
                  {event.host && <p className="hp-meta"><UserRound aria-hidden="true" />{event.host}</p>}
                  <div className="hp-spots">
                    {event.capacity ? (
                      <>
                        <small>{taken} of {event.capacity} places taken</small>
                        <div className="hp-bar" role="img" aria-label={`${pct}% full`}><i style={{ width: `${pct}%` }} /></div>
                      </>
                    ) : event.repeat === "weekly" ? (
                      <small>Every {WEEKDAY_NAMES[event.weekday]}</small>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className={`button button--primary hp-block${done ? " is-done" : ""}`}
                    disabled={done || full}
                    onClick={() =>
                      onRequest({
                        kind: "event",
                        id: event.id,
                        title: event.title,
                        cta: event.cta,
                        blurb: `${event.time} · ${event.venue}`,
                      })
                    }
                  >
                    {done ? (
                      <><Check aria-hidden="true" />{event.cta === "RSVP" ? "You're going" : "Registered"}</>
                    ) : full ? (
                      "Fully booked"
                    ) : (
                      event.cta
                    )}
                  </button>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="hp-empty hp-empty--wide">No upcoming events are scheduled right now. Please check back soon.</p>
        )}
        {content.sections.calendar.enabled && (
          <div className="hp-foot">
            <a className="hp-link" href="#calendar">See everything on the calendar <ArrowRight aria-hidden="true" /></a>
          </div>
        )}
      </div>
    </section>
  );
}

/* ------------------------------- Sermons --------------------------------- */

function formatSermonDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${MON3[m - 1]} ${y}`;
}

function SermonCard({ sermon, index }: { sermon: HomepageSermon; index: number }) {
  const playHref = sermon.videoUrl || sermon.audioUrl || "/sermons";
  const playable = Boolean(sermon.videoUrl || sermon.audioUrl);
  return (
    <article className="hp-card hp-sermon">
      <div className={`hp-thumb hp-art hp-art--${(index % 7) + 1}`}>
        {sermon.imageUrl && <img src={sermon.imageUrl} alt="" loading="lazy" />}
        {sermon.series && <span className="hp-chip hp-chip--glass">{sermon.series}</span>}
        <SmartLink href={playHref} className="hp-bigplay">
          <Play aria-hidden="true" />
          <span className="sr-only">{playable ? "Play" : "Open"} {sermon.title}</span>
        </SmartLink>
        {sermon.duration && <span className="hp-dur">{sermon.duration}</span>}
      </div>
      <div className="hp-sermon__body">
        <h3>{sermon.title}</h3>
        {sermon.speaker && <p className="hp-meta"><UserRound aria-hidden="true" />{sermon.speaker}</p>}
        <p className="hp-meta"><Clock3 aria-hidden="true" />{formatSermonDate(sermon.date)}</p>
        <div className="hp-sermon__btns">
          <SmartLink href={playHref} className="button button--primary hp-sm">
            <Play aria-hidden="true" />{playable ? "Play" : "View"}
          </SmartLink>
          {sermon.videoUrl && sermon.audioUrl && (
            <SmartLink href={sermon.audioUrl} className="button button--secondary hp-sm">
              <Headphones aria-hidden="true" />Audio
            </SmartLink>
          )}
          {sermon.downloadUrl && (
            <SmartLink href={sermon.downloadUrl} className="button button--secondary hp-sm hp-sm--icon">
              <Download aria-hidden="true" /><span className="sr-only">Download {sermon.title}</span>
            </SmartLink>
          )}
        </div>
      </div>
    </article>
  );
}

export function SermonsSection({ content }: { content: HomepageContent }) {
  const sermons = content.sermons
    .filter((s) => s.active)
    .sort((a, b) => b.date.localeCompare(a.date))
    .slice(0, 6);
  return (
    <section className="hp-section hp-section--alt" id="sermons">
      <div className="hp-wrap">
        <SectionHead content={content} id="sermons" />
        {sermons.length ? (
          <div className="hp-sermons">
            {sermons.map((s, i) => <SermonCard sermon={s} index={i} key={s.id} />)}
          </div>
        ) : (
          <p className="hp-empty hp-empty--wide">New messages will appear here soon.</p>
        )}
        <div className="hp-foot">
          <Link className="hp-link" to="/sermons">View all sermons <ArrowRight aria-hidden="true" /></Link>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------ Ministries ------------------------------- */

export function MinistriesSection({
  content,
  onRequest,
  registered,
}: {
  content: HomepageContent;
  onRequest: (target: RequestTarget) => void;
  registered: Set<string>;
}) {
  const units = content.units.filter((u) => u.active);
  return (
    <section className="hp-section" id="ministries">
      <div className="hp-wrap">
        <SectionHead content={content} id="ministries" />
        {units.length ? (
          <div className="hp-units">
            {units.map((u) => {
              const Icon = UNIT_ICON_COMPONENTS[u.icon] ?? UNIT_ICON_COMPONENTS.users;
              const done = registered.has(`unit:${u.id}`);
              return (
                <article className="hp-card hp-unit" key={u.id}>
                  <div className="hp-unit__ico"><Icon aria-hidden="true" /></div>
                  <h3>{u.name}</h3>
                  {u.description && <p>{u.description}</p>}
                  {u.meeting && <p className="hp-meta"><Clock3 aria-hidden="true" />{u.meeting}</p>}
                  <button
                    type="button"
                    className={`button button--secondary hp-block${done ? " is-done" : ""}`}
                    disabled={done}
                    onClick={() =>
                      onRequest({
                        kind: "unit",
                        id: u.id,
                        title: u.name,
                        cta: "Join",
                        blurb: "Leave your details and the unit leader will reach out about the next meeting.",
                      })
                    }
                  >
                    {done ? <><Check aria-hidden="true" />Request sent</> : "Join this unit"}
                  </button>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="hp-empty hp-empty--wide">Ministry teams will be listed here soon.</p>
        )}
      </div>
    </section>
  );
}

/* ------------------------------- Calendar -------------------------------- */

const CALENDAR_FILTERS: { key: CalendarKind | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "sunday", label: "Sunday Worship" },
  { key: "midweek", label: "Midweek" },
  { key: "vigil", label: "Vigils" },
  { key: "event", label: "Events & Outreach" },
];

const noon = (d: Date) => {
  const copy = new Date(d);
  copy.setHours(12, 0, 0, 0);
  return copy;
};

export function CalendarSection({ content }: { content: HomepageContent }) {
  const [selected, setSelected] = useState(() => noon(new Date()));
  const [view, setView] = useState(() => ({ y: selected.getFullYear(), m: selected.getMonth() }));
  const [filter, setFilter] = useState<CalendarKind | "all">("all");
  const data = useMemo(() => ({ services: content.services, events: content.events }), [content.services, content.events]);

  const first = new Date(view.y, view.m, 1);
  const lead = first.getDay();
  const days = new Date(view.y, view.m + 1, 0).getDate();
  const total = Math.ceil((lead + days) / 7) * 7;
  const todayKey = ymd(new Date());
  const selectedKey = ymd(selected);

  const go = (delta: number) => {
    const d = new Date(view.y, view.m + delta, 1);
    setView({ y: d.getFullYear(), m: d.getMonth() });
  };
  const goToday = () => {
    const t = noon(new Date());
    setSelected(t);
    setView({ y: t.getFullYear(), m: t.getMonth() });
  };

  const agenda = calendarItems(selected, filter, data);
  const next = useMemo(() => {
    const rows: { date: Date; item: ReturnType<typeof calendarItems>[number] }[] = [];
    for (let i = 1; i <= 60 && rows.length < 4; i++) {
      const date = new Date(selected.getFullYear(), selected.getMonth(), selected.getDate() + i, 12);
      for (const item of calendarItems(date, filter, data)) if (rows.length < 4) rows.push({ date, item });
    }
    return rows;
  }, [selected, filter, data]);

  const cells = [];
  for (let i = 0; i < total; i++) {
    const n = i - lead + 1;
    if (n < 1 || n > days) {
      cells.push(<div className="hp-day is-off" key={i} aria-hidden="true" />);
      continue;
    }
    const date = new Date(view.y, view.m, n, 12);
    const key = ymd(date);
    const items = calendarItems(date, filter, data);
    cells.push(
      <button
        type="button"
        key={i}
        className={`hp-day${key === todayKey ? " is-today" : ""}`}
        aria-pressed={key === selectedKey}
        aria-label={`${n} ${MONTHS[view.m]}, ${items.length ? `${items.length} ${items.length > 1 ? "items" : "item"}` : "nothing scheduled"}`}
        onClick={() => setSelected(date)}
      >
        <span className="hp-day__n">{n}</span>
        {items.slice(0, 2).map((it, idx) => (
          <span className={`hp-pill hp-k-${it.type}`} key={idx}>{it.short} {it.title}</span>
        ))}
        {items.length > 2 && <span className="hp-more">+{items.length - 2} more</span>}
        <span className="hp-dots">{items.slice(0, 4).map((it, idx) => <i className={`hp-k-${it.type}`} key={idx} />)}</span>
      </button>,
    );
  }

  return (
    <section className="hp-section hp-section--alt" id="calendar">
      <div className="hp-wrap">
        <SectionHead content={content} id="calendar" />
        <div className="hp-cal">
          <div className="hp-card hp-cal__main">
            <div className="hp-cal__bar">
              <h3 aria-live="polite">{MONTHS[view.m]} {view.y}</h3>
              <div className="hp-cal__nav">
                <button type="button" className="hp-icon-btn" aria-label="Previous month" onClick={() => go(-1)}><ChevronLeft aria-hidden="true" /></button>
                <button type="button" className="hp-today" onClick={goToday}>Today</button>
                <button type="button" className="hp-icon-btn" aria-label="Next month" onClick={() => go(1)}><ChevronRight aria-hidden="true" /></button>
              </div>
            </div>
            <div className="hp-tabs hp-tabs--left" role="group" aria-label="Filter by service type">
              {CALENDAR_FILTERS.map((f) => (
                <button key={f.key} type="button" className="hp-tab" aria-pressed={filter === f.key} onClick={() => setFilter(f.key)}>
                  {f.label}
                </button>
              ))}
            </div>
            <div className="hp-dow" aria-hidden="true">{DOW3.map((d) => <span key={d}>{d}</span>)}</div>
            <div className="hp-grid7">{cells}</div>
            <div className="hp-legend">
              {(Object.keys(CALENDAR_LABELS) as CalendarKind[]).map((k) => (
                <span className={`hp-k-${k}`} key={k}><i />{CALENDAR_LABELS[k]}</span>
              ))}
            </div>
          </div>
          <aside className="hp-card hp-cal__side" aria-live="polite">
            <h4>{selected.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</h4>
            <p className="hp-sub">{selectedKey === todayKey ? "Today" : selected.getFullYear()}</p>
            {agenda.length ? (
              <ul className="hp-agenda">
                {agenda.map((it, i) => (
                  <li className={`hp-k-${it.type}`} key={i}>
                    <span className="hp-tm">{it.time}</span>
                    <b>{it.title}</b>
                    <small>{it.venue} · {CALENDAR_LABELS[it.type]}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hp-empty">Nothing scheduled on this day{filter !== "all" ? " for this filter" : ""}. Pick another date or see what's next below.</p>
            )}
            {next.length > 0 && (
              <>
                <hr />
                <h5>Coming up</h5>
                <ul className="hp-agenda">
                  {next.map((x, i) => (
                    <li className={`hp-k-${x.item.type}`} key={i}>
                      <span className="hp-tm">{DOW3[x.date.getDay()]} {x.date.getDate()} {MON3[x.date.getMonth()]} · {x.item.time}</span>
                      <b>{x.item.title}</b>
                      <small>{x.item.venue}</small>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </aside>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------- Gallery -------------------------------- */

export function GallerySection({ content }: { content: HomepageContent }) {
  const items = content.gallery.filter((g) => g.active);
  return (
    <section className="hp-section" id="gallery">
      <div className="hp-wrap">
        <SectionHead content={content} id="gallery" />
        {items.length ? (
          <div className="hp-gal">
            {items.map((g, i) => (
              <Link to={`/gallery/${encodeURIComponent(g.id)}`} className={`hp-gt hp-gt--${i < 7 ? i + 1 : 0}`} key={g.id} aria-label={`Open collection: ${g.title}`}>
                {g.imageUrl ? <img src={g.imageUrl} alt="" loading="lazy" /> : <div className={`hp-art hp-art--${(i % 7) + 1}`} />}
                <span className="hp-scrim" />
                <Camera className="hp-cam" aria-hidden="true" />
                <span className="hp-cap"><b>{g.title}</b>{g.subtitle && <small>{g.subtitle}</small>}<small>View collection</small></span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="hp-empty hp-empty--wide">Photos will be added here soon.</p>
        )}
        <div className="hp-foot">
          <Link className="hp-link" to="/gallery">View full gallery <ArrowRight aria-hidden="true" /></Link>
        </div>
      </div>
    </section>
  );
}
