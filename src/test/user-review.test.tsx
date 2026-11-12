import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { RouteScrollManager } from "../components/route-scroll";
import { CookieConsent } from "../features/public-site";
import {
  isSafeExternalUrl,
  readCookieConsent,
  requestCookiePreferenceReview,
} from "../lib/cookie-consent";
import { classifyKioskScan } from "../lib/use-qr-scanner";
import { Link } from "react-router-dom";

vi.mock("../components/intro/chapelflow-intro", () => ({
  ChapelFlowIntro: () => null,
}));
vi.mock("../components/motion/motion-system", () => ({
  useReducedMotionPreference: () => true,
  useAuthMotion: vi.fn(),
  usePortalMotion: vi.fn(),
  usePublicMotion: vi.fn(),
  useFeatureMotion: vi.fn(),
  MOTION: {
    duration: { micro: 0.16, fast: 0.24, normal: 0.4, medium: 0.55, slow: 0.8 },
    ease: { standard: "power2.out", smooth: "power3.out", enter: "power4.out", exit: "power2.inOut" },
    distance: { xs: 4, sm: 8, md: 16, lg: 28 },
  },
}));

describe("kiosk QR classification", () => {
  it("treats matric numbers and emails as identifiers", () => {
    expect(classifyKioskScan("CU/2026/001")).toBe("identifier");
    expect(classifyKioskScan("student@example.edu.ng")).toBe("identifier");
  });

  it("treats opaque identity tokens as QR payloads", () => {
    expect(classifyKioskScan("a1b2c3d4e5f6opaque-member-token")).toBe("token");
  });
});

describe("social destination safety", () => {
  it("accepts only http(s) URLs", () => {
    expect(isSafeExternalUrl("https://www.instagram.com/example")).toContain("instagram.com");
    expect(isSafeExternalUrl("javascript:alert(1)")).toBeNull();
    expect(isSafeExternalUrl("#")).toBeNull();
    expect(isSafeExternalUrl("")).toBeNull();
  });
});

describe("cookie consent", () => {
  it("persists a necessary-only choice and can reopen settings", async () => {
    localStorage.clear();
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CookieConsent />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: /use necessary only/i }));
    expect(readCookieConsent()).toBe("necessary");
    expect(screen.queryByText(/your privacy, your choice/i)).not.toBeInTheDocument();
    requestCookiePreferenceReview();
    expect(await screen.findByText(/your privacy, your choice/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /cookie policy/i })).toHaveAttribute("href", "/cookies");
  });
});

describe("route transitions", () => {
  it("scrolls to the top on ordinary navigation and honors hashes", async () => {
    const scrollTo = vi.fn();
    window.scrollTo = scrollTo as unknown as typeof window.scrollTo;
    const target = document.createElement("div");
    target.id = "choice";
    target.scrollIntoView = vi.fn();
    document.body.append(target);
    const user = userEvent.setup();
    function Shell() {
      return (
        <>
          <RouteScrollManager />
          <Link to="/cookies">Cookies</Link>
          <Link to="/cookies#choice">Cookie choice</Link>
          <Routes>
            <Route path="/" element={<p>Home</p>} />
            <Route path="/cookies" element={<p>Policy</p>} />
          </Routes>
        </>
      );
    }
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Shell />
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("link", { name: "Cookies" }));
    expect(scrollTo).toHaveBeenCalled();
    await user.click(screen.getByRole("link", { name: "Cookie choice" }));
    expect(target.scrollIntoView).toHaveBeenCalled();
    target.remove();
  });
});
