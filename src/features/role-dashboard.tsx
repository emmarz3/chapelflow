import { Building2, CalendarDays, ClipboardCheck, Users } from "lucide-react";
import { Link, Navigate } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { useAuth } from "./auth-context";

const copy = {
  chaplain: { eyebrow: "Chapel oversight", title: "Chaplain workspace", description: "Review chapel-wide ministry activity without technical system controls.", cards: [["Operations", "Live attendance, follow-up and chapel analytics", "/app/operations", ClipboardCheck], ["Students", "Review pastoral participation and follow-up", "/app/members", Users], ["Programmes", "Review upcoming chapel events", "/app/events", CalendarDays]] },
  student_chaplain: { eyebrow: "Student operations", title: "Student Chapel workspace", description: "Coordinate student-facing chapel activity within your approved scope.", cards: [["Operations", "Student activity, attendance and approved coordination", "/app/operations", ClipboardCheck], ["Students", "View registered student participation", "/app/members", Users], ["Programmes", "Plan approved student events", "/app/events", CalendarDays]] },
  unit_leader: { eyebrow: "Assigned unit", title: "Unit workspace", description: "Manage only the chapel unit assigned to your account.", cards: [["Unit operations", "Member register, announcements and reports", "/app/operations", Building2], ["Unit members", "View members within your assigned unit", "/app/members", Users], ["Meetings", "Review unit programmes and meeting dates", "/app/events", CalendarDays]] },
  fellowship_leader: { eyebrow: "Assigned fellowship", title: "Fellowship workspace", description: "Manage only the fellowship assigned to your account.", cards: [["Fellowship operations", "Member register, announcements and reports", "/app/operations", Building2], ["Fellowship members", "View members within your fellowship", "/app/members", Users], ["Meetings", "Review fellowship programmes and meeting dates", "/app/events", CalendarDays]] },
} as const;

export function RoleDashboardPage() {
  const { user } = useAuth();
  if (user?.role === "attendance_usher") return <Navigate to="/usher/attendance" replace />;
  const content = user && user.role in copy ? copy[user.role as keyof typeof copy] : null;
  if (!content) return null;
  return <><PageHeader eyebrow={content.eyebrow} title={content.title} description={content.description} /><section className="role-workspace-grid">{content.cards.map(([title, detail, path, Icon]) => <Link key={title} to={path} className="role-workspace-card"><Icon /><div><h2>{title}</h2><p>{detail}</p></div></Link>)}</section><section className="panel"><header className="panel-heading"><div><h2>Attendance and care</h2><p>Official service attendance remains controlled by authorized attendance sessions and the server-side scope of your account.</p></div><ClipboardCheck /></header></section></>;
}
