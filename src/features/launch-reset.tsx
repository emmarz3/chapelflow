import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button, PageHeader } from "../components/ui";
import { ApiError } from "../lib/api";
import { adminAccountService } from "../services/chapelflow";

/** Super Admin only: the route is protected; the API rechecks role and MFA. */
export function LaunchResetPage() {
  const [confirmed, setConfirmed] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [phraseError, setPhraseError] = useState(false);
  const confirmationInput = useRef<HTMLInputElement>(null);
  const preview = useMutation({ mutationFn: adminAccountService.resetPreview });
  const reset = useMutation({
    mutationFn: ({
      token,
      confirmation,
      password,
      otp,
    }: {
      token: string;
      confirmation: string;
      password: string;
      otp: string;
    }) => adminAccountService.resetDatabase(token, confirmation, password, otp),
    onSuccess: () => window.location.assign("/login"),
  });
  function review() {
    preview.reset();
    reset.reset();
    setConfirmed(false);
    setPhrase("");
    setPhraseError(false);
    preview.mutate();
  }
  useEffect(() => {
    if (preview.data) confirmationInput.current?.focus();
  }, [preview.data]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preview.data || !confirmed || reset.isPending) return;
    const confirmation = phrase.trim();
    if (confirmation !== preview.data.data.confirmation) {
      setPhraseError(true);
      confirmationInput.current?.focus();
      return;
    }
    const fields = new FormData(event.currentTarget);
    reset.mutate({
      token: preview.data.data.token,
      confirmation,
      password: String(fields.get("password") || ""),
      otp: String(fields.get("otp") || ""),
    });
  }
  return (
    <>
      <PageHeader
        eyebrow="Super Admin · Launch preparation"
        title="Reset saved accounts and records"
        description="Prepare ChapelFlow for launch by clearing saved application data."
      />
      <section className="panel">
        <h2>Step 1: Review what will be reset</h2>
        <p>
          Select <strong>Review records to reset</strong> below. The confirmation
          fields, including where to type the reset phrase, will appear next.
        </p>
        <h3>What this reset deletes</h3>
        <p>
          All other user accounts, member profiles, attendance, finance records,
          messages, gallery and website entries, upload references, and previous
          audit history are cleared from the application database.
        </p>
        <h3>What stays</h3>
        <p>
          Your Super Admin sign-in and authenticator, chapel branches, academic
          programmes, units, fellowships, roles, and permissions remain.
          Application code, database structure, and hosting settings remain.
          Files stored in Cloudinary or S3 and external payment records are
          outside this reset.
        </p>
        <p>
          <strong>This cannot be undone from the dashboard.</strong> Verify a
          restorable database backup before proceeding.
        </p>
        <Button
          type="button"
          variant="secondary"
          loading={preview.isPending}
          onClick={review}
        >
          Review records to reset
        </Button>
        {preview.isError && (
          <p className="form-error" role="alert">
            {preview.error.message}
          </p>
        )}
      </section>
      {preview.data && (
        <section className="panel" aria-label="Confirm launch reset">
          <h2>Step 2: Enter the confirmation phrase</h2>
          <p>
            {preview.data.data.accounts_to_remove} other accounts will be
            removed. The preview covers {preview.data.data.database_rows}{" "}
            database rows, including configuration that will be restored. It
            expires after five minutes or when record counts change.
          </p>
          <form className="form-grid" onSubmit={submit}>
            <label className="field">
              <span>Confirmation phrase</span>
              <small>Type <strong>{preview.data.data.confirmation}</strong> into the empty box below. The displayed phrase is not filled in for you.</small>
              <input
                ref={confirmationInput}
                name="confirmation"
                aria-label="Reset confirmation phrase"
                value={phrase}
                onChange={(event) => { setPhrase(event.target.value); setPhraseError(false); }}
                aria-invalid={phraseError}
                aria-describedby={phraseError ? "reset-phrase-error" : undefined}
                required
                autoComplete="off"
              />
              {phraseError && <small className="field__error" id="reset-phrase-error" role="alert">The phrase must match {preview.data.data.confirmation} exactly.</small>}
            </label>
            <label className="field">
              <span>Super Admin password</span>
              <input
                name="password"
                type="password"
                required
                autoComplete="current-password"
              />
            </label>
            <label className="field">
              <span>Authenticator code</span>
              <input
                name="otp"
                inputMode="numeric"
                pattern="[0-9]{6}"
                required
                autoComplete="one-time-code"
              />
            </label>
            <label className="field--full">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
                required
              />{" "}
              I have verified a restorable database backup.
            </label>
            {reset.isError && (
              <p className="form-error" role="alert">
                {reset.error.message}
                {reset.error instanceof ApiError && reset.error.status === 409 && " Review the records again to get a new preview."}
              </p>
            )}
            <div className="button-row">
              <Link
                className="button button--secondary"
                to="/app/admin/dashboard"
              >
                Cancel
              </Link>
              <Button
                type="submit"
                disabled={!confirmed}
                loading={reset.isPending}
              >
                Permanently reset saved accounts and records
              </Button>
            </div>
          </form>
        </section>
      )}
    </>
  );
}
