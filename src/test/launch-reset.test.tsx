import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { LaunchResetPage } from "../features/launch-reset";
import { ApiError } from "../lib/api";
import { adminAccountService } from "../services/chapelflow";

vi.mock("../services/chapelflow", () => ({
  adminAccountService: { resetPreview: vi.fn(), resetDatabase: vi.fn() },
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(adminAccountService.resetPreview).mockResolvedValue({ data: {
    token: "preview-token", confirmation: "RESET CHAPELFLOW DATA",
    accounts_to_remove: 3, database_rows: 10, counts: {},
  } });
  vi.mocked(adminAccountService.resetDatabase).mockImplementation(() => new Promise(() => {}));
});

it("requires a typed phrase and backup acknowledgement before sending a reset", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <LaunchResetPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );
  const phrase = screen.getByRole("textbox", { name: "Reset confirmation phrase" });
  expect(phrase).toHaveValue("");
  const resetButton = screen.getByRole("button", { name: "Permanently reset saved accounts and records" });
  expect(resetButton).toBeDisabled();
  await user.type(phrase, "WRONG PHRASE");
  await user.click(screen.getByRole("button", { name: "Review records to reset" }));
  await screen.findByText(/3 other accounts will be removed/i);
  expect(phrase).toHaveValue("WRONG PHRASE");
  await user.type(screen.getByLabelText("Super Admin password"), "password");
  await user.type(screen.getByLabelText("Authenticator code"), "123456");
  await user.click(screen.getByRole("checkbox", { name: /verified a restorable database backup/i }));
  await user.click(screen.getByRole("button", { name: "Permanently reset saved accounts and records" }));
  expect(screen.getByText(/phrase must match RESET CHAPELFLOW DATA exactly/i)).toBeInTheDocument();
  expect(adminAccountService.resetDatabase).not.toHaveBeenCalled();

  await user.clear(phrase);
  await user.type(phrase, "RESET CHAPELFLOW DATA");
  await user.click(screen.getByRole("button", { name: "Permanently reset saved accounts and records" }));
  await waitFor(() => expect(adminAccountService.resetDatabase).toHaveBeenCalledWith(
    "preview-token", "RESET CHAPELFLOW DATA", "password", "123456",
  ));
});


it("discards an expired preview and requires a fresh records review", async () => {
  const user = userEvent.setup();
  vi.mocked(adminAccountService.resetDatabase).mockRejectedValueOnce(
    new ApiError({
      code: "conflict",
      message: "The reset preview expired after five minutes. Review the current records to generate a new preview.",
      status: 409,
    }),
  );

  render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <LaunchResetPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );

  await user.click(screen.getByRole("button", { name: "Review records to reset" }));
  await screen.findByText(/3 other accounts will be removed/i);
  await user.type(screen.getByRole("textbox", { name: "Reset confirmation phrase" }), "RESET CHAPELFLOW DATA");
  await user.type(screen.getByLabelText("Super Admin password"), "password");
  await user.type(screen.getByLabelText("Authenticator code"), "123456");
  await user.click(screen.getByRole("checkbox", { name: /verified a restorable database backup/i }));
  await user.click(screen.getByRole("button", { name: "Permanently reset saved accounts and records" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/preview expired after five minutes/i);
  expect(screen.getByRole("textbox", { name: "Reset confirmation phrase" })).toHaveValue("");
  expect(screen.getByLabelText("Super Admin password")).toHaveValue("");
  expect(screen.getByLabelText("Authenticator code")).toHaveValue("");
  expect(screen.getByRole("checkbox", { name: /verified a restorable database backup/i })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Permanently reset saved accounts and records" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Review records again" }));
  await screen.findByText(/3 other accounts will be removed/i);
  expect(adminAccountService.resetPreview).toHaveBeenCalledTimes(2);
  expect(screen.getByRole("textbox", { name: "Reset confirmation phrase" })).toHaveValue("");
});
