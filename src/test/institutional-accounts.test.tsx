import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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
      ].map((name, index) => ({ id: `fellowship-${index + 1}`, name, group_type: "FELLOWSHIP", is_active: true })),
    ],
  });
  vi.mocked(institutionalAccountService.create).mockResolvedValue({ data: {} as never });
});

describe("institutional account provisioning", () => {
  it.each([
    ["CHAPLAIN", undefined],
    ["STUDENT_CHAPLAIN", undefined],
    ["ATTENDANCE_USHER", undefined],
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
    if (role === "FELLOWSHIP_LEADER") {
      expect(screen.queryByLabelText("Leadership office")).not.toBeInTheDocument();
    }
    if (groupId) await user.selectOptions(screen.getByLabelText(/^Unit or fellowship/), groupId);
    await user.click(screen.getByRole("button", { name: "Create securely" }));

    await waitFor(() => expect(institutionalAccountService.create).toHaveBeenCalled());
    expect(vi.mocked(institutionalAccountService.create).mock.calls[0]?.[0]).toMatchObject(
      {
        role,
        ...(groupId ? { institutional_group: groupId } : {}),
        ...(role === "FELLOWSHIP_LEADER" ? { institutional_office: "FELLOWSHIP_LEADER" } : {}),
      },
    );
  });

  it("offers the chapel's named units and fellowships without leader titles", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Create account" }));

    await user.selectOptions(screen.getByLabelText("Role"), "UNIT_HEAD");
    const assignment = screen.getByLabelText(/^Unit or fellowship/);
    const units = [
      "Intercessory", "Treasurer", "Chapel Protocol", "Music", "Instrumentalist",
      "Ushering", "Sanctuary Keepers", "Media & ICT", "Social Media", "Library",
      "Drama Team", "Technical & Sound",
    ];
    for (const unit of units) {
      expect(within(assignment).getByRole("option", { name: new RegExp(unit) })).toBeInTheDocument();
    }
    expect(within(assignment).getAllByRole("option")).toHaveLength(13);

    await user.selectOptions(screen.getByLabelText("Role"), "FELLOWSHIP_LEADER");
    const fellowships = [
      "Love Campus Fellowship", "Truth Campus Fellowship", "Favour Campus Fellowship",
      "Integrity Campus Fellowship", "Righteousness Campus Fellowship", "Mercy Campus Fellowship",
      "Excellence Campus Fellowship", "Grace Campus Fellowship", "Outstanding Campus Fellowship",
      "Peace Campus Fellowship",
    ];
    for (const fellowship of fellowships) {
      expect(within(assignment).getByRole("option", { name: new RegExp(fellowship) })).toBeInTheDocument();
    }
    expect(within(assignment).getAllByRole("option")).toHaveLength(11);
    expect(assignment).toBeInTheDocument();
  });

  it("adds the standard Chapel groups from the account page", async () => {
    const user = userEvent.setup();
    vi.mocked(chapelGroupService.bootstrapChapelGroups).mockResolvedValue({
      data: { created: [{ id: "new-group", name: "Treasurer" }], count: 1 },
    });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "Add chapel units & fellowships" }));

    await waitFor(() => expect(chapelGroupService.bootstrapChapelGroups).toHaveBeenCalledOnce());
    expect(chapelGroupService.list).toHaveBeenCalledWith({ accountAssignment: true });
  });

  it.each([
    ["ASSISTANT_STUDENT_CHAPLAIN", "ASSISTANT_STUDENT_CHAPLAIN_VLBC_ANNEX", undefined],
    ["HOSTEL_COORDINATOR", "MALE_HOSTEL_FELLOWSHIP_COORDINATOR", undefined],
    ["HOSTEL_COORDINATOR", "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_1", undefined],
    ["HOSTEL_COORDINATOR", "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_2", undefined],
    ["UNIT_HEAD", "HEAD_OF_MUSIC", "unit-4"],
    ["UNIT_HEAD", "ASSISTANT_HEAD_OF_MUSIC", "unit-4"],
    ["UNIT_HEAD", "CHIEF_USHER", "unit-6"],
    ["UNIT_HEAD", "ASSISTANT_CHIEF_USHER", "unit-6"],
    ["UNIT_HEAD", "HEAD_OF_SANCTUARY_KEEPERS", "unit-7"],
    ["UNIT_HEAD", "ASSISTANT_HEAD_OF_SANCTUARY_KEEPERS", "unit-7"],
    ["UNIT_HEAD", "HEAD_OF_INSTRUMENTALIST", "unit-5"],
  ])("can provision the %s office %s", async (role, office, groupId) => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Create account" }));
    await user.type(screen.getByLabelText("First name"), "Ada");
    await user.type(screen.getByLabelText("Last name"), "Lovelace");
    await user.type(screen.getByLabelText(/^Email/), `${office.toLowerCase()}@example.edu`);
    await user.type(screen.getByLabelText(/^Initial password/), "Safe-Initial-Password-483!");
    await user.selectOptions(screen.getByLabelText("Role"), role);
    await user.selectOptions(screen.getByLabelText("Leadership office"), office);
    await user.click(screen.getByRole("button", { name: "Create securely" }));
    await waitFor(() => expect(institutionalAccountService.create).toHaveBeenCalled());
    expect(vi.mocked(institutionalAccountService.create).mock.calls[0]?.[0]).toMatchObject({
      role, institutional_office: office,
      ...(groupId ? { institutional_group: groupId } : {}),
    });
  });

  it("lists every office from the Chapel register without preloading leader names", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "Create account" }));
    for (const [role, labels] of [
      ["UNIT_HEAD", [
        "Intercessory", "Treasurer", "Chapel Protocol", "Head of Music",
        "Assistant Head of Music", "Head of Instrumentalist", "Chief Usher",
        "Assistant Chief Usher", "Head of Sanctuary Keepers",
        "Assistant Head of Sanctuary Keepers", "Media & ICT", "Social Media",
        "Library", "Drama Team", "Technical & Sound",
      ]],
      ["HOSTEL_COORDINATOR", [
        "Male Hostel Fellowship Coordinator", "Female Hostel Fellowship Coordinator 1",
        "Female Hostel Fellowship Coordinator 2",
      ]],
      ["ASSISTANT_STUDENT_CHAPLAIN", [
        "Assistant Student Chaplain VLBC Annex Hostel",
      ]],
    ] as const) {
      await user.selectOptions(screen.getByLabelText("Role"), role);
      const officeSelect = screen.getByLabelText("Leadership office");
      for (const label of labels) {
        expect(within(officeSelect).getByRole("option", { name: label })).toBeInTheDocument();
      }
    }
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
