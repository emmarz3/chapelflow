import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Role, User } from "../types/domain";
import { api, ApiError } from "../lib/api";
import { buildDemoUser, hasPermission } from "../lib/permissions";
import { isDemoMode } from "../lib/fixtures";
import { useQueryClient } from "@tanstack/react-query";
import { disableBrowserPush } from "../lib/push";
import { clearRecentUpperRoomMedia } from "../lib/upper-room-media-cache";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  authError: string | null;
  retryAuth: () => void;
  setProfilePhoto: (url: string) => void;
  login: (
    identifier: string,
    password: string,
    role?: Role,
    otp?: string,
  ) => Promise<User>;
  logout: () => Promise<void>;
  switchDemoRole: (role: Role) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

let authBootstrapRequest: ReturnType<typeof loadCurrentUser> | null = null;

async function loadCurrentUser() {
  // A brief proxy or API interruption during page load should not strand a
  // member on the sign-in page. A 401 is an ordinary signed-out session.
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await api.get<{ data: { csrf_token: string } }>("/auth/csrf");
      return await api.get<{ data: User }>("/auth/me");
    } catch (error) {
      if (!(error instanceof ApiError) || ![0, 408, 502, 503, 504].includes(error.status) || attempt === 1)
        throw error;
      await new Promise((resolve) => window.setTimeout(resolve, 700));
    }
  }
  throw new Error("Account bootstrap did not complete.");
}

function getCurrentUserOnce() {
  if (!authBootstrapRequest) {
    authBootstrapRequest = loadCurrentUser().finally(() => {
      authBootstrapRequest = null;
    });
  }
  return authBootstrapRequest;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const authRevision = useRef(0);
  const [user, setUser] = useState<User | null>(() => {
    if (!isDemoMode) return null;
    const role = window.sessionStorage.getItem(
      "chapelflow-demo-role",
    ) as Role | null;
    return role ? buildDemoUser(role) : null;
  });
  const [loading, setLoading] = useState(!isDemoMode);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authRetry, setAuthRetry] = useState(0);
  useEffect(() => {
    if (isDemoMode) return;
    let active = true;
    const revision = authRevision.current;
    getCurrentUserOnce()
      .then((response) => {
        if (active && authRevision.current === revision) {
          setUser(response.data);
          setAuthError(null);
        }
      })
      .catch((error: unknown) => {
        if (active && authRevision.current === revision) {
          if (error instanceof ApiError && error.status === 401) setAuthError(null);
          else if (error instanceof ApiError && [0, 408, 502, 503, 504].includes(error.status))
            setAuthError("ChapelFlow's account service is temporarily unavailable. Please retry shortly.");
          else setAuthError("We could not check your account session. Please retry.");
          setUser(null);
        }
      })
      .finally(() => {
        if (active && authRevision.current === revision) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [authRetry]);
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      authError,
      setProfilePhoto(url) {
        setUser((current) => current ? { ...current, photoUrl: url } : current);
      },
      retryAuth() {
        setAuthError(null);
        setLoading(true);
        setAuthRetry((attempt) => attempt + 1);
      },
      async login(identifier, password, role = "chapel_admin", otp) {
        authRevision.current += 1;
        setAuthError(null);
        setLoading(true);
        try {
          if (isDemoMode) {
            await new Promise((resolve) => window.setTimeout(resolve, 500));
            window.sessionStorage.setItem("chapelflow-demo-role", role);
            const demoUser = buildDemoUser(role);
            setUser(demoUser);
            return demoUser;
          }
          const response = await api.post<{ data: User }>("/auth/login", {
            identifier,
            password,
            ...(otp ? { otp } : {}),
          });
          if (user && user.id !== response.data.id) await clearRecentUpperRoomMedia().catch(() => undefined);
          queryClient.clear();
          setAuthError(null);
          setUser(response.data);
          return response.data;
        } finally {
          setLoading(false);
        }
      },
      async logout() {
        authRevision.current += 1;
        if (!isDemoMode) await disableBrowserPush().catch(() => undefined);
        await clearRecentUpperRoomMedia().catch(() => undefined);
        if (isDemoMode)
          window.sessionStorage.removeItem("chapelflow-demo-role");
        queryClient.clear();
        setAuthError(null);
        setUser(null);
        setLoading(false);
        if (!isDemoMode) await api.post("/auth/logout");
      },
      switchDemoRole(role) {
        if (isDemoMode) {
          window.sessionStorage.setItem("chapelflow-demo-role", role);
          setUser(buildDemoUser(role));
        }
      },
    }),
    [user, loading, authError, queryClient],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
export { hasPermission };
