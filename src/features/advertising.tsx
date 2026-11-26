import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import "./advertising.css";
import "./dashboard-ads.css";

type PaymentRecord = { reference: string; amount_ngn: number; paid_at: string };
type DecisionRecord = { action: string; note: string; actor_email: string; created_at: string };
type Campaign = {
  id: string; brand_name: string; description: string; ad_category: string; image_url: string;
  destination_url: string; contact_email: string; plan: "CAMPUS" | "FEATURED";
  program?: string | null; program_name?: string; program_code?: string;
  applicant_community: "STUDENT" | "STAFF" | "GUEST"; founding_offer_awarded: boolean;
  status: string; review_note: string; reviewed_at: string | null; paid_until: string | null;
  cancel_at_period_end: boolean; scendey_opt_in: boolean; impressions: number; clicks: number;
  monthly_price_ngn: number; payment_history: PaymentRecord[];
  owner_email?: string; reviewed_by_email?: string; decision_history?: DecisionRecord[]; placements?: string[];
};
type SubscriptionProgram = {
  id: string; code: string; name: string; description: string;
  monthly_price_ngn: number; audience: "STUDENT" | "OUTSIDER"; base_plan: "CAMPUS" | "FEATURED";
  placements: ("home" | "events" | "dashboard")[]; is_active: boolean; sort_order: number;
  campaign_count: number;
};
type Plans = {
  plans: {
    id: string; code: string; name: string; description: string; price_ngn: number;
    audience: "STUDENT" | "OUTSIDER"; base_plan: "CAMPUS" | "FEATURED"; placements: ("home" | "events" | "dashboard")[];
  }[];
  consent_text: string; checkout_available: boolean; checkout_reason?: string;
  founding_offer?: { enabled: boolean; remaining: number; limit: number; first_month_price_ngn: number; renewal_note: string };
};
type AdvertisingSettings = {
  emergency_paused: boolean; emergency_pause_reason: string; founding_offer_enabled: boolean;
  founding_offer_awarded: number; founding_offer_remaining: number; policy_approved: boolean; checkout_configured: boolean;
};

type ActiveAd = Pick<Campaign, "id" | "brand_name" | "description" | "image_url"> & { ad_category?: string; plan?: Campaign["plan"] };

async function openAdvertiser(id: string) {
  const result = await api.post<{ url: string }>(`/ads/${id}/click/`);
  const target = new URL(result.url);
  if (target.protocol !== "https:") throw new Error("The advertiser's link is unavailable.");
  window.location.assign(target.href);
}

function localDate() {
  const date = new Date();
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
}

export function DashboardAdPopup({ userId }: { userId: string }) {
  const key = `chapelflow-dashboard-ad:${userId}`;
  const [eligible, setEligible] = useState(() => {
    try { return localStorage.getItem(key) !== localDate(); } catch { return true; }
  });
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");
  const ad = useQuery({
    queryKey: ["dashboard-sponsored-ad", userId],
    queryFn: () => api.get<{ ad: ActiveAd | null }>("/ads/dashboard-placement/"),
    enabled: eligible,
    staleTime: 5 * 60_000,
    retry: false,
  });
  useEffect(() => {
    if (!eligible || !ad.data?.ad) return;
    const timer = window.setTimeout(() => {
      try { localStorage.setItem(key, localDate()); } catch { /* Storage can be unavailable. */ }
      setVisible(true);
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [ad.data, eligible, key]);
  useEffect(() => {
    if (!visible) return;
    const dismissOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setVisible(false); setEligible(false); }
    };
    document.addEventListener("keydown", dismissOnEscape);
    return () => document.removeEventListener("keydown", dismissOnEscape);
  }, [visible]);
  if (!visible || !ad.data?.ad) return null;
  const current = ad.data.ad;
  return <aside className="dashboard-ad-popup" aria-label="Sponsored advertisement">
    <div className="dashboard-ad-popup__top"><span>Sponsored</span><button type="button" aria-label="Close sponsored advertisement" onClick={() => { setVisible(false); setEligible(false); }}>×</button></div>
    <img src={current.image_url} alt="" loading="lazy" />
    <div className="dashboard-ad-popup__body"><strong>{current.brand_name}</strong><p>{current.description}</p>
      {error && <small role="alert">{error}</small>}
      <div className="dashboard-ad-popup__actions"><button type="button" onClick={() => void openAdvertiser(current.id).catch(() => setError("Could not open this brand. Please try again."))}>View brand</button><Link to="/app/ads">Browse ads</Link></div>
    </div>
  </aside>;
}

export function AdsDirectoryPage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const ads = useQuery({
    queryKey: ["ads-directory", query, page],
    queryFn: () => api.get<{ items: ActiveAd[]; total: number; page_size: number }>(`/ads/directory/?page=${page}&q=${encodeURIComponent(query)}`),
  });
  return <div className="ads-page ads-directory">
    <header><p className="eyebrow">ChapelFlow brands</p><h1>Discover our advertisers</h1><p>Explore approved brands with active subscriptions. Every listing is marked as sponsored.</p></header>
    <form className="ads-directory__search" role="search" onSubmit={(event) => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
      <label htmlFor="ads-directory-search">Search brands or categories</label><div><input id="ads-directory-search" value={search} onChange={(event) => setSearch(event.target.value)} maxLength={80} placeholder="Search brands" /><button type="submit">Search</button></div>
    </form>
    {ads.isPending && <p role="status">Loading brands…</p>}
    {ads.isError && <p role="alert">Could not load brands. <button type="button" onClick={() => void ads.refetch()}>Try again</button></p>}
    {error && <p role="alert">{error}</p>}
    {ads.isSuccess && ads.data.items.length === 0 && <p>No active ads match your search.</p>}
    <div className="ads-directory__grid">{ads.data?.items.map((item) => <article key={item.id}>
      <img src={item.image_url} alt="" loading="lazy" /><div><small>Sponsored{item.ad_category ? ` · ${item.ad_category}` : ""}</small><h2>{item.brand_name}</h2><p>{item.description}</p>
        <button type="button" onClick={() => void openAdvertiser(item.id).catch(() => setError("Could not open this brand. Please try again."))}>View brand ↗</button></div>
    </article>)}</div>
    {ads.data && ads.data.total > ads.data.page_size && <nav className="ads-directory__pagination" aria-label="Ad directory pages">
      <button type="button" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span>Page {page} of {Math.ceil(ads.data.total / ads.data.page_size)}</span><button type="button" disabled={page * ads.data.page_size >= ads.data.total} onClick={() => setPage((value) => value + 1)}>Next</button>
    </nav>}
  </div>;
}

export function SponsoredCard({ placement }: { placement: "home" | "events" }) {
  const [ad, setAd] = useState<Pick<Campaign, "id" | "brand_name" | "description" | "image_url" | "plan"> | null>(null);
  useEffect(() => {
    let active = true;
    api.get<{ ad: typeof ad }>(`/ads/placement/${placement}/`).then((result) => {
      if (active) setAd(result.ad);
    }).catch(() => {});
    return () => { active = false; };
  }, [placement]);
  if (!ad) return null;
  const currentAd = ad;
  async function open() {
    try {
      const result = await api.post<{ url: string }>(`/ads/${currentAd.id}/click/`);
      const target = new URL(result.url);
      if (target.protocol === "https:") window.location.assign(target.href);
    } catch {
      // Keep the public ChapelFlow page usable if click tracking is temporarily unavailable.
    }
  }
  return <section className="sponsored-card" aria-label="Sponsored advertisement">
    <span className="sponsored-card__label">Sponsored · {ad.plan === "FEATURED" ? "Featured brand" : "Campus brand"}</span>
    <div className="sponsored-card__body">
      <img src={ad.image_url} alt="" loading="lazy" />
      <div><h2>{ad.brand_name}</h2><p>{ad.description}</p><button type="button" onClick={() => void open()}>Explore brand ↗</button></div>
    </div>
  </section>;
}

export function AdvertisePage() {
  const [params] = useSearchParams();
  const plans = useQuery({ queryKey: ["ads-plans"], queryFn: () => api.get<Plans>("/ads/plans/") });
  const campaigns = useQuery({ queryKey: ["ads-mine"], queryFn: () => api.get<Campaign[]>("/ads/mine/") });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const id = params.get("campaign");
    if (!id) return;
    api.post(`/ads/${id}/verify/`).then(() => {
      setMessage("Payment checked. Your campaign status has been updated.");
      void campaigns.refetch();
    }).catch((error: Error) => setMessage(error.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("campaign")]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = event.currentTarget;
    const fields = new FormData(form);
    try {
      const file = fields.get("image");
      if (!(file instanceof File) || !file.size || file.size > 2 * 1024 * 1024) {
        throw new Error("Choose a PNG, JPEG or WebP image under 2 MB.");
      }
      const upload = new FormData();
      upload.append("file", file);
      const image = await api.postForm<{ image_url: string }>("/ads/image/", upload);
      await api.post("/ads/mine/", {
        brand_name: fields.get("brand_name"),
        ad_category: fields.get("ad_category"),
        description: fields.get("description"),
        destination_url: fields.get("destination_url"),
        contact_email: fields.get("contact_email"),
        image_url: image.image_url,
        program: fields.get("program"),
        scendey_opt_in: fields.get("scendey_opt_in") === "on",
      });
      form.reset();
      setMessage("Application submitted. Your advertisement is awaiting review.");
      void campaigns.refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not submit your ad.");
    } finally {
      setBusy(false);
    }
  }

  async function action(path: string, redirect = false) {
    setBusy(true);
    setMessage("");
    try {
      if (redirect) {
        const response = await api.post<{ checkout_url: string }>(path);
        const target = new URL(response.checkout_url);
        if (target.protocol !== "https:") throw new Error("Invalid payment link.");
        window.location.assign(target.href);
      } else {
        await api.post(path);
        setMessage("Renewal has been cancelled. Your current paid period remains active until its end date.");
        void campaigns.refetch();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  return <div className="ads-page">
    <header className="ads-hero">
      <p className="eyebrow">CHAPELFLOW ADVERTISING</p>
      <h1>Bring your brand to the ChapelFlow community.</h1>
      <p className="ads-hero__intro">Reach students, staff and guests through approved placements across ChapelFlow. Choose a subscription program, submit your advertisement and pay securely after approval.</p>
      <ol className="ads-steps" aria-label="How advertising works">
        <li><span>01</span><div><strong>Choose a program</strong><small>Compare rates and placements.</small></div></li>
        <li><span>02</span><div><strong>Submit your ad</strong><small>Share your brand and creative.</small></div></li>
        <li><span>03</span><div><strong>Get approval</strong><small>We will review your submission.</small></div></li>
        <li><span>04</span><div><strong>Pay and publish</strong><small>Complete checkout to go live.</small></div></li>
      </ol>
    </header>
    {message && <p role="status" className="ads-notice">{message}</p>}
    <section className="ads-section ads-section--plans">
      <div className="ads-section__heading">
        <div>
          <p className="eyebrow">Find the right fit</p>
          <h2>Subscription programs</h2>
          <p>Compare the available audiences, monthly rates and placements before you apply.</p>
        </div>
      </div>
      {plans.isPending && <p role="status" className="ads-empty-state">Loading subscription programs…</p>}
      {plans.isError && <p role="alert" className="ads-empty-state">We could not load subscription programs. Please refresh the page and try again.</p>}
      <div className="ads-plans">
        {plans.data?.plans.map((plan) => <article className="ads-plan-card" key={plan.id}>
          <div className="ads-plan-card__top">
            <span className="ads-plan-card__audience">{plan.audience === "STUDENT" ? "Chrisland University students" : "Staff and guests"}</span>
            <span className="ads-plan-card__billing">Monthly plan</span>
          </div>
          <h3>{plan.name}</h3>
          <p className="ads-plan-card__description">{plan.description || (plan.base_plan === "FEATURED" ? "A higher-visibility rotation across selected ChapelFlow placements." : "A rotating sponsored placement across selected ChapelFlow pages.")}</p>
          <p className="ads-plan-card__price"><strong>₦{plan.price_ngn.toLocaleString()}</strong><span>/ month</span></p>
          <div className="ads-plan-card__placements">
            <span>Included placements</span>
            <div>{plan.placements.map((placement) => <span key={placement}>{placement === "home" ? "Homepage" : placement === "dashboard" ? "Dashboard" : "Events"}</span>)}</div>
          </div>
        </article>)}
      </div>
      {plans.data?.plans.length === 0 && <p className="ads-empty-state">There are no subscription programs available right now.</p>}
      {plans.data?.founding_offer?.enabled && <p className="ads-founding-note">
        Student launch offer: the first 10 approved student advertisers pay ₦{plans.data.founding_offer.first_month_price_ngn.toLocaleString()} for the first month. The selected program’s regular monthly rate applies from month two. {plans.data.founding_offer.remaining} places remain.
      </p>}
      <p className="ads-section__footnote">Advertising results are not guaranteed. Your selected rate, any first-month offer and the renewal price will be shown before checkout.</p>
      {!plans.data?.checkout_available && <p className="ads-policy-note">{plans.data?.checkout_reason || "Online checkout is not available yet. You can still submit an application; payment will open when checkout is enabled."}</p>}
    </section>
    <section className="ads-section ads-section--apply">
      <div className="ads-section__heading">
        <div>
          <p className="eyebrow">Start here</p>
          <h2>Apply to advertise</h2>
          <p>Tell us about your brand and choose the subscription program that suits your audience.</p>
        </div>
      </div>
      <div className="ads-policy-note" role="note">
        <strong>Before you apply</strong>
        <p>Select the rate that matches your affiliation. Chrisland University students use the student rate; staff and guests use the outside rate. Submitting an application is free. Your advertisement will be reviewed, and Paystack checkout will become available after approval.</p>
      </div>
      <form onSubmit={(event) => void submit(event)} className="ads-form">
        <div className="ads-form__group">
          <div className="ads-form__group-heading">
            <h3>Brand details</h3>
            <p>Provide accurate information so people can recognise and contact your brand.</p>
          </div>
          <label>Brand or business name<input name="brand_name" maxLength={120} placeholder="Enter your brand name" autoComplete="organization" required /></label>
          <label>Ad category<input name="ad_category" maxLength={80} placeholder="For example: food, fashion or services" required /></label>
          <label>Contact email<input name="contact_email" type="email" maxLength={254} placeholder="name@example.com" autoComplete="email" required /></label>
          <label className="ads-form__field--full">Brand description<textarea name="description" maxLength={300} placeholder="Briefly describe what you offer (up to 300 characters)." required /></label>
          <label className="ads-form__field--full">Website or social media link <span className="ads-field-hint">Use a secure link beginning with https://.</span><input name="destination_url" type="url" pattern="https://.*" placeholder="https://example.com" required /></label>
          <label className="ads-form__field--full">Advertisement image <span className="ads-field-hint">PNG, JPEG or WebP. Maximum file size: 2 MB.</span><input name="image" type="file" accept="image/png,image/jpeg,image/webp" required /></label>
        </div>
        <div className="ads-form__group">
          <div className="ads-form__group-heading">
            <h3>Subscription and updates</h3>
            <p>Choose the program you want to apply for. You will review the price again before payment.</p>
          </div>
          <label className="ads-form__field--full">Subscription program<select name="program" required disabled={!plans.data?.plans.length}>
            <option value="">Select a subscription program</option>
            {plans.data?.plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name} · {plan.audience === "STUDENT" ? "Student rate" : "Outside rate"} · ₦{plan.price_ngn.toLocaleString()} per month</option>)}
          </select></label>
          <label className="ads-consent">
            <input type="checkbox" name="scendey_opt_in" />
            <span>{plans.data?.consent_text || "Send me Scendey waitlist updates when Scendey launches."} This is optional and will not affect your ChapelFlow application.</span>
          </label>
        </div>
        <div className="ads-form__submit">
          <p>No payment is collected with this application.</p>
          <button disabled={busy || !plans.data?.plans.length} type="submit">{busy ? "Submitting application…" : "Submit application"}</button>
        </div>
      </form>
    </section>
    <section className="ads-section ads-section--campaigns">
      <div className="ads-section__heading"><div><p className="eyebrow">Your account</p><h2>My advertisements</h2><p>Check each application’s review status, payment details and performance.</p></div></div>
      {campaigns.isError && <p>Could not load your advertisements.</p>}
      {campaigns.isPending && <p>Loading your advertisements…</p>}
      {campaigns.data?.length === 0 && <p>You have not submitted an ad yet.</p>}
      {campaigns.data?.map((ad) => <article className="ads-entry" key={ad.id}>
        <img src={ad.image_url} alt="" />
        <div className="ads-entry__content">
          <h3>{ad.brand_name}</h3>
          <p><strong>{ad.status === "PENDING" ? "Awaiting review" : ad.status.replaceAll("_", " ")}</strong> · {ad.program_name || (ad.plan === "FEATURED" ? "Featured Brand" : "Campus Brand")} · {ad.applicant_community === "STUDENT" ? "Student" : ad.applicant_community === "STAFF" ? "Staff" : "Guest"}</p>
          {ad.status === "PENDING" && <p className="ads-policy-note">Your application is being reviewed. You will be notified when a decision is made. Payment becomes available after approval.</p>}
          {ad.status === "APPROVED" && <p className="ads-founding-note">Your advertisement has been approved. Complete payment to activate it.</p>}
          {ad.status === "REJECTED" && <p className="ads-policy-note">This application was not approved. Review the decision note below.</p>}
          <p>Category: {ad.ad_category}</p>
          {ad.founding_offer_awarded && <p className="ads-founding-note">Launch offer awarded: ₦{(plans.data?.founding_offer?.first_month_price_ngn ?? 2000).toLocaleString()} for the first month, then ₦{ad.monthly_price_ngn.toLocaleString()} per month.</p>}
          {ad.review_note && <p>Review note: {ad.review_note}</p>}
          {ad.paid_until && <p>{ad.cancel_at_period_end ? "Paid through" : "Next renewal date"}: <time dateTime={ad.paid_until}>{new Date(ad.paid_until).toLocaleDateString()}</time></p>}
          {ad.cancel_at_period_end && <p>Renewal cancelled. Your paid period remains active until the date above.</p>}
          <p>{ad.impressions.toLocaleString()} views · {ad.clicks.toLocaleString()} clicks</p>
          {ad.status === "CHANGES" && <form className="ads-change-form" onSubmit={async (event) => {
            event.preventDefault();
            setBusy(true);
            try {
              const form = new FormData(event.currentTarget);
              const patch: Record<string, unknown> = {
                brand_name: form.get("brand_name"),
                ad_category: form.get("ad_category"),
                description: form.get("description"),
                destination_url: form.get("destination_url"),
                contact_email: form.get("contact_email"),
              };
              const file = form.get("image");
              if (file instanceof File && file.size) {
                if (file.size > 2 * 1024 * 1024) throw new Error("Image must be under 2 MB.");
                const upload = new FormData();
                upload.append("file", file);
                const image = await api.postForm<{ image_url: string }>("/ads/image/", upload);
                patch.image_url = image.image_url;
              }
              await api.patch(`/ads/mine/${ad.id}/`, patch);
              setMessage("Your changes have been resubmitted for review.");
              void campaigns.refetch();
            } catch (error) {
              setMessage(error instanceof Error ? error.message : "Could not submit changes.");
            } finally {
              setBusy(false);
            }
          }}>
            <h4>Requested changes</h4>
            <label>Brand name<input name="brand_name" defaultValue={ad.brand_name} maxLength={120} required /></label>
            <label>Proposed category<input name="ad_category" defaultValue={ad.ad_category} maxLength={80} required /></label>
            <label>Description<textarea name="description" defaultValue={ad.description} maxLength={300} required /></label>
            <label>Destination URL<input name="destination_url" type="url" defaultValue={ad.destination_url} required /></label>
            <label>Contact email<input name="contact_email" type="email" defaultValue={ad.contact_email} required /></label>
            <label>Replace image (optional)<input name="image" type="file" accept="image/png,image/jpeg,image/webp" /></label>
            <button disabled={busy}>Resubmit for review</button>
          </form>}
          {ad.status === "APPROVED" && <div className="ads-checkout">
            <p>Monthly renewal: ₦{ad.monthly_price_ngn.toLocaleString()} per month.</p>
            {ad.founding_offer_awarded && <p>First month: ₦{(plans.data?.founding_offer?.first_month_price_ngn ?? 2000).toLocaleString()}. From month two: ₦{ad.monthly_price_ngn.toLocaleString()} per month.</p>}
            <button disabled={busy || !plans.data?.checkout_available} onClick={() => void action(`/ads/${ad.id}/checkout/`, true)}>
              {plans.data?.checkout_available ? "Continue to Paystack" : "Checkout unavailable"}
            </button>
          </div>}
          {["ACTIVE", "PAUSED"].includes(ad.status) && !ad.cancel_at_period_end && <button disabled={busy} onClick={() => void action(`/ads/${ad.id}/cancel/`)}>Cancel renewal</button>}
          {ad.payment_history?.length > 0 && <details className="ads-payment-history">
            <summary>Payment history ({ad.payment_history.length})</summary>
            <ul>{ad.payment_history.map((payment) => <li key={payment.reference}>₦{payment.amount_ngn.toLocaleString()} · {new Date(payment.paid_at).toLocaleDateString()} · <code>{payment.reference}</code></li>)}</ul>
          </details>}
        </div>
      </article>)}
    </section>
  </div>;
}

export function AdvertisingAdminPage() {
  const campaigns = useQuery({ queryKey: ["ads-admin"], queryFn: () => api.get<Campaign[]>("/ads/admin/") });
  const settings = useQuery({ queryKey: ["ads-admin-settings"], queryFn: () => api.get<AdvertisingSettings>("/ads/admin/settings/") });
  const programs = useQuery({ queryKey: ["ads-admin-programs"], queryFn: () => api.get<SubscriptionProgram[]>("/ads/admin/programs/") });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [pauseReason, setPauseReason] = useState("");
  const [programFormOpen, setProgramFormOpen] = useState(false);
  const [editingProgram, setEditingProgram] = useState<SubscriptionProgram | null>(null);

  async function review(id: string, action: string, note: string) {
    setBusy(true);
    setMessage("");
    try {
      await api.post(`/ads/admin/${id}/review/`, { action, note });
      setMessage("Decision saved and audit record created.");
      await campaigns.refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Decision failed.");
    } finally { setBusy(false); }
  }

  async function saveProgram(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    const placements = form.getAll("placements").map(String);
    if (!placements.length) {
      setMessage("Choose at least one placement for this program.");
      setBusy(false);
      return;
    }
    const payload = {
      name: String(form.get("name") || "").trim(),
      code: String(form.get("code") || "").trim(),
      description: String(form.get("description") || "").trim(),
      monthly_price_ngn: Number(form.get("monthly_price_ngn")),
      audience: String(form.get("audience") || "STUDENT"),
      base_plan: String(form.get("base_plan") || "CAMPUS"),
      placements,
      sort_order: Number(form.get("sort_order") || 0),
      is_active: form.get("is_active") === "on",
    };
    try {
      if (editingProgram) {
        await api.patch(`/ads/admin/programs/${editingProgram.id}/`, payload);
        setMessage("Subscription program updated. Existing subscriptions keep their agreed billing price.");
      } else {
        await api.post("/ads/admin/programs/", payload);
        setMessage("Subscription program created and made available to advertisers.");
      }
      setProgramFormOpen(false);
      setEditingProgram(null);
      await programs.refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save subscription program.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleProgram(program: SubscriptionProgram) {
    setBusy(true);
    setMessage("");
    try {
      await api.patch(`/ads/admin/programs/${program.id}/`, { is_active: !program.is_active });
      setMessage(program.is_active ? "Program deactivated. Current subscribers are not affected." : "Program activated for new applications.");
      await programs.refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update subscription program.");
    } finally {
      setBusy(false);
    }
  }

  async function control(action: string) {
    setBusy(true);
    setMessage("");
    try {
      await api.post("/ads/admin/settings/", { action, note: pauseReason });
      setMessage("Advertising controls updated.");
      setPauseReason("");
      await settings.refetch();
      await campaigns.refetch();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update advertising controls.");
    } finally { setBusy(false); }
  }

  return <div className="ads-page">
    <header><p className="eyebrow">Super Admin</p><h1>Advertising review</h1><p>Review creative, proposed category and destination before approval. Payment does not override rejection, pause or revocation.</p></header>
    {message && <p role="status" className="ads-notice">{message}</p>}
    <section className="ads-admin-controls">
      <h2>Subscription programs</h2>
      <p>Create and manage the offers advertisers can choose from. Price changes apply to new applications; existing campaigns retain their agreed monthly price and Paystack renewal plan.</p>
      <div className="ads-admin-control-actions">
        <button type="button" disabled={busy} onClick={() => { setEditingProgram(null); setProgramFormOpen((open) => !open); }}>
          {programFormOpen && !editingProgram ? "Close program form" : "Add subscription program"}
        </button>
      </div>
      {programFormOpen && (
        <form className="ads-admin-review" onSubmit={(event) => void saveProgram(event)}>
          <h3>{editingProgram ? "Edit subscription program" : "New subscription program"}</h3>
          <label>Program name<input name="name" defaultValue={editingProgram?.name || ""} maxLength={120} required /></label>
          <label>Program code<input name="code" defaultValue={editingProgram?.code || ""} pattern="[a-z0-9]+(?:-[a-z0-9]+)*" readOnly={Boolean(editingProgram)} required /></label>
          <label>Description<textarea name="description" defaultValue={editingProgram?.description || ""} maxLength={500} /></label>
          <label>Audience<select name="audience" defaultValue={editingProgram?.audience ?? "STUDENT"}><option value="STUDENT">School students</option><option value="OUTSIDER">Outside advertisers and staff</option></select></label>
          <label>Monthly price (NGN)<input name="monthly_price_ngn" type="number" min={100} max={1000000} step={1} defaultValue={editingProgram?.monthly_price_ngn ?? 3500} required /></label>
          <label>Placement profile<select name="base_plan" defaultValue={editingProgram?.base_plan || "CAMPUS"}>
            <option value="CAMPUS">Campus Brand rotation</option>
            <option value="FEATURED">Featured Brand rotation</option>
          </select></label>
          <fieldset>
            <legend>Where can this advertisement appear?</legend>
            <label><input type="checkbox" name="placements" value="home" defaultChecked={editingProgram ? editingProgram.placements.includes("home") : true} /> Homepage</label>
            <label><input type="checkbox" name="placements" value="events" defaultChecked={editingProgram ? editingProgram.placements.includes("events") : false} /> Public events page</label>
            <label><input type="checkbox" name="placements" value="dashboard" defaultChecked={editingProgram ? editingProgram.placements.includes("dashboard") : true} /> Dashboard popup (overview only)</label>
          </fieldset>
          <label>Display order<input name="sort_order" type="number" min={0} max={999} defaultValue={editingProgram?.sort_order ?? 10} /></label>
          <label><input type="checkbox" name="is_active" defaultChecked={editingProgram?.is_active ?? true} /> Available to new advertisers</label>
          <div className="ads-admin-control-actions">
            <button type="submit" disabled={busy}>{busy ? "Saving…" : editingProgram ? "Save program changes" : "Create program"}</button>
            <button type="button" className="button-secondary" disabled={busy} onClick={() => { setEditingProgram(null); setProgramFormOpen(false); }}>Cancel</button>
          </div>
        </form>
      )}
      {programs.isError && <p role="alert">Could not load subscription programs.</p>}
      <div className="ads-program-table">
        {(programs.data || []).map((program) => <article key={program.id}>
          <div>
            <strong>{program.name}</strong>
            <p>₦{program.monthly_price_ngn.toLocaleString()} / month · {program.audience === "STUDENT" ? "School students" : "Outside advertisers"} · {program.placements.map((placement) => placement === "home" ? "Homepage" : placement === "dashboard" ? "Dashboard popup" : "Events").join(" · ")}</p>
            <small>{program.campaign_count} application(s) · {program.is_active ? "Available" : "Inactive"}</small>
            {program.description && <p>{program.description}</p>}
          </div>
          <div className="ads-admin-control-actions">
            <button type="button" className="button-secondary" disabled={busy} onClick={() => { setEditingProgram(program); setProgramFormOpen(true); }}>Edit</button>
            <button type="button" disabled={busy} onClick={() => void toggleProgram(program)}>
              {program.is_active ? "Deactivate" : "Activate"}
            </button>
          </div>
        </article>)}
        {programs.data?.length === 0 && <p>No subscription programs are configured.</p>}
      </div>
    </section>
    <section className="ads-admin-controls">
      <h2>Advertising controls</h2>
      <p>Policy approval: {settings.data?.policy_approved ? "Approved in server configuration" : "Not approved — checkout stays closed"}</p>
      <p>Paystack: {settings.data?.checkout_configured ? "Backend key configured" : "Not configured"}</p>
      <p>Founding places awarded: {settings.data?.founding_offer_awarded ?? 0} / 10 · Remaining: {settings.data?.founding_offer_remaining ?? 10}</p>
      <div className="ads-admin-control-actions">
        {settings.data?.emergency_paused
          ? <button type="button" disabled={busy} onClick={() => void control("resume_all")}>Resume all advertising</button>
          : <form onSubmit={(event) => { event.preventDefault(); void control("pause_all"); }}>
              <label>Emergency pause reason<textarea value={pauseReason} onChange={(event) => setPauseReason(event.target.value)} maxLength={2000} required /></label>
              <button type="submit" disabled={busy}>Pause all advertising now</button>
            </form>}
        <button type="button" className="button-secondary" disabled={busy} onClick={() => void control(settings.data?.founding_offer_enabled ? "disable_founding_offer" : "enable_founding_offer")}>
          {settings.data?.founding_offer_enabled ? "Close founding offer to new approvals" : "Enable founding offer"}
        </button>
      </div>
      {settings.data?.emergency_paused && <p className="ads-admin-warning">All ads are hidden. Reason: {settings.data.emergency_pause_reason}</p>}
    </section>
    {campaigns.isError && <p>Could not load campaigns.</p>}
    {campaigns.data?.length === 0 && <p>No applications yet.</p>}
    {campaigns.data?.map((ad) => <article className="ads-entry ads-admin-entry" key={ad.id}>
      <div className="ads-admin-preview-grid">
        <div className="ads-preview ads-preview--desktop"><span>Desktop preview</span><img src={ad.image_url} alt="" /><strong>Sponsored · {ad.brand_name}</strong><p>{ad.description}</p></div>
        <div className="ads-preview ads-preview--mobile"><span>Mobile preview</span><img src={ad.image_url} alt="" /><strong>Sponsored · {ad.brand_name}</strong><p>{ad.description}</p></div>
      </div>
      <div className="ads-entry__content">
        <h2>{ad.brand_name}</h2>
        <p>{ad.owner_email} · {ad.applicant_community} · {ad.program_name || ad.plan} · {ad.status}</p>
        <p>Proposed category: {ad.ad_category} · Placements: {(ad.placements || ["home", "events"]).map((placement) => placement === "home" ? "Homepage" : "Events").join(", ")}</p>
        <p>Destination: <a href={ad.destination_url} target="_blank" rel="noreferrer">Inspect HTTPS destination ↗</a></p>
        <p>{ad.impressions.toLocaleString()} views · {ad.clicks.toLocaleString()} clicks</p>
        {ad.reviewed_by_email && <p>Last reviewed by {ad.reviewed_by_email}{ad.reviewed_at ? ` on ${new Date(ad.reviewed_at).toLocaleString()}` : ""}</p>}
        {ad.paid_until && <p>Paid through {new Date(ad.paid_until).toLocaleDateString()}</p>}
        {ad.payment_history?.length > 0 && <details className="ads-payment-history"><summary>Payment history ({ad.payment_history.length})</summary>
          <ul>{ad.payment_history.map((payment) => <li key={payment.reference}>₦{payment.amount_ngn.toLocaleString()} · {new Date(payment.paid_at).toLocaleString()} · <code>{payment.reference}</code></li>)}</ul>
        </details>}
        {(ad.decision_history ?? []).length > 0 && <details className="ads-payment-history"><summary>Review/audit trail ({(ad.decision_history ?? []).length})</summary>
          <ul>{(ad.decision_history ?? []).map((item, index) => <li key={item.action + index}>{item.action} · {item.actor_email} · {new Date(item.created_at).toLocaleString()}{item.note ? ` — ${item.note}` : ""}</li>)}</ul>
        </details>}
        {["PENDING", "CHANGES", "ACTIVE", "PAUSED", "APPROVED"].includes(ad.status) && <form className="ads-admin-review" onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          void review(ad.id, String(data.get("action")), String(data.get("note") || ""));
        }}>
          <label>Decision<select name="action">
            {["PENDING", "CHANGES"].includes(ad.status) && <><option value="approve">Approve</option><option value="reject">Reject</option><option value="changes">Request changes</option></>}
            {ad.status === "ACTIVE" && <option value="pause">Pause this ad</option>}
            {ad.status === "PAUSED" && <option value="resume">Resume this ad</option>}
            {["APPROVED", "ACTIVE", "PAUSED"].includes(ad.status) && <option value="revoke">Revoke this ad</option>}
          </select></label>
          <label>Reason (required for rejection, changes, pause or revocation)<textarea name="note" maxLength={2000} /></label>
          <button disabled={busy}>Save decision</button>
        </form>}
      </div>
    </article>)}
  </div>;
}
