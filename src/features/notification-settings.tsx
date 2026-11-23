import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, ErrorState, LoadingState, PageHeader, useToast } from "../components/ui";
import { notificationService, type NotificationPreferences } from "../services/chapelflow";

const categories: { key: keyof NotificationPreferences; label: string; detail: string }[] = [
  { key: "announcementsEnabled", label: "Chapel announcements", detail: "Updates from your chapel branch." },
  { key: "eventsEnabled", label: "Upcoming events", detail: "Event and programme reminders." },
  { key: "serviceRemindersEnabled", label: "Service reminders", detail: "Serving and volunteer assignments." },
  { key: "devotionalEnabled", label: "Devotional reminders", detail: "Optional devotional updates when available." },
  { key: "fellowshipEnabled", label: "Fellowship updates", detail: "Messages for communities you belong to." },
  { key: "prayerUpdatesEnabled", label: "My prayer updates", detail: "Updates about requests in your care." },
  { key: "publicPrayerEnabled", label: "Public prayer", detail: "Opt in to shared prayer notices." },
  { key: "liveServiceEnabled", label: "Live service", detail: "Announcements when a live service starts." },
  { key: "adminAlertsEnabled", label: "Administrative alerts", detail: "Account and workspace updates." },
  { key: "birthdayEnabled", label: "Birthday celebrations", detail: "Community birthday notices." },
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Notification preferences could not be saved.";
}

export function NotificationSettingsPage() {
  const client = useQueryClient();
  const toast = useToast();
  const [quietOverride, setQuietOverride] = useState<boolean | null>(null);
  const query = useQuery({ queryKey: ["notification-preferences"], queryFn: async () => (await notificationService.preferences()).data });
  const save = useMutation({
    mutationFn: notificationService.savePreferences,
    onSuccess: () => { toast("Notification preferences saved."); void client.invalidateQueries({ queryKey: ["notification-preferences"] }); },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const current = query.data;
    if (!current) return;
    const values: NotificationPreferences = { ...current };
    for (const key of ["masterEnabled", "inAppEnabled", ...categories.map((item) => item.key), "quietHoursEnabled"] as (keyof NotificationPreferences)[]) {
      (values as unknown as Record<string, unknown>)[key] = form.has(key);
    }
    values.emailEnabled = form.has("emailEnabled");
    values.smsEnabled = form.has("smsEnabled");
    values.quietHoursStart = String(form.get("quietHoursStart") || "");
    values.quietHoursEnd = String(form.get("quietHoursEnd") || "");
    values.timezoneName = String(form.get("timezoneName") || "Africa/Lagos").trim();
    save.mutate(values);
  }

  if (query.isPending) return <LoadingState label="Loading notification settings" />;
  if (query.isError) return <ErrorState description={errorMessage(query.error)} onRetry={() => void query.refetch()} />;
  const preference = query.data;
  const quietEnabled = quietOverride ?? preference.quietHoursEnabled;
  return <>
    <PageHeader eyebrow="My account" title="Notification settings" description="Choose which ordinary updates you receive. Your choices are checked again before delivery." />
    <section className="panel">
      <form className="form-grid" onSubmit={submit}>
        <label className="field field--full checkbox-field"><input type="checkbox" name="masterEnabled" defaultChecked={preference.masterEnabled} /><span><strong>Allow ordinary notifications</strong><small>Turn off to pause all ordinary updates. Your category choices are kept for later.</small></span></label>
        <div className="field--full"><h2>Delivery channels</h2><p>On-site notifications appear in ChapelFlow. Off-site email and SMS notifications are sent through the chapel's configured delivery providers.</p></div>
        <label className="field checkbox-field"><input type="checkbox" name="inAppEnabled" defaultChecked={preference.inAppEnabled} /><span><strong>In-app</strong><small>On-site notification inbox and unread alerts.</small></span></label>
        <label className="field checkbox-field"><input type="checkbox" name="emailEnabled" defaultChecked={preference.emailEnabled} /><span><strong>Email</strong><small>{preference.emailAvailable === false ? "Email provider is not configured yet. Your preference will be ready when the chapel enables delivery." : "Off-site email updates to your registered address."}</small></span></label>
        <label className="field checkbox-field"><input type="checkbox" name="smsEnabled" defaultChecked={preference.smsEnabled} /><span><strong>SMS</strong><small>{preference.smsAvailable === false ? "Termii is not configured yet. Your preference will be ready when the chapel enables SMS delivery." : "Off-site text-message updates to your registered phone number."}</small></span></label>
        <p className="field--full">Browser push notifications are not active yet. They require a device subscription and permission flow, which ChapelFlow does not currently provide.</p>
        <div className="field--full"><h2>Topics</h2><p>Choose each kind of update independently.</p></div>
        {categories.map(({ key, label, detail }) => <label key={key} className="field field--full checkbox-field"><input type="checkbox" name={key} defaultChecked={Boolean(preference[key])} /><span><strong>{label}</strong><small>{detail}</small></span></label>)}
        <div className="field--full"><h2>Quiet hours</h2><p>External messages wait until quiet hours end. In-app updates remain available when you open ChapelFlow.</p></div>
        <label className="field field--full checkbox-field"><input type="checkbox" name="quietHoursEnabled" defaultChecked={preference.quietHoursEnabled} onChange={(event) => setQuietOverride(event.target.checked)} /><span>Use quiet hours</span></label>
        <label className="field"><span>Start</span><input type="time" name="quietHoursStart" defaultValue={preference.quietHoursStart} required={quietEnabled} /></label>
        <label className="field"><span>End</span><input type="time" name="quietHoursEnd" defaultValue={preference.quietHoursEnd} required={quietEnabled} /></label>
        <label className="field field--full"><span>Time zone</span><input name="timezoneName" defaultValue={preference.timezoneName} maxLength={64} required /><small>Use an IANA name such as Africa/Lagos or Europe/London.</small></label>
        {save.isError && <p className="form-error field--full" role="alert">{errorMessage(save.error)}</p>}
        <Button type="submit" loading={save.isPending} icon={<Bell />}>Save notification settings</Button>
      </form>
    </section>
  </>;
}
