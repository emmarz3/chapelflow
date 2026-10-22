import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { InstitutionalAccountsPage } from "../features/institutional-accounts";
import { ApiError } from "../lib/api";
import { chapelGroupService, institutionalAccountService } from "../services/chapelflow";

vi.mock("../services/chapelflow", () => ({
  chapelGroupService: {
    list: vi.fn(),
    bootstrapChapelGroups: vi.fn(),
  },
  institutionalAccountService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    resetPassword: vi.fn(),
  },
}));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <InstitutionalAccountsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(institutionalAccountService.list).mockResolvedValue({ data: [] });
  vi.mocked(chapelGroupService.list).mockResolvedValue({
    data: [
      ...[
        "Intercessory",
        "Treasurer",
        "Chapel Protocol",
        "Music",
        "Instrumentalist",
        "Ushering",
        "Sanctuary Keepers",
        "Media & ICT",
        "Social Media",
        "Library",
        "Drama Team",
        "Technical & Sound",
        "Head of Music",
      ].map((name, index) => ({ id: `unit-${index + 1}`, name, group_type: "UNIT", is_active: true })),
      ...[
        "Love Campus Fellowship",
        "Truth Campus Fellowship",
        "Favour Campus Fellowship",
        "Integrity Campus Fellowship",
        "Righteousness Campus Fellowship",
        "Mercy Campus Fellowship",
        "Excellence Campus Fellowship",
        "Grace Campus Fellowship",
        "Outstanding Campus Fellowship",
        "Peace Campus Fellowship",
        "Love Fellowship",
      ].map((name, index) => ({ id: `fellowship-${index + 1}`, name, group_type: "FELLOWSHIP", is_active: true })),
    ],
  });
  vi.mocked(institutionalAccountService.create).mockResolvedValue({ data: {} as never });
});

describe("institutional account provisioning", () => {
  it.each([
    ["CHAPLAIN", undefined],
    ["STUDENT_CHAPLAIN", undefined],
    ["UNIT_HEAD", "unit-4"],
    ["FELLOWSHIP_LEADER", "fellowship-1"],
  ])("submits %s with the right group assignment", async (role, groupId) => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Create account" }));
    await user.type(screen.getByLabelText("First name"), "Ada");
    await user.type(screen.getByLabelText("Last name"), "Lovelace");
    await user.type(screen.getByLabelText(/^Email/), `${String(role).toLowerCase()}@example.edu`);
    await user.type(screen.getByLabelText(/^Initial password/), "Safe-Initial-Password-483!");
    await user.selectOptions(screen.getByLabelText("Role"), String(role));
    if (groupId) await user.selectOptions(screen.getByLabelText(/^Unit or fellowship/), groupId);
    await user.click(screen.getByRole("button", { name: "Create securely" }));

    await waitFor(() => expect(institutionalAccountService.create).toHaveBeenCalled());
    expect(vi.mocked(institutionalAccountService.create).mock.calls[0]?.[0]).toMatchObject(
      groupId ? { role, institutional_group: groupId } : { role },
    );
  });

  it("offers the chapel's named units and fellowships without leader titles", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Create account" }));

    const assignment = screen.getByLabelText(/^Unit or fellowship/);
    await user.selectOptions(screen.getByLabelText("Role"), "UNIT_HEAD");
    for (const unit of ["Intercessory", "Treasurer", "Music", "Technical & Sound"]) {
      expect(screen.getByRole("option", { name: new RegExp(unit) })).toBeInTheDocument();
    }
    expect(screen.queryByRole("option", { name: /Head of Music/ })).toBeNull();

    await user.selectOptions(screen.getByLabelText("Role"), "FELLOWSHIP_LEADER");
    for (const fellowship of ["Love Campus Fellowship", "Truth Campus Fellowship", "Peace Campus Fellowship"]) {
      expect(screen.getByRole("option", { name: new RegExp(fellowship) })).toBeInTheDocument();
    }
    expect(assignment).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Love Fellowship/ })).toBeNull();
  });

  it("shows server-side password validation when account creation is rejected", async () => {
    const user = userEvent.setup();
    vi.mocked(institutionalAccountService.create).mockRejectedValueOnce(
      new ApiError({
        code: "VALIDATION_ERROR",
        message: "Validation failed. password: This password is too common.",
        fieldErrors: { password: ["This password is too common."] },
        status: 400,
      }),
    );
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Create account" }));
    await user.type(screen.getByLabelText("First name"), "Ada");
    await user.type(screen.getByLabelText("Last name"), "Lovelace");
    await user.type(screen.getByLabelText(/^Email/), "ada@example.edu");
    await user.type(screen.getByLabelText(/^Initial password/), "Safe-Initial-Password-483!");
    await user.click(screen.getByRole("button", { name: "Create securely" }));

    expect(await screen.findByText("This password is too common.")).toBeInTheDocument();
    expect(screen.getByText(/Validation failed\. password: This password is too common\./)).toBeInTheDocument();
  });
});
