import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { boardNameFromFile, detectType, isImage, matcher, uniqueName } from "../lib/boards";

const DEFAULT_TYPES = ["Softboard", "Longboard", "Midlength", "Funboard", "Shortboard"];
// The prototype's board names and photo file names only (no customers): tests/fixtures/prototype-boards.json.
const { files, boards }: { files: string[]; boards: { name: string; cat: string; file: string }[] } =
  JSON.parse(readFileSync("tests/fixtures/prototype-boards.json", "utf8"));
const prototype = { boards };

test("all 95 real file names get the expected types", () => {
  expect(files).toHaveLength(95);
  const counts: Record<string, number> = {};
  for (const f of files) {
    const type = detectType(boardNameFromFile(f), "Archive/" + f, DEFAULT_TYPES);
    counts[type] = (counts[type] ?? 0) + 1;
  }
  expect(counts).toEqual({ Funboard: 20, Longboard: 7, Midlength: 19, Shortboard: 49 });
});

test("names and types match what the prototype made from the same photos", () => {
  const taken = new Set<string>();
  for (const b of prototype.boards) {
    const base = boardNameFromFile(b.file);
    const name = uniqueName(base, taken);
    taken.add(name);
    expect([name, detectType(base, "", DEFAULT_TYPES)]).toEqual([b.name, b.cat]);
  }
});

test("file name -> board name", () => {
  expect(boardNameFromFile("FUNBOARD 6'10 SWOLLOW TORQ  .HEIC")).toBe("FUNBOARD 6'10 SWOLLOW TORQ");
  expect(boardNameFromFile("MIDLENGTH 7'4 TORQ. .HEIC")).toBe("MIDLENGTH 7'4 TORQ");
  expect(boardNameFromFile("LONGBOARD  9'1   NOSERIDER.jpg")).toBe("LONGBOARD 9'1 NOSERIDER");
});

test("duplicate models become #2, #3, #4", () => {
  const taken = new Set<string>();
  const names = ["X  .HEIC", "X .HEIC", "X..HEIC", "X.HEIC"].map((f) => {
    const name = uniqueName(boardNameFromFile(f), taken);
    taken.add(name);
    return name;
  });
  expect(names).toEqual(["X", "X #2", "X #3", "X #4"]);
});

test("type detection rules from the spec", () => {
  expect(detectType("FUNBOARD-SHORT 6'4 TORQ", "", DEFAULT_TYPES)).toBe("Funboard");
  expect(detectType("SHORTBOARD-FISH 5'4", "", DEFAULT_TYPES)).toBe("Shortboard");
  expect(detectType("MIDLENGTH 7'6 TORQ HYBRID-SOFT", "", DEFAULT_TYPES)).toBe("Midlength");
  expect(detectType("SUP 10'6", "", [...DEFAULT_TYPES, "SUP"])).toBe("SUP");
  expect(detectType("FUNBOARD 7'0", "", ["Longboard", "Fun / Mini-Mal"])).toBe("Fun / Mini-Mal");
  expect(detectType("Blue soft 8'0", "", DEFAULT_TYPES)).toBe("Softboard");
  expect(detectType("IMG_0423", "Boards/Longboards/IMG_0423.jpg", DEFAULT_TYPES)).toBe("Longboard");
  expect(detectType("Blue soft 8'0", "", ["Longboard"])).toBe("Other"); // keyword type doesn't exist
  expect(detectType("IMG_0423", "", DEFAULT_TYPES)).toBe("Other");
});

test("import keeps images and HEIC (even without a MIME type), skips the rest", () => {
  expect(isImage({ name: "A.HEIC", type: "" })).toBe(true);
  expect(isImage({ name: "a.jpg", type: "image/jpeg" })).toBe(true);
  expect(isImage({ name: ".DS_Store", type: "" })).toBe(false);
  expect(isImage({ name: "notes.txt", type: "text/plain" })).toBe(false);
});

test("search: every word must match", () => {
  expect(matcher("torq 7'6")("MIDLENGTH 7'6 TORQ")).toBe(true);
  expect(matcher("torq 7'4")("MIDLENGTH 7'6 TORQ")).toBe(false);
  expect(matcher("  ")("anything")).toBe(true);
});
