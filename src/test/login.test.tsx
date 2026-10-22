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
    expect(screen.getByRole("alert")).toHaveTextContent(/enter your email/i);
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

  it("opens the role-aware member dashboard after sign-in", async () => {
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
              role: "MEMBER",
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
              <Route path="/app" element={<AuthenticatedDashboard />} />
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
});
