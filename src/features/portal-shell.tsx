import {
  Activity,
  BarChart3,
  Bell,
  Building2,
  CalendarDays,
  ChevronDown,
  ClipboardCheck,
  Coins,
  FileText,
  Gauge,
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
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Brand, Modal } from "../components/ui";
import { hasPermission, useAuth } from "./auth-context";
import { isDemoMode } from "../lib/fixtures";
import type { Permission, Role } from "../types/domain";

interface NavItem {
  label: string;
  path: string;
  icon: ReactNode;
  permission?: Permission;
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
      },
      {
        label: "Events",
        path: "/app/events",
        icon: <CalendarDays />,
        permission: "events:read",
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

export function ProtectedRoute({ permission }: { permission?: Permission }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="route-loader" role="status">
        <span />
        <p>Opening ChapelFlow securely…</p>
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  if (!hasPermission(user, permission))
    return <Navigate to="/access-denied" replace />;
  return <Outlet />;
}

export function PortalShell() {
  const { user, logout, switchDemoRole } = useAuth();
  const location = useLocation();
  const online = useNetworkStatus();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("chapelflow-theme") || "light",
  );
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
      navGroups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) =>
            hasPermission(user, item.permission),
          ),
        }))
        .filter((group) => group.items.length),
    [user],
  );
  if (!user) return null;
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
      <aside className={`sidebar ${mobileOpen ? "sidebar--open" : ""}`}>
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
                  key={item.path}
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
          <button className="global-search" onClick={() => setSearchOpen(true)}>
            <Search />
            <span>Search members, events, records…</span>
            <kbd>Ctrl K</kbd>
          </button>
          <div className="topbar__context">
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
          </div>
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
              <span>3</span>
            </button>
            <button
              className="profile-button"
              onClick={() => setProfileOpen((value) => !value)}
            >
              <span className="avatar">{user.initials}</span>
              <span>
                <strong>{user.name}</strong>
                <small>{user.role.replaceAll("_", " ")}</small>
              </span>
              <ChevronDown />
            </button>
          </div>
          {profileOpen && (
            <div className="profile-menu">
              <Link to="/app/settings">Profile and settings</Link>
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
                    <option value="member">Member</option>
                  </select>
                </label>
              )}
              <button onClick={() => void logout()}>Sign out</button>
            </div>
          )}
          {notificationsOpen && (
            <NotificationPanel onClose={() => setNotificationsOpen(false)} />
          )}
        </header>
        <motion.main
          id="portal-content"
          key={location.pathname}
          className="portal-content"
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
        >
          <Outlet />
        </motion.main>
        <nav
          className="mobile-bottom-nav"
          aria-label="Primary mobile navigation"
        >
          <NavLink end to="/app">
            <Gauge />
            Home
          </NavLink>
          <NavLink to="/app/attendance">
            <ClipboardCheck />
            Attendance
          </NavLink>
          <NavLink to="/app/events">
            <CalendarDays />
            Events
          </NavLink>
          <button onClick={() => setMobileOpen(true)}>
            <Menu />
            More
          </button>
        </nav>
      </div>
      <SearchModal open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}

function NotificationPanel({ onClose }: { onClose: () => void }) {
  const items = [
    {
      icon: <ClipboardCheck />,
      title: "Attendance session active",
      body: "842 people have checked in.",
      time: "2 min",
    },
    {
      icon: <Users />,
      title: "New member registrations",
      body: "7 registrations are ready for review.",
      time: "18 min",
    },
    {
      icon: <Activity />,
      title: "Worker roster updated",
      body: "Three open positions remain for Sunday.",
      time: "1 hr",
    },
  ];
  return (
    <div className="notification-panel">
      <header>
        <div>
          <h2>Notifications</h2>
          <p>3 unread updates</p>
        </div>
        <button className="icon-button" onClick={onClose}>
          <X />
        </button>
      </header>
      {items.map((item) => (
        <article key={item.title}>
          <span>{item.icon}</span>
          <div>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
            <small>{item.time} ago</small>
          </div>
        </article>
      ))}
      <Link to="/app/communication" onClick={onClose}>
        View notification centre
      </Link>
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
      <Link className="button button--primary" to="/app">
        Return to dashboard
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
