import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ScendeyWaitlistModal, ScendeyWaitlistPage, ScendeyWaitlistPromo } from "../features/scendey-waitlist";

describe("Scendey waitlist Phase 2 experience", () => {
  it("renders a dedicated waitlist page and keeps marketing consent optional", () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /discover scendey/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /join the waitlist/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/send me scendey progress/i)).not.toBeChecked();
    expect(screen.getByRole("link", { name: /explore the scendey website/i })).toHaveAttribute("target", "_blank");
  });

  it("collects business details only for the business audience", () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    expect(screen.queryByLabelText(/business \/ brand name/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /business \/ brand/i }));
    expect(screen.getByLabelText(/business \/ brand name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/business category/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /student/i }));
    expect(screen.queryByLabelText(/business \/ brand name/i)).not.toBeInTheDocument();
  });

  it("validates locally without sending or saving registration data", () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    const form = screen.getByRole("button", { name: /join the waitlist/i }).closest("form");
    expect(form).not.toBeNull();
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Test User" } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "test@example.com" } });
    fireEvent.submit(form!);
    expect(screen.getByRole("status")).toHaveTextContent(/nothing has been sent or saved/i);
  });

  it("opens the shared waitlist form from a homepage promotion", () => {
    render(<MemoryRouter><ScendeyWaitlistPromo variant="homepage" /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: /join the waitlist/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
  });

  it("renders the dashboard promotion with an external Scendey link", () => {
    render(<MemoryRouter><ScendeyWaitlistPromo variant="dashboard" /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /discover scendey/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /explore scendey/i })).toHaveAttribute("target", "_blank");
  });

  it("does not open the modal when the modal is closed", () => {
    render(<MemoryRouter><ScendeyWaitlistModal open={false} onClose={() => undefined} /></MemoryRouter>);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
