import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createUpperRoomShareCard } from "../lib/upper-room-share";
import type { UpperRoomPost } from "../services/chapelflow";

vi.mock("../lib/api", () => ({ API_BASE_URL: "/api/v1" }));

const mediaPost = (mediaType: "IMAGE" | "VIDEO"): UpperRoomPost => ({
  id: "post-1", caption: "Sunday service", authorName: "Emmanuel Abisola", branchName: "Chapel",
  createdAt: "2026-11-26T12:00:00Z", updatedAt: "2026-11-26T12:00:00Z",
  media: [{ id: "media-1", url: "https://res.cloudinary.com/example/image/upload/file.jpg", mediaType, position: 0 }],
  likeCount: 0, commentCount: 0, isLiked: false,
});

describe("Upper Room image card", () => {
  const drawImage = vi.fn();
  beforeEach(() => {
    drawImage.mockReset();
    const gradient = { addColorStop: vi.fn() };
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      createLinearGradient: () => gradient, fillRect: vi.fn(), drawImage,
      beginPath: vi.fn(), arc: vi.fn(), fill: vi.fn(), stroke: vi.fn(), fillText: vi.fn(),
      measureText: (value: string) => ({ width: value.length * 10 }),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => callback(new Blob(["card"], { type: "image/png" })));
    vi.stubGlobal("createImageBitmap", vi.fn(async () => ({ width: 1200, height: 630, close: vi.fn() })));
  });

  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it.each(["IMAGE", "VIDEO"] as const)("renders the %s preview instead of initials", async (mediaType) => {
    const fetchMock = vi.fn(async () => ({ ok: true, blob: async () => new Blob(["still"], { type: "image/jpeg" }) }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await createUpperRoomShareCard(mediaPost(mediaType));
    expect(result.type).toBe("image/png");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/social/media/media-1/share-preview/", expect.objectContaining({ credentials: "include" }));
    expect(drawImage).toHaveBeenCalled();
  });

  it("rejects a failed media preview rather than making a misleading initials card", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("Unavailable", { status: 502 })));
    await expect(createUpperRoomShareCard(mediaPost("IMAGE"))).rejects.toThrow("photo or video preview could not be loaded");
    expect(drawImage).not.toHaveBeenCalled();
  });

  it("extracts a frame when the authorized preview is a bucket video", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, blob: async () => new Blob(["video"], { type: "video/mp4" }) })));
    vi.stubGlobal("URL", class extends URL {
      static createObjectURL() { return "blob:https://chapelflow.test/clip"; }
      static revokeObjectURL() { /* The test checks the generated frame. */ }
    });
    vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(function (this: HTMLMediaElement) {
      Object.defineProperty(this, "videoWidth", { configurable: true, value: 640 });
      Object.defineProperty(this, "videoHeight", { configurable: true, value: 360 });
      queueMicrotask(() => this.onloadeddata?.(new Event("loadeddata")));
    });
    await createUpperRoomShareCard(mediaPost("VIDEO"));
    expect(drawImage).toHaveBeenCalledTimes(2); // Video to frame, then frame to card.
  });
});
