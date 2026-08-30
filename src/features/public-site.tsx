import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Headphones,
  MapPin,
  Menu,
  Play,
  Radio,
  Users,
  X,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Brand, Button, PageHeader, SectionLink } from "../components/ui";
import { usePublicMotion } from "../components/motion/motion-system";
import { isDemoMode } from "../lib/fixtures";
import { LivePublicDetailPage, LivePublicPage } from "./live-public";

const publicNav = [
  ["About", "/about"],
  ["Events", "/events"],
  ["Sermons", "/sermons"],
  ["Livestream", "/livestream"],
  ["Giving", "/giving"],
] as const;

export function PublicLayout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  usePublicMotion(mainRef, location.pathname);
  return (
    <div className="public-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="public-nav">
        <Link to="/" aria-label="ChapelFlow home">
          <Brand />
        </Link>
        <nav aria-label="Public navigation">
          {publicNav.map(([label, path]) => (
            <NavLink key={path} to={path}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="public-nav__actions">
          <Link className="text-link" to="/login">
            Sign in
          </Link>
          <Link className="button button--primary" to="/register">
            Join the chapel
          </Link>
        </div>
        <button
          className="icon-button public-nav__menu"
          aria-label="Open navigation"
          onClick={() => setOpen(true)}
        >
          <Menu />
        </button>
      </header>
      {open && (
        <div className="mobile-menu">
          <button
            className="icon-button"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <X />
          </button>
          <Brand />
          {publicNav.map(([label, path]) => (
            <Link onClick={() => setOpen(false)} key={path} to={path}>
              {label}
            </Link>
          ))}
          <Link onClick={() => setOpen(false)} to="/login">
            Sign in
          </Link>
          <Link
            onClick={() => setOpen(false)}
            className="button button--primary"
            to="/register"
          >
            Join the chapel
          </Link>
        </div>
      )}
      <main id="main-content" ref={mainRef}>
        <Outlet />
      </main>
      <PublicFooter />
    </div>
  );
}

function PublicFooter() {
  return (
    <footer className="public-footer">
      <div className="public-footer__main">
        <div>
          <Brand inverse />
          <p>
            A connected chapel community for worship, service, and growth at
            Chrisland University, Abeokuta.
          </p>
        </div>
        <div>
          <h3>Visit</h3>
          <p>
            Chrisland University Chapel
            <br />
            Abeokuta Campus, Ogun State
          </p>
          <Link to="/contact">Contact the chapel</Link>
        </div>
        <div>
          <h3>Explore</h3>
          <Link to="/about">About us</Link>
          <Link to="/events">Events</Link>
          <Link to="/sermons">Sermons</Link>
          <Link to="/faq">Frequently asked questions</Link>
        </div>
        <div>
          <h3>Policies</h3>
          <Link to="/privacy">Privacy policy</Link>
          <Link to="/terms">Terms of use</Link>
          <Link to="/accessibility">Accessibility</Link>
        </div>
      </div>
      <div className="public-footer__legal">
        <span>© 2026 Chrisland University Chapel</span>
        <span>Powered by ChapelFlow</span>
      </div>
    </footer>
  );
}

export function HomePage() {
  if (!isDemoMode) return <LivePublicPage slug="home" />;
  return <DemoHomePage />;
}

function DemoHomePage() {
  return (
    <>
      <section className="hero">
        <img
          src="/chapel-hero.png"
          alt="Students approaching a university chapel in the morning"
        />
        <div className="hero__shade" />
        <div className="hero__content">
          <span className="hero__kicker">Faith. Fellowship. Formation.</span>
          <h1>A chapel community for every part of university life.</h1>
          <p>
            Join us as we worship, grow, and serve together at Chrisland
            University Chapel, Abeokuta.
          </p>
          <div>
            <Link className="button button--gold" to="/events">
              Plan your visit <ArrowRight size={18} />
            </Link>
            <Link className="button button--glass" to="/sermons">
              <Play size={17} /> Watch latest sermon
            </Link>
          </div>
        </div>
        <div className="service-ribbon">
          <span className="service-ribbon__icon">
            <Clock3 />
          </span>
          <div>
            <small>Next gathering</small>
            <strong>Sunday Worship Service</strong>
          </div>
          <div>
            <small>Sunday, 30 August</small>
            <strong>9:00 AM · University Chapel</strong>
          </div>
          <Link to="/events">
            View service details <ArrowRight size={17} />
          </Link>
        </div>
      </section>
      <section className="welcome section">
        <div className="section-heading">
          <p className="eyebrow">Welcome home</p>
          <h2>A place to belong, believe, and become.</h2>
        </div>
        <div className="welcome__copy">
          <p>
            Our chapel is at the heart of campus life — a warm, thoughtful
            community where students and staff encounter God, build lasting
            relationships, and discover meaningful ways to serve.
          </p>
          <Link to="/about">
            <SectionLink>Discover our story</SectionLink>
          </Link>
        </div>
      </section>
      <UpcomingSection />
      <section className="sermon-feature section">
        <div className="sermon-feature__visual">
          <img src="/chapel-hero.png" alt="University chapel exterior" />
          <span className="play-button">
            <Play fill="currentColor" />
          </span>
        </div>
        <div>
          <p className="eyebrow">Latest message</p>
          <h2>Steady faith in changing seasons</h2>
          <p className="sermon-meta">Pastor Daniel Eze · 23 August 2026</p>
          <p>
            Faith is not the absence of uncertainty. It is choosing where to
            stand while the world around us changes.
          </p>
          <div className="tag-row">
            <span>Hebrews 10:23</span>
            <span>Faith</span>
            <span>Student life</span>
          </div>
          <Link className="button button--secondary" to="/sermons">
            <Headphones size={18} /> Listen to message
          </Link>
        </div>
      </section>
      <section className="ministries section">
        <div className="section-heading centered">
          <p className="eyebrow">Find your place</p>
          <h2>There is room for your gift here.</h2>
          <p>
            Grow in community and make a difference through one of our service
            teams.
          </p>
        </div>
        <div className="ministry-grid">
          {[
            [
              "Music & worship",
              "Lead our community in thoughtful, excellent worship.",
            ],
            [
              "Welcome & hospitality",
              "Help every person feel seen from the moment they arrive.",
            ],
            [
              "Media & production",
              "Use technology and creativity to carry the message further.",
            ],
            [
              "Prayer & care",
              "Stand with our community through prayer and practical support.",
            ],
          ].map(([name, copy], index) => (
            <article key={name}>
              <span>0{index + 1}</span>
              <h3>{name}</h3>
              <p>{copy}</p>
              <Link to="/register">
                Learn more <ArrowRight size={16} />
              </Link>
            </article>
          ))}
        </div>
      </section>
      <section className="livestream-strip">
        <div>
          <Radio />
          <span>
            <small>Join from anywhere</small>
            <strong>Sunday service streams live at 9:00 AM</strong>
          </span>
        </div>
        <Link className="button button--gold" to="/livestream">
          Watch livestream
        </Link>
      </section>
    </>
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

export function LegalPage({
  type,
}: {
  type: "privacy" | "terms" | "accessibility";
}) {
  const privacy = type === "privacy";
  const title = privacy
    ? "Privacy Policy"
    : type === "terms"
      ? "Terms of Use"
      : "Accessibility Statement";
  return (
    <div className="legal-page">
      <PageHeader
        eyebrow="ChapelFlow policies"
        title={title}
        description={
          privacy
            ? "How Chrisland University Chapel handles information within ChapelFlow."
            : "Important information about using ChapelFlow."
        }
      />
      <div className="legal-layout">
        <aside>
          <strong>On this page</strong>
          <a href="#overview">Overview</a>
          <a href="#information">Information and use</a>
          <a href="#choices">Your choices</a>
          <a href="#contact">Contact</a>
        </aside>
        <article className="legal-copy">
          <div className="legal-notice">
            This policy template is structured for Nigerian institutional use
            and requires final legal review before production publication.
            Official privacy contact details must be configured.
          </div>
          <section id="overview">
            <h2>Overview</h2>
            <p>
              ChapelFlow supports worship, membership, attendance, events,
              communication, giving, and administration for Chrisland University
              Chapel. We handle information only for legitimate chapel and
              institutional purposes, with access limited by role and
              responsibility.
            </p>
          </section>
          <section id="information">
            <h2>
              {privacy
                ? "Information we collect and why"
                : "Using this service"}
            </h2>
            <p>
              {privacy
                ? "Depending on how you use ChapelFlow, records may include account identity, student or membership information, attendance, event registrations, giving transactions, communication preferences, and technical device information. These records help operate chapel services, maintain accurate administration, communicate relevant updates, protect accounts, and meet institutional obligations."
                : "Use ChapelFlow lawfully, protect your account credentials, provide accurate information, and respect the privacy and rights of other members. Access may be restricted when platform security or institutional policy requires it."}
            </p>
            <h3>Access and sharing</h3>
            <p>
              Authorized chapel and university personnel may access only the
              information needed for their responsibilities. Service providers
              may process limited information under appropriate contractual and
              security arrangements. Personal data is not sold.
            </p>
            <h3>Storage, security, and retention</h3>
            <p>
              Administrative, technical, and organizational controls are used to
              protect information. Records are retained according to
              institutional requirements and then securely deleted or anonymized
              where appropriate.
            </p>
          </section>
          <section id="choices">
            <h2>Your choices and rights</h2>
            <p>
              You may request access to or correction of your information,
              manage communication preferences, and submit an account or data
              request where institutional policy permits. Some records may need
              to be retained for legitimate administrative, financial, security,
              or legal reasons.
            </p>
            <h3>Cookies and local storage</h3>
            <p>
              Essential browser storage may be used for security, theme
              preferences, accessibility, and reliable operation. Optional
              analytics or communication technologies should be enabled only
              where configured and appropriately disclosed.
            </p>
          </section>
          <section id="contact">
            <h2>Questions and requests</h2>
            <p>
              Privacy and policy enquiries should be sent to the official
              contact configured by Chrisland University Chapel. No official
              contact has been configured in this frontend.
            </p>
            <p>
              <strong>Effective date:</strong> To be approved ·{" "}
              <strong>Last reviewed:</strong> 27 August 2026
            </p>
          </section>
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
  kind: "event" | "sermon" | "article";
}) {
  if (!isDemoMode)
    return (
      <LivePublicDetailPage
        kind={
          kind === "event" ? "events" : kind === "sermon" ? "sermons" : "news"
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
                  : "/news"
            }
          >
            {kind === "event"
              ? "Register for this event"
              : kind === "sermon"
                ? "Play message"
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
