import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { PwaPrompt } from "../components/pwa-prompt";
import { OfflineAttendanceSync } from "../components/offline-attendance-sync";
import { RouteScrollManager } from "../components/route-scroll";
import { ToastProvider } from "../components/ui";
import { CookieConsent } from "../components/cookie-consent";

import { ErrorBoundary, ERROR_REGISTRY } from "../features/error-pages";
import { markAppPerformance } from "../lib/performance";

const ChapelFlowIntro = lazy(() =>
  import("../components/intro/chapelflow-intro").then((module) => ({
    default: module.ChapelFlowIntro,
  })),
);
const AccountProfilePage = lazy(() =>
  import("../features/profile-photo").then((module) => ({ default: module.AccountProfilePage })),
);
const AccessDeniedPage = lazy(() => import("../features/portal-shell").then((module) => ({ default: module.AccessDeniedPage })));
const NotFoundPage = lazy(() => import("../features/portal-shell").then((module) => ({ default: module.NotFoundPage })));
const PortalShell = lazy(() => import("../features/portal-shell").then((module) => ({ default: module.PortalShell })));
const ProtectedRoute = lazy(() => import("../features/portal-shell").then((module) => ({ default: module.ProtectedRoute })));
const StudentOnlyRoute = lazy(() => import("../features/portal-shell").then((module) => ({ default: module.StudentOnlyRoute })));

const AuthLayout = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.AuthLayout })));
const AuthNoticePage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.AuthNoticePage })));
const ForgotPasswordPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.ForgotPasswordPage })));
const LoginPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.LoginPage })));
const OtpPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.OtpPage })));
const RequiredPasswordChangePage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.RequiredPasswordChangePage })));
const RegisterPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.RegisterPage })));
const ResetPasswordPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.ResetPasswordPage })));
const SuperAdminSetupPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.SuperAdminSetupPage })));
const VerifyEmailPage = lazy(() => import("../features/auth-pages").then((module) => ({ default: module.VerifyEmailPage })));

const AttendanceKioskPage = lazy(() => import("../features/attendance-kiosk").then((module) => ({ default: module.AttendanceKioskPage })));
const StudentAttendancePassPage = lazy(() => import("../features/student-attendance-pass").then((module) => ({ default: module.StudentAttendancePassPage })));
const UsherAttendancePage = lazy(() => import("../features/usher-attendance").then((module) => ({ default: module.UsherAttendancePage })));
const InstitutionalAccountsPage = lazy(() => import("../features/institutional-accounts").then((module) => ({ default: module.InstitutionalAccountsPage })));
const LaunchResetPage = lazy(() => import("../features/launch-reset").then((module) => ({ default: module.LaunchResetPage })));
const AdminOperationsPage = lazy(() => import("../features/admin-operations").then((module) => ({ default: module.AdminOperationsPage })));
const RoleOperationsPage = lazy(() => import("../features/role-operations").then((module) => ({ default: module.RoleOperationsPage })));
const GivingPage = lazy(() => import("../features/giving-page").then((module) => ({ default: module.GivingPage })));
const UpperRoomPage = lazy(() => import("../features/upper-room").then((module) => ({ default: module.UpperRoomPage })));
const CommunitySafetyPage = lazy(() => import("../features/moderation").then((module) => ({ default: module.CommunitySafetyPage })));
const NotificationSettingsPage = lazy(() => import("../features/notification-settings").then((module) => ({ default: module.NotificationSettingsPage })));
const GalleryPage = lazy(() => import("../features/gallery-page").then((module) => ({ default: module.GalleryPage })));
const AdvertisePage = lazy(() => import("../features/advertising").then((module) => ({ default: module.AdvertisePage })));
const AdvertisingAdminPage = lazy(() => import("../features/advertising").then((module) => ({ default: module.AdvertisingAdminPage })));
const AdsDirectoryPage = lazy(() => import("../features/advertising").then((module) => ({ default: module.AdsDirectoryPage })));
const CommunityOversightPage = lazy(() => import("../features/leadership-channel").then((module) => ({ default: module.CommunityOversightPage })));
const LeadershipNoticesPage = lazy(() => import("../features/leadership-channel").then((module) => ({ default: module.LeadershipNoticesPage })));
const LeadershipNoticePage = lazy(() => import("../features/leadership-channel").then((module) => ({ default: module.LeadershipNoticePage })));

const StudentAttendanceHistoryPage = lazy(() => import("../features/student-portal").then((module) => ({ default: module.StudentAttendanceHistoryPage })));
const StudentAnnouncementsPage = lazy(() => import("../features/student-portal").then((module) => ({ default: module.StudentAnnouncementsPage })));
const StudentIdentityPassPage = lazy(() => import("../features/student-portal").then((module) => ({ default: module.StudentIdentityPassPage })));
const StudentJoinCommunityPage = lazy(() => import("../features/student-portal").then((module) => ({ default: module.StudentJoinCommunityPage })));
const StudentNotificationsPage = lazy(() => import("../features/student-portal").then((module) => ({ default: module.StudentNotificationsPage })));
const StudentProfilePage = lazy(() => import("../features/student-portal").then((module) => ({ default: module.StudentProfilePage })));
const StudentProfileEditorPage = lazy(() => import("../features/student-profile-editor").then((module) => ({ default: module.StudentProfileEditorPage })));

const AboutPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.AboutPage })));
const FellowshipPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.FellowshipPage })));
const UnitsPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.UnitsPage })));
const HomePage = lazy(() => import("../features/public-site").then((module) => ({ default: module.HomePage })));
const LegalPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.LegalPage })));
const PublicContentPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.PublicContentPage })));
const PublicDetailPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.PublicDetailPage })));
const PublicInfoPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.PublicInfoPage })));
const PublicLayout = lazy(() => import("../features/public-site").then((module) => ({ default: module.PublicLayout })));
const StudentLeadersPage = lazy(() => import("../features/public-site").then((module) => ({ default: module.StudentLeadersPage })));

const ErrorIndexPage = lazy(() => import("../features/error-pages").then((module) => ({ default: module.ErrorIndexPage })));
const ErrorPage = lazy(() => import("../features/error-pages").then((module) => ({ default: module.ErrorPage })));
const ErrorRoutePage = lazy(() => import("../features/error-pages").then((module) => ({ default: module.ErrorRoutePage })));

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
  const location = useLocation();

  useEffect(() => {
    markAppPerformance("application_shell_ready");
  }, []);

  return (
    <>
      {location.pathname === "/" && (
        <Suspense fallback={null}>
          <ChapelFlowIntro />
        </Suspense>
      )}
      <RouteScrollManager />
      <ToastProvider>
        <ErrorBoundary>
          <Suspense fallback={<RouteLoader />}>
            <Routes>
            <Route element={<PublicLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route
                path="/about"
                element={<AboutPage />}
              />
              <Route path="/fellowship" element={<FellowshipPage />} />
              <Route path="/units" element={<UnitsPage />} />
              <Route path="/student-leaders" element={<StudentLeadersPage />} />
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
                element={<GalleryPage />}
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
                <Route path="/app/account" element={<AccountProfilePage />} />
                <Route path="/app/giving" element={<GivingPage />} />
                <Route path="/app/upper-room" element={<UpperRoomPage />} />
                <Route path="/app/ads" element={<AdsDirectoryPage />} />
                <Route element={<ProtectedRoute roles={["member"]} />}>
                  <Route path="/app/advertise" element={<AdvertisePage />} />
                </Route>
                <Route path="/app/community-safety" element={<CommunitySafetyPage />} />
                <Route path="/app/notifications" element={<StudentNotificationsPage />} />
                <Route path="/app/notification-settings" element={<NotificationSettingsPage />} />
                <Route element={<ProtectedRoute roles={["super_admin", "chaplain", "student_chaplain"]} />}>
                  <Route path="/app/community-oversight" element={<CommunityOversightPage />} />
                  <Route path="/app/community-oversight/:groupId" element={<CommunityOversightPage />} />
                </Route>
                <Route element={<ProtectedRoute roles={["super_admin", "chaplain", "student_chaplain", "unit_leader", "fellowship_leader", "member"]} />}>
                  <Route path="/app/leadership-notices" element={<LeadershipNoticesPage />} />
                  <Route path="/app/leadership-notices/:noticeId" element={<LeadershipNoticePage />} />
                </Route>
                <Route element={<ProtectedRoute roles={["chaplain", "student_chaplain", "unit_leader", "fellowship_leader"]} />}>
                  <Route path="/app/operations" element={<RoleOperationsPage />} />
                </Route>
                <Route element={<ProtectedRoute permission="members:read" />}>
                  <Route path="/app/members" element={<MembersPage />} />
                </Route>
                <Route
                  element={
                    <ProtectedRoute
                      permission="attendance:read"
                      roles={["super_admin", "chapel_admin", "chaplain", "student_chaplain"]}
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
                    path="/app/admin/dashboard"
                    element={<DashboardPage />}
                  />
                  <Route
                    path="/app/admin/accounts"
                    element={<InstitutionalAccountsPage />}
                  />
                  <Route path="/app/admin/advertising" element={<AdvertisingAdminPage />} />
                  <Route
                    path="/app/admin/launch-reset"
                    element={<LaunchResetPage />}
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
              element={<ErrorPage code="CF-NET-003" />}
            />
            <Route path="/404" element={<NotFoundPage />} />

            {/* Dedicated error page for every live error, each with its code */}
            <Route path="/error" element={<ErrorIndexPage />} />
            {Object.keys(ERROR_REGISTRY).map((code) => (
              <Route
                key={code}
                path={`/error/${code.toLowerCase()}`}
                element={<ErrorPage code={code} />}
              />
            ))}
            <Route path="/error/:code" element={<ErrorRoutePage />} />

            <Route path="*" element={<Navigate to="/404" replace />} />
          </Routes>
        </Suspense>
        </ErrorBoundary>
        <CookieConsent />
        <OfflineAttendanceSync />
        <PwaPrompt />
      </ToastProvider>
    </>
  );
}
