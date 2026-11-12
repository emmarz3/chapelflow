import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Cookie,
  ChevronLeft,
  ChevronRight,
  Home,
  Gauge,
  MapPin,
  Menu,
  Info,
  Pause,
  Play,
  Radio,
  Moon,
  Sun,
  Users,
  X,
  Mail,
  Instagram,
  Twitter,
  Facebook,
  Youtube,
  ChevronUp,
  Send,
  BookOpen,
  GraduationCap,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./auth-context";
import { Button, PageHeader, SectionLink } from "../components/ui";
import {
  COOKIE_CONSENT_EVENT,
  isSafeExternalUrl,
  readCookieConsent,
  requestCookiePreferenceReview,
  writeCookieConsent,
  type CookieConsentChoice,
} from "../lib/cookie-consent";
import { usePublicMotion } from "../components/motion/motion-system";
import { isDemoMode } from "../lib/fixtures";
import { homepageService, publicService } from "../services/chapelflow";
import type { EventSummary } from "../types/domain";
import { LivePublicDetailPage, LivePublicPage } from "./live-public";

const publicNav = [
  ["About", "/about"],
  ["Events", "/events"],
  ["Sermons", "/sermons"],
  ["Gallery", "/gallery"],
] as const;

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0] ?? "U";
  const last = parts.at(-1) ?? first;
  return `${first.charAt(0)}${parts.length > 1 ? last.charAt(0) : first.charAt(1)}`.toUpperCase();
}

export function PublicLayout() {
  const [open, setOpen] = useState(false);
  const { user, loading } = useAuth();
  const location = useLocation();
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    localStorage.getItem("chapelflow-theme") === "dark" ? "dark" : "light",
  );
  const mainRef = useRef<HTMLElement>(null);
  usePublicMotion(mainRef, location.pathname);
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("chapelflow-theme", theme);
  }, [theme]);
  return (
    <div className={`public-shell ${location.pathname === "/" ? "public-shell--home" : ""}`}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="public-nav">
        <Link to="/" aria-label="ChapelFlow home">
          <PublicWordmark />
        </Link>
        <nav aria-label="Public navigation">
          {publicNav.map(([label, path]) => (
            <NavLink key={path} to={path}>
              {label}
            </NavLink>
          ))}
        </nav>
        {location.pathname === "/" && <button className="icon-button public-theme-toggle" type="button" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} onClick={() => setTheme((value) => value === "dark" ? "light" : "dark")}>{theme === "dark" ? <Sun /> : <Moon />}</button>}
        <div className="public-nav__actions">
          {!loading && (user ? <Link className="public-nav__avatar-link" to="/app" aria-label={`Open ${user.name}'s dashboard`} title={user.name}><span className="public-nav__avatar" aria-hidden="true">{getInitials(user.name)}</span></Link> : <><Link className="text-link" to="/login">Sign in</Link><Link className="button button--primary" to="/register">Create account <ArrowRight size={16} /></Link></>)}
        </div>
        <button
          className="icon-button public-nav__menu"
          type="button"
          aria-expanded={open}
          aria-controls="public-mobile-menu"
          aria-label={open ? "Close navigation" : "Open navigation"}
          onClick={() => setOpen(true)}
        >
          <Menu />
        </button>
      </header>
      {open && (
        <div className="mobile-menu" id="public-mobile-menu" role="dialog" aria-modal="true" aria-label="Site navigation">
          <button
            className="icon-button"
            type="button"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <X />
          </button>
          <PublicWordmark />
          {publicNav.map(([label, path]) => (
            <Link onClick={() => setOpen(false)} key={path} to={path}>
              {label}
            </Link>
          ))}
          {!loading && (user ? <Link className="mobile-menu__account" onClick={() => setOpen(false)} to="/app" aria-label={`Open ${user.name}'s dashboard`}><span className="public-nav__avatar" aria-hidden="true">{getInitials(user.name)}</span><span>Dashboard</span></Link> : <><Link onClick={() => setOpen(false)} to="/login">Sign in</Link><Link onClick={() => setOpen(false)} className="button button--primary" to="/register">Create account <ArrowRight size={16} /></Link></>)}
        </div>
      )}
      <main id="main-content" ref={mainRef}>
        <Outlet />
      </main>
      <nav className="public-mobile-nav" aria-label="Mobile chapel navigation">
        <NavLink to="/" end><Home aria-hidden="true" /><span>Home</span></NavLink>
        <NavLink to="/events"><CalendarDays aria-hidden="true" /><span>Events</span></NavLink>
        {user ? <NavLink className="public-mobile-nav__account" to="/app" aria-label={`Open ${user.name}'s dashboard`} title="Dashboard"><span className="public-nav__avatar" aria-hidden="true">{getInitials(user.name)}</span></NavLink> : <NavLink to="/app"><Gauge aria-hidden="true" /><span>Dashboard</span></NavLink>}
        <NavLink to="/about"><Info aria-hidden="true" /><span>About</span></NavLink>
      </nav>
      <SiteFooter />
    </div>
  );
}

function SiteFooter() {
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);
  const currentYear = new Date().getFullYear();

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setSubscribed(true);
    setEmail("");
    setTimeout(() => setSubscribed(false), 4000);
  };

  return (
    <footer className="site-footer">
      <div className="site-footer__main">
        <div className="site-footer__brand">
          <div className="site-footer__wordmark">
            <strong>Chapel<em>Flow</em></strong>
            <small>Chrisland University Chapel</small>
          </div>
          <p>
            A connected chapel community for worship, service, and growth at
            Chrisland University, Abeokuta.
          </p>
          <div className="site-footer__badge">
            <GraduationCap size={14} aria-hidden="true" />
            <span>CUC Verified</span>
          </div>
        </div>

        <div className="site-footer__nav">
          <div>
            <h3>Explore</h3>
            <Link to="/about">About us</Link>
            <Link to="/events">Events</Link>
            <Link to="/sermons">Sermons</Link>
            <Link to="/gallery">Gallery</Link>
          </div>
          <div>
            <h3>Community</h3>
            <Link to="/faq">Frequently asked questions</Link>
            <Link to="/contact">Contact the chapel</Link>
            <Link to="/privacy">Privacy policy</Link>
            <Link to="/terms">Terms of use</Link>
          </div>
        </div>

        <div className="site-footer__contact">
          <h3>Connect</h3>
          <p>
            <MapPin size={16} aria-hidden="true" />
            <span>
              Chrisland University Chapel
              <br />
              Abeokuta Campus, Ogun State
            </span>
          </p>
          <p>
            <Mail size={16} aria-hidden="true" />
            <a href="mailto:chapel@chrislanduniversity.edu.ng">chapel@chrislanduniversity.edu.ng</a>
          </p>
        </div>

        <div className="site-footer__social">
          <h3>Follow along</h3>
          <FooterSocialLinks />
          <form className="site-footer__newsletter" onSubmit={handleSubscribe}>
            <label htmlFor="footer-newsletter">Chapel updates</label>
            <div className="site-footer__newsletter-row">
              <input
                id="footer-newsletter"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
              <button type="submit" aria-label="Subscribe to chapel updates">
                {subscribed ? <BookOpen size={18} aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
              </button>
            </div>
            <small>Occasional updates. No spam, ever.</small>
          </form>
        </div>
      </div>

      <div className="site-footer__legal">
        <div className="site-footer__legal-left">
          <span>© {currentYear} Chrisland University Chapel</span>
          <span className="site-footer__dot" aria-hidden="true" />
          <span>Powered by Zephyrcore</span>
        </div>
        <div className="site-footer__legal-right">
          <Link to="/cookies">Cookie policy</Link>
          <button type="button" className="site-footer__cookie-settings" onClick={requestCookiePreferenceReview}>
            Cookie settings
          </button>
          <Link to="/accessibility">Accessibility</Link>
          <button
            type="button"
            className="site-footer__back-to-top"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            aria-label="Back to top"
          >
            <ChevronUp size={16} aria-hidden="true" />
            <span>Back to top</span>
          </button>
        </div>
      </div>
    </footer>
  );
}

function FooterSocialLinks() {
  const homepage = useQuery({
    queryKey: ["site-homepage"],
    queryFn: async () => (await homepageService.get()).data,
    staleTime: 5 * 60_000,
  });
  const contact = homepage.data?.content?.contact;
  const channels = [
    { label: "Chrisland University Chapel on Instagram", href: isSafeExternalUrl(contact?.instagram), Icon: Instagram },
    { label: "Chrisland University Chapel on X", href: isSafeExternalUrl(contact?.x), Icon: Twitter },
    { label: "Chrisland University Chapel on Facebook", href: isSafeExternalUrl(contact?.facebook), Icon: Facebook },
    { label: "Chrisland University Chapel on YouTube", href: isSafeExternalUrl(contact?.youtube), Icon: Youtube },
  ].filter((channel): channel is typeof channel & { href: string } => Boolean(channel.href));

  if (!channels.length) {
    return (
      <p className="site-footer__social-unavailable">
        Official chapel social channels are not listed yet. They will appear here after the chapel publishes verified destinations.
      </p>
    );
  }

  return (
    <div className="site-footer__social-links">
      {channels.map(({ label, href, Icon }) => (
        <a
          key={label}
          href={href}
          aria-label={label}
          className="site-footer__social-link"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Icon size={20} aria-hidden="true" />
        </a>
      ))}
    </div>
  );
}

function PublicWordmark({ inverse = false }: { inverse?: boolean }) {
  return (
    <span className={`cuc-wordmark ${inverse ? "cuc-wordmark--inverse" : ""}`}>
      <strong>Chapel<em>Flow</em></strong>
      <small>Chrisland University Chapel</small>
    </span>
  );
}

export function HomePage() {
  return <DemoHomePage />;
}

function localDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function DemoHomePage() {
  const { user, loading } = useAuth();
  const eventsQuery = useQuery({
    queryKey: ["public-home-events"],
    queryFn: async () => (await publicService.events({ page: 1, pageSize: 50 })).data,
    refetchInterval: 60_000,
  });
  const today = localDateKey(new Date());
  const upcomingEvents = (eventsQuery.data ?? [])
    .filter((event) => event.visibility === "public" && event.date >= today)
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
  return (
    <div className="cuc-home">
      <section className="cuc-home__hero">
        <div className="cuc-home__hero-copy">
          <p className="cuc-home__eyebrow">Chrisland University Chapel</p>
          <h1>Where faith becomes <em>community.</em></h1>
          <p className="cuc-home__lede">One beautiful place to worship, belong, grow, and stay connected to chapel life at CUC.</p>
          <div className="cuc-home__actions">
            <Link className="button button--primary" to="/service-times">Plan your visit <ArrowRight size={18} /></Link>
            {!loading && <Link className="button button--ghost" to={user ? "/app" : "/login"}>Open ChapelFlow</Link>}
          </div>
        </div>
        <HomeHeroSlideshow />
      </section>
      <section className="cuc-home__worship" aria-labelledby="cuc-home-worship-title">
        <div>
          <p className="cuc-home__eyebrow">Worship with us</p>
          <h2 id="cuc-home-worship-title">You are welcome at the chapel.</h2>
          <p>Join us for worship, prayer and fellowship. Check the chapel's current service information before you visit.</p>
        </div>
        <Link className="cuc-home__service-link" to="/service-times">
          <span><small>Service times and venues</small><strong>Plan your visit</strong><em>View the latest published schedule</em></span>
          <ArrowRight aria-hidden="true" />
        </Link>
        <p className="cuc-home__schedule-note">Schedule details are awaiting chapel confirmation.</p>
      </section>
      <section className="cuc-home__belonging">
        <div>
          <p className="cuc-home__eyebrow">Who we are</p>
          <h2>About the Chapel</h2>
          <p>Chrisland University Chapel is the spiritual heart of campus: a community where faith and academic excellence grow together.</p>
          <blockquote className="cuc-home__quote">“The intensification of worship is an inner Godward experience of the heart, and the act of serving God is a consistent expression of allegiance to Him.”</blockquote>
          <p className="cuc-home__about-detail">At CUC, we come together as one family in God for electrifying moments of worship, the undiluted Word of God, fervent prayers, and refreshing programmes.</p>
        </div>
        <div className="cuc-home__photo-rail" role="img" aria-label="Students sharing a joyful moment at Chrisland University Chapel, shown as a three-panel photograph">
          <span aria-hidden="true" /><span aria-hidden="true" /><span aria-hidden="true" />
        </div>
        <div className="cuc-home__pillars">
          <article><h3>Our Role</h3><p>Nurturing the spiritual life of students, staff, and faculty through worship, teaching, and pastoral care.</p></article>
          <article><h3>Our Impact</h3><p>Shaping character, building lasting friendships, and sending graduates into the world with purpose.</p></article>
          <article><h3>Our Programs</h3><p>Weekly services, fellowships, church units, outreach, counselling, and special events through the year.</p><Link to="/events">See programs &amp; upcoming events <ArrowRight size={16} aria-hidden="true" /></Link></article>
        </div>
      </section>
      <section className="cuc-home__chaplain" aria-labelledby="cuc-home-chaplain-title">
        <div className="cuc-home__chaplain-photo"><img src="/chaplain.jpg" alt="Portrait of the University Chaplain" loading="lazy" /></div>
        <div>
          <p className="cuc-home__eyebrow">Pastoral leadership</p>
          <h2 id="cuc-home-chaplain-title">Meet the Chaplain</h2>
          <p>Learn about the chapel's pastoral leadership and the people who guide our community.</p>
          <blockquote className="cuc-home__chaplain-quote">
            <p>Sharing the core values of Chrisland University Chapel means more than preaching or organising programmes; it is about living out the message of Christ daily and encouraging others to do the same. Through the commitment to raising godly morals and instilling spiritual values, the Chapel remains a beacon of hope and a catalyst for change in the lives of students, shaping them into leaders who fear God, serve humanity, and transform the world.</p>
            <footer><cite>Rev. Canon Oluwajuwonlo Onasanya</cite><span>University Chaplain</span></footer>
          </blockquote>
          <Link to="/leadership">Read profile <ArrowRight size={17} /></Link>
        </div>
      </section>
      <section className="cuc-home__growth" aria-labelledby="cuc-home-growth-title">
        <div className="cuc-home__growth-inner">
          <div><p className="cuc-home__eyebrow">Life at the chapel</p><h2 id="cuc-home-growth-title">Belonging, Purpose <em>&amp;</em> Growth</h2></div>
          <div className="cuc-home__growth-list">
            <article><h3>Belonging &amp; Support</h3><p>Every student finds a family here: people who pray with you, walk with you, and cheer you on.</p></article>
            <article><h3>Visionary Mandate</h3><p>Raising a generation grounded in faith, excellence, and service to God and humanity.</p></article>
            <article><h3>Community Expansion</h3><p>Reaching beyond the campus walls to serve our neighbours and grow the fellowship.</p></article>
          </div>
        </div>
      </section>
      <section className="cuc-home__university" aria-labelledby="cuc-home-university-title">
        <header><p className="cuc-home__eyebrow">Chrisland University</p><h2 id="cuc-home-university-title">The university we serve.</h2></header>
        <div className="cuc-home__university-statements">
          <article><span>Where we are going</span><h3>Our Vision</h3><p>To become a world-class university renowned for intellectual freedom, ethical standards, research, community service and the outstanding training of a new generation of leaders.</p></article>
          <article><span>Why we exist</span><h3>Our Mission</h3><p>To create a learning environment that nurtures a sound moral and intellectual culture that attracts an excellent blend of faculty from across the world and deploys resources to educate the total person.</p></article>
        </div>
      </section>
      <section className="cuc-home__fellowships" aria-labelledby="cuc-home-fellowships-title">
        <div>
          <p className="cuc-home__eyebrow">Find your people</p>
          <h2 id="cuc-home-fellowships-title">Fellowships and units</h2>
          <p>Whether you want to worship, welcome, create, pray or serve, there is room to take part in chapel life.</p>
        </div>
        {!loading && <Link className="button button--primary" to={user ? "/app/join-community" : "/register"}>{user ? "Explore communities" : "Join the chapel community"} <ArrowRight size={17} /></Link>}
      </section>
      <section className="cuc-home__programmes">
        <NextGathering events={upcomingEvents} loading={eventsQuery.isPending} failed={eventsQuery.isError} />
        <p className="cuc-home__eyebrow">What's on</p>
        <div className="cuc-home__section-head"><h2>Moments worth showing up for.</h2><Link to="/events">See all programmes <ArrowRight size={17} /></Link></div>
        <HomepageCalendar events={upcomingEvents} loading={eventsQuery.isPending} failed={eventsQuery.isError} />
        <div className="cuc-home__media-links"><Link to="/gallery">Explore the chapel gallery <ArrowRight size={16} /></Link><Link to="/sermons">Listen to a sermon <ArrowRight size={16} /></Link><Link to="/giving">Support chapel life <ArrowRight size={16} /></Link></div>
      </section>
      <section className="cuc-home__gallery-entry">
        <div><p className="cuc-home__eyebrow">Chapel gallery</p><h2>Keep the moments close.</h2><p>Browse photographs and videos from worship, fellowship, service, and the life of the chapel.</p></div>
        <Link className="button button--secondary" to="/gallery">Open the gallery <ArrowRight size={17} /></Link>
      </section>
      <section className="cuc-home__wisdom">
        <div className="cuc-home__wisdom-image"><img src="/chaplain-sermon.jpg" alt="The Chaplain preaching at Chrisland University Chapel" /></div>
        <div className="cuc-home__sermons-link"><p className="cuc-home__eyebrow">Sermons and media</p><h2>Wisdom for the journey.</h2><p>Watch messages and teaching shared by the Chaplain.</p><Link className="button button--primary" to="/sermons">Explore sermons <ArrowRight size={17} /></Link></div>
      </section>
      <section className="cuc-home__attendance cuc-home__attendance--compact">
        <div>
          <p className="cuc-home__eyebrow">For students</p>
          <h2>Check in and stay connected.</h2>
          <p>Use ChapelFlow to scan the official usher QR code for attendance, then keep up with your chapel activity in your student account.</p>
          {!loading && <Link className="button button--primary" to={user ? "/app/chapel-pass" : "/login"}>{user ? "Open attendance pass" : "Sign in to ChapelFlow"} <ArrowRight size={17} /></Link>}
        </div>
        <div className="cuc-home__attendance-art"><AttendanceProcessIllustration /></div>
      </section>
      <section className="cuc-home__closing">
        <div className="cuc-home__closing-content">
          <div className="cuc-home__closing-copy"><p className="cuc-home__eyebrow">Chrisland University Chapel</p><h2>Stay connected to everything happening at CUC.</h2><p>Join ChapelFlow and become part of a growing community of faith, purpose, and impact.</p><div className="cuc-home__closing-actions">{!loading && <Link className="button button--primary" to={user ? "/app" : "/register"}>{user ? "Open your dashboard" : "Join the chapel community"} <ArrowRight size={18} /></Link>}<Link className="button button--ghost" to="/contact">Contact the chapel</Link></div></div>
          <div className="cuc-home__closing-media"><video className="cuc-home__closing-video" autoPlay muted loop playsInline preload="metadata" aria-hidden="true" tabIndex={-1}><source src="/you-are-blessed.mp4" type="video/mp4" /></video></div>
        </div>
      </section>
    </div>
  );
}

function formatHomepageEventDate(date: string, time: string) {
  const start = new Date(`${date}T${time || "00:00"}`);
  const eventDate = Number.isNaN(start.getTime()) ? new Date(`${date}T12:00:00`) : start;
  if (Number.isNaN(eventDate.getTime())) return [date, time].filter(Boolean).join(" · ");
  const dateLabel = new Intl.DateTimeFormat("en", { weekday: "short", month: "short", day: "numeric" }).format(eventDate);
  const timeLabel = Number.isNaN(start.getTime()) ? time : new Intl.DateTimeFormat("en", { hour: "numeric", minute: "2-digit" }).format(start);
  return timeLabel ? `${dateLabel} · ${timeLabel}` : dateLabel;
}

function NextGathering({ events, loading, failed }: { events: EventSummary[]; loading: boolean; failed: boolean }) {
  const [activeIndex, setActiveIndex] = useState(0);
  useEffect(() => {
    setActiveIndex(0);
    if (events.length < 2) return;
    const timer = window.setInterval(() => setActiveIndex((index) => (index + 1) % events.length), 5000);
    return () => window.clearInterval(timer);
  }, [events.length]);
  const event = events[activeIndex];
  return <div className="cuc-home__gathering"><span>Next gathering</span><div className="cuc-home__gathering-track" aria-live="polite" aria-atomic="true">{event ? <strong key={event.id}>{event.title} · {formatHomepageEventDate(event.date, event.time)}</strong> : <strong>{loading ? "Loading published events…" : failed ? "Events are temporarily unavailable" : "No upcoming public events yet"}</strong>}</div><Link to="/events">View programmes <ArrowRight size={15} /></Link></div>;
}

function HomepageCalendar({ events, loading, failed }: { events: EventSummary[]; loading: boolean; failed: boolean }) {
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState(() => localDateKey(new Date()));
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const firstWeekday = new Date(year, monthIndex, 1).getDay();
  const monthEvents = events.filter((event) => event.date.startsWith(`${year}-${String(monthIndex + 1).padStart(2, "0")}-`));
  const dayEvents = events.filter((event) => event.date === selectedDate);
  const moveMonth = (offset: number) => {
    const nextMonth = new Date(year, monthIndex + offset, 1);
    setMonth(nextMonth);
    setSelectedDate(`${nextMonth.getFullYear()}-${String(nextMonth.getMonth() + 1).padStart(2, "0")}-01`);
  };
  return <div className="cuc-home__calendar"><div className="cuc-home__calendar-main"><header><button type="button" aria-label="Previous month" onClick={() => moveMonth(-1)}><ChevronLeft /></button><h3>{new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(month)}</h3><button type="button" aria-label="Next month" onClick={() => moveMonth(1)}><ChevronRight /></button></header><div className="cuc-home__calendar-grid" role="group" aria-label="Upcoming programmes calendar">{["S", "M", "T", "W", "T", "F", "S"].map((day, index) => <span className="cuc-home__calendar-weekday" key={`${day}-${index}`} aria-hidden="true">{day}</span>)}{Array.from({ length: firstWeekday }, (_, index) => <span key={`blank-${index}`} />)}{Array.from({ length: daysInMonth }, (_, index) => { const day = index + 1; const date = `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`; const hasEvent = monthEvents.some((event) => event.date === date); return <button type="button" key={date} className={date === selectedDate ? "is-selected" : undefined} aria-label={`${new Intl.DateTimeFormat("en", { month: "long" }).format(month)} ${day}${hasEvent ? ", event scheduled" : ""}`} aria-pressed={date === selectedDate} onClick={() => setSelectedDate(date)}>{day}{hasEvent && <i aria-hidden="true" />}</button>; })}</div></div><aside className="cuc-home__calendar-agenda"><p>{new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" }).format(new Date(`${selectedDate}T12:00:00`))}</p>{loading ? <span>Loading published events…</span> : failed ? <span>Events are temporarily unavailable.</span> : dayEvents.length ? dayEvents.map((event) => <Link key={event.id} to={`/events/${encodeURIComponent(event.id)}`}><strong>{event.title}</strong><span>{formatHomepageEventDate(event.date, event.time).split(" · ")[1]}</span><small>{event.venue}</small></Link>) : <span>No events scheduled for this date.</span>}<Link className="cuc-home__calendar-all" to="/events">Browse all events <ArrowRight size={15} /></Link></aside></div>;
}

function AttendanceProcessIllustration() {
  return <div className="cuc-home__attendance-visual" role="img" aria-label="Attendance process: see the chapel service, scan the usher's rotating QR code, and receive confirmation"><img src="/chapel-hero.jpg" alt="" /><div className="cuc-home__attendance-card"><span>CHAPELFLOW · ATTENDANCE</span><strong>Scan the live code</strong><div className="cuc-home__attendance-qr" aria-hidden="true">▦</div><small><CheckCircle2 size={16} /> Confirmed in seconds</small></div></div>;
}

const HOME_HERO_SLIDES = [
  { src: "/chapel-home-01.jpg", alt: "A student leading worship at Chrisland University Chapel" },
  { src: "/chapel-home-02.jpg", alt: "Students celebrating together at a chapel gathering" },
  { src: "/chapel-home-03.jpg", alt: "A student sharing a joyful moment at chapel" },
  { src: "/chapel-home-04.jpg", alt: "Students worshipping together" },
  { src: "/chapel-home-05.jpg", alt: "Two students smiling during a chapel event" },
  { src: "/chapel-home-06.jpg", alt: "A student at a chapel programme" },
  { src: "/chapel-home-07.jpg", alt: "Chapel members gathered for a programme" },
  { src: "/chapel-home-08.jpg", alt: "Students sharing a moment at a chapel event" },
  { src: "/chapel-home-09.jpg", alt: "A student enjoying a chapel gathering" },
  { src: "/chapel-home-10.jpg", alt: "Students hosting a Christmas chapel event" },
  { src: "/chapel-home-11.jpg", alt: "Students celebrating Christmas at chapel" },
  { src: "/chapel-home-12.jpg", alt: "A student playing keyboard during chapel worship" },
  { src: "/chapel-home-13.jpg", alt: "A student worshipping during a chapel service" },
  { src: "/chapel-home-14.jpg", alt: "A chapel member following the service" },
  { src: "/chapel-home-15.jpg", alt: "Students gathered together at chapel" },
  { src: "/chapel-home-16.jpg", alt: "A chapel member taking notes during a service" },
  { src: "/chapel-home-17.jpg", alt: "A student worshipping with eyes closed" },
  { src: "/chapel-home-18.jpg", alt: "A student praying during chapel" },
  { src: "/chapel-home-19.jpg", alt: "A student raising a hand during worship" },
  { src: "/chapel-home-20.jpg", alt: "A student leading a song at chapel" },
  { src: "/chapel-home-21.jpg", alt: "Students leading music during chapel" },
  { src: "/chapel-home-22.jpg", alt: "A student worshipping during a chapel gathering" },
  { src: "/chapel-home-23.jpg", alt: "Students worshipping together at Chrisland University Chapel" },
];

function HomeHeroSlideshow() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [outgoingIndex, setOutgoingIndex] = useState<number | null>(null);
  const [readyIndex, setReadyIndex] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const activeIndexRef = useRef(0);
  const pendingIndexRef = useRef<number | null>(null);
  const requestRef = useRef(0);
  const preloadRef = useRef<HTMLImageElement | null>(null);
  const fadeTimerRef = useRef<number | null>(null);
  const shouldPause = paused || hovered || focused || reducedMotion;

  const goTo = useCallback((index: number) => {
    const target = (index + HOME_HERO_SLIDES.length) % HOME_HERO_SLIDES.length;
    if (target === activeIndexRef.current || target === pendingIndexRef.current) return;
    const slide = HOME_HERO_SLIDES[target];
    if (!slide) return;
    const request = ++requestRef.current;
    pendingIndexRef.current = target;
    if (preloadRef.current) preloadRef.current.onload = preloadRef.current.onerror = null;
    const image = new Image();
    preloadRef.current = image;
    let settled = false;
    const show = () => {
      if (settled || request !== requestRef.current) return;
      settled = true;
      image.onload = image.onerror = null;
      pendingIndexRef.current = null;
      const previous = activeIndexRef.current;
      activeIndexRef.current = target;
      setOutgoingIndex(previous);
      setReadyIndex(target);
      setActiveIndex(target);
      if (fadeTimerRef.current !== null) window.clearTimeout(fadeTimerRef.current);
      fadeTimerRef.current = window.setTimeout(() => setOutgoingIndex(null), 900);
    };
    image.onload = show;
    image.onerror = () => { if (request === requestRef.current) pendingIndexRef.current = null; };
    image.src = slide.src;
    if (image.complete && image.naturalWidth > 0) show();
  }, []);

  useEffect(() => () => {
    requestRef.current += 1;
    if (preloadRef.current) preloadRef.current.onload = preloadRef.current.onerror = null;
    if (fadeTimerRef.current !== null) window.clearTimeout(fadeTimerRef.current);
  }, []);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    if (shouldPause) return;
    const timer = window.setInterval(() => goTo(activeIndexRef.current + 1), 5600);
    return () => window.clearInterval(timer);
  }, [goTo, shouldPause]);

  const visibleSlideIndices = Array.from(
    { length: Math.min(5, HOME_HERO_SLIDES.length) },
    (_, position) => (activeIndex + position - 2 + HOME_HERO_SLIDES.length) % HOME_HERO_SLIDES.length,
  );
  const shownIndices = outgoingIndex !== null && outgoingIndex !== activeIndex
    ? [outgoingIndex, activeIndex]
    : [activeIndex];

  return (
    <figure className="cuc-home__hero-image" role="region" aria-roledescription="carousel" aria-label="Chrisland University Chapel photos" onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)} onFocus={() => setFocused(true)} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocused(false); }}>
      {shownIndices.map((index) => {
        const slide = HOME_HERO_SLIDES[index];
        if (!slide) return null;
        const active = index === activeIndex;
        return <img key={slide.src} className={`cuc-home__hero-slide${active ? ` is-active${readyIndex === index ? " is-ready" : ""}` : " is-outgoing"}`} src={slide.src} alt={active ? slide.alt : ""} aria-hidden={!active} fetchPriority={active ? "high" : "auto"} decoding="async" onLoad={() => { if (activeIndexRef.current === index) setReadyIndex(index); }} onError={() => { if (active) goTo(index + 1); }} />;
      })}
      <div className="cuc-home__hero-controls" role="group" aria-label="Slideshow controls">
        <button type="button" aria-label="Previous image" onClick={() => goTo(activeIndex - 1)}><ChevronLeft size={16} /></button>
        <button type="button" aria-label={paused ? "Play slideshow" : "Pause slideshow"} aria-pressed={paused} onClick={() => setPaused((value) => !value)}>{paused ? <Play size={15} /> : <Pause size={15} />}</button>
        <button type="button" aria-label="Next image" onClick={() => goTo(activeIndex + 1)}><ChevronRight size={16} /></button>
      </div>
      <div className="cuc-home__hero-pagination" role="group" aria-label="Choose an image">
        {visibleSlideIndices.map((index) => { const slide = HOME_HERO_SLIDES[index]; return slide ? <button key={slide.src} type="button" aria-label={`Show image ${index + 1}`} aria-current={index === activeIndex ? "true" : undefined} onClick={() => goTo(index)} /> : null; })}
      </div>
      <figcaption>Chrisland University Chapel</figcaption>
    </figure>
  );
}

export function AboutPage() {
  const { user, loading } = useAuth();
  const leaders = [
    { title: "University Chaplain", name: "Rev. Canon Juwon Onasanya", image: "/chaplain.jpg", alt: "University Chaplain portrait" },
    { title: "Student Chaplain", name: "Akintobi Olubori Favour", image: "/student-chaplain.jpg", alt: "Student Chaplain portrait" },
    { title: "Vice-Chancellor", name: "Professor Oyedunni Sola Arulogun", image: "https://chrislanduniversity.edu.ng/images/pages/prof-oyedunni-sola-arulogun.jpg", alt: "Professor Oyedunni Sola Arulogun" },
    { title: "Registrar", name: "Mr. Samuel Babatola Omotosho, FCIA", image: "https://chrislanduniversity.edu.ng/images/pages/mr-samuel-omotosho.jpg", alt: "Mr. Samuel Babatola Omotosho" },
  ];
  return (
    <div className="cuc-about">
      <section className="cuc-about__hero cuc-about__hero--immersive">
        <div className="cuc-about__hero-copy">
          <p className="cuc-home__eyebrow">The heart of chapel life</p>
          <h1>Faith takes shape when we <em>worship, belong, and serve.</em></h1>
          <p>Chrisland University Chapel is a spiritual home for students and staff: a place to grow in faith, find community, and contribute with purpose.</p>
          {!loading && <Link className="button button--primary" to={user ? "/app" : "/register"}>{user ? "Open your dashboard" : "Find your place at chapel"} <ArrowRight size={18} /></Link>}
        </div>
        <div className="cuc-about__note-stage" aria-label="Chapel mission, vision, and objectives">
          <article className="cuc-about__note cuc-about__note--mission"><span>Our mission</span><p>To cultivate Christ-centred lives through worship, discipleship, fellowship, and service.</p><small>Why we gather</small></article>
          <article className="cuc-about__note cuc-about__note--vision"><span>Our vision</span><p>A university community known for mature faith, excellent character, compassionate leadership, and meaningful contribution.</p><small>Where we are going</small></article>
          <article className="cuc-about__note cuc-about__note--objectives"><span>Our objectives</span><ul><li>Grow through Scripture, prayer, and worship.</li><li>Build fellowship and care across campus.</li><li>Equip students to lead and serve.</li></ul><small>How we live it</small></article>
          <span className="cuc-about__note-pin" aria-hidden="true">CUC / FAITH IN ACTION</span>
        </div>
      </section>
      <section className="cuc-about__story">
        <div>
          <p className="cuc-home__eyebrow">Why we are here</p>
          <h2>Faith has a place in the whole of university life.</h2>
        </div>
        <div className="cuc-about__story-copy">
          <p>We gather to worship, learn from Scripture, pray for one another, and grow into people of faith, character, and service. Chapel is not an extra activity—it is a community that walks with you through university life.</p>
          <p>Whether you are arriving as a new student, looking for a fellowship, serving in a unit, or simply seeking a place to belong, there is room for you here.</p>
        </div>
      </section>
      <section className="cuc-about__rhythm">
        <header><p className="cuc-home__eyebrow">Our shared rhythm</p><h2>Worship. Belonging. Formation. Service.</h2></header>
        <div>
          {[
            ["Worship together", "Gather in chapel services that centre worship, Scripture, prayer, and a Christ-shaped life."],
            ["Belong deeply", "Find your people through fellowships, units, care, and campus friendships that last beyond a semester."],
            ["Grow in faith", "Build steady habits through messages, discipleship, thoughtful conversations, and pastoral support."],
            ["Serve with purpose", "Use your gifts in chapel ministry and practical service to the university and wider community."],
          ].map(([title, detail]) => <article key={title}><span>CUC</span><h3>{title}</h3><p>{detail}</p></article>)}
        </div>
      </section>
      <section className="cuc-about__leadership">
        <header><p className="cuc-home__eyebrow">People who guide our community</p><h2>Chapel and university leadership.</h2><p>Pastoral care, student ministry, and university leadership working together for campus life.</p></header>
        <div className="cuc-about__leaders">{leaders.map((leader) => <article className="cuc-about__leader" key={leader.title}><div className="cuc-about__leader-photo">{leader.image ? <img src={leader.image} alt={leader.alt} loading="lazy" /> : <span aria-hidden="true">SC</span>}</div><div className="cuc-about__leader-copy"><span>{leader.title}</span><h3>{leader.name}</h3></div></article>)}</div>
      </section>
      <section className="cuc-about__invitation">
        <div><p className="cuc-home__eyebrow">Your place is here</p><h2>Come as you are. Grow as you go.</h2><p>Join ChapelFlow to follow programmes, find a community, receive chapel updates, and take part in the life of CUC.</p></div>
        <div>{!loading && <Link className="button button--primary" to={user ? "/app" : "/register"}>{user ? "Open your dashboard" : "Create account"} <ArrowRight size={18} /></Link>}<Link className="button button--ghost" to="/contact">Contact the chapel</Link></div>
      </section>
    </div>
  );
}

export function CookieConsent() {
  const [choice, setChoice] = useState<CookieConsentChoice | null>(readCookieConsent);
  const [reviewing, setReviewing] = useState(false);
  useEffect(() => {
    const open = () => setReviewing(true);
    window.addEventListener(COOKIE_CONSENT_EVENT, open);
    return () => window.removeEventListener(COOKIE_CONSENT_EVENT, open);
  }, []);
  const save = (nextChoice: CookieConsentChoice) => {
    writeCookieConsent(nextChoice);
    setChoice(nextChoice);
    setReviewing(false);
  };
  if (import.meta.env.VITE_E2E_TEST === "true" && !reviewing) return null;
  if (choice && !reviewing) return null;
  return (
    <section className="cookie-consent" role="region" aria-labelledby="cookie-consent-title" tabIndex={-1}>
      <Cookie aria-hidden="true" />
      <div>
        <h2 id="cookie-consent-title">Your privacy, your choice</h2>
        <p>ChapelFlow uses essential cookies for secure sign-in and reliable service. Optional analytics and marketing cookies are not active in this version.</p>
        <Link to="/cookies">Read the Cookie Policy</Link>
      </div>
      <div className="cookie-consent__actions">
        <button className="button button--secondary" type="button" onClick={() => save("necessary")}>Use necessary only</button>
        <button className="button button--primary" type="button" onClick={() => save("all")}>Accept cookies</button>
      </div>
    </section>
  );
}

function UpcomingSection() {
  const cards = [
    {
      date: "06",
      month: "SEP",
      title: "Freshers Welcome Service",
      time: "9:00 AM",
      place: "University Chapel",
      type: "Campus worship",
    },
    {
      date: "12",
      month: "SEP",
      title: "Workers Leadership Retreat",
      time: "10:00 AM",
      place: "Senate Chamber",
      type: "Leadership",
    },
    {
      date: "18",
      month: "SEP",
      title: "Evening of Worship",
      time: "5:00 PM",
      place: "University Auditorium",
      type: "Worship",
    },
  ];
  return (
    <section className="events-section section">
      <div className="section-heading section-heading--row">
        <div>
          <p className="eyebrow">Coming up</p>
          <h2>Gather with us.</h2>
        </div>
        <Link to="/events">
          <SectionLink>View all events</SectionLink>
        </Link>
      </div>
      <div className="public-event-grid">
        {cards.map((card) => (
          <article key={card.title}>
            <div className="date-block">
              <strong>{card.date}</strong>
              <span>{card.month}</span>
            </div>
            <span className="event-type">{card.type}</span>
            <h3>{card.title}</h3>
            <p>
              <Clock3 size={16} /> {card.time}
            </p>
            <p>
              <MapPin size={16} /> {card.place}
            </p>
            <Link to="/events">
              Event details <ArrowRight size={16} />
            </Link>
          </article>
        ))}
      </div>
    </section>
  );
}

const pageCopy: Record<
  string,
  { eyebrow: string; title: string; description: string; content: ReactNode }
> = {
  about: {
    eyebrow: "Our chapel",
    title: "Forming people of faith and purpose.",
    description:
      "The spiritual centre of Chrisland University, serving students, staff, and the wider community.",
    content: (
      <>
        <h2>Rooted in truth, open to all</h2>
        <p>
          Chrisland University Chapel exists to nurture spiritual maturity,
          build a caring campus community, and equip people to lead with
          integrity. Our gatherings combine biblical teaching, thoughtful
          worship, prayer, and practical service.
        </p>
        <div className="value-grid">
          <article>
            <CheckCircle2 />
            <h3>Our mission</h3>
            <p>
              To cultivate Christ-centred lives through worship, discipleship,
              fellowship, and service.
            </p>
          </article>
          <article>
            <Users />
            <h3>Our community</h3>
            <p>
              A welcoming, interdenominational family for every student and
              member of staff.
            </p>
          </article>
          <article>
            <CalendarDays />
            <h3>Our rhythm</h3>
            <p>
              Weekly worship, small groups, pastoral care, and opportunities to
              serve across campus.
            </p>
          </article>
        </div>
      </>
    ),
  },
  events: {
    eyebrow: "Chapel calendar",
    title: "Events that bring us together.",
    description:
      "Worship gatherings, student programmes, leadership development, and community service.",
    content: <UpcomingSection />,
  },
  sermons: {
    eyebrow: "Messages",
    title: "Truth for the life in front of you.",
    description:
      "Browse recent messages, series, and resources from our chapel community.",
    content: (
      <div className="media-grid">
        {[
          "Steady faith in changing seasons",
          "Wisdom for the road ahead",
          "The courage to serve",
        ].map((title, index) => (
          <article key={title}>
            <div className="media-art">
              <Play />
            </div>
            <span>Sunday message · {23 - index * 7} August 2026</span>
            <h3>{title}</h3>
            <p>Pastor Daniel Eze</p>
            <Link
              className="button button--ghost"
              to={`/sermons/${title.toLowerCase().replaceAll(" ", "-")}`}
            >
              <Play size={16} /> Play message
            </Link>
          </article>
        ))}
      </div>
    ),
  },
  livestream: {
    eyebrow: "Live chapel",
    title: "Worship with us from wherever you are.",
    description:
      "Our Sunday worship service streams at 9:00 AM West Africa Time.",
    content: (
      <div className="video-placeholder">
        <Radio />
        <h2>The stream will begin before the next service.</h2>
        <p>Sunday, 30 August · 9:00 AM</p>
        <Link className="button button--primary" to="/events/sunday-worship">
          View service details
        </Link>
      </div>
    ),
  },
  giving: {
    eyebrow: "Generosity",
    title: "Give with purpose and confidence.",
    description: "Support chapel ministry, student care, and community impact.",
    content: (
      <div className="giving-layout">
        <div>
          <h2>Your giving makes ministry possible.</h2>
          <p>
            Choose a giving category and complete your gift through the
            university’s configured payment provider. You will receive a secure
            receipt after confirmation.
          </p>
        </div>
        <form className="public-form">
          <label>
            Giving category
            <select>
              <option>Offering</option>
              <option>Chapel project</option>
              <option>Student support</option>
            </select>
          </label>
          <label>
            Amount
            <input type="number" inputMode="decimal" placeholder="0.00" />
          </label>
          <Button type="button" disabled>
            Payment unavailable in preview
          </Button>
          <small>
            Payment processing requires backend provider configuration.
          </small>
        </form>
      </div>
    ),
  },
};

export function PublicContentPage({ page }: { page: keyof typeof pageCopy }) {
  if (!isDemoMode) return <LivePublicPage slug={page} />;
  const copy = pageCopy[page]!;
  return (
    <div className="content-page">
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
      />
      <div className="prose-section section">{copy.content}</div>
    </div>
  );
}

type LegalPolicy = "privacy" | "terms" | "cookies" | "community" | "accessibility";

const legalPolicies: Record<LegalPolicy, { title: string; description: string; sections: Array<{ id: string; title: string; paragraphs: string[] }> }> = {
  privacy: {
    title: "Privacy Policy",
    description: "How Chrisland University Chapel handles information within ChapelFlow.",
    sections: [
      { id: "overview", title: "Our commitment", paragraphs: ["ChapelFlow supports worship, membership, attendance, events, communication, giving, and administration for Chrisland University Chapel. Information is used only for legitimate chapel and university purposes, with access limited by role and responsibility."] },
      { id: "information", title: "Information we use", paragraphs: ["Depending on your use of ChapelFlow, this may include account identity, student or membership details, attendance, programme registrations, giving records, prayer or counselling requests, testimony submissions, communication preferences, and technical security information.", "These records help operate chapel services, maintain accurate administration, communicate relevant updates, protect accounts, and meet institutional obligations."] },
      { id: "sharing", title: "Access, security, and retention", paragraphs: ["Authorized chapel and university personnel may access information needed for their responsibilities. Private prayer and counselling requests are limited to the requester and authorized pastoral staff. Prayer details are shared with the chapel community only after requester consent and pastoral approval; the requester's identity is not included in the community view. Avoid including names or other identifying details in prayer text you consent to share.", "Service providers may process limited information under appropriate contractual and security arrangements. Personal data is not sold. Information is retained according to approved institutional requirements, then securely deleted or anonymized where appropriate."] },
      { id: "choices", title: "Your choices", paragraphs: ["You may review and update permitted profile information, manage communication preferences, and submit a data export or account deletion request. ChapelFlow records a 30-day action deadline for deletion requests. Requests are reviewed under institutional policy; some records may need to be retained for legitimate administrative, financial, safeguarding, security, or legal reasons."] },
    ],
  },
  terms: {
    title: "Terms of Use",
    description: "The rules that keep ChapelFlow reliable, respectful, and secure for the CUC community.",
    sections: [
      { id: "overview", title: "Using ChapelFlow", paragraphs: ["ChapelFlow is provided to connect the Chrisland University Chapel community. Use the service lawfully, provide accurate information, and keep your sign-in details private. You are responsible for activity carried out through your account."] },
      { id: "conduct", title: "Respect for the community", paragraphs: ["Do not use ChapelFlow to harass, impersonate, exploit, deceive, distribute harmful content, or interfere with another person’s access. Respect the privacy and rights of members, staff, guests, and chapel leaders."] },
      { id: "access", title: "Access and availability", paragraphs: ["ChapelFlow access is role-based. The chapel may update, suspend, or restrict access where security, safeguarding, institutional policy, or reliable operation requires it. Features and schedules may change as chapel services develop."] },
      { id: "contact", title: "Questions and reports", paragraphs: ["If you identify a security issue, an account concern, or harmful conduct, contact the chapel office promptly. Do not share another person’s information while making a report."] },
    ],
  },
  cookies: {
    title: "Cookie Policy",
    description: "How ChapelFlow uses essential browser storage and records your cookie choice.",
    sections: [
      { id: "overview", title: "Essential cookies and storage", paragraphs: ["ChapelFlow uses secure HttpOnly cookies for signed-in sessions and a CSRF cookie to protect form submissions. These are required for the service to work and are not used for advertising.", "The browser may also keep ChapelFlow display preferences, the cookie-choice record, the brand-introduction flag, and a temporary attendance queue in session storage so kiosk check-ins can sync when a connection returns. Service-worker caches may store previously downloaded ChapelFlow pages and local brand images so they remain available offline after an online visit."] },
      { id: "optional", title: "Optional technologies", paragraphs: ["ChapelFlow does not currently run optional analytics, advertising, or marketing cookies. Choosing “Accept cookies” records that preference so a future optional technology can respect it; it does not enable analytics today."] },
      { id: "choice", title: "Your choice", paragraphs: ["You can choose necessary cookies only or accept cookies, and you can reopen that choice from Cookie settings in the footer. If browser storage is blocked, the choice is kept for the current page session only. Removing ChapelFlow site data from the browser will show the request again and may require you to sign in again."] },
      { id: "contact", title: "More information", paragraphs: ["Read the Privacy Policy for details about information handling. Contact the chapel office if you need help with your ChapelFlow account or privacy preferences."] },
    ],
  },
  community: {
    title: "Community Standards",
    description: "The shared expectations for conversations, media, events, and care within ChapelFlow.",
    sections: [
      { id: "overview", title: "Build one another up", paragraphs: ["Use ChapelFlow in ways that reflect dignity, honesty, care, and respect. Disagreement is welcome when it is constructive; personal attacks, discrimination, threats, and deliberate disruption are not."] },
      { id: "media", title: "Media and shared moments", paragraphs: ["Share only media you are authorized to publish. Do not post personal information, private prayer requests, or images of others without the appropriate permission. Chapel leaders may review or remove content to protect the community."] },
      { id: "care", title: "Care and safeguarding", paragraphs: ["ChapelFlow is not an emergency service. If someone may be in immediate danger, contact the appropriate emergency or university support service. Sensitive care concerns should be directed to an authorized chaplain or the chapel office."] },
      { id: "report", title: "Report a concern", paragraphs: ["Report harmful content, suspected impersonation, or safeguarding concerns promptly through the chapel office. Reports are handled as confidentially as the situation and institutional process allow."] },
    ],
  },
  accessibility: {
    title: "Accessibility Statement",
    description: "Our commitment to making ChapelFlow usable for the widest possible CUC community.",
    sections: [
      { id: "overview", title: "Our approach", paragraphs: ["ChapelFlow is designed to support keyboard navigation, readable text, responsive layouts, visible focus states, reduced motion preferences, and clear form feedback. We continue to improve the experience as the service grows."] },
      { id: "support", title: "Where you may need support", paragraphs: ["Some uploaded media or third-party services may not yet meet the same standard. Chapel teams should provide alternative information where a feature creates a barrier, especially for essential programme, attendance, or care information."] },
      { id: "feedback", title: "Tell us about a barrier", paragraphs: ["If a ChapelFlow page is difficult to use with your device or assistive technology, contact the chapel office with the page, what you were trying to do, and the support you need. We will use that feedback to prioritize a practical alternative or improvement."] },
    ],
  },
};

export function LegalPage({ type }: { type: LegalPolicy }) {
  const policy = legalPolicies[type];
  return (
    <div className="legal-page">
      <PageHeader eyebrow="ChapelFlow policies" title={policy.title} description={policy.description} />
      <div className="legal-layout">
        <aside><strong>On this page</strong>{policy.sections.map((section) => <a href={`#${section.id}`} key={section.id}>{section.title}</a>)}</aside>
        <article className="legal-copy">
          <div className="legal-notice">These public policies must be approved by Chrisland University before production publication. Add the official policy contact, retention schedule, and effective date during that approval.</div>
          {policy.sections.map((section) => <section id={section.id} key={section.id}><h2>{section.title}</h2>{section.paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}</section>)}
          <p className="legal-copy__review"><strong>Publication status:</strong> Pending institutional approval · <strong>Last product review:</strong> 19 September 2026</p>
        </article>
      </div>
    </div>
  );
}

const infoPages: Record<
  string,
  {
    eyebrow: string;
    title: string;
    description: string;
    sections: [string, string][];
  }
> = {
  mission: {
    eyebrow: "Mission and vision",
    title: "Grounded in faith. Prepared for service.",
    description:
      "Our shared direction for spiritual life at Chrisland University.",
    sections: [
      [
        "Our mission",
        "To cultivate Christ-centred lives through worship, discipleship, fellowship, and service.",
      ],
      [
        "Our vision",
        "A university community known for mature faith, excellent character, compassionate leadership, and meaningful contribution.",
      ],
    ],
  },
  leadership: {
    eyebrow: "Chapel leadership",
    title: "Serving with wisdom and care.",
    description:
      "Meet the pastoral and ministry leaders supporting our chapel community.",
    sections: [
      [
        "Pastoral leadership",
        "Our pastoral team provides biblical teaching, spiritual formation, and confidential care within appropriate safeguarding boundaries.",
      ],
      [
        "Student and worker leaders",
        "Trained students and staff help coordinate worship, hospitality, media, prayer, and community programmes.",
      ],
    ],
  },
  services: {
    eyebrow: "Service times",
    title: "Make room for worship in your week.",
    description: "Regular gatherings at the Abeokuta campus chapel.",
    sections: [
      ["Sunday Worship Service", "Sundays at 9:00 AM · University Chapel"],
      ["Midweek Chapel Gathering", "Wednesdays at 5:00 PM · University Chapel"],
      ["Prayer Gathering", "Fridays at 6:00 PM · Prayer Room"],
    ],
  },
  gallery: {
    eyebrow: "Media gallery",
    title: "Life in our chapel community.",
    description: "Stories of worship, service, fellowship, and growth.",
    sections: [
      [
        "Worship and formation",
        "Selected images and videos will appear here when published through the ChapelFlow media library.",
      ],
      [
        "Community service",
        "Authorized media is published with appropriate consent and accessibility information.",
      ],
    ],
  },
  news: {
    eyebrow: "News and updates",
    title: "What is happening around the chapel.",
    description: "Announcements, reflections, and stories from our community.",
    sections: [
      [
        "Freshers Welcome Service registration opens",
        "New and returning students are invited to begin the academic session in worship and fellowship.",
      ],
      [
        "Applications open for service teams",
        "Explore opportunities in worship, welcome, media, prayer, protocol, and care.",
      ],
    ],
  },
  contact: {
    eyebrow: "Contact the chapel",
    title: "We are here to listen and help.",
    description:
      "Reach the chapel office or plan a visit to the Abeokuta campus.",
    sections: [
      [
        "Visit us",
        "Chrisland University Chapel, Abeokuta Campus, Ogun State. Official office hours and contact channels must be configured before publication.",
      ],
      [
        "Pastoral support",
        "Confidential support requests should use the institution’s approved pastoral care channel when configured.",
      ],
    ],
  },
  faq: {
    eyebrow: "Frequently asked questions",
    title: "Helpful answers before you arrive.",
    description: "What to expect from ChapelFlow and the chapel community.",
    sections: [
      [
        "Who can attend?",
        "Students, staff, and welcomed members of the university community may attend public chapel services.",
      ],
      [
        "How do I join a service team?",
        "Create a ChapelFlow account, complete your profile, and register your interest. A team leader will follow up.",
      ],
      [
        "How is attendance information used?",
        "Attendance supports chapel administration and considerate engagement. Access is limited by role; see the Privacy Policy for details.",
      ],
    ],
  },
};

export function PublicInfoPage({ page }: { page: keyof typeof infoPages }) {
  if (!isDemoMode) return <LivePublicPage slug={page} />;
  const content = infoPages[page]!;
  return (
    <div className="content-page">
      <PageHeader
        eyebrow={content.eyebrow}
        title={content.title}
        description={content.description}
      />
      <div className="info-sections section">
        {content.sections.map(([heading, copy]) => (
          <section key={heading}>
            <h2>{heading}</h2>
            <p>{copy}</p>
          </section>
        ))}
      </div>
    </div>
  );
}

export function PublicDetailPage({
  kind,
}: {
  kind: "event" | "sermon" | "article" | "gallery";
}) {
  if (!isDemoMode)
    return (
      <LivePublicDetailPage
        kind={
          kind === "event"
            ? "events"
            : kind === "sermon"
              ? "sermons"
              : kind === "gallery"
                ? "gallery"
                : "news"
        }
      />
    );
  const detail =
    kind === "event"
      ? {
          eyebrow: "Upcoming event",
          title: "Freshers Welcome Service",
          description: "Sunday, 6 September 2026 · 9:00 AM · University Chapel",
        }
      : kind === "sermon"
        ? {
            eyebrow: "Sunday message",
            title: "Steady faith in changing seasons",
            description: "Pastor Daniel Eze · 23 August 2026 · Hebrews 10:23",
          }
        : kind === "gallery"
          ? {
              eyebrow: "Chapel gallery",
              title: "Life in our chapel community",
              description: "Published photographs from chapel events and services.",
            }
          : {
            eyebrow: "Chapel news",
            title: "Beginning the session with purpose",
            description: "Published 25 August 2026 · Chapel Office",
          };
  return (
    <div className="content-page">
      <PageHeader {...detail} />
      <div className="detail-feature section">
        <div>
          <h2>
            {kind === "event"
              ? "A shared beginning"
              : kind === "gallery"
                ? "A shared moment"
                : "A message for our community"}
          </h2>
          <p>
            Join the Chrisland University Chapel community for a thoughtful time
            of worship, formation, and fellowship. Confirmed information from
            the ChapelFlow content service will appear here.
          </p>
          <Link
            className="button button--primary"
            to={
              kind === "event"
                ? "/register"
                : kind === "sermon"
                  ? "/sermons"
                  : kind === "gallery"
                    ? "/gallery"
                    : "/news"
            }
          >
            {kind === "event"
              ? "Register for this event"
              : kind === "sermon"
                ? "Play message"
                : kind === "gallery"
                  ? "Back to gallery"
                  : "Share article"}
          </Link>
        </div>
        <aside>
          <h3>Details</h3>
          <p>
            <Clock3 /> 9:00 AM West Africa Time
          </p>
          <p>
            <MapPin /> Chrisland University Chapel
          </p>
        </aside>
      </div>
    </div>
  );
}
