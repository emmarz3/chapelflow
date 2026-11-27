import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScendeyWaitlistModal, ScendeyWaitlistPage, ScendeyWaitlistPromo } from "../features/scendey-waitlist";

const { join } = vi.hoisted(() => ({ join: vi.fn() }));
vi.mock("../features/scendey-waitlist-service", () => ({
  scendeyWaitlistService: { join },
}));

beforeEach(() => {
  join.mockReset();
  join.mockResolvedValue({
    data: {
      processed: true,
      message: "Your request has been processed. For new registrations, Scendey may send an email verification message. Existing registrations are not duplicated.",
    },
  });
});

describe("Scendey waitlist integration", () => {
  it("renders a dedicated waitlist page and keeps marketing consent optional", () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: /discover scendey/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /join the waitlist/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/send me scendey progress/i)).not.toBeChecked();
    expect(screen.getByRole("link", { name: /explore the scendey website/i })).toHaveAttribute("target", "_blank");
  });

  it("collects business fields only when Business / Brand is selected", () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    expect(screen.queryByLabelText(/business \/ brand name/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /business \/ brand/i }));
    expect(screen.getByLabelText(/business \/ brand name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/business category/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /student/i }));
    expect(screen.queryByLabelText(/business \/ brand name/i)).not.toBeInTheDocument();
  });

  it("submits a student audience through the ChapelFlow backend without opting into marketing", async () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Test Visitor" } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "test@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /join the waitlist/i }));
    await waitFor(() => expect(join).toHaveBeenCalledWith(expect.objectContaining({
      name: "Test Visitor",
      email: "test@example.com",
      audienceCategory: "student",
      marketingConsent: false,
    })));
    const success = await screen.findByRole("status");
    expect(success).toHaveTextContent(/your waitlist signup has been received/i);
    expect(success).not.toHaveTextContent(/email|verification|link|check your inbox/i);
    expect(join).toHaveBeenCalledTimes(1);
  });

  it("submits a business audience with brand name, category and explicit marketing consent", async () => {
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole("radio", { name: /business \/ brand/i }));
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Brand Owner" } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText(/business \/ brand name/i), { target: { value: "Good Things" } });
    fireEvent.change(screen.getByLabelText(/business category/i), { target: { value: "Fashion" } });
    fireEvent.click(screen.getByLabelText(/send me scendey progress/i));
    fireEvent.click(screen.getByRole("button", { name: /join the waitlist/i }));
    await waitFor(() => expect(join).toHaveBeenCalledWith(expect.objectContaining({
      audienceCategory: "business",
      brandName: "Good Things",
      category: "Fashion",
      marketingConsent: true,
    })));
  });

  it("shows an actionable error and lets the visitor retry after a backend failure", async () => {
    join.mockRejectedValueOnce(new Error("Backend unavailable"));
    render(<MemoryRouter><ScendeyWaitlistPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: "Test Visitor" } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: "test@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /join the waitlist/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/backend unavailable/i);
    expect(screen.getByLabelText(/full name/i)).toHaveValue("Test Visitor");
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
