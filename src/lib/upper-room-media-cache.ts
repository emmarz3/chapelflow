const CACHE_PREFIX = "chapelflow-upper-room-media-v1-";
const INDEX_PREFIX = "chapelflow-upper-room-media-index-v1-";
const MAX_MEDIA_BYTES = 50 * 1024 * 1024;
const MAX_CACHE_BYTES = 120 * 1024 * 1024;

interface CacheIndexEntry {
  mediaId: string;
  url: string;
  size: number;
  lastAccessedAt: number;
}

function cacheName(userId: string) {
  return `${CACHE_PREFIX}${encodeURIComponent(userId)}`;
}

function indexKey(userId: string) {
  return `${INDEX_PREFIX}${userId}`;
}

function absoluteUrl(url: string) {
  if (typeof window === "undefined") return url;
  return new URL(url, window.location.origin).toString();
}

function readIndex(userId: string): CacheIndexEntry[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(indexKey(userId)) || "[]");
    return Array.isArray(parsed) ? parsed as CacheIndexEntry[] : [];
  } catch {
    return [];
  }
}

function writeIndex(userId: string, entries: CacheIndexEntry[]) {
  try {
    localStorage.setItem(indexKey(userId), JSON.stringify(entries));
  } catch {
    // Cache Storage remains usable even when localStorage is full or disabled.
  }
}

function touchIndex(userId: string, mediaId: string, url: string, size: number) {
  const entries = readIndex(userId).filter((entry) => entry.mediaId !== mediaId);
  entries.push({ mediaId, url, size, lastAccessedAt: Date.now() });
  return entries;
}

/** Save a recently opened Upper Room asset for offline re-opening. */
export async function cacheUpperRoomMedia(userId: string, mediaId: string, url: string): Promise<boolean> {
  if (!userId || typeof caches === "undefined" || typeof fetch === "undefined") return false;
  const key = absoluteUrl(url);
  try {
    const cache = await caches.open(cacheName(userId));
    const existing = await cache.match(key);
    if (existing) {
      const blob = await existing.blob();
      writeIndex(userId, touchIndex(userId, mediaId, key, blob.size));
      return true;
    }

    const response = await fetch(key, { method: "GET", credentials: "include", cache: "no-store" });
    if (!response.ok || response.type === "opaque") return false;
    const blob = await response.blob();
    if (!blob.size || blob.size > MAX_MEDIA_BYTES) return false;

    await cache.put(key, new Response(blob, {
      status: 200,
      headers: {
        "Content-Type": blob.type || response.headers.get("Content-Type") || "application/octet-stream",
        "X-ChapelFlow-Cached": "1",
      },
    }));

    let entries = touchIndex(userId, mediaId, key, blob.size);
    let totalBytes = entries.reduce((sum, entry) => sum + entry.size, 0);
    entries.sort((a, b) => a.lastAccessedAt - b.lastAccessedAt);
    while (totalBytes > MAX_CACHE_BYTES && entries.length > 1) {
      const oldest = entries.shift()!;
      await cache.delete(oldest.url);
      totalBytes -= oldest.size;
    }
    writeIndex(userId, entries);
    return true;
  } catch {
    // Offline mode, browser quota, storage policy, or CORS may prevent caching.
    return false;
  }
}

/** Return a temporary object URL for an offline copy, or null if not cached. */
export async function getCachedUpperRoomMediaUrl(userId: string, mediaId: string, url: string): Promise<string | null> {
  if (!userId || typeof caches === "undefined") return null;
  try {
    const key = absoluteUrl(url);
    const cache = await caches.open(cacheName(userId));
    const response = await cache.match(key);
    if (!response) return null;
    const blob = await response.blob();
    if (!blob.size) return null;
    writeIndex(userId, touchIndex(userId, mediaId, key, blob.size));
    return URL.createObjectURL(blob);
  } catch {
    return null;
  }
}

/** Remove cached Upper Room media for the currently signed-in account. */
export async function clearUpperRoomMediaCache(userId: string): Promise<void> {
  if (!userId || typeof caches === "undefined") return;
  try {
    await caches.delete(cacheName(userId));
    localStorage.removeItem(indexKey(userId));
  } catch {
    // A browser may deny cache deletion; it must not block the feed.
  }
}
