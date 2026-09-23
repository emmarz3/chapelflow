import { CheckCircle2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Button, Field, Modal } from "../../components/ui";
import { ApiError } from "../../lib/api";
import { homepageService } from "../../services/chapelflow";

export interface RequestTarget {
  kind: "event" | "unit";
  id: string;
  title: string;
  /** Button wording that opened the form. */
  cta: "Register" | "RSVP" | "Join";
  blurb: string;
}

type Errors = Partial<Record<"name" | "email" | "matricNo" | "consent" | "form", string>>;

/** Public event registration / RSVP / unit-join form. Submissions are stored for the Super Admin. */
export function RequestModal({
  target,
  onClose,
  onDone,
}: {
  target: RequestTarget | null;
  onClose: () => void;
  onDone: (target: RequestTarget) => void;
}) {
  return (
    <Modal
      open={Boolean(target)}
      onClose={onClose}
      title={target ? heading(target) : ""}
      description={target?.blurb}
    >
      {target && <RequestForm key={`${target.kind}:${target.id}`} target={target} onClose={onClose} onDone={onDone} />}
    </Modal>
  );
}

function heading(target: RequestTarget) {
  if (target.cta === "Join") return `Join the ${target.title} unit`;
  return `${target.cta === "RSVP" ? "RSVP" : "Register"}: ${target.title}`;
}

function RequestForm({
  target,
  onClose,
  onDone,
}: {
  target: RequestTarget;
  onClose: () => void;
  onDone: (target: RequestTarget) => void;
}) {
  const [values, setValues] = useState({ name: "", email: "", matricNo: "", consent: false, website: "" });
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);
  const [doneName, setDoneName] = useState<string | null>(null);

  const validate = (): Errors => {
    const next: Errors = {};
    if (values.name.trim().length < 2) next.name = "Enter your full name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) next.email = "Enter a valid email address.";
    if (!values.consent) next.consent = "Tick the box to agree to the privacy notice.";
    return next;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await homepageService.submitRequest({
        kind: target.kind,
        itemId: target.id,
        itemTitle: target.title,
        name: values.name.trim(),
        email: values.email.trim(),
        matricNo: values.matricNo.trim(),
        consent: values.consent,
        website: values.website,
      });
      setDoneName(values.name.trim().split(/\s+/)[0] ?? "");
      onDone(target);
    } catch (error) {
      if (error instanceof ApiError && error.fieldErrors) {
        const first = (key: string) => error.fieldErrors?.[key]?.[0];
        setErrors({
          name: first("name"),
          email: first("email"),
          matricNo: first("matricNo"),
          consent: first("consent"),
          form: first("itemId") || first("kind") ? error.message : undefined,
        });
      } else {
        setErrors({ form: error instanceof Error ? error.message : "We could not send that. Please try again." });
      }
    } finally {
      setBusy(false);
    }
  };

  if (doneName !== null)
    return (
      <div className="hp-request-done" role="status">
        <CheckCircle2 aria-hidden="true" />
        <h3>{target.kind === "unit" ? `Thanks, ${doneName}!` : target.cta === "RSVP" ? `See you there, ${doneName}!` : `You're registered, ${doneName}!`}</h3>
        <p>
          {target.kind === "unit"
            ? `Your request to join ${target.title} has been received. The unit leader will reach out about the next meeting.`
            : `We've noted your place for ${target.title}.`}
        </p>
        <Button type="button" onClick={onClose}>
          Done
        </Button>
      </div>
    );

  return (
    <form className="hp-request-form" onSubmit={submit} noValidate>
      <Field
        label="Full name"
        autoComplete="name"
        placeholder="e.g. Tolu Adeyemi"
        value={values.name}
        error={errors.name}
        onChange={(e) => setValues({ ...values, name: e.target.value })}
      />
      <Field
        label="Email"
        type="email"
        autoComplete="email"
        placeholder="you@example.com"
        value={values.email}
        error={errors.email}
        onChange={(e) => setValues({ ...values, email: e.target.value })}
      />
      <Field
        label="Matric number (optional)"
        placeholder="e.g. 22/1234"
        value={values.matricNo}
        error={errors.matricNo}
        onChange={(e) => setValues({ ...values, matricNo: e.target.value })}
      />
      {/* Honeypot: hidden from people, tempting to bots. */}
      <div className="hp-hp" aria-hidden="true">
        <label>
          Website
          <input tabIndex={-1} autoComplete="off" value={values.website} onChange={(e) => setValues({ ...values, website: e.target.value })} />
        </label>
      </div>
      <label className="hp-consent">
        <input type="checkbox" checked={values.consent} onChange={(e) => setValues({ ...values, consent: e.target.checked })} />
        <span>
          I agree that the chapel may store these details to manage this request.{" "}
          <Link to="/privacy" onClick={onClose}>
            Read the privacy notice
          </Link>
          .
        </span>
      </label>
      {errors.consent && (
        <p className="hp-form-error" role="alert">
          {errors.consent}
        </p>
      )}
      {errors.form && (
        <p className="hp-form-error" role="alert">
          {errors.form}
        </p>
      )}
      <Button type="submit" loading={busy}>
        {target.cta === "Join" ? "Send request" : target.cta === "RSVP" ? "Confirm RSVP" : "Complete registration"}
      </Button>
    </form>
  );
}
