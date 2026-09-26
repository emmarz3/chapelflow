import {
  Activity,
  BarChart3,
  Bell,
  Building2,
  CalendarDays,
  Camera,
  ChevronDown,
  ClipboardCheck,
  Coins,
  FileText,
  Gauge,
  HeartHandshake,
  House,
  Image,
  MessagesSquare,
  Menu,
  MessageSquareText,
  Moon,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Radio,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  UserRound,
  Users,
  Video,
  WifiOff,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { Brand, Modal } from "../components/ui";
import { usePortalMotion } from "../components/motion/motion-system";
import { hasPermission, useAuth } from "./auth-context";
import { isDemoMode } from "../lib/fixtures";
import {
  getAuthenticatedHomePath,
  getAccountMenuItem,
  getMobilePrimaryItem,
  isStudentMember,
} from "../lib/permissions";
import type { Permission, Role, User } from "../types/domain";
import { authService, communityService, notificationService } from "../services/chapelflow";

interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
  permission?: Permission;
  roles?: Role[];
}
const navGroups: { label: string; items: NavItem[] }[] = [
  {
    label: "Overview",
    items: [
      {
        label: "Dashboard",
        path: "/app",
        icon: <Gauge />,
        permission: "dashboard:view",
      },
      { label: "The Upper Room", path: "/app/upper-room", icon: <MessagesSquare /> },
      {
        label: "Members",
        path: "/app/members",
        icon: <Users />,
        permission: "members:read",
      },
      {
        label: "Attendance",
        path: "/app/attendance",
        icon: <ClipboardCheck />,
        permission: "attendance:read",
        roles: ["super_admin", "chapel_admin"],
      },
      {
        label: "My Chapel Pass",
        path: "/app/chapel-pass",
        icon: <ShieldCheck />,
        roles: ["member"],
      },
      {
        label: "Events",
        path: "/app/events",
        icon: <CalendarDays />,
        permission: "events:read",
      },
      {
        label: "My communities",
        path: "/app/communities",
        icon: <Users />,
        permission: "community:view",
      },
      {
        label: "Prayer and care",
        path: "/app/care",
        icon: <HeartHandshake />,
      },
    ],
  },
  {
    label: "Community",
    items: [
      {
        label: "Leadership",
        path: "/app/leadership",
        icon: <ShieldCheck />,
        permission: "leadership:view",
      },
      {
        label: "Manage communities",
        path: "/app/admin/communities",
        icon: <Building2 />,
        permission: "community:manage",
      },
      {
        label: "Manage leadership",
        path: "/app/admin/leadership",
        icon: <UserRound />,
        permission: "leadership:manage",
      },
      {
        label: "Institutional accounts",
        path: "/app/admin/accounts",
        icon: <UserRound />,
        roles: ["super_admin"],
      },
      {
        label: "Service control room",
        path: "/app/admin/control-room",
        icon: <Activity />,
        roles: ["super_admin"],
      },
    ],
  },
  {
    label: "Ministry",
    items: [
      {
        label: "Workers",
        path: "/app/workers",
        icon: <UserRound />,
        permission: "workers:read",
      },
      {
        label: "Communication",
        path: "/app/communication",
        icon: <MessageSquareText />,
        permission: "communication:write",
      },
      {
        label: "Sermons & media",
        path: "/app/media",
        icon: <Video />,
        permission: "media:write",
      },
      {
        label: "Finance",
        path: "/app/finance",
        icon: <Coins />,
        permission: "finance:read",
      },
    ],
  },
  {
    label: "Operations",
    items: [
      {
        label: "Assets",
        path: "/app/assets",
        icon: <Package />,
        permission: "assets:read",
      },
      {
        label: "Analytics",
        path: "/app/analytics",
        icon: <BarChart3 />,
        permission: "analytics:read",
      },
      {
        label: "Website CMS",
        path: "/app/cms",
        icon: <FileText />,
        permission: "cms:write",
      },
      {
        label: "Branches",
        path: "/app/branches",
        icon: <Building2 />,
        permission: "branches:manage",
      },
      {
        label: "Audit log",
        path: "/app/audit",
        icon: <ShieldCheck />,
        permission: "audit:read",
      },
      { label: "Settings", path: "/app/settings", icon: <Settings /> },
    ],
  },
];

function studentNavGroups(communities: { type: string }[]): { label: string; items: NavItem[] }[] {
  const hasUnit = communities.some((community) => community.type === "unit");
  const hasFellowship = communities.some((community) => community.type !== "unit");
  return [
    {
      label: "My chapel",
      items: [
        { label: "Overview", path: "/app", icon: <Gauge />, roles: ["member"] },
        { label: "Scan attendance", path: "/app/chapel-pass", icon: <Camera />, roles: ["member"] },
        { label: "My attendance", path: "/app/my-attendance", icon: <ClipboardCheck />, roles: ["member"] },
        { label: "Chapel schedule & events", path: "/app/events", icon: <CalendarDays />, roles: ["member"] },
        { label: "Fellowships & Units", path: "/app/join-community", icon: <Users />, roles: ["member"] },
        { label: "Prayer and care", path: "/app/care", icon: <HeartHandshake />, roles: ["member"] },
        { label: "The Upper Room", path: "/app/upper-room", icon: <MessagesSquare />, roles: ["member"] },
        ...(hasFellowship ? [{ label: "My fellowship", path: "/app/communities", icon: <Users />, roles: ["member"] as Role[] }] : []),
        ...(hasUnit ? [{ label: "My chapel unit", path: "/app/communities", icon: <Building2 />, roles: ["member"] as Role[] }] : []),
      ],
    },
    {
      label: "My account",
      items: [
        { label: "My QR pass", path: "/app/identity-pass", icon: <ShieldCheck />, roles: ["member"] },
        { label: "Offerings & tithes", path: "/app/giving", icon: <Coins />, roles: ["member"] },
        { label: "Announcements", path: "/app/announcements", icon: <MessageSquareText />, roles: ["member"] },
        { label: "Notifications", path: "/app/notifications", icon: <Bell />, roles: ["member"] },
        { label: "Profile and security", path: "/app/profile/edit", icon: <UserRound />, roles: ["member"] },
        { label: "Help and support", path: "/contact", icon: <MessageSquareText />, roles: ["member"] },
      ],
    },
  ];
}

function memberAccountNavGroups(): { label: string; items: NavItem[] }[] {
  return [
    {
      label: "My account",
      items: [
        { label: "Overview", path: "/app", icon: <Gauge />, roles: ["member"] },
        { label: "Service times", path: "/service-times", icon: <CalendarDays />, roles: ["member"] },
        { label: "Chapel events", path: "/events", icon: <CalendarDays />, roles: ["member"] },
        { label: "The Upper Room", path: "/app/upper-room", icon: <MessagesSquare />, roles: ["member"] },
        { label: "Offerings & tithes", path: "/app/giving", icon: <Coins />, roles: ["member"] },
        { label: "Announcements", path: "/app/announcements", icon: <Bell />, roles: ["member"] },
        { label: "Notifications", path: "/app/notifications", icon: <Bell />, roles: ["member"] },
        { label: "Profile and security", path: "/app/profile/edit", icon: <UserRound />, roles: ["member"] },
        { label: "Help and support", path: "/contact", icon: <MessageSquareText />, roles: ["member"] },
      ],
    },
  ];
}

function operationalNavGroups(user: User): { label: string; items: NavItem[] }[] | null {
  const { role } = user;
  const overview: NavItem = { label: "Overview", path: "/app", icon: <Gauge />, roles: [role] };
  const members: NavItem = { label: "Students", path: "/app/members", icon: <Users />, permission: "members:read", roles: [role] };
  const events: NavItem = { label: "Events and programmes", path: "/app/events", icon: <CalendarDays />, permission: "events:read", roles: [role] };
  const operations: NavItem = { label: "Operations", path: "/app/operations", icon: <Activity />, roles: [role] };
  const care: NavItem = { label: "Prayer and care", path: "/app/care", icon: <HeartHandshake />, roles: [role] };
  const upperRoom: NavItem = { label: "The Upper Room", path: "/app/upper-room", icon: <MessagesSquare />, roles: [role] };
  const officialGallery: NavItem = { label: "Official gallery", path: "/app/media", icon: <Image />, permission: "media:write", roles: [role] };
  const mediaItems = hasPermission(user, "media:write") ? [officialGallery] : [];
  const giving: NavItem = { label: "Offerings & tithes", path: "/app/giving", icon: <Coins />, roles: [role] };
  const inventory: NavItem = { label: "Inventory", path: "/app/assets", icon: <Package />, permission: "assets:read", roles: [role] };
  const inventoryItems = hasPermission(user, "assets:read") ? [inventory] : [];
  if (role === "chaplain") return [{ label: "Chapel oversight", items: [overview, operations, care, upperRoom, giving, ...mediaItems, ...inventoryItems, members, events] }];
  if (role === "student_chaplain") return [{ label: "Student operations", items: [overview, operations, care, upperRoom, giving, ...mediaItems, ...inventoryItems, members, { ...events, label: "Chapel services" }] }];
  if (role === "unit_leader" || role === "fellowship_leader") {
    const label = role === "unit_leader" ? "Unit" : "Fellowship";
    return [{ label: `${label} workspace`, items: [overview, operations, care, upperRoom, giving, ...mediaItems, ...inventoryItems, { ...members, label: "Members" }, { ...events, label: "Meetings and programmes" }] }];
  }
  return null;
}

function useNetworkStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

export function ProtectedRoute({
  permission,
  roles,
}: {
  permission?: Permission;
  roles?: Role[];
}) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="route-loader" role="status">
        <span />
        <p>Opening ChapelFlow securely…</p>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  if (user.passwordChangeRequired)
    return <Navigate to="/change-password-required" replace />;
  if (roles && !roles.includes(user.role))
    return <Navigate to="/access-denied" replace />;
  if (!hasPermission(user, permission))
    return <Navigate to="/access-denied" replace />;
  return <Outlet />;
}

export function StudentOnlyRoute() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!isStudentMember(user)) return <Navigate to="/app" replace />;
  return <Outlet />;
}

export function PortalShell() {
  const { user, logout, switchDemoRole } = useAuth();
  const location = useLocation();
  const online = useNetworkStatus();
  const isStudent = isStudentMember(user);
  const isLimitedMember = user?.role === "member" && !isStudent;
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const contentRef = useRef<HTMLElement>(null);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("chapelflow-theme") || "light",
  );
  const notificationQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await notificationService.list()).data,
    enabled: Boolean(user),
    refetchInterval: 30_000,
  });
  const studentCommunities = useQuery({
    queryKey: ["communities"],
    queryFn: async () => (await communityService.mine()).data,
    enabled: isStudent,
  });
  const unreadNotifications =
    notificationQuery.data?.filter((item) => !item.read_at).length ?? 0;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("chapelflow-theme", theme);
  }, [theme]);
  useEffect(() => setMobileOpen(false), [location.pathname]);
  useEffect(() => {
    const openSearch = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener("keydown", openSearch);
    return () => window.removeEventListener("keydown", openSearch);
  }, []);
  const visibleGroups = useMemo(
    () =>
      (user?.role === "member"
        ? isStudent
          ? studentNavGroups(studentCommunities.data ?? [])
          : memberAccountNavGroups()
        : user ? operationalNavGroups(user) ?? navGroups : navGroups)
        .map((group) => ({
          ...group,
          items: group.items.filter(
            (item) =>
              hasPermission(user, item.permission) &&
              (!item.roles || Boolean(user && item.roles.includes(user.role))),
          ),
        }))
        .filter((group) => group.items.length),
    [isStudent, user, studentCommunities.data],
  );
  usePortalMotion(contentRef, sidebarRef, location.pathname);
  if (!user) return null;
  const accountMenuItem = getAccountMenuItem(user.role);
  const mobilePrimaryItem = isLimitedMember
    ? { label: "Services", path: "/service-times" }
    : getMobilePrimaryItem(user.role);
  return (
    <div
      className={`portal-shell ${collapsed ? "portal-shell--collapsed" : ""}`}
    >
      <a className="skip-link" href="#portal-content">
        Skip to content
      </a>
      {!online && (
        <div className="offline-banner" role="status">
          <WifiOff /> You are offline. Read-only content remains available;
          changes are paused.
        </div>
      )}
      <aside
        ref={sidebarRef}
        className={`sidebar ${mobileOpen ? "sidebar--open" : ""}`}
      >
        <div className="sidebar__brand">
          <Link to="/app">
            <Brand compact={collapsed} inverse />
          </Link>
          <button
            className="icon-button sidebar__mobile-close"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X />
          </button>
        </div>
        <nav aria-label="Portal navigation">
          {visibleGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <small>{collapsed ? "" : group.label}</small>
              {group.items.map((item) => (
                <NavLink
                  end={item.path === "/app"}
                  key={`${group.label}-${item.label}`}
                  to={item.path}
                  title={collapsed ? item.label : undefined}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <button
          className="sidebar__theme"
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          onClick={() => setTheme(theme === "light" ? "dark" : "light")}
        >
          {theme === "light" ? <Moon /> : <Sun />}
          <span>{theme === "light" ? "Dark theme" : "Light theme"}</span>
        </button>
        <button
          className="sidebar__collapse"
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          <span>{collapsed ? "" : "Collapse sidebar"}</span>
        </button>
      </aside>
      {mobileOpen && (
        <button
          aria-label="Close navigation overlay"
          className="sidebar-scrim"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <div className="portal-main">
        <header className="topbar">
          <button
            className="icon-button topbar__menu"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu />
          </button>
          <Link className="topbar__home-link" to="/" aria-label="Open Chapel homepage">
            <House />
            <span>Chapel homepage</span>
          </Link>
          {user.role !== "member" && <button className="global-search" onClick={() => setSearchOpen(true)}>
            <Search />
            <span>Search members, events, records…</span>
            <kbd>Ctrl K</kbd>
          </button>}
          {user.role !== "member" && <div className="topbar__context">
            <label className="context-select">
              <Building2 />
              <span className="sr-only">Active branch</span>
              <select aria-label="Active branch">
                <option>{user.branchName}</option>
                {user.role === "super_admin" && (
                  <option>Lagos Liaison Chapel</option>
                )}
              </select>
            </label>
            <label className="context-select period-select">
              <CalendarDays />
              <span className="sr-only">Reporting period</span>
              <select aria-label="Reporting period">
                <option>2026/27 Session</option>
                <option>2025/26 Session</option>
              </select>
            </label>
          </div>}
          <div className="topbar__actions">
            <button
              className="icon-button"
              aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            >
              {theme === "light" ? <Moon /> : <Sun />}
            </button>
            <button
              className="icon-button notification-button"
              aria-label="Notifications"
              onClick={() => setNotificationsOpen((value) => !value)}
            >
              <Bell />
              {unreadNotifications > 0 && <span>{unreadNotifications}</span>}
            </button>
            <button
              className="profile-button"
              onClick={() => setProfileOpen((value) => !value)}
            >
              <span className="avatar">{user.initials}</span>
              <span>
                <strong>{user.name}</strong>
                <small>{isLimitedMember ? `${user.community} account` : user.role.replaceAll("_", " ")}</small>
              </span>
              <ChevronDown />
            </button>
          </div>
          {profileOpen && (
            <div className="profile-menu">
              <Link to={accountMenuItem.path}>{accountMenuItem.label}</Link>
              {isDemoMode && (
                <label>
                  Preview role
                  <select
                    value={user.role}
                    onChange={(event) =>
                      switchDemoRole(event.target.value as Role)
                    }
                  >
                    <option value="super_admin">Super administrator</option>
                    <option value="chapel_admin">Chapel administrator</option>
                    <option value="pastor">Pastor</option>
                    <option value="worker">Worker</option>
                    <option value="attendance_usher">Attendance usher</option>
                    <option value="member">Member</option>
                  </select>
                </label>
              )}
              <button onClick={() => void logout()}>Sign out</button>
            </div>
          )}
          {notificationsOpen && (
            <NotificationPanel onClose={() => setNotificationsOpen(false)} showCommunities={isStudent} />
          )}
        </header>
        <main ref={contentRef} id="portal-content" className="portal-content">
          <Outlet />
        </main>
        <nav
          className="mobile-bottom-nav"
          aria-label="Dashboard and chapel navigation"
        >
          <NavLink to="/">
            <House />
            Home
          </NavLink>
          <NavLink
            to={mobilePrimaryItem.path}
          >
            {isLimitedMember ? <CalendarDays /> : <ClipboardCheck />}
            {mobilePrimaryItem.label}
          </NavLink>
          {isStudent ? (
            <NavLink to="/app/my-attendance"><ClipboardCheck />My attendance</NavLink>
          ) : isLimitedMember ? (
            <NavLink to="/events"><CalendarDays />Events</NavLink>
          ) : (
            <NavLink to="/app/events"><CalendarDays />Events</NavLink>
          )}
          <button onClick={() => setMobileOpen(true)}>
            <Menu />
            More
          </button>
        </nav>
        {user.role === "member" && location.pathname === "/app" && !isDemoMode && <BirthdayPrompt userId={user.id} />}
      </div>
      {user.role !== "member" && <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />}
    </div>
  );
}

function BirthdayPrompt({ userId }: { userId: string }) {
  const client = useQueryClient();
  const dismissalKey = `chapelflow-birthday-prompt-dismissed:${userId}`;
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(dismissalKey) === "1");
  const profile = useQuery({
    queryKey: ["student-profile"],
    queryFn: async () => (await authService.studentProfile()).data,
    enabled: !dismissed,
  });
  const save = useMutation({
    mutationFn: (date_of_birth: string) => authService.updateStudentProfile({ date_of_birth }),
    onSuccess: () => {
      setDismissed(true);
      void client.invalidateQueries({ queryKey: ["student-profile"] });
    },
  });
  const open = profile.isSuccess && !profile.data.date_of_birth && !dismissed;
  const defer = () => {
    sessionStorage.setItem(dismissalKey, "1");
    setDismissed(true);
  };
  return <Modal
    open={open}
    onClose={defer}
    title="When is your birthday?"
    description="Add it once so ChapelFlow can celebrate you with the chapel community. Your birth year is never shown."
    footer={<><button className="button button--ghost" type="button" onClick={defer}>Not now</button><button className="button button--primary" type="submit" form="birthday-form" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save birthday"}</button></>}
  >
    <form id="birthday-form" className="form-grid" onSubmit={(event) => {
      event.preventDefault();
      const date = String(new FormData(event.currentTarget).get("date_of_birth") || "");
      if (date) save.mutate(date);
    }}>
      <label className="field field--full"><span>Birthday</span><input name="date_of_birth" type="date" max={new Date().toISOString().slice(0, 10)} required /></label>
      {save.isError && <p className="form-error field--full">Your birthday could not be saved. Please try again.</p>}
    </form>
  </Modal>;
}

function NotificationPanel({ onClose, showCommunities }: { onClose: () => void; showCommunities: boolean }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await notificationService.list()).data,
  });
  const markRead = useMutation({
    mutationFn: notificationService.markRead,
    onSuccess: () =>
      void client.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const items = query.data ?? [];
  const unread = items.filter((item) => !item.read_at).length;
  return (
    <div className="notification-panel">
      <header>
        <div>
          <h2>Notifications</h2>
          <p>{unread} unread updates</p>
        </div>
        <button className="icon-button" onClick={onClose}>
          <X />
        </button>
      </header>
      {items.map((item) => (
        <article key={item.id}>
          <span>{item.community_id ? <Users /> : <Activity />}</span>
          <div>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
            <small>{new Date(item.created_at).toLocaleString()}</small>
          </div>
          {!item.read_at && (
            <button
              className="text-link"
              disabled={markRead.isPending}
              onClick={() => markRead.mutate(item.id)}
            >
              Mark read
            </button>
          )}
        </article>
      ))}
      {!items.length && (
        <p className="notification-panel__empty">No new notifications.</p>
      )}
      {showCommunities && <Link to="/app/communities" onClick={onClose}>Open my communities</Link>}
    </div>
  );
}

function SearchModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const [value, setValue] = useState("");
  return (
    <Modal open={open} onClose={onClose} title="Search ChapelFlow">
      <label className="command-input">
        <Search />
        <input
          autoFocus
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Search members, events, records, and pages"
        />
      </label>
      <div className="command-results">
        {value ? (
          <>
            <small>Suggested results</small>
            <Link to="/app/members" onClick={onClose}>
              <Users />
              <span>
                <strong>Search members for “{value}”</strong>
                <small>Member directory</small>
              </span>
            </Link>
            <Link to="/app/events" onClick={onClose}>
              <CalendarDays />
              <span>
                <strong>Search events for “{value}”</strong>
                <small>Events and registrations</small>
              </span>
            </Link>
          </>
        ) : (
          <>
            <small>Quick destinations</small>
            <Link to="/app/attendance" onClick={onClose}>
              <ClipboardCheck />
              <span>
                <strong>Attendance scanner</strong>
                <small>Open current check-in</small>
              </span>
            </Link>
            {hasPermission(user, "media:write") ? (
              <Link to="/app/media" onClick={onClose}>
                <Radio />
                <span>
                  <strong>Sermons and media</strong>
                  <small>Manage published media</small>
                </span>
              </Link>
            ) : (
              <Link to="/app/events" onClick={onClose}>
                <CalendarDays />
                <span>
                  <strong>Chapel events</strong>
                  <small>Review upcoming gatherings</small>
                </span>
              </Link>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

export function AccessDeniedPage() {
  const { user } = useAuth();
  const homePath = getAuthenticatedHomePath(user);
  return (
    <div className="status-page">
      <span>
        <ShieldCheck />
      </span>
      <h1>Access restricted</h1>
      <p>
        Your current role does not have permission to view this page. If your
        responsibilities have changed, ask a chapel administrator to review your
        access.
      </p>
      <Link className="button button--primary" to={homePath}>
        {user?.role === "attendance_usher"
          ? "Open attendance scanner"
          : "Return to dashboard"}
      </Link>
    </div>
  );
}
export function NotFoundPage() {
  return (
    <div className="status-page">
      <span>
        <FileText />
      </span>
      <h1>Page not found</h1>
      <p>The page may have moved, been archived, or no longer be available.</p>
      <Link className="button button--primary" to="/">
        Return home
      </Link>
    </div>
  );
}
