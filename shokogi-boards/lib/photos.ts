// Board photos (SPEC section 5): two JPEGs per board in the public "boards" bucket, a large one for
// Board details and a thumb for grids and tables. Browser-only.
import type { SupabaseClient } from "@supabase/supabase-js";
import { isHeic } from "./boards";

export const photoUrl = (path: string | null) =>
  path ? `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/boards/${path}` : "";

// iPhone HEIC can't be opened by most browsers, so heic-to decodes it (loaded only when needed).
async function decode(file: File) {
  if (!isHeic(file)) return createImageBitmap(file);
  const { heicTo } = await import("heic-to");
  return heicTo({ blob: file, type: "bitmap" });
}

function toJpeg(bitmap: ImageBitmap, max: number, quality: number) {
  const k = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * k);
  canvas.height = Math.round(bitmap.height * k);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Couldn't encode the photo"))), "image/jpeg", quality));
}

type BoardPhoto = { id: string; photo_path: string | null; thumb_path: string | null };

// Uploads a new photo for the board and removes the old files. New file names also bust any cached copy.
export async function setBoardPhoto(db: SupabaseClient, board: BoardPhoto, file: File) {
  const bitmap = await decode(file);
  let large: Blob, thumb: Blob;
  try {
    large = await toJpeg(bitmap, 1600, 0.85);
    thumb = await toJpeg(bitmap, 400, 0.8);
  } finally {
    bitmap.close(); // free the full-size photo now, or a 95-photo import runs out of memory
  }
  const stamp = Date.now();
  const paths = { photo_path: `${board.id}/${stamp}.jpg`, thumb_path: `${board.id}/${stamp}-thumb.jpg` };
  const bucket = db.storage.from("boards");
  for (const [path, blob] of [[paths.photo_path, large], [paths.thumb_path, thumb]] as const) {
    const { error } = await bucket.upload(path, blob, { contentType: "image/jpeg" });
    if (error) throw error;
  }
  await db.from("boards").update(paths).eq("id", board.id).throwOnError();
  const old = [board.photo_path, board.thumb_path].filter((p): p is string => !!p);
  if (old.length) await bucket.remove(old); // best effort: a leftover file is harmless
  return paths;
}
