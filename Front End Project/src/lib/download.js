const EXTENSIONS = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/avif": "avif",
  "image/gif": "gif",
  "image/svg+xml": "svg",
};

function safeFilename(title) {
  const base = String(title || "wallpaper")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return base || "wallpaper";
}

/** Fetch an image URL as a blob and hand it to the browser's downloader. */
export async function downloadFromUrl(url, title) {
  // Cross-origin <a download> is unreliable. Fetch a real image blob instead.
  const response = await fetch(url, { signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw new Error("The image host did not return an image.");
  const blob = await response.blob();
  if (!blob.size || !blob.type.startsWith("image/"))
    throw new Error("The image source is unavailable.");
  const extension = EXTENSIONS[blob.type] || "img";
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = `${safeFilename(title)}.${extension}`;
  document.body.append(link);
  link.click();
  link.remove();
  // Leave time for the browser to start reading the blob.
  const revoke = setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
  // Node keeps the process alive for pending timers; browsers return a number.
  revoke?.unref?.();
}

export async function downloadWallpaper(wallpaper) {
  // Local catalogue mode: the image URL itself is the source of truth.
  return downloadFromUrl(wallpaper.url, wallpaper.title);
}
