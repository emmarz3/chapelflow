import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { AdminOperationsPage } from "../features/admin-operations";
import { adminAttendanceService, operationsService } from "../services/chapelflow";

vi.mock("../services/chapelflow", () => ({
  adminAttendanceService: {
    sessions: vi.fn(), records: vi.fn(), scanAttempts: vi.fn(),
    createSession: vi.fn(), transition: vi.fn(), correct: vi.fn(),
  },
  operationsService: { list: vi.fn() },
  securityService: { auditLogs: vi.fn(), sessions: vi.fn(), revokeSession: vi.fn(), revokeAllSessions: vi.fn() },
}));

function renderPage() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><AdminOperationsPage /></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(operationsService.list).mockResolvedValue({ data: [{ id: "chapel-1", primary: "Chrisland Chapel" }] } as never);
  vi.mocked(adminAttendanceService.sessions).mockResolvedValue({ data: [] });
  vi.mocked(adminAttendanceService.records).mockResolvedValue({ data: [] });
  vi.mocked(adminAttendanceService.scanAttempts).mockResolvedValue({ data: [] });
  vi.mocked(adminAttendanceService.createSession).mockResolvedValue({ data: {} } as never);
});

it("starts attendance with the selected chapel and time window", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByRole("option", { name: "Chrisland Chapel" });
  await user.type(screen.getByLabelText("Service name"), "Sunday worship");
  fireEvent.change(screen.getByLabelText("Opens"), { target: { value: "2026-11-15T09:00" } });
  fireEvent.change(screen.getByLabelText("Closes"), { target: { value: "2026-11-15T11:00" } });
  await user.click(screen.getByRole("button", { name: "Start attendance" }));
  await waitFor(() => expect(adminAttendanceService.createSession).toHaveBeenCalledWith(expect.objectContaining({
    branch: "chapel-1", label: "Sunday worship", window_opens_at: expect.any(String), window_closes_at: expect.any(String),
  }), expect.anything()));
  expect(await screen.findByRole("status")).toHaveTextContent("Attendance scheduled.");
});

it("stops a paused session and removes its stop control after refresh", async () => {
  const user = userEvent.setup();
  const session = { id: "service-1", label: "Sunday worship", state: "PAUSED", is_open: true, record_count: 0 };
  vi.mocked(adminAttendanceService.sessions).mockResolvedValue({ data: [session] } as never);
  vi.mocked(adminAttendanceService.transition).mockImplementation(async () => {
    vi.mocked(adminAttendanceService.sessions).mockResolvedValue({ data: [{ ...session, state: "CLOSED", is_open: false }] } as never);
    return { data: {} } as never;
  });
  renderPage();
  await user.click(await screen.findByRole("button", { name: "Stop attendance" }));
  await waitFor(() => expect(adminAttendanceService.transition).toHaveBeenCalledWith("service-1", "close"));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Stop attendance" })).not.toBeInTheDocument());
  expect(screen.getByText("closed")).toBeInTheDocument();
});

it("rejects a closing time before the opening time", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByRole("option", { name: "Chrisland Chapel" });
  await user.type(screen.getByLabelText("Service name"), "Sunday worship");
  fireEvent.change(screen.getByLabelText("Opens"), { target: { value: "2026-11-15T11:00" } });
  fireEvent.change(screen.getByLabelText("Closes"), { target: { value: "2026-11-15T09:00" } });
  await user.click(screen.getByRole("button", { name: "Start attendance" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("closing time after the opening time");
  expect(adminAttendanceService.createSession).not.toHaveBeenCalled();
});


it("pre-fills today's local start time and a later closing time", async () => {
  renderPage();
  await screen.findByRole("option", { name: "Chrisland Chapel" });
  const opening = (screen.getByLabelText("Opens") as HTMLInputElement).value;
  const closing = (screen.getByLabelText("Closes") as HTMLInputElement).value;
  expect(opening).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  expect(new Date(closing).getTime()).toBeGreaterThan(new Date(opening).getTime());
});

it("shows an actionable error when the backend rejects an attendance start", async () => {
  const user = userEvent.setup();
  vi.mocked(adminAttendanceService.createSession).mockRejectedValue(new Error("Closing time must be after opening time."));
  renderPage();
  await screen.findByRole("option", { name: "Chrisland Chapel" });
  await user.type(screen.getByLabelText("Service name"), "Sunday worship");
  await user.click(screen.getByRole("button", { name: "Start attendance" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Closing time must be after opening time.");
  expect(screen.queryByText("Attendance session started.")).not.toBeInTheDocument();
});

it("stops an open attendance session and confirms that QR check-ins are blocked", async () => {
  const user = userEvent.setup();
  const session = { id: "service-open", label: "Morning worship", state: "OPEN", is_open: true, record_count: 5 };
  vi.mocked(adminAttendanceService.sessions).mockResolvedValue({ data: [session] } as never);
  vi.mocked(adminAttendanceService.transition).mockImplementation(async () => {
    vi.mocked(adminAttendanceService.sessions).mockResolvedValue({ data: [{ ...session, state: "CLOSED", is_open: false }] } as never);
    return { data: {} } as never;
  });
  renderPage();
  await user.click(await screen.findByRole("button", { name: "Stop attendance" }));
  await waitFor(() => expect(adminAttendanceService.transition).toHaveBeenCalledWith("service-open", "close"));
  expect(await screen.findByRole("status")).toHaveTextContent("New QR check-ins are blocked.");
  await waitFor(() => expect(screen.queryByRole("button", { name: "Stop attendance" })).not.toBeInTheDocument());
});

it("shows a retryable error if attendance records cannot be loaded", async () => {
  vi.mocked(adminAttendanceService.records).mockRejectedValue(new Error("Attendance records unavailable"));
  renderPage();
  expect(await screen.findByText("Attendance records unavailable")).toBeInTheDocument();
});
