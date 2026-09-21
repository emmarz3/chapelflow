import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Badge, Button, ErrorState, LoadingState, Modal, PageHeader, useToast } from "../../components/ui";
import { ApiError } from "../../lib/api";
import { downloadCsv } from "../../lib/export";
import {
  DEFAULT_HOMEPAGE,
  UNIT_ICONS,
  newId,
  resolveHomepage,
  type HomepageContent,
  type HomepageSectionKey,
  type ServiceRule,
  type ServiceType,
  type UnitIcon,
} from "../../lib/homepage-content";
import { homepageService, type HomepageRequestRow } from "../../services/chapelflow";
import { UNIT_ICON_LABELS } from "./home-icons";
import { ImageInput, ItemCard, NumberInput, SelectInput, TextArea, TextInput, Toggle } from "./homepage-admin-fields";
import { HOMEPAGE_QUERY_KEY } from "./use-homepage";

type Tab = "general" | "announcements" | "services" | "events" | "sermons" | "ministries" | "gallery" | "verses" | "contact" | "signups";
type Errors = Record<string, string[]>;

const TABS: { key: Tab; label: string }[] = [
  { key: "general", label: "Hero & page text" },
  { key: "announcements", label: "Announcements" },
  { key: "services", label: "Services" },
  { key: "events", label: "Events" },
  { key: "sermons", label: "Sermons" },
  { key: "ministries", label: "Ministries" },
  { key: "gallery", label: "Gallery" },
  { key: "verses", label: "Verses" },
  { key: "contact", label: "Contact & social" },
  { key: "signups", label: "Sign-ups" },
];

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map((label, value) => ({ value, label }));
const SECTION_LABELS: Record<HomepageSectionKey, string> = {
  schedule: "Service schedule",
  events: "Upcoming events",
  sermons: "Recent sermons",
  ministries: "Ministries & units",
  calendar: "Chapel calendar",
  gallery: "Gallery",
};

const PATH_LABELS: Record<string, string> = {
  announcements: "Announcement",
  services: "Service",
  events: "Event",
  sermons: "Sermon",
  units: "Ministry",
  gallery: "Photo",
  "verse.verses": "Verse",
  "hero.stats": "Hero number",
  "belonging.pillars": "Pillar",
};
const splitCamel = (value: string) => value.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
/** "events[4].startDate" → "Event 5 · start date" */
function friendlyPath(path: string) {
  const item = path.match(/^(.+?)\[(\d+)\]\.?(.*)$/);
  if (item) {
    const [, list, index, field] = item;
    return `${PATH_LABELS[list!] ?? list} ${Number(index) + 1}${field ? ` · ${splitCamel(field)}` : ""}`;
  }
  return splitCamel(path.replace(/\./g, " · "));
}

const err = (errors: Errors, path: string) => errors[path]?.[0];
const hasErr = (errors: Errors, prefix: string) => Object.keys(errors).some((key) => key.startsWith(prefix));

/** Generic editor for a list of objects that each have an `id`. */
function ListEditor<T extends { id: string; active?: boolean }>({
  items,
  onChange,
  create,
  addLabel,
  path,
  errors,
  summary,
  emptyText,
  max,
  onDeleteRequest,
  children,
}: {
  items: T[];
  onChange: (items: T[]) => void;
  create: () => T;
  addLabel: string;
  path: string;
  errors: Errors;
  summary: (item: T) => { title: string; subtitle?: string };
  emptyText: string;
  max: number;
  onDeleteRequest: (message: string, run: () => void) => void;
  children: (item: T, update: (patch: Partial<T>) => void, itemPath: string) => ReactNode;
}) {
  const [justAdded, setJustAdded] = useState<string | null>(null);
  const move = (index: number, delta: number) => {
    const next = [...items];
    const [item] = next.splice(index, 1);
    if (item) next.splice(index + delta, 0, item);
    onChange(next);
  };
  return (
    <div className="hpa-list">
      {items.length === 0 && <p className="hpa-empty">{emptyText}</p>}
      {items.map((item, index) => {
        const itemPath = `${path}[${index}]`;
        const { title, subtitle } = summary(item);
        return (
          <ItemCard
            key={item.id}
            title={title}
            subtitle={subtitle}
            active={"active" in item ? item.active : undefined}
            onActive={"active" in item ? (value) => onChange(items.map((i) => (i.id === item.id ? { ...i, active: value } : i))) : undefined}
            onUp={index > 0 ? () => move(index, -1) : undefined}
            onDown={index < items.length - 1 ? () => move(index, 1) : undefined}
            onDelete={() => onDeleteRequest(`Delete “${title || "this entry"}”? This cannot be undone until you leave without saving.`, () => onChange(items.filter((i) => i.id !== item.id)))}
            defaultOpen={item.id === justAdded}
            hasError={hasErr(errors, itemPath)}
          >
            <div className="hpa-grid">
              {children(item, (patch) => onChange(items.map((i) => (i.id === item.id ? { ...i, ...patch } : i))), itemPath)}
            </div>
          </ItemCard>
        );
      })}
      <Button
        type="button"
        variant="secondary"
        disabled={items.length >= max}
        onClick={() => {
          const created = create();
          setJustAdded(created.id);
          onChange([...items, created]);
        }}
      >
        <Plus aria-hidden="true" /> {addLabel}
      </Button>
      {items.length >= max && <small className="hpa-hint">You have reached the limit of {max}.</small>}
    </div>
  );
}

function Group({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="hpa-group">
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------------ */

export function HomepageAdminPage() {
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({
    queryKey: ["admin-homepage"],
    queryFn: async () => (await homepageService.adminGet()).data,
    refetchOnWindowFocus: false,
  });
  const [draft, setDraft] = useState<HomepageContent | null>(null);
  const [baseline, setBaseline] = useState("");
  const [version, setVersion] = useState(0);
  const [tab, setTab] = useState<Tab>("general");
  const [errors, setErrors] = useState<Errors>({});
  const [conflict, setConflict] = useState(false);
  const [confirm, setConfirm] = useState<{ message: string; run: () => void } | null>(null);
  const [resetOpen, setResetOpen] = useState(false);

  const load = (data: NonNullable<typeof query.data>) => {
    const resolved = resolveHomepage(data.content);
    setDraft(resolved);
    setBaseline(JSON.stringify(resolved));
    setVersion(data.version);
    setErrors({});
    setConflict(false);
  };

  useEffect(() => {
    if (query.data && !draft) load(query.data);
    // The draft is seeded exactly once from the first successful load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);

  const dirty = draft !== null && JSON.stringify(draft) !== baseline;
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const publish = (data: NonNullable<typeof query.data>) => {
    client.setQueryData(["admin-homepage"], data);
    client.setQueryData(HOMEPAGE_QUERY_KEY, data);
  };

  const save = useMutation({
    mutationFn: async () => (await homepageService.save(draft as HomepageContent, version)).data,
    onSuccess: (data) => {
      publish(data);
      load(data);
      toast("Homepage saved and live.");
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) return setConflict(true);
      if (error instanceof ApiError && error.fieldErrors) {
        setErrors(error.fieldErrors as Errors);
        return toast("Some fields need attention. They are marked in red.", "error");
      }
      toast(error instanceof Error ? error.message : "The homepage could not be saved.", "error");
    },
  });

  const reset = useMutation({
    mutationFn: async () => (await homepageService.reset()).data,
    onSuccess: (data) => {
      publish(data);
      load(data);
      setResetOpen(false);
      toast("The homepage now shows the built-in defaults.");
    },
    onError: (error) => toast(error instanceof Error ? error.message : "Could not restore defaults.", "error"),
  });

  const errorCount = Object.keys(errors).length;
  const tabErrors = useMemo(() => {
    const prefixes: Record<Tab, string[]> = {
      general: ["siteName", "hero", "sections", "belonging", "closing", "countdown"],
      announcements: ["announcements"],
      services: ["services"],
      events: ["events"],
      sermons: ["sermons"],
      ministries: ["units"],
      gallery: ["gallery"],
      verses: ["verse"],
      contact: ["contact"],
      signups: [],
    };
    const result = {} as Record<Tab, boolean>;
    for (const t of TABS) result[t.key] = prefixes[t.key].some((p) => hasErr(errors, p));
    return result;
  }, [errors]);

  if (query.isPending || (query.data && !draft)) return <LoadingState label="Loading homepage content" />;
  if (query.isError || !draft) return <ErrorState description="The homepage content could not be loaded." onRetry={() => void query.refetch()} />;

  const set = (patch: Partial<HomepageContent>) => setDraft({ ...draft, ...patch });
  const ask = (message: string, run: () => void) => setConfirm({ message, run });

  return (
    <div className="hpa">
      <PageHeader
        eyebrow="Website content"
        title="Homepage studio"
        description="Edit the names, programmes, sermons and text that appear on the public homepage. Changes go live as soon as you save."
        actions={
          <>
            <a className="button button--secondary" href="/" target="_blank" rel="noopener noreferrer">
              <ExternalLink aria-hidden="true" /> View homepage
            </a>
            <Button type="button" variant="ghost" onClick={() => setResetOpen(true)}>
              <RotateCcw aria-hidden="true" /> Restore defaults
            </Button>
            <Button type="button" loading={save.isPending} disabled={!dirty} onClick={() => save.mutate()}>
              <Save aria-hidden="true" /> Save changes
            </Button>
          </>
        }
      />

      {conflict && (
        <div className="hpa-banner hpa-banner--error" role="alert">
          <span>Someone else saved the homepage while you were editing. Reload to see their changes; your unsaved edits will be replaced.</span>
          <Button type="button" variant="secondary" onClick={() => void query.refetch().then((r) => r.data && load(r.data))}>
            Reload latest
          </Button>
        </div>
      )}
      {errorCount > 0 && (
        <div className="hpa-banner hpa-banner--error" role="alert">
          <span>
            {errorCount} {errorCount === 1 ? "field needs" : "fields need"} attention. Tabs with problems are marked.
            {Object.entries(errors).slice(0, 3).map(([path, messages]) => (
              <em key={path}> {friendlyPath(path)}: {messages[0]}</em>
            ))}
          </span>
        </div>
      )}
      {dirty && !errorCount && <div className="hpa-banner" role="status">You have unsaved changes.</div>}

      <div className="hpa-tabs" role="tablist" aria-label="Homepage sections">
        {TABS.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} className={tabErrors[t.key] ? "has-error" : ""} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="hpa-panel" role="tabpanel">
        {tab === "general" && <GeneralTab draft={draft} set={set} errors={errors} />}

        {tab === "announcements" && (
          <Group title="Announcement ticker" description="Short notices that scroll across the top of the homepage. Visitors can dismiss them.">
            <ListEditor
              items={draft.announcements}
              onChange={(announcements) => set({ announcements })}
              create={() => ({ id: newId("ann"), text: "", linkLabel: "", linkHref: "", active: true })}
              addLabel="Add announcement"
              path="announcements"
              errors={errors}
              max={10}
              emptyText="No announcements. The ticker is hidden until you add one."
              summary={(a) => ({ title: a.text, subtitle: a.linkLabel })}
              onDeleteRequest={ask}
            >
              {(a, update, p) => (
                <>
                  <TextArea wide required label="Message" value={a.text} maxLength={220} error={err(errors, `${p}.text`)} onChange={(text) => update({ text })} rows={2} />
                  <TextInput label="Link label" hint="e.g. See schedule" value={a.linkLabel} maxLength={40} error={err(errors, `${p}.linkLabel`)} onChange={(linkLabel) => update({ linkLabel })} />
                  <TextInput label="Link address" hint="#schedule, /events or https://…" value={a.linkHref} error={err(errors, `${p}.linkHref`)} onChange={(linkHref) => update({ linkHref })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "services" && (
          <Group title="Service schedule" description="Weekly services, monthly vigils and one-off dates. Times are West Africa Time (24-hour). These also feed the calendar and the countdown.">
            <ListEditor
              items={draft.services}
              onChange={(services) => set({ services })}
              create={() => ({ id: newId("svc"), type: "sunday" as ServiceType, title: "", venue: "", minister: "", time: "09:00", duration: 90, rule: "weekly" as ServiceRule, weekday: 0, date: "", active: true })}
              addLabel="Add service"
              path="services"
              errors={errors}
              max={30}
              emptyText="No services yet."
              summary={(s) => ({ title: s.title, subtitle: `${s.type} · ${s.rule === "date" ? s.date : s.rule === "lastfri" ? "last Friday" : WEEKDAYS[s.weekday]?.label} · ${s.time}` })}
              onDeleteRequest={ask}
            >
              {(s, update, p) => (
                <>
                  <TextInput wide required label="Service name" value={s.title} maxLength={140} error={err(errors, `${p}.title`)} onChange={(title) => update({ title })} />
                  <SelectInput<ServiceType> label="Category" value={s.type} error={err(errors, `${p}.type`)} onChange={(type) => update({ type })} options={[{ value: "sunday", label: "Sunday worship" }, { value: "midweek", label: "Midweek service" }, { value: "vigil", label: "Special vigil" }]} />
                  <TextInput required label="Venue" value={s.venue} maxLength={140} error={err(errors, `${p}.venue`)} onChange={(venue) => update({ venue })} />
                  <TextInput label="Minister / host" hint="Name shown on the card" value={s.minister} maxLength={140} error={err(errors, `${p}.minister`)} onChange={(minister) => update({ minister })} />
                  <SelectInput<ServiceRule> label="Repeats" value={s.rule} error={err(errors, `${p}.rule`)} onChange={(rule) => update({ rule })} options={[{ value: "weekly", label: "Every week" }, { value: "lastfri", label: "Last Friday of the month" }, { value: "date", label: "One date only" }]} />
                  {s.rule === "weekly" && <SelectInput label="Day" value={s.weekday} onChange={(weekday) => update({ weekday })} options={WEEKDAYS} />}
                  {s.rule === "date" && <TextInput required type="date" label="Date" value={s.date} error={err(errors, `${p}.date`)} onChange={(date) => update({ date })} />}
                  <TextInput required type="time" label="Start time" value={s.time} error={err(errors, `${p}.time`)} onChange={(time) => update({ time })} />
                  <NumberInput label="Length (minutes)" min={15} max={1440} value={s.duration} error={err(errors, `${p}.duration`)} onChange={(duration) => update({ duration: duration ?? 90 })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "events" && (
          <Group title="Upcoming events" description="One-off programmes or weekly activities. Visitors can register or RSVP, and each sign-up counts toward “places taken”.">
            <ListEditor
              items={draft.events}
              onChange={(events) => set({ events })}
              create={() => ({ id: newId("evt"), category: "Event", title: "", repeat: "none" as const, weekday: 0, startDate: "", endDate: "", startTime: "09:00", time: "", venue: "", cta: "Register" as const, capacity: null, taken: 0, active: true })}
              addLabel="Add event"
              path="events"
              errors={errors}
              max={40}
              emptyText="No events yet."
              summary={(e) => ({ title: e.title, subtitle: `${e.category} · ${e.repeat === "weekly" ? `every ${WEEKDAYS[e.weekday]?.label}` : e.startDate}` })}
              onDeleteRequest={ask}
            >
              {(e, update, p) => (
                <>
                  <TextInput wide required label="Event name" value={e.title} maxLength={140} error={err(errors, `${p}.title`)} onChange={(title) => update({ title })} />
                  <TextInput required label="Category label" hint="e.g. Retreat, Conference" value={e.category} maxLength={40} error={err(errors, `${p}.category`)} onChange={(category) => update({ category })} />
                  <SelectInput<"Register" | "RSVP"> label="Button" value={e.cta} onChange={(cta) => update({ cta })} options={[{ value: "Register", label: "Register" }, { value: "RSVP", label: "RSVP" }]} />
                  <SelectInput<"none" | "weekly"> label="Repeats" value={e.repeat} onChange={(repeat) => update({ repeat })} options={[{ value: "none", label: "One-off (dates)" }, { value: "weekly", label: "Every week" }]} />
                  {e.repeat === "weekly" ? (
                    <SelectInput label="Day" value={e.weekday} onChange={(weekday) => update({ weekday })} options={WEEKDAYS} />
                  ) : (
                    <>
                      <TextInput required type="date" label="Start date" value={e.startDate} error={err(errors, `${p}.startDate`)} onChange={(startDate) => update({ startDate })} />
                      <TextInput type="date" label="End date" hint="Leave empty for a single day" value={e.endDate} error={err(errors, `${p}.endDate`)} onChange={(endDate) => update({ endDate })} />
                    </>
                  )}
                  <TextInput required type="time" label="Start time" value={e.startTime} error={err(errors, `${p}.startTime`)} onChange={(startTime) => update({ startTime })} />
                  <TextInput required label="Time as shown on the card" hint="e.g. Fri 4:00 PM to Sun 2:00 PM" value={e.time} maxLength={80} error={err(errors, `${p}.time`)} onChange={(time) => update({ time })} />
                  <TextInput required label="Venue" value={e.venue} maxLength={140} error={err(errors, `${p}.venue`)} onChange={(venue) => update({ venue })} />
                  <NumberInput label="Places available" hint="Leave empty for unlimited" min={1} value={e.capacity} error={err(errors, `${p}.capacity`)} onChange={(capacity) => update({ capacity })} />
                  <NumberInput label="Places already taken" hint="Offline sign-ups, added to online ones" min={0} value={e.taken} error={err(errors, `${p}.taken`)} onChange={(taken) => update({ taken: taken ?? 0 })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "sermons" && (
          <Group title="Recent sermons" description="The newest six active messages appear on the homepage, ordered by date. Add links so visitors can play, listen or download.">
            <ListEditor
              items={draft.sermons}
              onChange={(sermons) => set({ sermons })}
              create={() => ({ id: newId("srm"), series: "", title: "", speaker: "", date: new Date().toISOString().slice(0, 10), duration: "", videoUrl: "", audioUrl: "", downloadUrl: "", imageUrl: "", active: true })}
              addLabel="Add sermon"
              path="sermons"
              errors={errors}
              max={40}
              emptyText="No sermons yet."
              summary={(s) => ({ title: s.title, subtitle: [s.speaker, s.date].filter(Boolean).join(" · ") })}
              onDeleteRequest={ask}
            >
              {(s, update, p) => (
                <>
                  <TextInput wide required label="Title" value={s.title} maxLength={160} error={err(errors, `${p}.title`)} onChange={(title) => update({ title })} />
                  <TextInput label="Speaker" value={s.speaker} maxLength={140} error={err(errors, `${p}.speaker`)} onChange={(speaker) => update({ speaker })} />
                  <TextInput label="Series" value={s.series} maxLength={80} error={err(errors, `${p}.series`)} onChange={(series) => update({ series })} />
                  <TextInput required type="date" label="Date preached" value={s.date} error={err(errors, `${p}.date`)} onChange={(date) => update({ date })} />
                  <TextInput label="Length" hint="e.g. 42:18" value={s.duration} maxLength={12} error={err(errors, `${p}.duration`)} onChange={(duration) => update({ duration })} />
                  <TextInput wide label="Video link" hint="Opens when visitors press Play" value={s.videoUrl} error={err(errors, `${p}.videoUrl`)} onChange={(videoUrl) => update({ videoUrl })} />
                  <TextInput wide label="Audio link" value={s.audioUrl} error={err(errors, `${p}.audioUrl`)} onChange={(audioUrl) => update({ audioUrl })} />
                  <TextInput wide label="Download link" value={s.downloadUrl} error={err(errors, `${p}.downloadUrl`)} onChange={(downloadUrl) => update({ downloadUrl })} />
                  <ImageInput wide label="Cover image (optional)" value={s.imageUrl} error={err(errors, `${p}.imageUrl`)} onChange={(imageUrl) => update({ imageUrl })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "ministries" && (
          <Group title="Ministries & units" description="Teams visitors can ask to join. Requests appear under Sign-ups.">
            <ListEditor
              items={draft.units}
              onChange={(units) => set({ units })}
              create={() => ({ id: newId("unit"), name: "", icon: "users" as UnitIcon, description: "", meeting: "", active: true })}
              addLabel="Add ministry or unit"
              path="units"
              errors={errors}
              max={30}
              emptyText="No ministries yet."
              summary={(u) => ({ title: u.name, subtitle: u.meeting })}
              onDeleteRequest={ask}
            >
              {(u, update, p) => (
                <>
                  <TextInput required label="Name" value={u.name} maxLength={80} error={err(errors, `${p}.name`)} onChange={(name) => update({ name })} />
                  <SelectInput label="Icon" value={u.icon} error={err(errors, `${p}.icon`)} onChange={(icon) => update({ icon })} options={UNIT_ICONS.map((value) => ({ value, label: UNIT_ICON_LABELS[value] }))} />
                  <TextArea wide label="Description" value={u.description} maxLength={300} error={err(errors, `${p}.description`)} onChange={(description) => update({ description })} />
                  <TextInput wide label="When they meet" hint="e.g. Rehearsals: Tuesdays, 6:00 PM" value={u.meeting} maxLength={120} error={err(errors, `${p}.meeting`)} onChange={(meeting) => update({ meeting })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "gallery" && (
          <Group title="Gallery highlights" description="Photos shown in “Moments of Grace”. Without an image a branded artwork tile is used. The first tile is displayed largest.">
            <ListEditor
              items={draft.gallery}
              onChange={(gallery) => set({ gallery })}
              create={() => ({ id: newId("gal"), title: "", subtitle: "", imageUrl: "", active: true })}
              addLabel="Add photo"
              path="gallery"
              errors={errors}
              max={40}
              emptyText="No photos yet."
              summary={(g) => ({ title: g.title, subtitle: g.subtitle })}
              onDeleteRequest={ask}
            >
              {(g, update, p) => (
                <>
                  <TextInput required label="Caption" value={g.title} maxLength={120} error={err(errors, `${p}.title`)} onChange={(title) => update({ title })} />
                  <TextInput label="Sub-caption" hint="e.g. June 2026" value={g.subtitle} maxLength={80} error={err(errors, `${p}.subtitle`)} onChange={(subtitle) => update({ subtitle })} />
                  <ImageInput wide label="Photo" value={g.imageUrl} error={err(errors, `${p}.imageUrl`)} onChange={(imageUrl) => update({ imageUrl })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "verses" && (
          <Group title="Verse of the day" description="One verse is chosen per day, cycling through this list in order.">
            <Toggle label="Show the verse of the day" checked={draft.verse.enabled} onChange={(enabled) => set({ verse: { ...draft.verse, enabled } })} />
            <ListEditor
              items={draft.verse.verses.map((v) => ({ ...v, active: undefined }))}
              onChange={(verses) => set({ verse: { ...draft.verse, verses: verses.map(({ id, text, reference, translation, note }) => ({ id, text, reference, translation, note })) } })}
              create={() => ({ id: newId("v"), text: "", reference: "", translation: "KJV", note: "", active: undefined })}
              addLabel="Add verse"
              path="verse.verses"
              errors={errors}
              max={400}
              emptyText="No verses yet. The verse card is hidden until you add one."
              summary={(v) => ({ title: v.reference, subtitle: v.text.slice(0, 80) })}
              onDeleteRequest={ask}
            >
              {(v, update, p) => (
                <>
                  <TextArea wide required label="Verse text" value={v.text} maxLength={600} error={err(errors, `${p}.text`)} onChange={(text) => update({ text })} />
                  <TextInput required label="Reference" hint="e.g. Isaiah 40:31" value={v.reference} maxLength={60} error={err(errors, `${p}.reference`)} onChange={(reference) => update({ reference })} />
                  <TextInput label="Translation" value={v.translation} maxLength={20} error={err(errors, `${p}.translation`)} onChange={(translation) => update({ translation })} />
                  <TextArea wide label="Short reflection" value={v.note} maxLength={400} error={err(errors, `${p}.note`)} onChange={(note) => update({ note })} />
                </>
              )}
            </ListEditor>
          </Group>
        )}

        {tab === "contact" && (
          <Group title="Contact & social" description="Shown in the footer of every public page. Leave a field empty to hide it.">
            <div className="hpa-grid">
              <TextArea wide label="Address" value={draft.contact.address} maxLength={240} rows={2} error={err(errors, "contact.address")} onChange={(address) => set({ contact: { ...draft.contact, address } })} />
              <TextInput type="email" label="Public email" value={draft.contact.email} error={err(errors, "contact.email")} onChange={(email) => set({ contact: { ...draft.contact, email } })} />
              <TextInput label="Public phone" value={draft.contact.phone} maxLength={40} error={err(errors, "contact.phone")} onChange={(phone) => set({ contact: { ...draft.contact, phone } })} />
              <TextInput label="Facebook page" value={draft.contact.facebook} error={err(errors, "contact.facebook")} onChange={(facebook) => set({ contact: { ...draft.contact, facebook } })} />
              <TextInput label="X (Twitter) profile" value={draft.contact.x} error={err(errors, "contact.x")} onChange={(x) => set({ contact: { ...draft.contact, x } })} />
              <TextInput label="Instagram profile" value={draft.contact.instagram} error={err(errors, "contact.instagram")} onChange={(instagram) => set({ contact: { ...draft.contact, instagram } })} />
              <TextInput label="YouTube channel" value={draft.contact.youtube} error={err(errors, "contact.youtube")} onChange={(youtube) => set({ contact: { ...draft.contact, youtube } })} />
            </div>
          </Group>
        )}

        {tab === "signups" && <SignupsTab />}
      </div>

      <Modal open={Boolean(confirm)} onClose={() => setConfirm(null)} title="Delete this entry?" description={confirm?.message}
        footer={<><Button type="button" variant="ghost" onClick={() => setConfirm(null)}>Keep it</Button><Button type="button" variant="danger" onClick={() => { confirm?.run(); setConfirm(null); }}>Delete</Button></>}
      >
        <p>Nothing is removed from the live site until you press “Save changes”.</p>
      </Modal>
      <Modal open={resetOpen} onClose={() => setResetOpen(false)} title="Restore the built-in defaults?" description="This replaces every name, programme, sermon and text with the original sample content, on the live homepage."
        footer={<><Button type="button" variant="ghost" onClick={() => setResetOpen(false)}>Cancel</Button><Button type="button" variant="danger" loading={reset.isPending} onClick={() => reset.mutate()}>Restore defaults</Button></>}
      >
        <p>Visitor sign-ups are not deleted. You can edit the defaults again afterwards.</p>
      </Modal>
    </div>
  );
}

/* ------------------------------ General tab ------------------------------ */

function GeneralTab({ draft, set, errors }: { draft: HomepageContent; set: (patch: Partial<HomepageContent>) => void; errors: Errors }) {
  const { hero, belonging, closing } = draft;
  const setHero = (patch: Partial<typeof hero>) => set({ hero: { ...hero, ...patch } });
  const setBelonging = (patch: Partial<typeof belonging>) => set({ belonging: { ...belonging, ...patch } });
  return (
    <>
      <Group title="Names" description="Used in the hero, calendar files and footer.">
        <div className="hpa-grid">
          <TextInput wide required label="Chapel name" value={draft.siteName} maxLength={120} error={err(errors, "siteName")} onChange={(siteName) => set({ siteName })} />
        </div>
      </Group>

      <Group title="Hero">
        <div className="hpa-grid">
          <TextInput wide label="Small heading above the title" value={hero.eyebrow} maxLength={80} error={err(errors, "hero.eyebrow")} onChange={(eyebrow) => setHero({ eyebrow })} />
          <TextInput required label="Hero title" value={hero.titleLead} maxLength={120} error={err(errors, "hero.titleLead")} onChange={(titleLead) => setHero({ titleLead })} />
          <TextInput label="Hero title, second part" value={hero.titleAccent} maxLength={60} error={err(errors, "hero.titleAccent")} onChange={(titleAccent) => setHero({ titleAccent })} />
          <TextArea wide label="Intro text" value={hero.lede} maxLength={400} error={err(errors, "hero.lede")} onChange={(lede) => setHero({ lede })} />
          <TextInput label="Main button label" value={hero.primaryLabel} maxLength={60} error={err(errors, "hero.primaryLabel")} onChange={(primaryLabel) => setHero({ primaryLabel })} />
          <TextInput label="Main button link" value={hero.primaryHref} error={err(errors, "hero.primaryHref")} onChange={(primaryHref) => setHero({ primaryHref })} />
          <TextInput label="Second button label" value={hero.secondaryLabel} maxLength={60} error={err(errors, "hero.secondaryLabel")} onChange={(secondaryLabel) => setHero({ secondaryLabel })} />
          <TextInput label="Second button link" value={hero.secondaryHref} error={err(errors, "hero.secondaryHref")} onChange={(secondaryHref) => setHero({ secondaryHref })} />
          <ImageInput wide label="Hero photo" hint="Leave empty to keep the standard chapel photo" value={hero.imageUrl === DEFAULT_HOMEPAGE.hero.imageUrl ? "" : hero.imageUrl} error={err(errors, "hero.imageUrl")} onChange={(imageUrl) => setHero({ imageUrl })} />
          <TextInput wide label="Photo caption" value={hero.imageCaption} maxLength={120} error={err(errors, "hero.imageCaption")} onChange={(imageCaption) => setHero({ imageCaption })} />
        </div>
        <h4 className="hpa-sub">Numbers under the title</h4>
        <div className="hpa-rows">
          {hero.stats.map((stat, i) => (
            <div className="hpa-row" key={i}>
              <TextInput label={`Number ${i + 1}`} value={stat.value} maxLength={20} error={err(errors, `hero.stats[${i}].value`)} onChange={(value) => setHero({ stats: hero.stats.map((s, j) => (j === i ? { ...s, value } : s)) })} />
              <TextInput label={`Label ${i + 1}`} value={stat.label} maxLength={40} error={err(errors, `hero.stats[${i}].label`)} onChange={(label) => setHero({ stats: hero.stats.map((s, j) => (j === i ? { ...s, label } : s)) })} />
              <button type="button" className="icon-button hpa-danger" aria-label={`Remove number ${i + 1}`} onClick={() => setHero({ stats: hero.stats.filter((_, j) => j !== i) })}><Trash2 /></button>
            </div>
          ))}
          <Button type="button" variant="secondary" disabled={hero.stats.length >= 4} onClick={() => setHero({ stats: [...hero.stats, { value: "", label: "" }] })}><Plus aria-hidden="true" /> Add number</Button>
        </div>
      </Group>

      <Group title="Countdown" description="Counts down to the next start time of one of your services.">
        <Toggle label="Show the countdown in the hero" checked={draft.countdown.enabled} onChange={(enabled) => set({ countdown: { ...draft.countdown, enabled } })} />
        {draft.countdown.enabled && (
          <SelectInput
            label="Count down to"
            value={draft.countdown.serviceId}
            error={err(errors, "countdown.serviceId")}
            onChange={(serviceId) => set({ countdown: { ...draft.countdown, serviceId } })}
            options={[{ value: "", label: "Choose a service…" }, ...draft.services.map((s) => ({ value: s.id, label: s.title || s.id }))]}
          />
        )}
      </Group>

      <Group title="Section headings" description="Turn a section off to hide it, or change its heading and intro.">
        {(Object.keys(SECTION_LABELS) as HomepageSectionKey[]).map((key) => {
          const section = draft.sections[key];
          const update = (patch: Partial<typeof section>) => set({ sections: { ...draft.sections, [key]: { ...section, ...patch } } });
          return (
            <fieldset className="hpa-fieldset" key={key}>
              <legend>{SECTION_LABELS[key]}</legend>
              <Toggle label="Show this section" checked={section.enabled} onChange={(enabled) => update({ enabled })} />
              <div className="hpa-grid">
                <TextInput label="Small heading" value={section.eyebrow} maxLength={60} error={err(errors, `sections.${key}.eyebrow`)} onChange={(eyebrow) => update({ eyebrow })} />
                <TextInput required label="Heading" value={section.title} maxLength={100} error={err(errors, `sections.${key}.title`)} onChange={(title) => update({ title })} />
                <TextArea wide label="Intro text" rows={2} value={section.description} maxLength={300} error={err(errors, `sections.${key}.description`)} onChange={(description) => update({ description })} />
              </div>
            </fieldset>
          );
        })}
      </Group>

      <Group title="Welcome section">
        <div className="hpa-grid">
          <TextInput wide label="Small heading" value={belonging.eyebrow} maxLength={80} error={err(errors, "belonging.eyebrow")} onChange={(eyebrow) => setBelonging({ eyebrow })} />
          <TextInput wide required label="Heading" value={belonging.title} maxLength={140} error={err(errors, "belonging.title")} onChange={(title) => setBelonging({ title })} />
          <TextArea wide label="Paragraph" value={belonging.body} maxLength={500} error={err(errors, "belonging.body")} onChange={(body) => setBelonging({ body })} />
          <TextInput wide label="Quote" value={belonging.quote} maxLength={200} error={err(errors, "belonging.quote")} onChange={(quote) => setBelonging({ quote })} />
        </div>
        <h4 className="hpa-sub">Four pillars</h4>
        <div className="hpa-rows">
          {belonging.pillars.map((pillar, i) => (
            <div className="hpa-row" key={i}>
              <TextInput label={`Pillar ${i + 1} title`} value={pillar.title} maxLength={60} error={err(errors, `belonging.pillars[${i}].title`)} onChange={(title) => setBelonging({ pillars: belonging.pillars.map((p, j) => (j === i ? { ...p, title } : p)) })} />
              <TextInput label={`Pillar ${i + 1} detail`} value={pillar.detail} maxLength={120} error={err(errors, `belonging.pillars[${i}].detail`)} onChange={(detail) => setBelonging({ pillars: belonging.pillars.map((p, j) => (j === i ? { ...p, detail } : p)) })} />
              <button type="button" className="icon-button hpa-danger" aria-label={`Remove pillar ${i + 1}`} onClick={() => setBelonging({ pillars: belonging.pillars.filter((_, j) => j !== i) })}><Trash2 /></button>
            </div>
          ))}
          <Button type="button" variant="secondary" disabled={belonging.pillars.length >= 6} onClick={() => setBelonging({ pillars: [...belonging.pillars, { title: "", detail: "" }] })}><Plus aria-hidden="true" /> Add pillar</Button>
        </div>
      </Group>

      <Group title="Closing invitation">
        <div className="hpa-grid">
          <TextInput label="Small heading" value={closing.eyebrow} maxLength={80} error={err(errors, "closing.eyebrow")} onChange={(eyebrow) => set({ closing: { ...closing, eyebrow } })} />
          <TextInput label="Button label" value={closing.ctaLabel} maxLength={60} error={err(errors, "closing.ctaLabel")} onChange={(ctaLabel) => set({ closing: { ...closing, ctaLabel } })} />
          <TextInput wide required label="Heading" value={closing.title} maxLength={160} error={err(errors, "closing.title")} onChange={(title) => set({ closing: { ...closing, title } })} />
          <TextArea wide label="Paragraph" value={closing.body} maxLength={400} error={err(errors, "closing.body")} onChange={(body) => set({ closing: { ...closing, body } })} />
        </div>
      </Group>
    </>
  );
}

/* ------------------------------ Sign-ups tab ----------------------------- */

const csvSafe = (value: string) => (/^[=+\-@\t\r]/.test(value) ? `'${value}` : value);

function SignupsTab() {
  const client = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState<"" | "event" | "unit">("");
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<HomepageRequestRow | null>(null);
  const list = useQuery({
    queryKey: ["admin-homepage-requests", kind, search],
    queryFn: async () => (await homepageService.requests({ kind: kind ? kind.toUpperCase() : undefined, search: search || undefined })).data,
  });
  const refresh = () => void client.invalidateQueries({ queryKey: ["admin-homepage-requests"] });
  const status = useMutation({
    mutationFn: ({ id, value }: { id: string; value: HomepageRequestRow["status"] }) => homepageService.updateRequest(id, value),
    onSuccess: refresh,
    onError: () => toast("The status could not be updated.", "error"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => homepageService.deleteRequest(id),
    onSuccess: () => {
      setPendingDelete(null);
      refresh();
      toast("Sign-up deleted.");
    },
    onError: () => toast("The sign-up could not be deleted.", "error"),
  });
  const rows = list.data?.results ?? [];
  return (
    <Group title="Visitor sign-ups" description="Event registrations, RSVPs and requests to join a ministry, submitted from the homepage.">
      <div className="hpa-filters">
        <SelectInput label="Type" value={kind} onChange={setKind} options={[{ value: "", label: "All" }, { value: "event", label: "Events" }, { value: "unit", label: "Ministries" }]} />
        <TextInput label="Search" placeholder="Name, email or programme" value={search} onChange={setSearch} />
        <Button
          type="button"
          variant="secondary"
          disabled={!rows.length}
          onClick={() =>
            downloadCsv("homepage-signups.csv", rows.map((r) => ({ Type: r.kind === "EVENT" ? "Event" : "Ministry", Programme: csvSafe(r.itemTitle), Name: csvSafe(r.name), Email: csvSafe(r.email), "Matric no.": csvSafe(r.matricNo), Status: r.status, Submitted: r.createdAt })))
          }
        >
          Export CSV
        </Button>
      </div>
      {list.isPending ? (
        <LoadingState label="Loading sign-ups" />
      ) : list.isError ? (
        <ErrorState description="Sign-ups could not be loaded." onRetry={() => void list.refetch()} />
      ) : rows.length === 0 ? (
        <p className="hpa-empty">No sign-ups yet.</p>
      ) : (
        <div className="table-panel">
          <table>
            <thead>
              <tr><th>Name</th><th>Contact</th><th>Programme</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td><strong>{r.name}</strong><br /><small>{new Date(r.createdAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}</small></td>
                  <td>{r.email}{r.matricNo && <><br /><small>{r.matricNo}</small></>}</td>
                  <td>{r.itemTitle || r.itemId}<br /><Badge tone={r.kind === "EVENT" ? "purple" : "neutral"}>{r.kind === "EVENT" ? "Event" : "Ministry"}</Badge></td>
                  <td>
                    <select aria-label={`Status for ${r.name}`} value={r.status} onChange={(e) => status.mutate({ id: r.id, value: e.target.value as HomepageRequestRow["status"] })}>
                      <option value="NEW">New</option>
                      <option value="CONTACTED">Contacted</option>
                      <option value="CLOSED">Closed</option>
                    </select>
                  </td>
                  <td><button type="button" className="icon-button hpa-danger" aria-label={`Delete sign-up from ${r.name}`} onClick={() => setPendingDelete(r)}><Trash2 /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(list.data?.total ?? 0) > rows.length && <small className="hpa-hint">Showing the newest {rows.length} of {list.data?.total}. Narrow the search to see others.</small>}
      <Modal open={Boolean(pendingDelete)} onClose={() => setPendingDelete(null)} title="Delete this sign-up?" description={pendingDelete ? `${pendingDelete.name} · ${pendingDelete.itemTitle}` : undefined}
        footer={<><Button type="button" variant="ghost" onClick={() => setPendingDelete(null)}>Cancel</Button><Button type="button" variant="danger" loading={remove.isPending} onClick={() => pendingDelete && remove.mutate(pendingDelete.id)}>Delete</Button></>}
      >
        <p>The person's details are permanently removed. Event places taken will drop by one.</p>
      </Modal>
    </Group>
  );
}
