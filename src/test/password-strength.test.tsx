import { render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { PasswordStrength, eightCharacterPasswordRules, usePasswordStrength } from "../components/ui/password-strength";

describe("password strength meter", () => {
  it("scores an empty password as empty", () => {
    const { result } = renderHook(() => usePasswordStrength(""));
    expect(result.current.score).toBe(0);
    expect(result.current.label).toBe("Empty");
  });

  it("marks requirements and announces the delayed result accessibly", async () => {
    const user = userEvent.setup();
    function Example() {
      const [value, setValue] = useState("");
      return <><label htmlFor="password">Password</label><input id="password" value={value} onChange={(event) => setValue(event.target.value)} /><PasswordStrength value={value} rules={eightCharacterPasswordRules} announceDelay={0} /></>;
    }
    render(<Example />);
    await user.type(screen.getByLabelText("Password"), "B7#mP2xV!");
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "4");
    await waitFor(() => expect(screen.getByText(/all requirements met/i)).toBeInTheDocument());
  });

  it("caps common guessable strings at weak", () => {
    render(<PasswordStrength value="passwordpassword12!A" announceDelay={0} />);
    expect(screen.getByText("Commonly guessed")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "1");
  });
});
