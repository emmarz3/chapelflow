import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { PwaPrompt } from "../components/pwa-prompt";
import { OfflineAttendanceSync } from "../components/offline-attendance-sync";
import { ChapelFlowIntro } from "../components/intro/chapelflow-intro";
import { RouteMotionLayer } from "../components/motion/motion-system";
import { ToastProvider } from "../components/ui";
import {
  AuthLayout,
  AuthNoticePage,
  ForgotPasswordPage,
  LoginPage,
  OtpPage,
  RequiredPasswordChangePage,
  RegisterPage,
  ResetPasswordPage,
  SuperAdminSetupPage,
  VerifyEmailPage,
} from "../features/auth-pages";
import { AttendanceKioskPage } from "../features/attendance-kiosk";
import { StudentAttendancePassPage } from "../features/student-attendance-pass";
import { UsherAttendancePage } from "../features/usher-attendance";
import { InstitutionalAccountsPage } from "../features/institutional-accounts";
import { AdminOperationsPage } from "../features/admin-operations";
import { RoleOperationsPage } from "../features/role-operations";
import { GivingPage } from "../features/giving-page";
import {
  StudentAttendanceHistoryPage,
  StudentAnnouncementsPage,
  StudentIdentityPassPage,
  StudentJoinCommunityPage,
  StudentNotificationsPage,
  StudentProfilePage,
} from "../features/student-portal";
import { StudentProfileEditorPage } from "../features/student-profile-editor";
import {
  AccessDeniedPage,
  NotFoundPage,
  PortalShell,
  ProtectedRoute,
  StudentOnlyRoute,
} from "../features/portal-shell";
import {
  AboutPage,
  CookieConsent,
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
const CommunitiesPage = lazy(() =>
  import("../features/community-pages").then((module) => ({
    default: module.CommunitiesPage,
  })),
);
const CommunityWorkspacePage = lazy(() =>
  import("../features/community-pages").then((module) => ({
    default: module.CommunityWorkspacePage,
  })),
);
const LeadershipDirectoryPage = lazy(() =>
  import("../features/community-pages").then((module) => ({
    default: module.LeadershipDirectoryPage,
  })),
);
const CommunityAdminPage = lazy(() =>
  import("../features/community-pages").then((module) => ({
    default: module.CommunityAdminPage,
  })),
);
const LeadershipAdminPage = lazy(() =>
  import("../features/community-pages").then((module) => ({
    default: module.LeadershipAdminPage,
  })),
);
const FinanceWorkspacePage = lazy(() =>
  import("../features/ministry-workspaces").then((module) => ({
    default: module.FinanceWorkspacePage,
  })),
);
const VolunteerWorkspacePage = lazy(() =>
  import("../features/ministry-workspaces").then((module) => ({
    default: module.VolunteerWorkspacePage,
  })),
);
const CareWorkspacePage = lazy(() =>
  import("../features/ministry-workspaces").then((module) => ({
    default: module.CareWorkspacePage,
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
    <>
      <ChapelFlowIntro />
      <RouteMotionLayer />
      <ToastProvider>
        <Suspense fallback={<RouteLoader />}>
          <Routes>
            <Route element={<PublicLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route
                path="/about"
                element={<AboutPage />}
              />
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
              <Route
                path="/gallery/:galleryId"
                element={<PublicDetailPage kind="gallery" />}
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
              <Route path="/cookies" element={<LegalPage type="cookies" />} />
              <Route path="/community-standards" element={<LegalPage type="community" />} />
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
              path="/setup/admin"
              element={
                <AuthLayout>
                  <SuperAdminSetupPage />
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
              path="/change-password-required"
              element={
                <AuthLayout>
                  <RequiredPasswordChangePage />
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
                <Route path="/app/giving" element={<GivingPage />} />
                <Route element={<ProtectedRoute roles={["chaplain", "student_chaplain", "unit_leader", "fellowship_leader"]} />}>
                  <Route path="/app/operations" element={<RoleOperationsPage />} />
                </Route>
                <Route element={<ProtectedRoute permission="members:read" />}>
                  <Route path="/app/members" element={<MembersPage />} />
                </Route>
                <Route
                  element={
                    <ProtectedRoute
                      permission="attendance:write"
                      roles={["super_admin", "chapel_admin"]}
                    />
                  }
                >
                  <Route path="/app/attendance" element={<AttendancePage />} />
                </Route>
                <Route element={<StudentOnlyRoute />}>
                  <Route
                    path="/app/chapel-pass"
                    element={<StudentAttendancePassPage />}
                  />
                  <Route
                    path="/app/my-attendance"
                    element={<StudentAttendanceHistoryPage />}
                  />
                  <Route
                    path="/app/identity-pass"
                    element={<StudentIdentityPassPage />}
                  />
                  <Route path="/app/profile" element={<StudentProfilePage />} />
                  <Route path="/app/join-community" element={<StudentJoinCommunityPage />} />
                </Route>
                <Route element={<ProtectedRoute roles={["member"]} />}>
                  <Route path="/app/profile/edit" element={<StudentProfileEditorPage />} />
                  <Route path="/app/announcements" element={<StudentAnnouncementsPage />} />
                  <Route path="/app/notifications" element={<StudentNotificationsPage />} />
                </Route>
                <Route element={<ProtectedRoute permission="events:read" />}>
                  <Route path="/app/events" element={<EventsPage />} />
                </Route>
                <Route element={<ProtectedRoute permission="community:view" />}>
                  <Route
                    path="/app/communities"
                    element={<CommunitiesPage />}
                  />
                  <Route
                    path="/app/communities/:slug"
                    element={<CommunityWorkspacePage />}
                  />
                </Route>
                <Route path="/app/care" element={<CareWorkspacePage />} />
                <Route
                  element={<ProtectedRoute permission="leadership:view" />}
                >
                  <Route
                    path="/app/leadership"
                    element={<LeadershipDirectoryPage />}
                  />
                </Route>
                <Route
                  element={<ProtectedRoute permission="community:manage" />}
                >
                  <Route
                    path="/app/admin/communities"
                    element={<CommunityAdminPage />}
                  />
                </Route>
                <Route
                  element={<ProtectedRoute permission="leadership:manage" />}
                >
                  <Route
                    path="/app/admin/leadership"
                    element={<LeadershipAdminPage />}
                  />
                </Route>
                <Route element={<ProtectedRoute roles={["super_admin"]} />}>
                  <Route
                    path="/app/admin/accounts"
                    element={<InstitutionalAccountsPage />}
                  />
                  <Route
                    path="/app/admin/control-room"
                    element={<AdminOperationsPage />}
                  />
                </Route>
                <Route element={<ProtectedRoute permission="workers:read" />}>
                  <Route
                    path="/app/workers"
                    element={<VolunteerWorkspacePage />}
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
                    element={<FinanceWorkspacePage />}
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
                <Route
                  element={<ProtectedRoute permission="branches:manage" />}
                >
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
                <Route element={<ProtectedRoute roles={["super_admin", "chapel_admin"]} />}>
                  <Route
                    path="/app/settings"
                    element={<OperationsPage module="settings" />}
                  />
                </Route>
              </Route>
            </Route>

            <Route
              element={
                <ProtectedRoute
                  permission="attendance:write"
                  roles={["super_admin", "chapel_admin"]}
                />
              }
            >
              <Route
                path="/kiosk/attendance"
                element={<AttendanceKioskPage />}
              />
            </Route>
            <Route element={<ProtectedRoute roles={["attendance_usher"]} />}>
              <Route
                path="/usher/attendance"
                element={<UsherAttendancePage />}
              />
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
        <CookieConsent />
        <OfflineAttendanceSync />
        <PwaPrompt />
      </ToastProvider>
    </>
  );
}
