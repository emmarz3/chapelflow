import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Navigate, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "../features/auth-context";
import { LoginPage } from "../features/auth-pages";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProtectedRoute } from "../features/portal-shell";

vi.mock("../components/motion/motion-system", () => ({
  useAuthMotion: () => {},
  usePortalMotion: () => {},
  useReducedMotionPreference: () => true,
}));

vi.mock("../components/motion/completion-animation", () => ({
  useCompletionAnimation: () => ({ playRegister: () => {} }),
}));

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

function AuthenticatedDashboard() {
  const { loading, user } = useAuth();
  if (loading) return <p>Opening dashboard</p>;
  return user ? <h1>Member dashboard</h1> : <Navigate to="/login" replace />;
}

function DashboardSignOut() {
  const { logout } = useAuth();
  return <button onClick={() => void logout()}>Sign out</button>;
}

describe("login", () => {
  it("shows secure validation without identifying an account", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthProvider>
            <LoginPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await user.type(screen.getByLabelText(/email, matric number/i), "x");
    await user.type(screen.getByLabelText(/^password/i), "short");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(screen.getByText(/enter your email/i)).toBeInTheDocument();
  });

  it("provides an accessible password visibility control", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <AuthProvider>
            <LoginPage />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const password = screen.getByLabelText(/^password/i);
    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: /show password/i }));
    expect(password).toHaveAttribute("type", "text");
  });

  it.each([
    { role: "MEMBER", path: "/app" },
    { role: "SUPER_ADMIN", path: "/app/admin/dashboard" },
  ])("opens the $role dashboard after sign-in", async ({ role, path }) => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/me/"))
        return Promise.resolve(jsonResponse({ detail: "Unauthenticated." }, 401));
      if (url.endsWith("/auth/login/"))
        return Promise.resolve(jsonResponse({
          data: {
            user: {
              id: "member-1",
              email: "ada@example.edu.ng",
              first_name: "Ada",
              last_name: "Okafor",
              role,
              community: "STUDENT",
              effective_permissions: [],
            },
          },
        }));
      if (url.endsWith("/auth/refresh/"))
        return Promise.resolve(jsonResponse({ detail: "No refresh cookie." }, 401));
      return Promise.resolve(jsonResponse({ data: {} }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/login"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path={path} element={<AuthenticatedDashboard />} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const signInButton = screen.getByRole("button", { name: /sign in/i });
    await waitFor(() => expect(signInButton).not.toBeDisabled());
    await user.type(screen.getByLabelText(/email, matric number/i), "ada@example.edu.ng");
    await user.type(screen.getByLabelText(/^password/i), "StrongPass123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("heading", { name: "Member dashboard" })).toBeInTheDocument();
  });

  it("shows authenticator enrollment instead of opening the Super Admin dashboard", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/me/"))
        return Promise.resolve(jsonResponse({ detail: "Unauthenticated." }, 401));
      if (url.endsWith("/auth/login/"))
        return Promise.resolve(jsonResponse({ data: { user: {
          id: "admin-1", email: "admin@example.edu.ng", role: "SUPER_ADMIN",
          mfa_required: true, effective_permissions: ["*"],
        } } }));
      return Promise.resolve(jsonResponse({ data: {} }));
    }));
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/login"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/app/admin/dashboard" element={<h1>Admin dashboard</h1>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await user.type(screen.getByLabelText(/email, matric number/i), "admin@example.edu.ng");
    await user.type(screen.getByLabelText(/^password/i), "StrongPass123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByRole("heading", { name: "Protect your account" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Admin dashboard" })).not.toBeInTheDocument();
  });

  it("explains how to recover when the MFA setup session cannot renew", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/me/"))
        return Promise.resolve(jsonResponse({ detail: "Unauthenticated." }, 401));
      if (url.endsWith("/auth/login/"))
        return Promise.resolve(jsonResponse({ data: { user: {
          id: "admin-1", email: "admin@example.edu.ng", role: "SUPER_ADMIN", mfa_required: true,
        } } }));
      if (url.endsWith("/auth/refresh/"))
        return Promise.resolve(jsonResponse({ message: "Invalid or expired refresh token." }, 401));
      return Promise.resolve(jsonResponse({ data: {} }));
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/login"]}>
          <AuthProvider><Routes><Route path="/login" element={<LoginPage />} /></Routes></AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await user.type(screen.getByLabelText(/email, matric number/i), "admin@example.edu.ng");
    await user.type(screen.getByLabelText(/^password/i), "StrongPass123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));
    await user.click(await screen.findByRole("button", { name: /set up authenticator/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/sign-in expired/i);
    expect(screen.getByRole("button", { name: /sign in again/i })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/auth/mfa/enroll/"))).toBe(false);
  });

  it("redirects an already signed-in Super Admin to MFA setup before protected pages", async () => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => Promise.resolve(
      String(input).endsWith("/auth/me/")
        ? jsonResponse({ data: { id: "admin-1", email: "admin@example.edu.ng", role: "SUPER_ADMIN", mfa_required: true, effective_permissions: ["*"] } })
        : jsonResponse({ data: {} }),
    )));
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/app/admin/dashboard"]}>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route path="/app/admin/dashboard" element={<h1>Admin dashboard</h1>} />
              </Route>
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Protect your account" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Admin dashboard" })).not.toBeInTheDocument();
  });

  it("redirects to sign in immediately while server sign-out is pending", async () => {
    let finishLogout!: (response: Response) => void;
    const pendingLogout = new Promise<Response>((resolve) => {
      finishLogout = resolve;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/auth/me/"))
        return Promise.resolve(jsonResponse({
          data: {
            id: "member-1",
            email: "ada@example.edu.ng",
            first_name: "Ada",
            last_name: "Okafor",
            role: "MEMBER",
            community: "STUDENT",
            effective_permissions: [],
          },
        }));
      if (url.endsWith("/auth/logout/")) return pendingLogout;
      if (url.endsWith("/auth/refresh/"))
        return Promise.resolve(jsonResponse({ detail: "No refresh cookie." }, 401));
      return Promise.resolve(jsonResponse({ data: {} }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/app"]}>
          <AuthProvider>
            <Routes>
              <Route element={<ProtectedRoute />}>
                <Route path="/app" element={<DashboardSignOut />} />
              </Route>
              <Route path="/login" element={<h1>Sign in page</h1>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /sign out/i }));
    expect(await screen.findByRole("heading", { name: "Sign in page" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/auth/logout/"))).toBe(true);
    finishLogout(new Response(null, { status: 204 }));
  });

  it("keeps the dashboard route during an account service outage and retries", async () => {
    let attempts = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/me/")) {
        attempts += 1;
        return Promise.resolve(attempts === 1
          ? jsonResponse({ detail: "Service unavailable." }, 503)
          : jsonResponse({ data: {
              id: "member-1",
              email: "ada@example.edu.ng",
              first_name: "Ada",
              last_name: "Okafor",
              role: "MEMBER",
              community: "STUDENT",
              effective_permissions: [],
            } }));
      }
      return Promise.resolve(jsonResponse({ data: {} }));
    }));

    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/app"]}>
          <AuthProvider>
            <Routes>
              <Route element={<ProtectedRoute />}>
                <Route path="/app" element={<h1>Member dashboard</h1>} />
              </Route>
              <Route path="/login" element={<h1>Sign in page</h1>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/account service/i);
    expect(screen.queryByRole("heading", { name: "Sign in page" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { name: "Member dashboard" })).toBeInTheDocument();
  });
});
