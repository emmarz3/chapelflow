import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, ImagePlus, Trash2 } from "lucide-react";
import { useId, useRef, useState, type ReactNode } from "react";
import { useToast } from "../../components/ui";
import { uploadService } from "../../services/chapelflow";

interface BaseProps {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  wide?: boolean;
}

function Shell({ label, hint, error, required, wide, htmlFor, children }: BaseProps & { htmlFor: string; children: ReactNode }) {
  return (
    <div className={`field hpa-field${wide ? " hpa-field--wide" : ""}`}>
      <label htmlFor={htmlFor}>
        {label}
        {required && <em>Required</em>}
      </label>
      {children}
      {(error || hint) && <small className={error ? "field__error" : ""}>{error || hint}</small>}
    </div>
  );
}

export function TextInput({
  value,
  onChange,
  type = "text",
  maxLength,
  placeholder,
  ...base
}: BaseProps & {
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email" | "date" | "time" | "url";
  maxLength?: number;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <Shell {...base} htmlFor={id}>
      <input
        id={id}
        type={type}
        value={value}
        maxLength={maxLength}
        placeholder={placeholder}
        aria-invalid={Boolean(base.error)}
        onChange={(event) => onChange(event.target.value)}
      />
    </Shell>
  );
}

export function NumberInput({
  value,
  onChange,
  min,
  max,
  ...base
}: BaseProps & { value: number | null; onChange: (value: number | null) => void; min?: number; max?: number }) {
  const id = useId();
  return (
    <Shell {...base} htmlFor={id}>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value ?? ""}
        aria-invalid={Boolean(base.error)}
        onChange={(event) => onChange(event.target.value === "" ? null : Math.trunc(Number(event.target.value)))}
      />
    </Shell>
  );
}

export function TextArea({
  value,
  onChange,
  maxLength,
  rows = 3,
  ...base
}: BaseProps & { value: string; onChange: (value: string) => void; maxLength?: number; rows?: number }) {
  const id = useId();
  return (
    <Shell {...base} htmlFor={id}>
      <textarea
        id={id}
        rows={rows}
        value={value}
        maxLength={maxLength}
        aria-invalid={Boolean(base.error)}
        onChange={(event) => onChange(event.target.value)}
      />
    </Shell>
  );
}

export function SelectInput<T extends string | number>({
  value,
  onChange,
  options,
  ...base
}: BaseProps & { value: T; onChange: (value: T) => void; options: { value: T; label: string }[] }) {
  const id = useId();
  return (
    <Shell {...base} htmlFor={id}>
      <select
        id={id}
        value={String(value)}
        aria-invalid={Boolean(base.error)}
        onChange={(event) => {
          const chosen = options.find((option) => String(option.value) === event.target.value);
          if (chosen) onChange(chosen.value);
        }}
      >
        {options.map((option) => (
          <option key={String(option.value)} value={String(option.value)}>
            {option.label}
          </option>
        ))}
      </select>
    </Shell>
  );
}

export function Toggle({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (value: boolean) => void; hint?: string }) {
  return (
    <label className="hpa-toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
    </label>
  );
}

/** A URL field with an optional upload button that stores the file through the uploads API. */
export function ImageInput({
  value,
  onChange,
  ...base
}: BaseProps & { value: string; onChange: (value: string) => void }) {
  const id = useId();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const upload = async (file: File) => {
    setBusy(true);
    try {
      const result = await uploadService.upload(file, "EVENT_IMAGE");
      onChange(result.data.file_url);
      toast("Image uploaded. Remember to save your changes.");
    } catch (error) {
      toast(error instanceof Error ? error.message : "The image could not be uploaded.", "error");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };
  return (
    <Shell {...base} htmlFor={id}>
      <div className="hpa-image-row">
        <input
          id={id}
          type="url"
          value={value}
          placeholder="https://… or /images/photo.jpg"
          aria-invalid={Boolean(base.error)}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" className="button button--secondary" disabled={busy} onClick={() => fileRef.current?.click()}>
          <ImagePlus aria-hidden="true" />
          {busy ? "Uploading…" : "Upload"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="sr-only"
          tabIndex={-1}
          aria-label={`Upload image for ${base.label}`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void upload(file);
          }}
        />
      </div>
      {value && /^(https?:\/\/|\/)/.test(value) && <img className="hpa-image-preview" src={value} alt="" loading="lazy" />}
    </Shell>
  );
}

/** Collapsible card for one list entry with show/hide, reorder and delete controls. */
export function ItemCard({
  title,
  subtitle,
  active,
  onActive,
  onUp,
  onDown,
  onDelete,
  defaultOpen = false,
  hasError = false,
  children,
}: {
  title: string;
  subtitle?: string;
  active?: boolean;
  onActive?: (value: boolean) => void;
  onUp?: () => void;
  onDown?: () => void;
  onDelete: () => void;
  defaultOpen?: boolean;
  hasError?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen || hasError);
  const bodyId = useId();
  return (
    <article className={`hpa-item${active === false ? " is-hidden" : ""}${hasError ? " has-error" : ""}`}>
      <header>
        <button type="button" className="hpa-item__main" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen(!open)}>
          {open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
          <span>
            <strong>{title || "Untitled"}</strong>
            {subtitle && <small>{subtitle}</small>}
          </span>
        </button>
        <div className="hpa-item__tools">
          {onActive && (
            <label className="hpa-switch" title={active ? "Shown on the homepage" : "Hidden from the homepage"}>
              <input type="checkbox" checked={active} onChange={(event) => onActive(event.target.checked)} />
              <span>{active ? "Shown" : "Hidden"}</span>
            </label>
          )}
          <button type="button" className="icon-button" aria-label={`Move ${title} up`} disabled={!onUp} onClick={onUp}><ArrowUp /></button>
          <button type="button" className="icon-button" aria-label={`Move ${title} down`} disabled={!onDown} onClick={onDown}><ArrowDown /></button>
          <button type="button" className="icon-button hpa-danger" aria-label={`Delete ${title}`} onClick={onDelete}><Trash2 /></button>
        </div>
      </header>
      {open && (
        <div className="hpa-item__body" id={bodyId}>
          {children}
        </div>
      )}
    </article>
  );
}
