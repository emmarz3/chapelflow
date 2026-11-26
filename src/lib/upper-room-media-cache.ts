import type { UpperRoomPost } from "../services/chapelflow";

const DATABASE_NAME = "chapelflow-upper-room-media";
const DATABASE_VERSION = 1;
const STORE_NAME = "recent-posts";
const MAX_RECENT_POSTS = 12;
const MAX_CACHED_BYTES = 150 * 1024 * 1024;
const MAX_MEDIA_BYTES = 50 * 1024 * 1024;

export interface CachedUpperRoomPost {
  key: string;
  userId: string;
  post: UpperRoomPost;
  media: Array<{ id: string; blob: Blob; bytes: number; contentType: string }>;
  savedAt: number;
  bytes: number;
}

function openDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("Offline media storage is not available in this browser."));
  }
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: "key" });
        store.createIndex("userId", "userId", { unique: false });
        store.createIndex("savedAt", "savedAt", { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open offline media storage."));
    request.onblocked = () => reject(new Error("Offline media storage is busy in another tab."));
  });
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Offline media storage failed."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline media storage was interrupted."));
  });
}

function readUserRecords(store: IDBObjectStore, userId: string): Promise<CachedUpperRoomPost[]> {
  return new Promise((resolve, reject) => {
    const request = store.index("userId").getAll(userId);
    request.onsuccess = () => resolve((request.result || []) as CachedUpperRoomPost[]);
    request.onerror = () => reject(request.error || new Error("Could not read recent media."));
  });
}

async function fetchMediaBlob(url: string): Promise<Blob | null> {
  try {
    const resolved = new URL(url, window.location.href);
    if (resolved.protocol !== "https:" && resolved.origin !== window.location.origin) return null;
    const response = await fetch(resolved.href, {
      method: "GET",
      credentials: "include",
      mode: "cors",
      cache: "no-store",
    });
    if (!response.ok) return null;
    const blob = await response.blob();
    if (!blob.size || blob.size > MAX_MEDIA_BYTES) return null;
    if (!blob.type.startsWith("image/") && !blob.type.startsWith("video/")) return null;
    return blob;
  } catch {
    return null;
  }
}

export async function saveRecentUpperRoomPost(
  userId: string,
  post: UpperRoomPost,
): Promise<{ cachedCount: number; mediaCount: number; bytes: number }> {
  if (!userId || !post.media.length || post.isStory) {
    return { cachedCount: 0, mediaCount: post.media.length, bytes: 0 };
  }

  const downloaded = await Promise.all(
    post.media.map(async (item) => {
      const blob = await fetchMediaBlob(item.url);
      return blob ? { id: item.id, blob, bytes: blob.size, contentType: blob.type } : null;
    }),
  );
  const media = downloaded.filter(
    (item): item is NonNullable<typeof item> => item !== null,
  );
  const bytes = media.reduce((total, item) => total + item.bytes, 0);
  const record: CachedUpperRoomPost = {
    key: userId + ":" + post.id,
    userId,
    post,
    media,
    savedAt: Date.now(),
    bytes,
  };

  const database = await openDatabase();
  const transaction = database.transaction(STORE_NAME, "readwrite");
  const store = transaction.objectStore(STORE_NAME);
  store.put(record);

  const allRequest = store.index("userId").getAll(userId);
  allRequest.onsuccess = () => {
    const records = (allRequest.result as CachedUpperRoomPost[])
      .sort((left, right) => right.savedAt - left.savedAt);
    let retainedPosts = 0;
    let retainedBytes = 0;
    for (const item of records) {
      const keep = retainedPosts < MAX_RECENT_POSTS &&
        (retainedPosts === 0 || retainedBytes + item.bytes <= MAX_CACHED_BYTES);
      if (keep) {
        retainedPosts += 1;
        retainedBytes += item.bytes;
      } else {
        store.delete(item.key);
      }
    }
  };
  await transactionDone(transaction);
  database.close();
  return { cachedCount: media.length, mediaCount: post.media.length, bytes };
}

export async function getRecentUpperRoomPosts(userId: string): Promise<CachedUpperRoomPost[]> {
  if (!userId) return [];
  const database = await openDatabase();
  const transaction = database.transaction(STORE_NAME, "readonly");
  const records = await readUserRecords(transaction.objectStore(STORE_NAME), userId);
  await transactionDone(transaction);
  database.close();
  return records.sort((left, right) => right.savedAt - left.savedAt).slice(0, MAX_RECENT_POSTS);
}

export async function clearRecentUpperRoomMedia(): Promise<void> {
  for (const key of Object.keys(window.localStorage)) {
    if (key.startsWith("chapelflow:recent-media:")) window.localStorage.removeItem(key);
  }
  if (typeof indexedDB === "undefined") return;
  try {
    const database = await openDatabase();
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).clear();
    await transactionDone(transaction);
    database.close();
  } catch {
    // Sign-out must continue even if browser storage has already been disabled or cleared.
  }
}
