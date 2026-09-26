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
import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { Button, Field } from "../components/ui";
import { useAuthMotion } from "../components/motion/motion-system";
import { useAuth } from "./auth-context";
import type { Role } from "../types/domain";
import { ApiError, api } from "../lib/api";
import { isDjangoBackend } from "../lib/backend";
import { isDemoMode } from "../lib/fixtures";
import { getAuthenticatedHomePath } from "../lib/permissions";
import { authService, communityService } from "../services/chapelflow";

const loginSchema = z.object({
  identifier: z
    .string()
    .min(3, "Enter your email, matric number, or staff ID."),
  password: z.string().min(8, "Password must contain at least 8 characters."),
});

const adminSetupSchema = z
  .object({
    first_name: z.string().trim().min(1, "Enter your first name."),
    last_name: z.string().trim().min(1, "Enter your last name."),
    email: z.string().email("Enter a valid email address."),
    password: z.string().min(12, "Use at least 12 characters."),
    confirm_password: z.string(),
  })
  .refine((values) => values.password === values.confirm_password, {
    message: "Passwords do not match.",
    path: ["confirm_password"],
  });

export function SuperAdminSetupPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const form = new FormData(event.currentTarget);
    const parsed = adminSetupSchema.safeParse(Object.fromEntries(form));
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message || "Check the form and try again.");
      return;
    }
    setLoading(true);
    try {
      const payload = {
        first_name: parsed.data.first_name,
        last_name: parsed.data.last_name,
        email: parsed.data.email,
        password: parsed.data.password,
      };
      await api.post("/auth/setup/super-admin", payload);
      window.location.assign("/app");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the account.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="auth-heading">
        <span className="auth-icon"><ShieldCheck /></span>
        <p className="eyebrow">One-time setup</p>
        <h1>Create the Super Admin</h1>
        <p>Create the first local administrator, then continue directly to the full dashboard.</p>
      </div>
      <form onSubmit={submit} noValidate>
        <Field name="first_name" label="First name" required autoComplete="given-name" />
        <Field name="last_name" label="Last name" required autoComplete="family-name" />
        <Field name="email" label="Admin email" type="email" required autoComplete="email" />
        <Field name="password" label="Password" type="password" required minLength={12} autoComplete="new-password" />
        <Field name="confirm_password" label="Confirm password" type="password" required minLength={12} autoComplete="new-password" />
        <div className="inline-alert">This setup page works only in local development and closes after the first Super Admin is created.</div>
        {error && <div className="form-error" role="alert">{error}</div>}
        <Button className="full-button" type="submit" loading={loading}>
          Create account and open dashboard <ArrowRight size={18} />
        </Button>
      </form>
      <p className="auth-switch">Already created it? <Link to="/login">Sign in</Link></p>
    </div>
  );
}

export function AuthLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const rootRef = useRef<HTMLDivElement>(null);
  const registration = location.pathname === "/register";
  useAuthMotion(rootRef, location.pathname);
  return (
    <div className={`auth-layout auth-layout--${registration ? "register" : "login"}`} ref={rootRef}>
      <aside className="auth-visual">
        <img
          src={registration ? "/chapelflow-auth-register-visual.png" : "/chapelflow-auth-login-visual.png"}
          alt="Students gathered at Chrisland University Chapel"
        />
        <div className="auth-visual__shade" />
      </aside>
      <main className="auth-main">
        <div className="auth-main__bar"><Link className="auth-back" to="/"><ArrowLeft size={17} /> Back to chapel website</Link><span><ShieldCheck size={15} /> Your information is secure</span></div>
        {children}
        <p className="auth-main__signature">Chrisland University Chapel<br /><span>Nurturing faith. Shaping lives. Impacting Nigeria.</span></p>
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
  if (user?.mfaRequired) return <MfaEnrollment />;
  if (user?.passwordChangeRequired)
    return <Navigate to="/change-password-required" replace />;
  if (user)
    return (
      <Navigate
        to={getAuthenticatedHomePath(user)}
        replace
      />
    );
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
      const authenticated = await login(
        parsed.data.identifier,
        parsed.data.password,
        role,
        String(form.get("otp") || ""),
      );
      navigate(getAuthenticatedHomePath(authenticated));
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
      {reason === "password-changed" && (
        <div className="inline-alert">
          Password changed successfully. Sign in with your new password.
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
        {isDjangoBackend && (
          <Field
            name="otp"
            label="Authenticator code (if enabled)"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
          />
        )}
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
              <option value="attendance_usher">Attendance usher</option>
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

function MfaEnrollment() {
  const { logout } = useAuth();
  const [setup, setSetup] = useState<{
    secret: string;
    qr_code_base64: string | null;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function start() {
    setLoading(true);
    setError("");
    try {
      setSetup(
        (
          await api.post<{
            data: { secret: string; qr_code_base64: string | null };
          }>("/auth/mfa/enroll", {})
        ).data,
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not start authenticator setup.",
      );
    } finally {
      setLoading(false);
    }
  }
  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/mfa/confirm", {
        otp: String(new FormData(event.currentTarget).get("otp")),
      });
      window.location.assign("/app");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not verify the code.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="auth-card">
      <h1>Protect your account</h1>
      <p>
        Your role requires an authenticator before you can access chapel
        records.
      </p>
      {!setup ? (
        <Button onClick={() => void start()} loading={loading}>
          Set up authenticator
        </Button>
      ) : (
        <form onSubmit={confirm}>
          <p>
            Scan this code in your authenticator app, or enter the setup key
            manually.
          </p>
          {setup.qr_code_base64 && (
            <img
              src={`data:image/png;base64,${setup.qr_code_base64}`}
              alt="Authenticator setup QR code"
              width={240}
              height={240}
            />
          )}
          <p>
            <code>{setup.secret}</code>
          </p>
          <Field
            name="otp"
            label="Six-digit code"
            required
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
          />
          <Button type="submit" loading={loading}>
            Verify and continue
          </Button>
        </form>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <Button variant="ghost" onClick={() => void logout()}>
        Sign out
      </Button>
    </div>
  );
}

const registrationSteps = ["Account", "Profile", "Membership", "Consent"];
const academicLevels = ["JUPEB", "100", "200", "300", "400", "500", "600"];

function registrationPayload(values: Record<string, string>) {
  return {
    ...values,
    acceptedPolicies: values.acceptedPolicies === "on",
    programmeUpdates: values.programmeUpdates === "on",
  };
}

function registrationError(caught: unknown) {
  if (caught instanceof ApiError && caught.fieldErrors) {
    const messages = Object.entries(caught.fieldErrors)
      .flatMap(([field, errors]) => errors.map((message) => `${field === "non_field_errors" ? "Registration" : field.replaceAll("_", " ")}: ${message}`));
    if (messages.length) return messages.join(" ");
  }
  return caught instanceof Error ? caught.message : "Registration could not be completed.";
}

export function RegisterPage() {
  const [step, setStep] = useState(0);
  const [complete, setComplete] = useState(false);
  const [verificationRequired, setVerificationRequired] = useState(true);
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [memberType, setMemberType] = useState("Student");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const communities = useQuery({
    queryKey: ["public-communities", "registration"],
    queryFn: async () => (await communityService.publicList()).data,
    enabled: step === 2 && !isDjangoBackend,
    staleTime: 5 * 60_000,
  });
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
      if (!isDemoMode) {
        const response = await authService.register(
          registrationPayload(merged),
        );
        setVerificationRequired(response.data.verificationRequired);
        setApprovalRequired(Boolean(response.data.approvalRequired));
      }
      setComplete(true);
    } catch (caught) {
      setError(registrationError(caught));
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
        <h1>
          {approvalRequired
            ? "Your registration is awaiting approval."
            : verificationRequired
              ? "Check your email to continue."
              : "Your account is ready."}
        </h1>
        <p>
          {approvalRequired ? (
            "The chapel administration will verify your student information before your account can sign in."
          ) : verificationRequired ? (
            <>
              We sent a verification link to{" "}
              <strong>{values.email || "your email address"}</strong>. The link
              expires in 30 minutes.
            </>
          ) : (
            memberType === "Student"
              ? "Sign in with your email or matric number to open your ChapelFlow account."
              : "Sign in with the email address you registered to open your ChapelFlow account."
          )}
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
          Choose the registration type that matches you. Student information is
          requested only for student accounts.
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
              <label className="field field--full">
                <span>Registration type</span>
                <select
                  name="memberType"
                  value={memberType}
                  onChange={(event) => setMemberType(event.target.value)}
                >
                  <option value="Student">Student</option>
                  <option value="Staff">Staff</option>
                  <option value="Guest">Guest</option>
                </select>
              </label>
              <Field
                name="email"
                defaultValue={values.email}
                label={
                  memberType === "Student"
                    ? "University email"
                    : memberType === "Staff"
                      ? "Work email"
                      : "Email address"
                }
                type="email"
                autoComplete="email"
                placeholder={memberType === "Guest" ? "name@example.com" : "name@example.edu.ng"}
                required
              />
              <Field
                name="password"
                defaultValue={values.password}
                label="Create password"
                type="password"
                autoComplete="new-password"
                hint="Use at least 10 characters. Avoid common passwords or personal details."
                minLength={10}
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
              {memberType === "Student" && (
                <Field
                  name="identifier"
                  defaultValue={values.identifier}
                  label="Matric number or staff ID"
                  hint="Use your university matric number, for example CU/2026/001."
                  pattern="[A-Za-z]{2,6}/[0-9]{2,4}/[0-9]{3,6}"
                  required
                />
              )}
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
              {isDjangoBackend ? (
                <>
                  <p className="form-note">
                    {memberType === "Student"
                      ? "Student records are organized by academic level."
                      : memberType === "Staff"
                        ? "Staff registration uses your email address. A staff ID is not required."
                        : "Guest registration uses your email address. No university ID is required."}
                  </p>
                  {memberType === "Student" && (
                    <label className="field">
                      <span>Academic level</span>
                      <select name="level" defaultValue={values.level || ""} required>
                        <option value="" disabled>Select your current level</option>
                        {academicLevels.map((level) => (
                          <option key={level} value={level}>
                            {level === "JUPEB" ? level : `${level} Level`}
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                </>
              ) : (
                <>
                  <Field
                    name="programme"
                    defaultValue={values.programme}
                    label="Programme or department"
                  />
                  <label className="field">
                    <span>Academic level</span>
                    <select name="level" defaultValue={values.level}>
                      {academicLevels.map((level) => (
                        <option key={level}>{level}</option>
                      ))}
                      <option>Not applicable</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>Chapel unit</span>
                    <select
                      name="unitCommunityId"
                      defaultValue={values.unitCommunityId || ""}
                      disabled={communities.isPending || communities.isError}
                      required
                    >
                      <option value="" disabled>
                        {communities.isPending
                          ? "Loading units…"
                          : "Select your unit"}
                      </option>
                      {communities.data
                        ?.filter((community) => community.type === "unit")
                        .map((community) => (
                          <option key={community.id} value={community.id}>
                            {community.name}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Campus fellowship</span>
                    <select
                      name="fellowshipCommunityId"
                      defaultValue={values.fellowshipCommunityId || ""}
                      disabled={communities.isPending || communities.isError}
                      required
                    >
                      <option value="" disabled>
                        {communities.isPending
                          ? "Loading fellowships…"
                          : "Select your fellowship"}
                      </option>
                      {communities.data
                        ?.filter(
                          (community) => community.type === "campus_fellowship",
                        )
                        .map((community) => (
                          <option key={community.id} value={community.id}>
                            {community.name}
                          </option>
                        ))}
                    </select>
                  </label>
                  {communities.isError && (
                    <div className="form-error" role="alert">
                      <span>Community options could not be loaded.</span>
                      <button
                        type="button"
                        className="text-link"
                        disabled={communities.isFetching}
                        onClick={() => void communities.refetch()}
                      >
                        {communities.isFetching
                          ? "Trying againâ€¦"
                          : "Try again"}
                      </button>
                    </div>
                  )}
                </>
              )}
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
              {!isDjangoBackend && (
                <label className="check-label">
                  <input name="programmeUpdates" type="checkbox" /> I would like
                  to receive non-essential chapel programme updates.
                </label>
              )}
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
  return (
    <div className="auth-card">
      <div className="auth-heading">
        <span className="auth-icon">
          <Mail />
        </span>
        <p className="eyebrow">Account recovery</p>
        <h1>Contact the Super Admin</h1>
        <p>
          Ask the ChapelFlow Super Admin to reset your account. They will give
          you a temporary password that must be changed immediately after you
          sign in.
        </p>
      </div>
      <div className="security-note">
        <ShieldCheck />
        <p>
          Your existing password cannot be viewed by anyone. The Super Admin
          can only replace it with a temporary password.
        </p>
      </div>
      <Link className="button button--secondary full-button" to="/login">
        Return to sign in
      </Link>
    </div>
  );
}

export function RequiredPasswordChangePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!user) return <Navigate to="/login" replace />;
  if (!user.passwordChangeRequired) return <Navigate to="/app" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const currentPassword = String(data.get("currentPassword"));
    const nextPassword = String(data.get("nextPassword"));
    const confirmation = String(data.get("confirmation"));
    if (nextPassword.length < 8) {
      setError("Use at least 8 characters for your new password.");
      return;
    }
    if (nextPassword !== confirmation) {
      setError("The new passwords do not match.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await authService.changePassword(currentPassword, nextPassword);
      await logout();
      navigate("/login?reason=password-changed", { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The password could not be changed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="auth-heading">
        <span className="auth-icon"><LockKeyhole /></span>
        <p className="eyebrow">Temporary password</p>
        <h1>Create your private password</h1>
        <p>You must replace the temporary password before opening ChapelFlow.</p>
      </div>
      <form onSubmit={(event) => void submit(event)}>
        <Field name="currentPassword" label="Temporary password" type="password" required autoComplete="current-password" />
        <Field name="nextPassword" label="New password" type="password" minLength={8} required autoComplete="new-password" />
        <Field name="confirmation" label="Confirm new password" type="password" minLength={8} required autoComplete="new-password" />
        {error && <div className="form-error" role="alert">{error}</div>}
        <Button type="submit" className="full-button" loading={loading}>Save new password</Button>
      </form>
    </div>
  );
}

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [complete, setComplete] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const token = params.get("token") || "";
  const setupToken = params.get("setup") || "";
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
      if (!isDemoMode) {
        if (setupToken) await authService.setupPassword(setupToken, password);
        else
          await authService.resetPassword(
            token,
            password,
            params.get("uid") || undefined,
          );
      }
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
  if (!token && !setupToken && !isDemoMode)
    return <AuthNoticePage type="invalid-link" />;
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
