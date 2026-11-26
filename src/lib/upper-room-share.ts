import type { UpperRoomPost } from "../services/chapelflow";

const WIDTH = 1200;
const HEIGHT = 630;

function wrapText(
  context: CanvasRenderingContext2D,
  value: string,
  maxWidth: number,
  maxLines: number,
): string[] {
  const words = value.trim().split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";
  let truncated = false;
  for (const word of words) {
    const candidate = line ? line + " " + word : word;
    if (line && context.measureText(candidate).width > maxWidth) {
      lines.push(line);
      line = word;
      if (lines.length === maxLines) {
        truncated = true;
        break;
      }
    } else {
      line = candidate;
    }
  }
  if (line && lines.length < maxLines) lines.push(line);
  else if (line) truncated = true;
  if (truncated && lines.length > 0) {
    const last = lines[maxLines - 1] || "";
    lines[maxLines - 1] = last.length > 3 ? last.replace(/[.,;:!?]?$/, "…") : last + "…";
  }
  return lines;
}

async function loadShareImage(post: UpperRoomPost): Promise<ImageBitmap | null> {
  const media = post.media.find((item) => item.mediaType === "IMAGE");
  if (!media?.url) return null;
  try {
    const response = await fetch(media.url, { credentials: "same-origin", mode: "cors", cache: "no-store" });
    if (!response.ok) return null;
    const blob = await response.blob();
    if (!blob.type.startsWith("image/")) return null;
    return await createImageBitmap(blob);
  } catch {
    return null;
  }
}

export async function createUpperRoomShareCard(post: UpperRoomPost): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser could not create the share image.");

  const background = context.createLinearGradient(0, 0, WIDTH, HEIGHT);
  background.addColorStop(0, "#21102f");
  background.addColorStop(0.58, "#47245f");
  background.addColorStop(1, "#68427b");
  context.fillStyle = background;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  const photo = await loadShareImage(post);
  if (photo) {
    const imageWidth = 520;
    const scale = Math.max(imageWidth / photo.width, HEIGHT / photo.height);
    const cropWidth = imageWidth / scale;
    const cropHeight = HEIGHT / scale;
    const sx = Math.max(0, (photo.width - cropWidth) / 2);
    const sy = Math.max(0, (photo.height - cropHeight) / 2);
    context.drawImage(photo, sx, sy, cropWidth, cropHeight, 0, 0, imageWidth, HEIGHT);
    photo.close();
    const shade = context.createLinearGradient(430, 0, 610, 0);
    shade.addColorStop(0, "rgba(33,16,47,0)");
    shade.addColorStop(1, "#2c1740");
    context.fillStyle = shade;
    context.fillRect(420, 0, 210, HEIGHT);
  } else {
    context.fillStyle = "rgba(232,196,94,.12)";
    context.beginPath();
    context.arc(255, 315, 165, 0, Math.PI * 2);
    context.fill();
    context.strokeStyle = "rgba(232,196,94,.55)";
    context.lineWidth = 3;
    context.beginPath();
    context.arc(255, 315, 118, 0, Math.PI * 2);
    context.stroke();
    context.fillStyle = "#f1d78e";
    context.font = "700 116px Arial, sans-serif";
    context.textAlign = "center";
    const initials = post.authorName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "UR";
    context.fillText(initials, 255, 355);
    context.textAlign = "left";
  }

  const panelX = 600;
  const panelWidth = WIDTH - panelX;
  const overlay = context.createLinearGradient(panelX, 0, WIDTH, HEIGHT);
  overlay.addColorStop(0, "rgba(44,23,64,.96)");
  overlay.addColorStop(1, "rgba(33,16,47,.99)");
  context.fillStyle = overlay;
  context.fillRect(panelX, 0, panelWidth, HEIGHT);

  context.fillStyle = "#e8c45e";
  context.fillRect(665, 88, 56, 5);
  context.fillStyle = "#f3d989";
  context.font = "700 22px Arial, sans-serif";
  context.fillText("CHAPELFLOW", 665, 135);
  context.fillStyle = "#ffffff";
  context.font = "700 40px Arial, sans-serif";
  context.fillText("THE UPPER ROOM", 665, 190);

  context.fillStyle = "#f6eef9";
  context.font = "600 31px Arial, sans-serif";
  const caption = post.caption || "A moment from our chapel community.";
  const lines = wrapText(context, caption, 455, 5);
  let captionY = 285;
  for (const line of lines) {
    context.fillText(line, 665, captionY);
    captionY += 47;
  }

  context.fillStyle = "#e8c45e";
  context.fillRect(665, 510, 62, 2);
  context.fillStyle = "#ffffff";
  context.font = "700 23px Arial, sans-serif";
  context.fillText(post.authorName || "Chapel member", 665, 558);
  context.fillStyle = "#d7c8df";
  context.font = "18px Arial, sans-serif";
  context.fillText(post.branchName || "Chrisland University Chapel", 665, 590);

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("The share image could not be generated."));
    }, "image/png");
  });
}

export async function createUpperRoomShareFile(post: UpperRoomPost): Promise<File> {
  const image = await createUpperRoomShareCard(post);
  return new File([image], "upper-room-" + post.id + ".png", { type: "image/png" });
}

export function downloadShareImage(file: File): void {
  const url = URL.createObjectURL(file);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.name;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
