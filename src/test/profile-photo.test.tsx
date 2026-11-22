import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfilePhotoEditor } from "../features/profile-photo";

const mocks = vi.hoisted(() => ({ upload: vi.fn(), setPhoto: vi.fn() }));
vi.mock("../features/auth-context", () => ({ useAuth: () => ({
  user: { id: "account-1", initials: "EM", photoUrl: "https://example.com/old.png" },
  setProfilePhoto: mocks.setPhoto,
}) }));
vi.mock("../services/chapelflow", () => ({ authService: { uploadProfilePhoto: mocks.upload } }));

function mount() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><ProfilePhotoEditor /></QueryClientProvider>);
  return invalidate;
}

describe("Profile photo upload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    URL.createObjectURL = vi.fn(() => "blob:preview");
    URL.revokeObjectURL = vi.fn();
  });
  it("previews a selection, saves it, and refreshes profile and attendance identity", async () => {
    mocks.upload.mockResolvedValue({ data: { photo_url: "https://example.com/new.png" } });
    const invalidate = mount();
    const file = new File(["photo"], "photo.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Choose profile picture"), { target: { files: [file] } });
    expect(await screen.findByAltText("Selected profile picture preview")).toHaveAttribute("src", "blob:preview");
    fireEvent.click(screen.getByRole("button", { name: "Save profile picture" }));
    await screen.findByText("Profile picture updated.");
    expect(mocks.upload).toHaveBeenCalledWith(file);
    expect(mocks.setPhoto).toHaveBeenCalledWith("https://example.com/new.png");
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["attendance-pass"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["student-profile"] });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  });
  it("rejects non-images without sending them", () => {
    mount();
    fireEvent.change(screen.getByLabelText("Choose profile picture"), { target: { files: [new File(["pdf"], "photo.pdf", { type: "application/pdf" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a JPG");
    expect(screen.getByRole("button", { name: "Save profile picture" })).toBeDisabled();
    expect(mocks.upload).not.toHaveBeenCalled();
  });
  it("keeps a failed upload available to retry without changing the saved avatar", async () => {
    mocks.upload.mockRejectedValue(new Error("Photo storage is unavailable."));
    mount();
    fireEvent.change(screen.getByLabelText("Choose profile picture"), { target: { files: [new File(["photo"], "photo.png", { type: "image/png" })] } });
    fireEvent.click(screen.getByRole("button", { name: "Save profile picture" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Photo storage is unavailable.");
    await waitFor(() => expect(screen.getByRole("button", { name: "Save profile picture" })).toBeEnabled());
    expect(mocks.setPhoto).not.toHaveBeenCalled();
  });
});
