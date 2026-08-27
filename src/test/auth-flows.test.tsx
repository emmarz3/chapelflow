import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { OtpPage, ResetPasswordPage } from "../features/auth-pages";

describe("authentication recovery flows", () => {
  it("validates a complete six-digit OTP before submission", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <OtpPage />
      </MemoryRouter>,
    );
    await user.type(screen.getByLabelText(/verification code/i), "123");
    await user.click(screen.getByRole("button", { name: /verify account/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/six-digit/i);
  });

  it("rejects mismatched reset passwords before calling the backend", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/reset-password?token=test-token"]}>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    await user.type(
      screen.getByLabelText(/^new password/i),
      "correct-password-1",
    );
    await user.type(
      screen.getByLabelText(/confirm new password/i),
      "different-password-1",
    );
    await user.click(screen.getByRole("button", { name: /update password/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/do not match/i);
  });
});
