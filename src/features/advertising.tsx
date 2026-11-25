import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import "./advertising.css";

type Campaign = {
  id: string; brand_name: string; description: string; image_url: string;
  destination_url: string; contact_email: string; plan: "CAMPUS" | "FEATURED";
  status: string; review_note: string; paid_until: string | null;
  cancel_at_period_end: boolean; scendey_opt_in: boolean; impressions: number; clicks: number;
  owner_email?: string;
};
type Plans = { plans: { code: string; name: string; price_ngn: number }[]; consent_text: string; checkout_available: boolean };

export function SponsoredCard({ placement }: { placement: "home" | "events" }) {
  const [ad, setAd] = useState<Pick<Campaign, "id" | "brand_name" | "description" | "image_url"> | null>(null);
  useEffect(() => {
    let active = true;
    api.get<{ ad: typeof ad }>(`/ads/placement/${placement}/`).then((result) => {
      if (active) setAd(result.ad);
    }).catch(() => {});
    return () => { active = false; };
  }, [placement]);
  if (!ad) return null;
  const current = ad;
  async function open() {
    try {
      const result = await api.post<{ url: string }>(`/ads/${current.id}/click/`);
      const url = new URL(result.url);
      if (url.protocol === "https:") window.open(url.href, "_blank", "noopener,noreferrer");
    } catch { /* Leave the page usable if click tracking fails. */ }
  }
  return <section className="sponsored-card" aria-label="Sponsored advertisement">
    <span className="sponsored-card__label">Sponsored · Campus brand</span>
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
  // The callback reference is fixed for this page load.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.get("campaign")]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const form = event.currentTarget;
    const fields = new FormData(form);
    try {
      const file = fields.get("image");
      if (!(file instanceof File) || !file.size || file.size > 2 * 1024 * 1024) throw new Error("Choose an image under 2 MB.");
      const upload = new FormData(); upload.append("file", file);
      const image = await api.postForm<{ image_url: string }>("/ads/image/", upload);
      await api.post("/ads/mine/", {
        brand_name: fields.get("brand_name"), description: fields.get("description"),
        destination_url: fields.get("destination_url"), contact_email: fields.get("contact_email"),
        image_url: image.image_url, plan: fields.get("plan"), scendey_opt_in: fields.get("scendey_opt_in") === "on",
      });
      form.reset(); setMessage("Application submitted for Super Admin review."); void campaigns.refetch();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not submit your ad."); }
    finally { setBusy(false); }
  }
  async function action(path: string, redirect = false) {
    setBusy(true); setMessage("");
    try {
      if (redirect) {
        const response = await api.post<{ checkout_url: string }>(path);
        const target = new URL(response.checkout_url);
        if (target.protocol !== "https:") throw new Error("Invalid payment link.");
        window.location.assign(target.href);
      } else {
        await api.post(path); setMessage("Subscription renewal cancelled. Your paid period remains visible until it ends.");
        void campaigns.refetch();
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Action failed."); }
    finally { setBusy(false); }
  }
  return <div className="ads-page"><header><p className="eyebrow">ChapelFlow advertising</p><h1>Share your brand with the campus.</h1><p>Submit your ad for approval, then subscribe monthly through Paystack. Ads appear only while approved and paid.</p></header>
    {message && <p role="status" className="ads-notice">{message}</p>}
    <section><h2>Monthly plans</h2><div className="ads-plans">{plans.data?.plans.map((plan) => <article key={plan.code}><h3>{plan.name}</h3><strong>₦{plan.price_ngn.toLocaleString()} / month</strong><p>{plan.code === "FEATURED" ? "Higher rotation priority on the homepage and events page." : "Rotating sponsored card on the homepage and events page."}</p></article>)}</div><p>No sales or view count is guaranteed. Your subscription starts after approval and checkout.</p></section>
    <section><h2>Apply for an ad</h2><form onSubmit={(event) => void submit(event)} className="ads-form">
      <label>Brand name<input name="brand_name" maxLength={120} required /></label>
      <label>Contact email<input name="contact_email" type="email" required /></label>
      <label>Brand description<textarea name="description" maxLength={300} required /></label>
      <label>Website or social link (HTTPS)<input name="destination_url" type="url" pattern="https://.*" required /></label>
      <label>Ad image (PNG, JPEG or WebP, max 2 MB)<input name="image" type="file" accept="image/png,image/jpeg,image/webp" required /></label>
      <label>Plan<select name="plan"><option value="CAMPUS">Campus Brand · ₦3,000/month</option><option value="FEATURED">Featured Brand · ₦7,500/month</option></select></label>
      <label className="ads-consent"><input type="checkbox" name="scendey_opt_in" />{plans.data?.consent_text || "Send me Scendey waitlist updates when Scendey launches."}</label>
      <button disabled={busy} type="submit">{busy ? "Submitting…" : "Submit for review"}</button>
    </form></section>
    <section><h2>My advertisements</h2>{campaigns.isError && <p>Could not load your advertisements.</p>}{campaigns.data?.length === 0 && <p>You have not submitted an ad yet.</p>}{campaigns.data?.map((ad) => <article className="ads-entry" key={ad.id}><img src={ad.image_url} alt="" /><div><h3>{ad.brand_name}</h3><p>{ad.status.replaceAll("_", " ")} · {ad.plan}</p>{ad.review_note && <p>Review note: {ad.review_note}</p>}{ad.paid_until && <p>Paid through {new Date(ad.paid_until).toLocaleDateString()}</p>}<p>{ad.impressions} views · {ad.clicks} clicks</p>{ad.status === "CHANGES" && <form onSubmit={async (event) => { event.preventDefault(); setBusy(true); try { const form = new FormData(event.currentTarget); await api.patch(`/ads/mine/${ad.id}/`, { description: form.get("description"), destination_url: form.get("destination_url") }); setMessage("Changes submitted for review."); void campaigns.refetch(); } catch (error) { setMessage(error instanceof Error ? error.message : "Could not submit changes."); } finally { setBusy(false); } }}><label>Revised description<textarea name="description" defaultValue={ad.description} maxLength={300} required /></label><label>Revised destination<input name="destination_url" type="url" defaultValue={ad.destination_url} required /></label><button disabled={busy}>Resubmit for review</button></form>}{ad.status === "APPROVED" && <button disabled={busy || !plans.data?.checkout_available} onClick={() => void action(`/ads/${ad.id}/checkout/`, true)}>{plans.data?.checkout_available ? "Subscribe with Paystack" : "Checkout not configured yet"}</button>}{ad.status === "ACTIVE" && !ad.cancel_at_period_end && <button disabled={busy} onClick={() => void action(`/ads/${ad.id}/cancel/`)}>Cancel renewal</button>}{ad.cancel_at_period_end && <p>Renewal cancelled.</p>}</div></article>)}</section>
  </div>;
}

export function AdvertisingAdminPage() {
  const campaigns = useQuery({ queryKey: ["ads-admin"], queryFn: () => api.get<Campaign[]>("/ads/admin/") });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function review(id: string, action: string, note: string) {
    setBusy(true); setMessage("");
    try { await api.post(`/ads/admin/${id}/review/`, { action, note }); setMessage("Decision saved."); await campaigns.refetch(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Decision failed."); }
    finally { setBusy(false); }
  }
  return <div className="ads-page"><header><p className="eyebrow">Super Admin</p><h1>Advertising review</h1><p>Review the creative and destination before approving. Pause any live campaign immediately.</p></header>{message && <p role="status" className="ads-notice">{message}</p>}{campaigns.isError && <p>Could not load campaigns.</p>}{campaigns.data?.length === 0 && <p>No applications yet.</p>}{campaigns.data?.map((ad) => <article className="ads-entry" key={ad.id}><img src={ad.image_url} alt={`Ad submitted by ${ad.brand_name}`} /><div><h2>{ad.brand_name}</h2><p>{ad.description}</p><p>{ad.owner_email} · {ad.plan} · {ad.status}</p><a href={ad.destination_url} target="_blank" rel="noreferrer">Inspect destination ↗</a><p>{ad.impressions} views · {ad.clicks} clicks</p>{ad.paid_until && <p>Paid through {new Date(ad.paid_until).toLocaleDateString()}</p>}{["PENDING", "CHANGES", "ACTIVE", "PAUSED"].includes(ad.status) && <form onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); void review(ad.id, String(data.get("action")), String(data.get("note") || "")); }}><label>Decision<select name="action">{["PENDING", "CHANGES"].includes(ad.status) && <><option value="approve">Approve</option><option value="reject">Reject</option><option value="changes">Request changes</option></>}{ad.status === "ACTIVE" && <option value="pause">Pause</option>}{ad.status === "PAUSED" && <option value="resume">Resume</option>}</select></label><label>Reason for rejection, changes or pause<textarea name="note" maxLength={2000} /></label><button disabled={busy}>Save decision</button></form>}</div></article>)}</div>;
}
