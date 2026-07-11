// Decode a JPEG frame (ArrayBuffer) into something drawable on a canvas.
// Prefers createImageBitmap (fast, off-main-thread); falls back to an <img>.
export type Drawable = ImageBitmap | HTMLImageElement;

export async function decodeFrame(buf: ArrayBuffer): Promise<Drawable | null> {
  const blob = new Blob([buf], { type: "image/jpeg" });
  if ("createImageBitmap" in window) {
    try {
      return await createImageBitmap(blob);
    } catch {
      /* fall through */
    }
  }
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(null);
    };
    img.src = url;
  });
}

export function drawableSize(d: Drawable): { w: number; h: number } {
  if (d instanceof HTMLImageElement) return { w: d.naturalWidth, h: d.naturalHeight };
  return { w: d.width, h: d.height };
}
