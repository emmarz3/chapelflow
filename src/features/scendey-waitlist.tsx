import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ExternalLink,
  Mail,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Modal } from "../components/ui";
import { scendeyWaitlistService } from "./scendey-waitlist-service";
import "./scendey-waitlist.css";

const SCENDEY_PUBLIC_URL = "https://scendey-waitlist-production.up.railway.app/";

type Audience = "student" | "staff" | "business" | "other";

const audienceOptions: { value: Audience; label: string; detail: string }[] = [
  { value: "student", label: "Student", detail: "Discover what's next" },
  { value: "staff", label: "Staff / Professional", detail: "Stay in the loop" },
  { value: "business", label: "Business / Brand", detail: "Grow your brand" },
  { value: "other", label: "Other", detail: "I'm curious about Scendey" },
];

const brandCategories = [
  "Fashion",
  "Beauty & cosmetics",
  "Wellness",
  "Technology",
  "Home & living",
  "Accessories",
  "Personal care",
  "Other",
];

function WaitlistForm() {
  const [audience, setAudience] = useState<Audience>("student");
  const [submission, setSubmission] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [feedback, setFeedback] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submission === "submitting") return;
    const values = new FormData(event.currentTarget);
    setSubmission("submitting");
    setFeedback("");
    try {
      const result = await scendeyWaitlistService.join({
        name: String(values.get("name") || "").trim(),
        email: String(values.get("email") || "").trim(),
        audienceCategory: audience,
        marketingConsent: values.get("updatesConsent") === "on",
        ...(audience === "business" ? {
          brandName: String(values.get("brandName") || "").trim(),
          category: String(values.get("category") || ""),
        } : {}),
        website: String(values.get("website") || ""),
      });
      setFeedback(result.data?.message || "Your request has been processed. Check your email if Scendey sends a verification message.");
      setSubmission("success");
    } catch (error) {
      const errorStatus = error && typeof error === "object" && "status" in error ? Number(error.status) : 0;
      setFeedback(errorStatus === 429
        ? "There have been too many attempts. Please wait a little and try again."
        : error instanceof Error && error.message
          ? error.message
          : "We could not connect to Scendey right now. Your details were not submitted. Please try again.");
      setSubmission("error");
    }
  }

  if (submission === "success") {
    return (
      <div className="scendey-waitlist-preview" role="status" aria-live="polite">
        <span className="scendey-waitlist-preview__icon"><CheckCircle2 aria-hidden="true" /></span>
        <p className="scendey-waitlist-kicker">Request processed</p>
        <h3>Thank you for your interest.</h3>
        <p>{feedback}</p>
        <a className="button button--secondary" href={SCENDEY_PUBLIC_URL} target="_blank" rel="noopener noreferrer">Visit Scendey <ExternalLink size={14} aria-hidden="true" /></a>
      </div>
    );
  }

  return (
    <form className="scendey-waitlist-form" onSubmit={handleSubmit}>
      <fieldset className="scendey-waitlist-audience">
        <legend>Which best describes you?</legend>
        <div className="scendey-waitlist-audience__grid">
          {audienceOptions.map((option) => (
            <label className={\`scendey-waitlist-audience__option \${audience === option.value ? "is-selected" : ""}\`} key={option.value}>
              <input type="radio" name="audience" value={option.value} checked={audience === option.value} onChange={() => setAudience(option.value)} />
              <span><strong>{option.label}</strong><small>{option.detail}</small></span>
              <span className="scendey-waitlist-audience__radio" aria-hidden="true" />
            </label>
          ))}
        </div>
      </fieldset>
      <div className="scendey-waitlist-fields">
        <label className="scendey-waitlist-field"><span>Full name <b aria-hidden="true">*</b></span><input name="name" type="text" autoComplete="name" placeholder="Enter your full name" minLength={2} maxLength={100} required /></label>
        <label className="scendey-waitlist-field"><span>Email address <b aria-hidden="true">*</b></span><input name="email" type="email" autoComplete="email" placeholder="you@example.com" maxLength={254} required /></label>
        {audience === "business" && <>
          <label className="scendey-waitlist-field"><span>Business / brand name <b aria-hidden="true">*</b></span><input name="brandName" type="text" autoComplete="organization" placeholder="Your brand name" minLength={2} maxLength={100} required /></label>
          <label className="scendey-waitlist-field"><span>Business category <b aria-hidden="true">*</b></span><select name="category" defaultValue="" required><option value="" disabled>Select a category</option>{brandCategories.map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
        </>}
      </div>
      <label className="scendey-waitlist-honeypot" aria-hidden="true">Website<input name="website" type="text" tabIndex={-1} autoComplete="off" /></label>
      <label className="scendey-waitlist-consent"><input type="checkbox" name="updatesConsent" /><span>Send me Scendey progress and launch updates. This is optional, and I can unsubscribe at any time.</span></label>
      <p className="scendey-waitlist-privacy">Your email is used to process your waitlist request and send necessary verification messages. Product updates are optional.</p>
      {submission === "error" && <p className="scendey-waitlist-error" role="alert">{feedback}</p>}
      <button className="button button--primary scendey-waitlist-submit" type="submit" disabled={submission === "submitting"}>{submission === "submitting" ? "Sending securely…" : "Join the waitlist"} {submission !== "submitting" && <ArrowRight size={17} aria-hidden="true" />}</button>
      <p className="scendey-waitlist-form__note">No payment required. Joining does not guarantee early access.</p>
    </form>
  );
}

export function ScendeyWaitlistModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Join the Scendey waitlist"
      description="Get considered for early updates as Scendey takes shape."
      className="scendey-waitlist-modal"
    >
      <WaitlistForm />
      <a className="scendey-waitlist-external" href={SCENDEY_PUBLIC_URL} target="_blank" rel="noopener noreferrer">
        Explore Scendey first <ExternalLink size={14} aria-hidden="true" />
      </a>
    </Modal>
  );
}

export function ScendeyWaitlistPromo({
  variant = "homepage",
}: {
  variant?: "homepage" | "dashboard";
}) {
  const [modalOpen, setModalOpen] = useState(false);

  if (variant === "dashboard") {
    return (
      <>
        <section className="scendey-waitlist-dashboard" aria-labelledby="scendey-dashboard-title">
          <div className="scendey-waitlist-dashboard__mark" aria-hidden="true"><Sparkles /></div>
          <div className="scendey-waitlist-dashboard__copy">
            <p className="scendey-waitlist-kicker">Something new is coming</p>
            <h2 id="scendey-dashboard-title">Discover Scendey.</h2>
            <p>Be among the first to hear about a new way for brands to grow and people to discover them.</p>
          </div>
          <div className="scendey-waitlist-dashboard__actions">
            <button className="button button--primary" type="button" onClick={() => setModalOpen(true)}>
              Join waitlist <ArrowRight size={16} aria-hidden="true" />
            </button>
            <a href={SCENDEY_PUBLIC_URL} target="_blank" rel="noopener noreferrer">
              Explore Scendey <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </div>
        </section>
        <ScendeyWaitlistModal open={modalOpen} onClose={() => setModalOpen(false)} />
      </>
    );
  }

  return (
    <>
      <section className="scendey-waitlist-home" aria-labelledby="scendey-home-title">
        <div className="scendey-waitlist-home__visual" aria-hidden="true">
          <div className="scendey-waitlist-home__orbit scendey-waitlist-home__orbit--one" />
          <div className="scendey-waitlist-home__orbit scendey-waitlist-home__orbit--two" />
          <span className="scendey-waitlist-home__wordmark">SCENDEY</span>
          <span className="scendey-waitlist-home__visual-caption">A new chapter for brands & discovery</span>
        </div>
        <div className="scendey-waitlist-home__content">
          <p className="scendey-waitlist-kicker"><Sparkles size={14} aria-hidden="true" /> Introducing Scendey</p>
          <h2 id="scendey-home-title">Discover what’s next.</h2>
          <p>Be among the first to experience what’s coming. Join the Scendey waitlist and get notified as we get closer to launch.</p>
          <div className="scendey-waitlist-home__actions">
            <button className="button button--primary" type="button" onClick={() => setModalOpen(true)}>
              Join the waitlist <ArrowRight size={17} aria-hidden="true" />
            </button>
            <a href={SCENDEY_PUBLIC_URL} target="_blank" rel="noopener noreferrer">
              Explore Scendey <ArrowUpRight size={15} aria-hidden="true" />
            </a>
          </div>
          <div className="scendey-waitlist-home__footnote"><Mail size={14} aria-hidden="true" /> Free to join · No payment details required</div>
        </div>
      </section>
      <ScendeyWaitlistModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}

export function ScendeyWaitlistPage() {
  return (
    <div className="scendey-waitlist-page">
      <section className="scendey-waitlist-page__intro">
        <div>
          <p className="scendey-waitlist-kicker"><Sparkles size={14} aria-hidden="true" /> Early access updates</p>
          <h1>Discover <em>Scendey.</em></h1>
          <p>Be among the first to experience what’s coming. Join the waitlist and get notified as Scendey moves closer to launch.</p>
          <a className="scendey-waitlist-page__external" href={SCENDEY_PUBLIC_URL} target="_blank" rel="noopener noreferrer">
            Explore the Scendey website <ArrowUpRight size={15} aria-hidden="true" />
          </a>
        </div>
        <div className="scendey-waitlist-page__aside" aria-hidden="true">
          <span className="scendey-waitlist-page__aside-label">Your next discovery</span>
          <strong>SCENDEY</strong>
          <span className="scendey-waitlist-page__aside-line" />
          <span className="scendey-waitlist-page__aside-caption">Brands in motion. Possibilities ahead.</span>
        </div>
      </section>

      <section className="scendey-waitlist-page__body" aria-labelledby="scendey-form-title">
        <div className="scendey-waitlist-page__form-heading">
          <p className="scendey-waitlist-kicker">The first step</p>
          <h2 id="scendey-form-title">Join the waitlist.</h2>
          <p>Tell us a little about yourself. It’s free to join.</p>
        </div>
        <WaitlistForm />
      </section>

      <div className="scendey-waitlist-page__reassurance">
        <span><CheckCircle2 size={16} aria-hidden="true" /> No payment required</span>
        <span><Mail size={16} aria-hidden="true" /> Email verification before confirmation</span>
        <span><ExternalLink size={15} aria-hidden="true" /> Explore Scendey whenever you like</span>
      </div>
      <p className="scendey-waitlist-page__back"><Link to="/">Return to ChapelFlow</Link></p>
    </div>
  );
}
