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

const TEST_HOME_CONTENT: HomepageContent = {
  ...structuredClone(DEFAULT_HOMEPAGE),
  services: [
    { id: "sunday-worship", type: "sunday", title: "Walking in Covenant Promise", venue: "Chapel Hall", minister: "", time: "11:30", duration: 60, rule: "weekly", weekday: 0, date: "", active: true },
    { id: "midweek-fellowship", type: "midweek", title: "Midweek Fellowship", venue: "Chapel Hall", minister: "", time: "17:00", duration: 90, rule: "weekly", weekday: 3, date: "", active: true },
  ],
  events: [
    { id: "evt-freshers-retreat", category: "Retreat", title: "Freshers' Welcome Retreat", repeat: "none", weekday: 0, startDate: "2099-11-06", endDate: "2099-11-08", startTime: "09:00", time: "9:00 AM", venue: "Chapel Hall", cta: "Register", capacity: 120, taken: 74, active: true },
    { id: "evt-community-outreach", category: "Outreach", title: "Owode-Ede Community Outreach", repeat: "none", weekday: 0, startDate: "2099-11-22", endDate: "", startTime: "09:00", time: "9:00 AM", venue: "Owode-Ede", cta: "RSVP", capacity: 40, taken: 35, active: true },
  ],
  gallery: [
    { id: "baptism-sunday", title: "Baptism Sunday", subtitle: "A day of celebration", imageUrl: "/baptism.jpg", active: true },
    { id: "night-of-encounter", title: "Night of Encounter", subtitle: "Worship together", imageUrl: "/encounter.jpg", active: true },
  ],
};

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
    for (const name of ["Service Schedule", "Upcoming Events", "Ministries & Units", "Chapel Calendar", "Moments of Grace"])
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    expect(screen.getByText(/verse of the day/i)).toBeInTheDocument();
    expect(screen.getByText(/for lectures, decisions, and everything you are carrying today/i)).toBeInTheDocument();
    expect(screen.getByText(/no services in this category right now/i)).toBeInTheDocument();
    expect(screen.getByText(/no upcoming events are scheduled right now/i)).toBeInTheDocument();
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
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
    renderHome(TEST_HOME_CONTENT);
    await user.click(await screen.findByRole("button", { name: /dismiss announcements/i }));
    expect(screen.queryByRole("region", { name: /announcements/i })).not.toBeInTheDocument();
  });

  it("switches schedule tabs", async () => {
    const user = userEvent.setup();
    renderHome(TEST_HOME_CONTENT);
    await screen.findByRole("tab", { name: /sunday worship/i });
    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Walking in Covenant Promise")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /midweek service/i }));
    expect(within(panel).getByText("Midweek Fellowship")).toBeInTheDocument();
    expect(within(panel).queryByText("Walking in Covenant Promise")).not.toBeInTheDocument();
  });

  it("registers for an event and reflects it on the button", async () => {
    const user = userEvent.setup();
    renderHome(TEST_HOME_CONTENT, { "evt-freshers-retreat": 3 });
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
    renderHome(TEST_HOME_CONTENT, { "evt-community-outreach": 60 });
    const card = (await screen.findByRole("heading", { name: "Owode-Ede Community Outreach" })).closest("article")!;
    expect(within(card).getByRole("button", { name: /fully booked/i })).toBeDisabled();
  });

  it("links gallery collections to their detail pages", async () => {
    renderHome(TEST_HOME_CONTENT);
    const collection = await screen.findByRole("link", { name: /open collection: baptism sunday/i });
    expect(collection).toHaveAttribute("href", "/gallery/baptism-sunday");
  });

  it("filters the calendar", async () => {
    const user = userEvent.setup();
    renderHome(null);
    const filters = await screen.findByRole("group", { name: /filter by service type/i });
    await user.click(within(filters).getByRole("button", { name: "Vigils" }));
    expect(within(filters).getByRole("button", { name: "Vigils" })).toHaveAttribute("aria-pressed", "true");
  });
});
