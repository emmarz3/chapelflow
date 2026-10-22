import { Component, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  FileText,
  Info,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

export type ErrorSeverity = "info" | "warning" | "danger";

export interface ErrorDefinition {
  /** Stable, human-readable error code shown on the page (e.g. CF-NET-001). */
  code: string;
  title: string;
  /** The meaning of the error, shown to the user. */
  description: string;
  severity: ErrorSeverity;
  actionLabel?: string;
  /** Route the primary action navigates to. Omit for a "try again" reload. */
  actionPath?: string;
}

/**
 * Every live error ChapelFlow can surface after deployment, each with a
 * unique error code and its meaning. Add new errors here to get a page.
 */
export const ERROR_REGISTRY: Record<string, ErrorDefinition> = {
  /* Network & connectivity */
  "CF-NET-001": {
    code: "CF-NET-001",
    title: "Network error",
    description:
      "We couldn't reach the ChapelFlow server. Check your internet connection and try again.",
    severity: "danger",
    actionLabel: "Try again",
  },
  "CF-NET-002": {
    code: "CF-NET-002",
    title: "Request timed out",
    description:
      "The request took too long to complete. Please try again.",
    severity: "warning",
    actionLabel: "Try again",
  },
  "CF-NET-003": {
    code: "CF-NET-003",
    title: "You're offline",
    description:
      "Reconnect to continue with your changes. Cached read-only pages remain available.",
    severity: "warning",
    actionLabel: "Return home",
    actionPath: "/",
  },

  /* Authentication */
  "CF-AUTH-400": {
    code: "CF-AUTH-400",
    title: "Sign-in failed",
    description:
      "The details you entered didn't match our records. Check your email or matriculation number and password.",
    severity: "danger",
    actionLabel: "Return to sign in",
    actionPath: "/login",
  },
  "CF-AUTH-401": {
    code: "CF-AUTH-401",
    title: "Session expired",
    description:
      "For your protection, sign in again to continue working in ChapelFlow.",
    severity: "warning",
    actionLabel: "Sign in again",
    actionPath: "/login",
  },
  "CF-AUTH-401-R": {
    code: "CF-AUTH-401-R",
    title: "Session ended",
    description:
      "Your session has ended and could not be renewed. Sign in again to continue.",
    severity: "warning",
    actionLabel: "Sign in again",
    actionPath: "/login",
  },
  "CF-AUTH-429": {
    code: "CF-AUTH-429",
    title: "Account temporarily locked",
    description:
      "Too many unsuccessful attempts were detected. Wait before trying again or contact the approved support channel.",
    severity: "danger",
    actionLabel: "Recover account",
    actionPath: "/forgot-password",
  },
  "CF-AUTH-400-MFA": {
    code: "CF-AUTH-400-MFA",
    title: "Verification code invalid",
    description:
      "The one-time security code was incorrect or has expired. Enter the current code from your authenticator app.",
    severity: "danger",
    actionLabel: "Return to sign in",
    actionPath: "/login",
  },
  "CF-AUTH-409": {
    code: "CF-AUTH-409",
    title: "Setup already complete",
    description:
      "Super Admin setup is already complete. Sign in with the existing account.",
    severity: "warning",
    actionLabel: "Sign in",
    actionPath: "/login",
  },
  "CF-AUTH-400-RST": {
    code: "CF-AUTH-400-RST",
    title: "Reset link invalid",
    description:
      "This password-reset link is invalid or has expired. Request a new one to continue.",
    severity: "danger",
    actionLabel: "Request new link",
    actionPath: "/forgot-password",
  },

  /* Authorization */
  "CF-403": {
    code: "CF-403",
    title: "Access restricted",
    description:
      "Your current role does not have permission to view this page. If your responsibilities have changed, ask a chapel administrator to review your access.",
    severity: "danger",
    actionLabel: "Return to dashboard",
    actionPath: "/app",
  },
  "CF-403-API": {
    code: "CF-403-API",
    title: "Action not permitted",
    description:
      "You don't have permission to perform this action. Contact a chapel administrator if you believe this is a mistake.",
    severity: "danger",
    actionLabel: "Return to dashboard",
    actionPath: "/app",
  },

  /* Resource & routing */
  "CF-404": {
    code: "CF-404",
    title: "Page not found",
    description:
      "The page may have moved, been archived, or no longer be available.",
    severity: "info",
    actionLabel: "Return home",
    actionPath: "/",
  },
  "CF-404-API": {
    code: "CF-404-API",
    title: "Record not found",
    description:
      "The requested record could not be found. It may have been removed or the link is incorrect.",
    severity: "info",
    actionLabel: "Return home",
    actionPath: "/",
  },
  "CF-405": {
    code: "CF-405",
    title: "Action not supported",
    description: "This action isn't supported on this resource.",
    severity: "warning",
    actionLabel: "Return home",
    actionPath: "/",
  },

  /* Validation */
  "CF-400": {
    code: "CF-400",
    title: "Information needs correcting",
    description:
      "Some of the information you entered needs correcting before we can continue.",
    severity: "warning",
    actionLabel: "Go back",
    actionPath: "/",
  },

  /* Server & infrastructure */
  "CF-500": {
    code: "CF-500",
    title: "Something went wrong",
    description:
      "An unexpected error occurred. Please try again later. If the problem persists, contact the chapel support channel.",
    severity: "danger",
    actionLabel: "Return home",
    actionPath: "/",
  },
  "CF-502": {
    code: "CF-502",
    title: "Server unreachable",
    description:
      "The chapel server is currently unreachable. Please try again shortly.",
    severity: "danger",
    actionLabel: "Try again",
  },
  "CF-503": {
    code: "CF-503",
    title: "Service unavailable",
    description:
      "ChapelFlow is temporarily unavailable while we perform maintenance. Please try again shortly.",
    severity: "warning",
    actionLabel: "Try again",
  },
  "CF-504": {
    code: "CF-504",
    title: "Server timeout",
    description:
      "The chapel server took too long to respond. Please try again.",
    severity: "warning",
    actionLabel: "Try again",
  },
  "CF-501": {
    code: "CF-501",
    title: "Feature unavailable",
    description:
      "This feature isn't available in the connected backend yet.",
    severity: "info",
    actionLabel: "Return home",
    actionPath: "/",
  },

  /* Feature-specific */
  "CF-ATT-400": {
    code: "CF-ATT-400",
    title: "Attendance unavailable",
    description:
      "A chapel branch must be assigned to this account before attendance sessions can be viewed.",
    severity: "warning",
    actionLabel: "Return to dashboard",
    actionPath: "/app",
  },
  "CF-GIVE-FAIL": {
    code: "CF-GIVE-FAIL",
    title: "Offering failed",
    description:
      "Your offering could not be processed. Please check your payment details and try again.",
    severity: "danger",
    actionLabel: "Try again",
  },
  "CF-UPLOAD-400": {
    code: "CF-UPLOAD-400",
    title: "Upload failed",
    description:
      "The file couldn't be uploaded. Check that it's an accepted image or document type and within the size limit.",
    severity: "danger",
    actionLabel: "Try again",
  },
};

const FALLBACK = ERROR_REGISTRY["CF-404"]!;

export function getError(code: string | undefined | null): ErrorDefinition {
  if (code) {
    const normalized = code.toUpperCase();
    if (ERROR_REGISTRY[normalized]) return ERROR_REGISTRY[normalized];
  }
  return FALLBACK;
}

const severityIcon: Record<ErrorSeverity, typeof Info> = {
  info: Info,
  warning: AlertTriangle,
  danger: ShieldAlert,
};

const severityBadge: Record<ErrorSeverity, string> = {
  info: "badge--purple",
  warning: "badge--warning",
  danger: "badge--danger",
};

export function ErrorPage({ code }: { code: string | undefined }) {
  const error = getError(code);
  const Icon = severityIcon[error.severity];
  return (
    <div className="status-page error-page">
      <span className={`error-page__icon error-page__icon--${error.severity}`}>
        <Icon />
      </span>
      <span className={`badge ${severityBadge[error.severity]} error-page__code`}>
        {error.code}
      </span>
      <h1>{error.title}</h1>
      <p>{error.description}</p>
      <div className="error-page__actions">
        {error.actionPath ? (
          <Link className="button button--primary" to={error.actionPath}>
            {error.actionLabel}
          </Link>
        ) : (
          <button
            className="button button--primary"
            onClick={() => window.location.reload()}
            type="button"
          >
            {error.actionLabel ?? "Try again"}
          </button>
        )}
        <Link className="button button--ghost" to="/">
          Return home
        </Link>
      </div>
    </div>
  );
}

export function ErrorRoutePage() {
  const { code } = useParams<{ code: string }>();
  return <ErrorPage code={code} />;
}

export function ErrorIndexPage() {
  const errors = Object.values(ERROR_REGISTRY);
  return (
    <div className="error-index">
      <header className="error-index__header">
        <span className="error-index__icon">
          <ShieldCheck />
        </span>
        <h1>Error pages</h1>
        <p>
          Every error ChapelFlow can show after deployment, with its code and
          meaning. Use the code when reporting an issue to the chapel support
          channel.
        </p>
      </header>
      <ul className="error-index__list">
        {errors.map((error) => (
          <li key={error.code}>
            <Link to={`/error/${error.code.toLowerCase()}`}>
              <span className={`badge ${severityBadge[error.severity]}`}>
                {error.code}
              </span>
              <span className="error-index__item">
                <strong>{error.title}</strong>
                <small>{error.description}</small>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * Catches render crashes anywhere in the app and shows the CF-500 error
 * page instead of a blank screen.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, info: unknown) {
    console.error("ChapelFlow render error", error, info);
  }

  render() {
    if (this.state.hasError) return <ErrorPage code="CF-500" />;
    return this.props.children;
  }
}

export { FileText };
