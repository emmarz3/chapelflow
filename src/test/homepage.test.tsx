import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../components/ui";
import { HomePage } from "../features/home/home-page";
import { DEFAULT_HOMEPAGE, type HomepageContent } from "../lib/homepage-content";
import { homepageService } from "../services/chapelflow";

vi.mock("../services/chapelflow", async (importOriginal) => {
  const original = await importOriginal<typeof import("../services/chapelflow")>();
  return { ...original, homepageService: { ...original.homepageService, get: vi.fn(), submitRequest: vi.fn() } };
});

function renderHome(content: HomepageContent | null, counts: Record<string, number> = {}) {
  vi.mocked(homepageService.get).mockResolvedValue({ data: { content, version: content ? 1 : 0, updatedAt: null, counts } });
  vi.mocked(homepageService.submitRequest).mockResolvedValue({ data: { received: true } });
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter>
          <HomePage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.clearAllMocks();
});

describe("homepage", () => {
  it("renders the default programme when nothing has been customised", async () => {
    renderHome(null);
    expect(await screen.findByRole("heading", { name: /where faith becomes/i })).toBeInTheDocument();
    for (const name of ["Service Schedule", "Upcoming Events", "Recent Sermons", "Ministries & Units", "Chapel Calendar", "Moments of Grace"])
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    expect(screen.getByText(/verse of the day/i)).toBeInTheDocument();
    expect(screen.getByRole("timer")).toBeInTheDocument();
  });

  it("shows names and programmes edited by the super admin", async () => {
    const content: HomepageContent = {
      ...structuredClone(DEFAULT_HOMEPAGE),
      hero: { ...DEFAULT_HOMEPAGE.hero, titleLead: "Grace for every student", titleAccent: "" },
      units: [{ id: "unit-ushers", name: "Welcome Team", icon: "door", description: "Greet everyone", meeting: "Sundays", active: true }],
      announcements: [{ id: "a1", text: "Bring a friend on Sunday", linkLabel: "", linkHref: "", active: true }],
      sections: { ...DEFAULT_HOMEPAGE.sections, gallery: { ...DEFAULT_HOMEPAGE.sections.gallery, enabled: false } },
    };
    renderHome(content);
    expect(await screen.findByRole("heading", { name: /grace for every student/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Welcome Team" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Choir" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Bring a friend on Sunday").length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { name: "Moments of Grace" })).not.toBeInTheDocument();
  });

  it("dismisses the announcement ticker for the session", async () => {
    const user = userEvent.setup();
    renderHome(null);
    await user.click(await screen.findByRole("button", { name: /dismiss announcements/i }));
    expect(screen.queryByRole("region", { name: /announcements/i })).not.toBeInTheDocument();
  });

  it("switches schedule tabs", async () => {
    const user = userEvent.setup();
    renderHome(null);
    await screen.findByRole("tab", { name: /sunday worship/i });
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Walking in Covenant Promise")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /midweek service/i }));
    expect(within(panel).getByText("Midweek Fellowship")).toBeInTheDocument();
    expect(within(panel).queryByText("Walking in Covenant Promise")).not.toBeInTheDocument();
  });

  it("registers for an event and reflects it on the button", async () => {
    const user = userEvent.setup();
    renderHome(null, { "evt-freshers-retreat": 3 });
    expect(await screen.findByText("77 of 120 places taken")).toBeInTheDocument();
    const card = screen.getByRole("heading", { name: "Freshers' Welcome Retreat" }).closest("article")!;
    await user.click(within(card).getByRole("button", { name: "Register" }));

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /complete registration/i }));
    expect(await within(dialog).findByText(/enter your full name/i)).toBeInTheDocument();
    expect(homepageService.submitRequest).not.toHaveBeenCalled();

    await user.type(within(dialog).getByLabelText(/full name/i), "Ada Obi");
    await user.type(within(dialog).getByLabelText(/^email/i), "ada@example.com");
    await user.click(within(dialog).getByRole("checkbox"));
    await user.click(within(dialog).getByRole("button", { name: /complete registration/i }));

    await waitFor(() => expect(homepageService.submitRequest).toHaveBeenCalledTimes(1));
    expect(homepageService.submitRequest).toHaveBeenCalledWith(expect.objectContaining({ kind: "event", itemId: "evt-freshers-retreat", email: "ada@example.com", consent: true }));
    expect(await within(dialog).findByText(/you're registered, ada/i)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Done" }));
    expect(within(card).getByRole("button", { name: /registered/i })).toBeDisabled();
  });

  it("disables registration when an event is full", async () => {
    renderHome(null, { "evt-community-outreach": 60 });
    const card = (await screen.findByRole("heading", { name: "Owode-Ede Community Outreach" })).closest("article")!;
    expect(within(card).getByRole("button", { name: /fully booked/i })).toBeDisabled();
  });

  it("opens the gallery lightbox and closes it with Escape", async () => {
    const user = userEvent.setup();
    renderHome(null);
    await user.click(await screen.findByRole("button", { name: /open photo: baptism sunday/i }));
    expect(screen.getByRole("dialog", { name: "Baptism Sunday" })).toBeInTheDocument();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("dialog", { name: "Night of Encounter" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("filters the calendar", async () => {
    const user = userEvent.setup();
    renderHome(null);
    const filters = await screen.findByRole("group", { name: /filter by service type/i });
    await user.click(within(filters).getByRole("button", { name: "Vigils" }));
    expect(within(filters).getByRole("button", { name: "Vigils" })).toHaveAttribute("aria-pressed", "true");
  });
});
