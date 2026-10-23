// Board naming and type detection for the photo-folder import (SPEC section 6). Pure functions, unit tested.

// "FUNBOARD 6'10 SWOLLOW TORQ  .HEIC" -> "FUNBOARD 6'10 SWOLLOW TORQ"
export const boardNameFromFile = (fileName: string) =>
  fileName.replace(/\.[^.]+$/, "").replace(/[\s.]+$/, "").replace(/\s+/g, " ").trim();

// The owner made duplicate models unique with trailing spaces/dots: those are different boards -> NAME, NAME #2, NAME #3.
export function uniqueName(base: string, taken: Set<string>) {
  let name = base;
  for (let n = 2; taken.has(name); n++) name = `${base} #${n}`;
  return name;
}

const KEYWORDS: [type: string, re: RegExp][] = [
  ["Softboard", /soft|foam/i],
  ["Longboard", /long/i],
  ["Midlength", /mid/i],
  ["Funboard", /fun|mini|malibu/i],
  ["Shortboard", /short|fish/i],
];

// First match wins: the name's first word against each type's first word ("FUNBOARD-SHORT 6'4" -> Funboard,
// "SUP 10'6" -> SUP, a type renamed "Fun / Mini-Mal" still matches FUNBOARD), then keywords in the name,
// then in the folder path, otherwise "Other". `types` are the existing type names, without "Other".
export function detectType(base: string, path: string, types: string[]) {
  const first = base.split(/[\s_-]/)[0].toLowerCase();
  const key = (type: string) => type.toLowerCase().match(/[a-z0-9]+/)?.[0] ?? "";
  const named = first.length > 2 && types.find((t) => key(t).length > 2 && (key(t).startsWith(first) || first.startsWith(key(t))));
  const keyword = (s: string) => KEYWORDS.find(([type, re]) => types.includes(type) && re.test(s))?.[0];
  return named || keyword(first) || keyword(base) || keyword(path) || "Other";
}

// Images the import keeps: anything the browser calls an image, plus HEIC/HEIF (Windows gives HEIC no MIME type).
export const isHeic = (f: { name: string; type: string }) => /\.hei[cf]$/i.test(f.name) || /hei[cf]/i.test(f.type);
export const isImage = (f: { name: string; type: string }) => f.type.startsWith("image/") || isHeic(f);

// Search where every word must appear: "torq 7'6" finds "MIDLENGTH 7'6 TORQ".
export function matcher(query: string) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return (s: string) => words.every((w) => s.toLowerCase().includes(w));
}

export const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name, undefined, { numeric: true });
