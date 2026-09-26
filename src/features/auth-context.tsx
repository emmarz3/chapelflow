import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Role, User } from "../types/domain";
import { api } from "../lib/api";
import { buildDemoUser, hasPermission } from "../lib/permissions";
import { isDemoMode } from "../lib/fixtures";
import { useQueryClient } from "@tanstack/react-query";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
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

function loadCurrentUser() {
  return api.get<{ data: User }>("/auth/me");
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
  const [user, setUser] = useState<User | null>(() => {
    if (!isDemoMode) return null;
    const role = window.sessionStorage.getItem(
      "chapelflow-demo-role",
    ) as Role | null;
    return role ? buildDemoUser(role) : null;
  });
  const [loading, setLoading] = useState(!isDemoMode);
  useEffect(() => {
    if (isDemoMode) return;
    let active = true;
    getCurrentUserOnce()
      .then((response) => {
        if (active) setUser(response.data);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async login(identifier, password, role = "chapel_admin", otp) {
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
          queryClient.clear();
          setUser(response.data);
          return response.data;
        } finally {
          setLoading(false);
        }
      },
      async logout() {
        await queryClient.cancelQueries();
        try {
          if (!isDemoMode) await api.post("/auth/logout");
        } finally {
          if (isDemoMode)
            window.sessionStorage.removeItem("chapelflow-demo-role");
          queryClient.clear();
          setUser(null);
        }
      },
      switchDemoRole(role) {
        if (isDemoMode) {
          window.sessionStorage.setItem("chapelflow-demo-role", role);
          setUser(buildDemoUser(role));
        }
      },
    }),
    [user, loading, queryClient],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
export { hasPermission };
