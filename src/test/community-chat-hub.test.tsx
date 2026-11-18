import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { CommunitiesPage } from "../features/community-pages";
import { communityService } from "../services/chapelflow";

vi.mock("../services/chapelflow", () => ({
  communityService: { mine: vi.fn() },
  communityAdminService: {},
  memberService: {},
  queryKeys: {
    communities: () => ["communities"],
    community: (slug: string) => ["communities", slug],
  },
}));

vi.mock("../features/auth-context", () => ({
  useAuth: () => ({ user: { permissions: [] } }),
}));

const community = (id: string, name: string, type: "unit" | "campus_fellowship") => ({
  id,
  name,
  slug: id,
  type,
  description: "",
  status: "active" as const,
  requires_approval: true,
  members_can_post: true,
  chat_enabled: true,
  membership_status: "active" as const,
  unreadCount: 0,
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CommunitiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("student community chat hub", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("separates Unit and Fellowship chats and opens each directly in its chat tab", async () => {
    vi.mocked(communityService.mine).mockResolvedValue({
      data: [
        community("unit-music", "Music", "unit"),
        community("unit-media", "Media & ICT", "unit"),
        community("fellowship-love", "Love Campus Fellowship", "campus_fellowship"),
      ],
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "Unit chats" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Fellowship chats" })).toBeInTheDocument();

    const unitMusic = screen.getByRole("link", { name: "Open Music chat" });
    const unitMedia = screen.getByRole("link", { name: "Open Media & ICT chat" });
    const fellowship = screen.getByRole("link", { name: "Open Love Campus Fellowship chat" });

    expect(unitMusic.getAttribute("href")).toBe("/app/communities/unit-music?tab=chat");
    expect(unitMedia.getAttribute("href")).toBe("/app/communities/unit-media?tab=chat");
    expect(fellowship.getAttribute("href")).toBe("/app/communities/fellowship-love?tab=chat");
  });

  it("keeps both sections visible when a student has not joined either group type", async () => {
    vi.mocked(communityService.mine).mockResolvedValue({ data: [] });

    renderPage();

    expect(await screen.findByText(/no approved chapel unit memberships yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no approved fellowship membership yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Browse/ })).toHaveLength(2);
  });
});
