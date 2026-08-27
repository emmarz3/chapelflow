import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { PwaPrompt } from "../components/pwa-prompt";
import { OfflineAttendanceSync } from "../components/offline-attendance-sync";
import { ToastProvider } from "../components/ui";
import {
  AuthLayout,
  AuthNoticePage,
  ForgotPasswordPage,
  LoginPage,
  OtpPage,
  RegisterPage,
  ResetPasswordPage,
  VerifyEmailPage,
} from "../features/auth-pages";
import { AttendanceKioskPage } from "../features/attendance-kiosk";
import {
  AccessDeniedPage,
  NotFoundPage,
  PortalShell,
  ProtectedRoute,
} from "../features/portal-shell";
import {
  HomePage,
  LegalPage,
  PublicContentPage,
  PublicDetailPage,
  PublicInfoPage,
  PublicLayout,
} from "../features/public-site";

const DashboardPage = lazy(() =>
  import("../features/portal-pages").then((module) => ({
    default: module.DashboardPage,
  })),
);
const MembersPage = lazy(() =>
  import("../features/portal-pages").then((module) => ({
    default: module.MembersPage,
  })),
);
const AttendancePage = lazy(() =>
  import("../features/portal-pages").then((module) => ({
    default: module.AttendancePage,
  })),
);
const EventsPage = lazy(() =>
  import("../features/portal-pages").then((module) => ({
    default: module.EventsPage,
  })),
);
const OperationsPage = lazy(() =>
  import("../features/portal-pages").then((module) => ({
    default: module.OperationsPage,
  })),
);
const AnalyticsPage = lazy(() =>
  import("../features/portal-pages").then((module) => ({
    default: module.AnalyticsPage,
  })),
);

function RouteLoader() {
  return (
    <div className="route-loader" role="status">
      <span />
      <p>Loading page…</p>
    </div>
  );
}

export function App() {
  return (
    <ToastProvider>
      <Suspense fallback={<RouteLoader />}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/about" element={<PublicContentPage page="about" />} />
            <Route
              path="/mission"
              element={<PublicInfoPage page="mission" />}
            />
            <Route
              path="/leadership"
              element={<PublicInfoPage page="leadership" />}
            />
            <Route
              path="/service-times"
              element={<PublicInfoPage page="services" />}
            />
            <Route
              path="/events"
              element={<PublicContentPage page="events" />}
            />
            <Route
              path="/events/:eventId"
              element={<PublicDetailPage kind="event" />}
            />
            <Route
              path="/sermons"
              element={<PublicContentPage page="sermons" />}
            />
            <Route
              path="/sermons/:sermonId"
              element={<PublicDetailPage kind="sermon" />}
            />
            <Route
              path="/livestream"
              element={<PublicContentPage page="livestream" />}
            />
            <Route
              path="/giving"
              element={<PublicContentPage page="giving" />}
            />
            <Route
              path="/gallery"
              element={<PublicInfoPage page="gallery" />}
            />
            <Route path="/news" element={<PublicInfoPage page="news" />} />
            <Route
              path="/news/:articleId"
              element={<PublicDetailPage kind="article" />}
            />
            <Route
              path="/contact"
              element={<PublicInfoPage page="contact" />}
            />
            <Route path="/faq" element={<PublicInfoPage page="faq" />} />
            <Route path="/privacy" element={<LegalPage type="privacy" />} />
            <Route path="/terms" element={<LegalPage type="terms" />} />
            <Route
              path="/accessibility"
              element={<LegalPage type="accessibility" />}
            />
          </Route>

          <Route
            path="/login"
            element={
              <AuthLayout>
                <LoginPage />
              </AuthLayout>
            }
          />
          <Route
            path="/register"
            element={
              <AuthLayout>
                <RegisterPage />
              </AuthLayout>
            }
          />
          <Route
            path="/forgot-password"
            element={
              <AuthLayout>
                <ForgotPasswordPage />
              </AuthLayout>
            }
          />
          <Route
            path="/reset-password"
            element={
              <AuthLayout>
                <ResetPasswordPage />
              </AuthLayout>
            }
          />
          <Route
            path="/verify-email"
            element={
              <AuthLayout>
                <VerifyEmailPage />
              </AuthLayout>
            }
          />
          <Route
            path="/verify-otp"
            element={
              <AuthLayout>
                <OtpPage />
              </AuthLayout>
            }
          />
          <Route
            path="/account-locked"
            element={
              <AuthLayout>
                <AuthNoticePage type="locked" />
              </AuthLayout>
            }
          />
          <Route
            path="/session-expired"
            element={
              <AuthLayout>
                <AuthNoticePage type="expired" />
              </AuthLayout>
            }
          />

          <Route element={<ProtectedRoute />}>
            <Route element={<PortalShell />}>
              <Route path="/app" element={<DashboardPage />} />
              <Route element={<ProtectedRoute permission="members:read" />}>
                <Route path="/app/members" element={<MembersPage />} />
              </Route>
              <Route element={<ProtectedRoute permission="attendance:read" />}>
                <Route path="/app/attendance" element={<AttendancePage />} />
              </Route>
              <Route element={<ProtectedRoute permission="events:read" />}>
                <Route path="/app/events" element={<EventsPage />} />
              </Route>
              <Route element={<ProtectedRoute permission="workers:read" />}>
                <Route
                  path="/app/workers"
                  element={<OperationsPage module="workers" />}
                />
              </Route>
              <Route
                element={<ProtectedRoute permission="communication:write" />}
              >
                <Route
                  path="/app/communication"
                  element={<OperationsPage module="communication" />}
                />
              </Route>
              <Route element={<ProtectedRoute permission="media:write" />}>
                <Route
                  path="/app/media"
                  element={<OperationsPage module="media" />}
                />
              </Route>
              <Route element={<ProtectedRoute permission="finance:read" />}>
                <Route
                  path="/app/finance"
                  element={<OperationsPage module="finance" />}
                />
              </Route>
              <Route element={<ProtectedRoute permission="assets:read" />}>
                <Route
                  path="/app/assets"
                  element={<OperationsPage module="assets" />}
                />
              </Route>
              <Route element={<ProtectedRoute permission="analytics:read" />}>
                <Route path="/app/analytics" element={<AnalyticsPage />} />
              </Route>
              <Route element={<ProtectedRoute permission="cms:write" />}>
                <Route
                  path="/app/cms"
                  element={<OperationsPage module="cms" />}
                />
              </Route>
              <Route element={<ProtectedRoute permission="branches:manage" />}>
                <Route
                  path="/app/branches"
                  element={<OperationsPage module="branches" />}
                />
              </Route>
              <Route element={<ProtectedRoute permission="audit:read" />}>
                <Route
                  path="/app/audit"
                  element={<OperationsPage module="audit" />}
                />
              </Route>
              <Route
                path="/app/settings"
                element={<OperationsPage module="settings" />}
              />
            </Route>
          </Route>

          <Route element={<ProtectedRoute permission="attendance:read" />}>
            <Route path="/kiosk/attendance" element={<AttendanceKioskPage />} />
          </Route>

          <Route path="/access-denied" element={<AccessDeniedPage />} />
          <Route
            path="/offline"
            element={
              <div className="status-page">
                <h1>You are offline</h1>
                <p>
                  Reconnect to continue with changes. Cached read-only pages
                  remain available.
                </p>
              </div>
            }
          />
          <Route path="/404" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </Suspense>
      <OfflineAttendanceSync />
      <PwaPrompt />
    </ToastProvider>
  );
}
