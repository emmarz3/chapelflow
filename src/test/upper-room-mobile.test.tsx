import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { UpperRoomPage } from "../features/upper-room";

const mocks = vi.hoisted(() => ({ feed: vi.fn(), stories: vi.fn() }));
vi.mock("../features/auth-context", () => ({ useAuth: () => ({ user: { id: "member-1", role: "member", name: "Test Member", initials: "TM" } }) }));
vi.mock("../services/chapelflow", () => ({ upperRoomService: { feed: mocks.feed, stories: mocks.stories } }));
vi.mock("../components/ui", async (original) => ({ ...(await original<typeof import("../components/ui")>()), useToast: () => vi.fn() }));

describe("Upper Room mobile controls", () => {
  beforeEach(() => {
    mocks.feed.mockReset();
    mocks.stories.mockReset();
    sessionStorage.setItem("chapelflow:upper-room-intro", "1");
  });

  it("keeps the story picker and composer usable when the feed fails", async () => {
    mocks.feed.mockRejectedValue(new Error("Feed temporarily unavailable"));
    mocks.stories.mockResolvedValue({ data: { items: [] } });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter><UpperRoomPage /></MemoryRouter></QueryClientProvider>);

    expect(screen.getByLabelText("Create an Upper Room post")).toBeInTheDocument();
    expect(await screen.findByText("Feed temporarily unavailable")).toBeInTheDocument();
    const picker = view.container.querySelector<HTMLInputElement>('.upper-room__story input[type="file"]');
    expect(picker).not.toBeNull();
    fireEvent.change(picker!, { target: { files: [new File(["photo"], "story.png", { type: "image/png" })] } });
    expect(screen.getByRole("button", { name: "Post story" })).toBeEnabled();
  });
});
