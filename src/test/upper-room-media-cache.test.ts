import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cacheUpperRoomMedia,
  clearUpperRoomMediaCache,
  getCachedUpperRoomMediaUrl,
} from "../lib/upper-room-media-cache";

describe("Upper Room offline media cache", () => {
  let store: Map<string, Response>;
  let cache: {
    match: ReturnType<typeof vi.fn>;
    put: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    store = new Map();
    cache = {
      match: vi.fn(async (key: string) => store.get(key)?.clone()),
      put: vi.fn(async (key: string, response: Response) => { store.set(key, response.clone()); }),
      delete: vi.fn(async (key: string) => store.delete(key)),
    };
    vi.stubGlobal("caches", {
      open: vi.fn(async () => cache),
      delete: vi.fn(async () => { store.clear(); return true; }),
    });
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      new Blob(["upper-room-photo"], { type: "image/jpeg" }),
      { status: 200, headers: { "Content-Type": "image/jpeg" } },
    )));
    URL.createObjectURL = vi.fn(() => "blob:cached-upper-room");
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("stores media once and returns a local object URL for offline re-opening", async () => {
    const saved = await cacheUpperRoomMedia("member-1", "media-1", "/api/v1/social/media/media-1/");
    expect(saved).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(1);

    const cachedUrl = await getCachedUpperRoomMediaUrl("member-1", "media-1", "/api/v1/social/media/media-1/");
    expect(cachedUrl).toBe("blob:cached-upper-room");
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);

    const secondSave = await cacheUpperRoomMedia("member-1", "media-1", "/api/v1/social/media/media-1/");
    expect(secondSave).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("clears cached files and the account cache index", async () => {
    await cacheUpperRoomMedia("member-1", "media-1", "/api/v1/social/media/media-1/");
    await clearUpperRoomMediaCache("member-1");

    expect(caches.delete).toHaveBeenCalledWith("chapelflow-upper-room-media-v1-member-1");
    expect(localStorage.getItem("chapelflow-upper-room-media-index-v1-member-1")).toBeNull();
    expect(store.size).toBe(0);
  });

  it("degrades safely when Cache Storage is unavailable", async () => {
    vi.stubGlobal("caches", undefined);
    await expect(cacheUpperRoomMedia("member-1", "media-1", "/media/photo.jpg")).resolves.toBe(false);
    await expect(getCachedUpperRoomMediaUrl("member-1", "media-1", "/media/photo.jpg")).resolves.toBeNull();
  });
});
