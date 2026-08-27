import {
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { z } from "zod";
import { Brand, Button, Field } from "../components/ui";
import { useAuth } from "./auth-context";
import type { Role } from "../types/domain";
import { ApiError } from "../lib/api";
import { isDemoMode } from "../lib/fixtures";
import { authService } from "../services/chapelflow";

const loginSchema = z.object({
  identifier: z
    .string()
    .min(3, "Enter your email, matric number, or staff ID."),
  password: z.string().min(8, "Password must contain at least 8 characters."),
});

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-layout">
      <aside className="auth-visual">
        <img src="/chapel-hero.png" alt="" />
        <div className="auth-visual__shade" />
        <Link to="/">
          <Brand inverse />
        </Link>
        <blockquote>
          “A community where faith becomes the foundation for purpose,
          character, and service.”
        </blockquote>
        <p>Chrisland University Chapel · Abeokuta</p>
      </aside>
      <main className="auth-main">
        <Link className="auth-back" to="/">
          <ArrowLeft size={17} /> Back to chapel website
        </Link>
        {children}
      </main>
    </div>
  );
}

export function LoginPage() {
  const { user, login, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [role, setRole] = useState<Role>("chapel_admin");
  if (user) return <Navigate to="/app" replace />;
  const reason = new URLSearchParams(location.search).get("reason");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const parsed = loginSchema.safeParse({
      identifier: form.get("identifier"),
      password: form.get("password"),
    });
    if (!parsed.success) {
      setError(
        parsed.error.issues[0]?.message || "Check the form and try again.",
      );
      return;
    }
    try {
      await login(parsed.data.identifier, parsed.data.password, role);
      navigate("/app");
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Sign in failed. Please try again.",
      );
    }
  }
  return (
    <div className="auth-card">
      <div className="auth-heading">
        <span className="auth-icon">
          <LockKeyhole />
        </span>
        <p className="eyebrow">Welcome back</p>
        <h1>Sign in to ChapelFlow</h1>
        <p>Access your chapel account and continue where you left off.</p>
      </div>
      {reason === "expired" && (
        <div className="inline-alert">
          Your session ended securely. Sign in to continue.
        </div>
      )}
      <form onSubmit={submit} noValidate>
        <Field
          name="identifier"
          label="Email, matric number, or staff ID"
          autoComplete="username"
          placeholder="Enter your identifier"
          required
        />
        <label className="field">
          <span>
            Password <em>Required</em>
          </span>
          <span className="password-wrap">
            <input
              name="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Enter your password"
              required
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? <EyeOff /> : <Eye />}
            </button>
          </span>
        </label>
        <div className="form-row">
          <label className="check-label">
            <input type="checkbox" name="remember" /> Keep me signed in
          </label>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        {isDemoMode && (
          <label className="field">
            <span>Preview role</span>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as Role)}
            >
              <option value="super_admin">Super administrator</option>
              <option value="chapel_admin">Chapel administrator</option>
              <option value="pastor">Pastor</option>
              <option value="worker">Worker</option>
              <option value="member">Member</option>
            </select>
            <small>
              Demo mode only. Production roles come from the authenticated
              session.
            </small>
          </label>
        )}
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <Button className="full-button" type="submit" loading={loading}>
          Sign in <ArrowRight size={18} />
        </Button>
      </form>
      <p className="auth-switch">
        New to ChapelFlow? <Link to="/register">Create an account</Link>
      </p>
      <div className="security-note">
        <ShieldCheck />
        <span>
          <strong>Your account is protected</strong>Credentials are sent
          securely and authentication tokens are never stored in browser
          storage.
        </span>
      </div>
    </div>
  );
}

const registrationSteps = ["Account", "Profile", "Community", "Consent"];
export function RegisterPage() {
  const [step, setStep] = useState(0);
  const [complete, setComplete] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  async function next(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const merged = {
      ...values,
      ...Object.fromEntries(
        [...form.entries()].map(([key, value]) => [key, String(value)]),
      ),
    };
    setValues(merged);
    if (step < registrationSteps.length - 1) {
      setStep((value) => value + 1);
      return;
    }
    setSubmitting(true);
    try {
      if (!isDemoMode) await authService.register(merged);
      setComplete(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Registration could not be completed.",
      );
    } finally {
      setSubmitting(false);
    }
  }
  if (complete)
    return (
      <div className="auth-card auth-success">
        <span className="auth-icon auth-icon--success">
          <Check />
        </span>
        <p className="eyebrow">Registration received</p>
        <h1>Check your email to continue.</h1>
        <p>
          We sent a verification link to{" "}
          <strong>{values.email || "your email address"}</strong>. The link
          expires in 30 minutes.
        </p>
        <Link className="button button--primary full-button" to="/login">
          Return to sign in
        </Link>
      </div>
    );
  return (
    <div className="auth-card auth-card--wide">
      <div className="auth-heading">
        <p className="eyebrow">Join the community</p>
        <h1>Create your ChapelFlow account</h1>
        <p>
          Use your university information so the chapel team can verify your
          membership.
        </p>
      </div>
      <ol className="stepper" aria-label="Registration progress">
        {registrationSteps.map((label, index) => (
          <li className={index <= step ? "active" : ""} key={label}>
            <span>{index < step ? <Check /> : index + 1}</span>
            <small>{label}</small>
          </li>
        ))}
      </ol>
      <AnimatePresence mode="wait">
        <motion.form
          key={step}
          onSubmit={(event) => void next(event)}
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -16 }}
        >
          {step === 0 && (
            <div className="form-grid">
              <Field
                name="email"
                defaultValue={values.email}
                label="University email"
                type="email"
                autoComplete="email"
                placeholder="name@example.edu.ng"
                required
              />
              <Field
                name="password"
                defaultValue={values.password}
                label="Create password"
                type="password"
                autoComplete="new-password"
                hint="Use at least 8 characters, including a number."
                minLength={8}
                required
              />
            </div>
          )}
          {step === 1 && (
            <div className="form-grid">
              <Field
                name="firstName"
                defaultValue={values.firstName}
                label="First name"
                autoComplete="given-name"
                required
              />
              <Field
                name="lastName"
                defaultValue={values.lastName}
                label="Last name"
                autoComplete="family-name"
                required
              />
              <Field
                name="identifier"
                defaultValue={values.identifier}
                label="Matric number or staff ID"
                required
              />
              <Field
                name="phone"
                defaultValue={values.phone}
                label="Phone number"
                type="tel"
                autoComplete="tel"
              />
            </div>
          )}
          {step === 2 && (
            <div className="form-grid">
              <label className="field">
                <span>Member type</span>
                <select name="memberType" defaultValue={values.memberType}>
                  <option>Student</option>
                  <option>Staff</option>
                  <option>Community member</option>
                </select>
              </label>
              <Field
                name="programme"
                defaultValue={values.programme}
                label="Programme or department"
              />
              <label className="field">
                <span>Academic level</span>
                <select name="level" defaultValue={values.level}>
                  <option>100</option>
                  <option>200</option>
                  <option>300</option>
                  <option>400</option>
                  <option>500</option>
                  <option>Not applicable</option>
                </select>
              </label>
              <label className="field">
                <span>Service team interest</span>
                <select name="department" defaultValue={values.department}>
                  <option>Not yet decided</option>
                  <option>Choir</option>
                  <option>Ushering</option>
                  <option>Media</option>
                  <option>Prayer</option>
                  <option>Protocol</option>
                </select>
              </label>
            </div>
          )}
          {step === 3 && (
            <div className="consent-box">
              <h2>Privacy and consent</h2>
              <p>
                ChapelFlow uses your information to manage membership,
                attendance, events, communications, and chapel participation.
                Read the <Link to="/privacy">Privacy Policy</Link> and{" "}
                <Link to="/terms">Terms of Use</Link> before continuing.
              </p>
              <label className="check-label">
                <input name="acceptedPolicies" type="checkbox" required /> I
                have read and accept the Privacy Policy and Terms of Use.
              </label>
              <label className="check-label">
                <input name="programmeUpdates" type="checkbox" /> I would like
                to receive non-essential chapel programme updates.
              </label>
            </div>
          )}
          {error && (
            <div className="form-error" role="alert">
              {error}
            </div>
          )}
          <div className="step-actions">
            {step > 0 && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => setStep((value) => value - 1)}
              >
                Back
              </Button>
            )}
            <Button type="submit" loading={submitting}>
              {step === registrationSteps.length - 1
                ? "Submit registration"
                : "Continue"}{" "}
              <ArrowRight size={18} />
            </Button>
          </div>
        </motion.form>
      </AnimatePresence>
      <p className="auth-switch">
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (!isDemoMode)
        await authService.forgotPassword(
          String(new FormData(event.currentTarget).get("identifier")),
        );
      setSent(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The request could not be submitted.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="auth-card">
      {sent ? (
        <div className="auth-success">
          <span className="auth-icon auth-icon--success">
            <Mail />
          </span>
          <p className="eyebrow">Check your inbox</p>
          <h1>Password reset email sent.</h1>
          <p>
            If an account matches that information, a secure reset link will
            arrive shortly.
          </p>
          <Link className="button button--secondary full-button" to="/login">
            Return to sign in
          </Link>
        </div>
      ) : (
        <>
          <div className="auth-heading">
            <span className="auth-icon">
              <Mail />
            </span>
            <p className="eyebrow">Account recovery</p>
            <h1>Reset your password</h1>
            <p>
              Enter your email or account identifier. We will send instructions
              if a matching account exists.
            </p>
          </div>
          <form onSubmit={(event) => void submit(event)}>
            <Field
              name="identifier"
              label="Email or account identifier"
              required
            />
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <Button type="submit" className="full-button" loading={loading}>
              Send reset instructions
            </Button>
          </form>
        </>
      )}
    </div>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [complete, setComplete] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const token = params.get("token") || "";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password"));
    const confirmation = String(data.get("confirmation"));
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (password !== confirmation) {
      setError("The passwords do not match.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (!isDemoMode) await authService.resetPassword(token, password);
      setComplete(true);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The password could not be reset.",
      );
    } finally {
      setLoading(false);
    }
  }
  if (!token && !isDemoMode) return <AuthNoticePage type="invalid-link" />;
  return (
    <div className="auth-card">
      {complete ? (
        <div className="auth-success">
          <span className="auth-icon auth-icon--success">
            <Check />
          </span>
          <h1>Password updated.</h1>
          <p>You can now sign in with your new password.</p>
          <Link className="button button--primary full-button" to="/login">
            Continue to sign in
          </Link>
        </div>
      ) : (
        <>
          <div className="auth-heading">
            <span className="auth-icon">
              <LockKeyhole />
            </span>
            <p className="eyebrow">Secure reset</p>
            <h1>Choose a new password</h1>
            <p>Use a unique password you do not use for another service.</p>
          </div>
          <form onSubmit={(event) => void submit(event)}>
            <Field
              name="password"
              label="New password"
              type="password"
              minLength={8}
              required
            />
            <Field
              name="confirmation"
              label="Confirm new password"
              type="password"
              minLength={8}
              required
            />
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <Button type="submit" className="full-button" loading={loading}>
              Update password
            </Button>
          </form>
        </>
      )}
    </div>
  );
}

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const [state, setState] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const token = params.get("token") || "";
  useEffect(() => {
    if (isDemoMode) {
      setState("success");
      return;
    }
    if (!token) {
      setState("error");
      return;
    }
    authService
      .verifyEmail(token)
      .then(() => setState("success"))
      .catch(() => setState("error"));
  }, [token]);
  return (
    <div className="auth-card auth-success">
      <span
        className={`auth-icon ${state === "success" ? "auth-icon--success" : ""}`}
      >
        {state === "success" ? <Check /> : <Mail />}
      </span>
      <p className="eyebrow">Email verification</p>
      <h1>
        {state === "loading"
          ? "Verifying your email…"
          : state === "success"
            ? "Email verified."
            : "This verification link is invalid."}
      </h1>
      <p>
        {state === "loading"
          ? "Please keep this page open."
          : state === "success"
            ? "Your account is ready for the next onboarding step."
            : "The link may have expired or already been used. Request a new link from sign in."}
      </p>
      {state !== "loading" && (
        <Link className="button button--primary full-button" to="/login">
          Continue to sign in
        </Link>
      )}
    </div>
  );
}

export function OtpPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = String(
      new FormData(event.currentTarget).get("code"),
    ).replaceAll(" ", "");
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the six-digit verification code.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      if (!isDemoMode)
        await authService.verifyOtp(params.get("identifier") || "", code);
      navigate("/app");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "The verification code was not accepted.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="auth-card">
      <div className="auth-heading">
        <span className="auth-icon">
          <ShieldCheck />
        </span>
        <p className="eyebrow">Account verification</p>
        <h1>Enter your verification code</h1>
        <p>Use the six-digit code sent to your configured contact channel.</p>
      </div>
      <form noValidate onSubmit={(event) => void submit(event)}>
        <Field
          name="code"
          label="Verification code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          maxLength={6}
          required
        />
        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        <Button type="submit" className="full-button" loading={loading}>
          Verify account
        </Button>
      </form>
    </div>
  );
}

export function AuthNoticePage({
  type,
}: {
  type: "locked" | "expired" | "invalid-link";
}) {
  const copy =
    type === "locked"
      ? [
          "Account temporarily locked",
          "Too many unsuccessful attempts were detected. Wait before trying again or contact the approved support channel.",
        ]
      : type === "expired"
        ? [
            "Your session has ended",
            "For your protection, sign in again to continue working in ChapelFlow.",
          ]
        : [
            "Invalid or expired link",
            "Request a new secure link and avoid forwarding it to another person.",
          ];
  return (
    <div className="auth-card auth-success">
      <span className="auth-icon">
        <ShieldCheck />
      </span>
      <p className="eyebrow">Account security</p>
      <h1>{copy[0]}</h1>
      <p>{copy[1]}</p>
      <Link
        className="button button--primary full-button"
        to={type === "locked" ? "/forgot-password" : "/login"}
      >
        {type === "locked" ? "Recover account" : "Return to sign in"}
      </Link>
    </div>
  );
}
