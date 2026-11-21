import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PublicLayout } from "../features/public-site";
import { useAuth } from "../features/auth-context";

vi.mock("../features/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("../components/motion/motion-system", () => ({
  usePublicMotion: vi.fn(),
}));

function renderLayout() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<p>Home page</p>} />
            <Route path="/login" element={<p>Login page</p>} />
            <Route path="/register" element={<p>Registration page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(useAuth).mockReturnValue({
    user: null,
    loading: false,
  } as ReturnType<typeof useAuth>);
});

describe("mobile public navigation", () => {
  it("puts visitor sign in and registration before the page links", async () => {
    const user = userEvent.setup();
    renderLayout();
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    const menu = screen.getByRole("dialog", { name: "Site navigation" });
    const signIn = within(menu).getByRole("link", { name: "Sign in" });
    const register = within(menu).getByRole("link", { name: "Register" });
    expect(signIn).toHaveAttribute("href", "/login");
    expect(register).toHaveAttribute("href", "/register");
    expect(
      signIn.compareDocumentPosition(
        within(menu).getByRole("link", { name: "About" }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    await user.click(register);
    expect(screen.getByText("Registration page")).toBeInTheDocument();
    expect(
      screen.queryByRole("dialog", { name: "Site navigation" }),
    ).not.toBeInTheDocument();
  });

  it("shows the dashboard instead of visitor actions for a signed-in user", async () => {
    vi.mocked(useAuth).mockReturnValue({
      user: { name: "Ada Obi" },
      loading: false,
    } as ReturnType<typeof useAuth>);
    renderLayout();
    await userEvent
      .setup()
      .click(screen.getByRole("button", { name: "Open navigation" }));
    const menu = screen.getByRole("dialog", { name: "Site navigation" });
    expect(
      within(menu).getByRole("link", { name: "Open Ada Obi's dashboard" }),
    ).toHaveAttribute("href", "/app");
    expect(
      within(menu).queryByRole("link", { name: "Register" }),
    ).not.toBeInTheDocument();
    expect(
      within(menu).queryByRole("link", { name: "Sign in" }),
    ).not.toBeInTheDocument();
  });
});
