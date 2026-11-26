/** Resize large photos before uploading; videos remain untouched. */
export async function prepareSocialMedia(files: File[]): Promise<File[]> {
  return Promise.all(files.map(async (file) => {
    if (!file.type.startsWith("image/") || file.type === "image/gif" || file.size < 2 * 1024 * 1024) return file;
    const url = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.src = url;
      await image.decode();
      const factor = Math.min(1, 1920 / Math.max(image.naturalWidth, image.naturalHeight));
      if (!image.naturalWidth || !image.naturalHeight) return file;
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(image.naturalWidth * factor);
      canvas.height = Math.round(image.naturalHeight * factor);
      const context = canvas.getContext("2d");
      if (!context) return file;
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", 0.82));
      return blob && blob.size < file.size ? new File([blob], file.name.replace(/\.[^.]+$/, ".webp"), { type: "image/webp" }) : file;
    } catch { return file; }
    finally { URL.revokeObjectURL(url); }
  }));
}
