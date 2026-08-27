import type {
  AttendanceRecord,
  EventSummary,
  Member,
  Metric,
} from "../types/domain";

export const dashboardMetrics: Metric[] = [
  {
    label: "Checked in today",
    value: "842",
    change: "68% of expected attendance",
    trend: "up",
  },
  {
    label: "Active members",
    value: "2,418",
    change: "42 joined this semester",
    trend: "up",
  },
  {
    label: "Worker coverage",
    value: "94%",
    change: "3 open duty positions",
    trend: "neutral",
  },
  {
    label: "Pending follow-ups",
    value: "18",
    change: "7 require attention today",
    trend: "down",
  },
];

export const attendanceTrend = [
  { week: "Jul 13", attendance: 718 },
  { week: "Jul 20", attendance: 752 },
  { week: "Jul 27", attendance: 734 },
  { week: "Aug 3", attendance: 801 },
  { week: "Aug 10", attendance: 776 },
  { week: "Aug 17", attendance: 829 },
  { week: "Aug 24", attendance: 842 },
];

export const members: Member[] = [
  {
    id: "m1",
    name: "Temiloluwa Akin",
    identifier: "CU/23/CSC/041",
    email: "temiloluwa@example.edu.ng",
    programme: "Computer Science",
    level: "300",
    department: "Media",
    status: "active",
    attendanceRate: 92,
    lastSeen: "2026-08-24",
  },
  {
    id: "m2",
    name: "Chisom Nwosu",
    identifier: "CU/24/BUS/118",
    email: "chisom@example.edu.ng",
    programme: "Business Administration",
    level: "200",
    department: "Choir",
    status: "active",
    attendanceRate: 86,
    lastSeen: "2026-08-24",
  },
  {
    id: "m3",
    name: "Aisha Balogun",
    identifier: "CU/22/MLS/064",
    email: "aisha@example.edu.ng",
    programme: "Medical Laboratory Science",
    level: "400",
    department: "Ushering",
    status: "follow_up",
    attendanceRate: 48,
    lastSeen: "2026-07-27",
  },
  {
    id: "m4",
    name: "Samuel Femi",
    identifier: "CU/25/ARC/012",
    email: "samuel@example.edu.ng",
    programme: "Architecture",
    level: "100",
    department: "None",
    status: "active",
    attendanceRate: 78,
    lastSeen: "2026-08-24",
  },
  {
    id: "m5",
    name: "Amarachi Ude",
    identifier: "CU/23/NUR/029",
    email: "amarachi@example.edu.ng",
    programme: "Nursing",
    level: "300",
    department: "Prayer",
    status: "inactive",
    attendanceRate: 31,
    lastSeen: "2026-06-21",
  },
];

export const recentAttendance: AttendanceRecord[] = [
  {
    id: "a1",
    memberName: "Temiloluwa Akin",
    identifier: "CU/23/CSC/041",
    time: "09:06",
    method: "qr",
    status: "present",
  },
  {
    id: "a2",
    memberName: "Chisom Nwosu",
    identifier: "CU/24/BUS/118",
    time: "09:05",
    method: "kiosk",
    status: "present",
  },
  {
    id: "a3",
    memberName: "Samuel Femi",
    identifier: "CU/25/ARC/012",
    time: "09:04",
    method: "manual",
    status: "present",
  },
  {
    id: "a4",
    memberName: "Amaka Peters",
    identifier: "CU/22/ECO/077",
    time: "09:03",
    method: "qr",
    status: "duplicate",
  },
];

export const events: EventSummary[] = [
  {
    id: "e1",
    title: "Freshers Welcome Service",
    date: "2026-09-06",
    time: "09:00",
    venue: "University Chapel",
    registered: 486,
    capacity: 650,
    visibility: "public",
  },
  {
    id: "e2",
    title: "Workers Leadership Retreat",
    date: "2026-09-12",
    time: "10:00",
    venue: "Senate Chamber",
    registered: 82,
    capacity: 100,
    visibility: "private",
  },
  {
    id: "e3",
    title: "Evening of Worship",
    date: "2026-09-18",
    time: "17:00",
    venue: "University Auditorium",
    registered: 721,
    capacity: 1000,
    visibility: "public",
  },
];

export const isDemoMode = import.meta.env.VITE_DATA_MODE === "demo";
