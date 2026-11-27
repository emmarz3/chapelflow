import { lazy, Suspense } from "react";
import { LoadingState } from "../components/ui";
import { isDemoMode } from "../lib/fixtures";
import { isStudentMember } from "../lib/permissions";
import { useAuth } from "./auth-context";

const StudentDashboardPage = lazy(() =>
  import("./student-dashboard").then((module) => ({ default: module.StudentDashboardPage })),
);
const MemberAccountHomePage = lazy(() =>
  import("./member-account-home").then((module) => ({ default: module.MemberAccountHomePage })),
);
const RoleDashboardPage = lazy(() =>
  import("./role-dashboard").then((module) => ({ default: module.RoleDashboardPage })),
);
const LiveDashboardPage = lazy(() =>
  import("./live-pages").then((module) => ({ default: module.LiveDashboardPage })),
);
const DemoDashboardPage = lazy(() =>
  import("./portal-pages").then((module) => ({ default: module.DemoDashboardPage })),
);

export function DashboardPage() {
  const { user } = useAuth();
  const isLeaderRole = ["chaplain", "student_chaplain", "assistant_student_chaplain", "hostel_coordinator", "unit_leader", "fellowship_leader", "attendance_usher"].includes(user?.role ?? "");
  const dashboard = user?.role === "member"
    ? (isStudentMember(user) ? <StudentDashboardPage /> : <MemberAccountHomePage />)
    : isLeaderRole
      ? <RoleDashboardPage />
      : isDemoMode
        ? <DemoDashboardPage />
        : <LiveDashboardPage />;

  return (
    <Suspense fallback={<LoadingState label="Loading your dashboard" />}>
      {dashboard}
    </Suspense>
  );
}
