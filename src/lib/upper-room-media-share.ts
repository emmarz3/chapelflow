import type { UpperRoomPost } from "../services/chapelflow";

const MAX_MEDIA_FILE_BYTES = 50 * 1024 * 1024;
const MAX_TOTAL_SHARE_BYTES = 150 * 1024 * 1024;

const EXTENSION_BY_MIME: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/gif": "gif",
  "image/webp": "webp",
  "video/mp4": "mp4",
  "video/quicktime": "mov",
  "video/webm": "webm",
};

function expectedMediaPrefix(mediaType: "IMAGE" | "VIDEO"): string {
  return mediaType === "VIDEO" ? "video/" : "image/";
}

function mediaFilename(postId: string, index: number, mimeType: string): string {
  const extension = EXTENSION_BY_MIME[mimeType.toLowerCase()] || (mimeType.startsWith("video/") ? "mp4" : "jpg");
  return `upper-room-${postId.slice(0, 8)}-${index + 1}.${extension}`;
}

async function fetchMediaFile(
  post: UpperRoomPost,
  media: UpperRoomPost["media"][number],
  index: number,
): Promise<File> {
  if (!media.url) {
    throw new Error(`Media file ${index + 1} is not available. Reopen the post while online and try again.`);
  }

  let url: URL;
  try {
    url = new URL(media.url, window.location.href);
  } catch {
    throw new Error(`Media file ${index + 1} has an invalid address.`);
  }

  const isSameOriginBlob = url.protocol === "blob:" && url.origin === window.location.origin;
  if (!isSameOriginBlob && url.protocol !== "https:" && url.origin !== window.location.origin) {
    throw new Error(`Media file ${index + 1} must use a secure address.`);
  }

  let response: Response;
  try {
    response = await fetch(url.href, {
      method: "GET",
      credentials: "same-origin",
      mode: "cors",
      cache: "no-store",
    });
  } catch {
    throw new Error(`Could not retrieve media file ${index + 1}. Check the media storage access and try again.`);
  }

  if (!response.ok) {
    throw new Error(`Media file ${index + 1} could not be retrieved (HTTP ${response.status}).`);
  }

  const blob = await response.blob();
  if (!blob.size) {
    throw new Error(`Media file ${index + 1} is empty.`);
  }
  if (blob.size > MAX_MEDIA_FILE_BYTES) {
    throw new Error(`Media file ${index + 1} exceeds the 50 MB sharing limit.`);
  }

  const mimeType = (blob.type || response.headers.get("content-type") || "").split(";")[0]?.trim().toLowerCase() || "";
  const expectedPrefix = expectedMediaPrefix(media.mediaType);
  if (!mimeType.startsWith(expectedPrefix)) {
    throw new Error(`Media file ${index + 1} is not a valid ${media.mediaType.toLowerCase()} file.`);
  }

  return new File([blob], mediaFilename(post.id, index, mimeType), {
    type: mimeType,
    lastModified: Date.now(),
  });
}

export async function createUpperRoomMediaFiles(post: UpperRoomPost): Promise<File[]> {
  if (!post.media.length) return [];

  const files: File[] = [];
  let totalBytes = 0;
  for (let index = 0; index < post.media.length; index += 1) {
    const media = post.media[index];
    if (!media) throw new Error("An attached media file is missing from this post.");
    const file = await fetchMediaFile(post, media, index);
    if (totalBytes + file.size > MAX_TOTAL_SHARE_BYTES) {
      throw new Error("The combined media files exceed the 150 MB sharing limit. Share fewer files at a time.");
    }
    totalBytes += file.size;
    files.push(file);
  }
  return files;
}

export function downloadUpperRoomMediaFiles(files: File[]): void {
  files.forEach((file, index) => {
    const url = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = file.name;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000 + index * 250);
  });
}

export function formatShareFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
