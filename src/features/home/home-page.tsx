import { ArrowRight, ArrowUp, BookOpen, CalendarDays, ChevronLeft, ChevronRight, Copy, Heart, LogIn, Megaphone, Pause, Play, Share2, Video, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LoadingState, useToast } from "../../components/ui";
import {
  countdownParts,
  countdownService,
  serviceStart,
  verseOfTheDay,
  type HomepageContent,
} from "../../lib/homepage-content";
import {
  CalendarSection,
  EventsSection,
  GallerySection,
  MinistriesSection,
  ScheduleSection,
} from "./home-sections";
import { RequestModal, type RequestTarget } from "./request-modal";
import { SmartLink } from "./smart-link";
import { useNow, usePublicHomepage, useRegistered } from "./use-homepage";

/* ------------------------------- Ticker ---------------------------------- */

const TICKER_KEY = "chapelflow:ticker-dismissed";

const DEFAULT_HERO_IMAGE = "/chapel-hero.jpg";
const HERO_SLIDES = [
  { src: DEFAULT_HERO_IMAGE, alt: "Students worshipping together at Chrisland University Chapel" },
  { src: "/chapel-slide-02.jpg", alt: "A student enjoying a chapel gathering" },
  { src: "/chapel-slide-03.jpg", alt: "Students hosting a Christmas chapel event" },
  { src: "/chapel-slide-04.jpg", alt: "Students leading a chapel programme" },
  { src: "/chapel-slide-05.jpg", alt: "A student singing during worship" },
  { src: "/chapel-slide-06.jpg", alt: "Students praising together at chapel" },
  { src: "/chapel-slide-07.jpg", alt: "A student worshipping with the chapel community" },
  { src: "/chapel-slide-08.jpg", alt: "Students sharing a moment during chapel" },
  { src: "/chapel-slide-09.jpg", alt: "A student singing with the chapel community" },
];

function HeroSlideshow({ primaryImage, siteName, caption }: { primaryImage: string; siteName: string; caption?: string }) {
  const slides = primaryImage === DEFAULT_HERO_IMAGE
    ? HERO_SLIDES
    : [{ ...HERO_SLIDES[0], src: primaryImage }, ...HERO_SLIDES.slice(1)];
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const shouldPause = paused || hovered || focused || reducedMotion;

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (shouldPause) return;
    const timer = window.setInterval(() => setActiveIndex((index) => (index + 1) % slides.length), 5600);
    return () => window.clearInterval(timer);
  }, [shouldPause, slides.length]);

  const goTo = (index: number) => setActiveIndex((index + slides.length) % slides.length);

  return (
    <figure
      className="cuc-home__hero-image"
      role="region"
      aria-roledescription="carousel"
      aria-label={`${siteName} photos`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") goTo(activeIndex - 1);
        if (event.key === "ArrowRight") goTo(activeIndex + 1);
      }}
    >
      {slides.map((slide, index) => (
        <img
          key={slide.src}
          className={`cuc-home__hero-slide${index === activeIndex ? " is-active" : ""}`}
          src={slide.src}
          alt={slide.alt}
          aria-hidden={index !== activeIndex}
          fetchPriority={index === 0 ? "high" : "auto"}
          decoding="async"
        />
      ))}
      <div className="cuc-home__hero-controls" role="group" aria-label="Slideshow controls">
        <button type="button" aria-label="Previous image" onClick={() => goTo(activeIndex - 1)}><ChevronLeft size={18} /></button>
        <button type="button" aria-label={paused ? "Play slideshow" : "Pause slideshow"} aria-pressed={paused} onClick={() => setPaused((value) => !value)}>
          {paused ? <Play size={15} /> : <Pause size={15} />}
        </button>
        <button type="button" aria-label="Next image" onClick={() => goTo(activeIndex + 1)}><ChevronRight size={18} /></button>
      </div>
      <div className="cuc-home__hero-pagination" role="group" aria-label="Choose an image">
        {slides.map((slide, index) => (
          <button key={slide.src} type="button" aria-label={`Show image ${index + 1}`} aria-current={index === activeIndex ? "true" : undefined} onClick={() => goTo(index)} />
        ))}
      </div>
      {activeIndex === 0 && <figcaption>{caption || "Chrisland University Chapel"}</figcaption>}
    </figure>
  );
}

function hashOf(value: string) {
  let h = 0;
  for (let i = 0; i < value.length; i++) h = (h * 31 + value.charCodeAt(i)) | 0;
  return String(h);
}

function AnnouncementTicker({ content }: { content: HomepageContent }) {
  const items = content.announcements.filter((a) => a.active);
  const signature = hashOf(items.map((a) => `${a.text}|${a.linkHref}`).join("\n"));
  const [hidden, setHidden] = useState(() => {
    try {
      return sessionStorage.getItem(TICKER_KEY) === signature;
    } catch {
      return false;
    }
  });
  if (!items.length || hidden) return null;

  const chars = items.reduce((sum, a) => sum + a.text.length + a.linkLabel.length, 0);
  // Repeat short lists so one set always spans a wide screen, then duplicate the set for a seamless loop.
  const repeat = Math.max(1, Math.ceil(260 / Math.max(chars, 1)));
  const duration = Math.max(24, Math.round(chars * repeat * 0.14));
  const renderSet = (hiddenSet: boolean) => (
    <div className="hp-ticker__set" aria-hidden={hiddenSet || undefined}>
      {Array.from({ length: repeat }).flatMap((_, r) =>
        items.map((a) => (
          <span className="hp-ticker__item" key={`${r}-${a.id}`}>
            {a.text}
            {a.linkLabel && a.linkHref && (
              <SmartLink href={a.linkHref} tabIndex={hiddenSet ? -1 : undefined}>
                {a.linkLabel}
              </SmartLink>
            )}
          </span>
        )),
      )}
    </div>
  );
  return (
    <div className="hp-ticker" role="region" aria-label="Chapel announcements">
      <span className="hp-ticker__label"><Megaphone aria-hidden="true" />Notice</span>
      <div className="hp-ticker__viewport">
        <div className="hp-ticker__track" style={{ animationDuration: `${duration}s` }}>
          {renderSet(false)}
          {renderSet(true)}
        </div>
      </div>
      <button
        type="button"
        className="hp-ticker__close"
        aria-label="Dismiss announcements"
        onClick={() => {
          setHidden(true);
          try {
            sessionStorage.setItem(TICKER_KEY, signature);
          } catch {
            // Dismissal simply lasts for this page view.
          }
        }}
      >
        <X aria-hidden="true" />
      </button>
    </div>
  );
}

/* ------------------------------ Countdown -------------------------------- */

function HeroCountdown({ content }: { content: HomepageContent }) {
  const now = useNow(1000);
  const service = countdownService(content);
  if (!service) return null;
  const target = serviceStart(service, now);
  if (!target) return null;
  const parts = countdownParts(target, now);
  const units: [string, string][] = [
    [parts.days, "Days"],
    [parts.hours, "Hours"],
    [parts.minutes, "Mins"],
    [parts.seconds, "Secs"],
  ];
  return (
    <div className="hp-countdown">
      <p className="hp-countdown__label">{service.title} begins in</p>
      <div className="hp-countdown__row" role="timer" aria-label={`Time until ${service.title}`}>
        {units.map(([value, label], i) => (
          <div className="hp-countdown__unit" key={label}>
            <div className="hp-countdown__box">{value}</div>
            <span>{label}</span>
            {i < units.length - 1 && <em aria-hidden="true">:</em>}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ----------------------------- Verse of the day -------------------------- */

function VerseOfTheDay({ content }: { content: HomepageContent }) {
  const toast = useToast();
  const verse = useMemo(() => (content.verse.enabled ? verseOfTheDay(content.verse.verses) : null), [content.verse]);
  if (!verse) return null;
  const full = `${verse.text} (${verse.reference}${verse.translation ? `, ${verse.translation}` : ""})`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(full);
      toast("Verse copied.");
    } catch {
      toast("Couldn't copy. Select the verse text and copy it manually.", "error");
    }
  };
  const share = async () => {
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title: "Verse of the day", text: full });
      } catch {
        // The person dismissed the share sheet.
      }
    } else await copy();
  };
  return (
    <section className="hp-verse-band" aria-labelledby="hp-verse-head">
      <div className="hp-verse">
        <div className="hp-verse__top">
          <span className="hp-verse__ico"><BookOpen aria-hidden="true" /></span>
          <div>
            <b id="hp-verse-head">Verse of the day</b>
            <small>{new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</small>
          </div>
        </div>
        <div className="hp-verse__main">
          <blockquote>“{verse.text}”</blockquote>
          <p className="hp-verse__ref">{verse.reference}{verse.translation ? ` · ${verse.translation}` : ""}</p>
          {verse.note && <p className="hp-verse__note">{verse.note}</p>}
        </div>
        <div className="hp-verse__actions">
          <button type="button" className="button button--secondary" onClick={() => void copy()}><Copy aria-hidden="true" />Copy verse</button>
          <button type="button" className="button button--secondary" onClick={() => void share()}><Share2 aria-hidden="true" />Share</button>
        </div>
      </div>
    </section>
  );
}

/* ----------------------------- Floating UI ------------------------------- */

function BackToTop() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 700);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <button
      type="button"
      className={`hp-btt${show ? " is-visible" : ""}`}
      aria-label="Back to top"
      tabIndex={show ? 0 : -1}
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
    >
      <ArrowUp aria-hidden="true" />
    </button>
  );
}

function MobileActionBar({ content }: { content: HomepageContent }) {
  return (
    <nav className="hp-mbar" aria-label="Quick actions">
      {content.sections.schedule.enabled && (
        <a href="#schedule"><CalendarDays aria-hidden="true" /><span>Schedule</span></a>
      )}
      <Link to="/giving"><Heart aria-hidden="true" /><span>Give</span></Link>
      <Link to="/sermons"><Video aria-hidden="true" /><span>Watch</span></Link>
      <Link className="is-cta" to="/login"><LogIn aria-hidden="true" /><span>Login</span></Link>
    </nav>
  );
}

/* --------------------------------- Page ---------------------------------- */

export function HomePage() {
  const { content, counts } = usePublicHomepage();
  const { registered, remember } = useRegistered();
  const [target, setTarget] = useState<RequestTarget | null>(null);

  if (!content)
    return (
      <div className="cuc-home hp-loading">
        <LoadingState label="Loading the chapel homepage" />
      </div>
    );

  const { hero, belonging, closing, sections } = content;
  return (
    <div className="cuc-home">
      <AnnouncementTicker content={content} />
      <section className="cuc-home__hero">
        <div className="cuc-home__hero-copy">
          {hero.eyebrow && <p className="cuc-home__eyebrow">{hero.eyebrow}</p>}
          <h1>
            {hero.titleLead}
            {hero.titleAccent && <> <em>{hero.titleAccent}</em></>}
          </h1>
          {hero.lede && <p className="cuc-home__lede">{hero.lede}</p>}
          <HeroCountdown content={content} />
          <div className="cuc-home__actions">
            {hero.primaryLabel && (
              <SmartLink className="button button--primary" href={hero.primaryHref || "/register"}>
                {hero.primaryLabel} <ArrowRight size={18} />
              </SmartLink>
            )}
            {hero.secondaryLabel && (
              <SmartLink className="button button--ghost" href={hero.secondaryHref || "/about"}>
                {hero.secondaryLabel}
              </SmartLink>
            )}
          </div>
          {hero.stats.length > 0 && (
            <dl className="cuc-home__stats">
              {hero.stats.map((stat) => (
                <div key={`${stat.value}-${stat.label}`}><dt>{stat.value}</dt><dd>{stat.label}</dd></div>
              ))}
            </dl>
          )}
        </div>
        <HeroSlideshow primaryImage={hero.imageUrl || "/chapel-hero.jpg"} siteName={content.siteName} caption={hero.imageCaption} />
      </section>

      <VerseOfTheDay content={content} />

      <section className="cuc-home__belonging">
        <div>
          {belonging.eyebrow && <p className="cuc-home__eyebrow">{belonging.eyebrow}</p>}
          <h2>{belonging.title}</h2>
          {belonging.body && <p>{belonging.body}</p>}
          {belonging.quote && <p className="cuc-home__quote">{belonging.quote}</p>}
        </div>
        <div className="cuc-home__photo-rail" aria-label="Chapel community moments">
          <img className="cuc-home__photo-rail-left" src="/chapel-community-left.jpg" alt="" />
          <img className="cuc-home__photo-rail-center" src="/chapel-community-center.jpg" alt="" />
          <img className="cuc-home__photo-rail-right" src="/chapel-community-right.jpg" alt="" />
        </div>
        {belonging.pillars.length > 0 && (
          <div className="cuc-home__pillars">
            {belonging.pillars.map((p) => (
              <article key={p.title}><strong>{p.title}</strong><span>{p.detail}</span></article>
            ))}
          </div>
        )}
      </section>

      {sections.schedule.enabled && <ScheduleSection content={content} />}

      <section className="cuc-home__attendance">
        <div>
          <p className="cuc-home__eyebrow">Secure chapel attendance</p>
          <h2>Present in the moment.<br />Confirmed in seconds.</h2>
          <p>Students scan the official QR shown by an authorized usher. Every live code refreshes automatically and one attendance record is kept for each service.</p>
          <ol><li><span>01</span> Official usher QR</li><li><span>02</span> Rotates every 45 seconds</li><li><span>03</span> Scan with ChapelFlow</li><li><span>04</span> One attendance per service</li></ol>
        </div>
        <div className="cuc-home__attendance-art">
          <img src="/chapel-hero.jpg" alt="Students gathering at the chapel" />
          <div className="cuc-home__qr-card"><small>Official usher QR</small><strong>QR</strong><span>00:45</span></div>
        </div>
      </section>

      {sections.events.enabled && <EventsSection content={content} counts={counts} onRequest={setTarget} registered={registered} />}
      {sections.ministries.enabled && <MinistriesSection content={content} onRequest={setTarget} registered={registered} />}
      {sections.calendar.enabled && <CalendarSection content={content} />}
      {sections.gallery.enabled && <GallerySection content={content} />}

      <section className="cuc-home__closing">
        <img src="/chapel-hero.jpg" alt="" />
        <div>
          {closing.eyebrow && <p className="cuc-home__eyebrow">{closing.eyebrow}</p>}
          <h2>{closing.title}</h2>
          {closing.body && <p>{closing.body}</p>}
          {closing.ctaLabel && (
            <Link className="button button--primary" to="/register">{closing.ctaLabel} <ArrowRight size={18} /></Link>
          )}
        </div>
      </section>

      <RequestModal
        target={target}
        onClose={() => setTarget(null)}
        onDone={(done) => remember(`${done.kind}:${done.id}`)}
      />
      <BackToTop />
      <MobileActionBar content={content} />
    </div>
  );
}
