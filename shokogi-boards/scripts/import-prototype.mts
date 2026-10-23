// Moves the prototype's data into the app (SPEC section 11). Safe to run again: nothing is added twice.
//
//   node scripts/import-prototype.mts <folder with data.json and photos/> [--dry-run]
//
// Targets the LOCAL Supabase from .env.local, unless IMPORT_SUPABASE_URL and IMPORT_SUPABASE_SECRET_KEY are set.
//
// - Board types and rental lengths the app doesn't have yet are added.
// - Boards match on the original photo file name (source_file_name), then on the prototype id; matched boards keep
//   their name and photo (a folder import has sharper photos) but take the prototype's repair state and notes.
//   New boards get the prototype's photo: large as is (800 px) and a 400 px thumb.
// - Customers: same phone digits, or without a phone the same name; otherwise new.
// - Rentals keep the prototype ids, so a rental is only ever imported once. Returned rentals close their board at
//   exactly the return time (that's how History tells "brought back" from "swapped out").
// - A board that only exists in the history (deleted in the prototype) comes back as a deleted board, so the history keeps its name.
import { createClient } from "@supabase/supabase-js";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import sharp from "sharp";

type ProtoBoard = { id: string; name: string; cat: string; file?: string; photo?: number; repair?: boolean; notes?: string };
type ProtoRenter = { id: string; name: string; phone?: string; boardId: string | null; since: number; until: number | null };
type ProtoHistory = ProtoRenter & { board: string; cat: string; ended: number };
type Proto = { boards: ProtoBoard[]; renters: ProtoRenter[]; history?: ProtoHistory[]; settings?: { cats?: string[]; lengths?: { label: string; mins: number }[] } };

const [folder] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
const dryRun = process.argv.includes("--dry-run");
if (!folder) throw new Error("Usage: node scripts/import-prototype.mts <folder with data.json and photos/> [--dry-run]");
if (!process.env.IMPORT_SUPABASE_URL) process.loadEnvFile(".env.local");
const url = process.env.IMPORT_SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL!;
const db = createClient(url, process.env.IMPORT_SUPABASE_SECRET_KEY ?? process.env.SUPABASE_SECRET_KEY!, { auth: { persistSession: false } });
const proto: Proto = JSON.parse(readFileSync(join(folder, "data.json"), "utf8"));
const iso = (ms: number) => new Date(ms).toISOString();
const count = { types: 0, lengths: 0, boardsMatched: 0, boardsNew: 0, photos: 0, deletedBoards: 0, customersNew: 0, rentalsActive: 0, rentalsReturned: 0, skipped: 0 };
const notes: string[] = [];
const write = async <T,>(label: string, action: () => PromiseLike<{ data: T; error: unknown }>) => {
  if (dryRun) return null;
  const { data, error } = await action();
  if (error) throw new Error(`${label}: ${(error as Error).message}`);
  return data;
};
console.log(`${dryRun ? "DRY RUN against" : "Importing into"} ${url}: ${proto.boards.length} boards, ${proto.renters.length} active rentals, ${proto.history?.length ?? 0} returned.`);

// ---------- Board types and rental lengths ----------
const { data: typeRows } = await db.from("board_types").select("id, name, sort_order, is_system").throwOnError();
const types = typeRows!;
for (const name of proto.settings?.cats ?? []) {
  if (types.some((t) => t.name.toLowerCase() === name.toLowerCase())) continue;
  const sort_order = Math.max(0, ...types.filter((t) => !t.is_system).map((t) => t.sort_order)) + 1;
  const row = await write("type", () => db.from("board_types").insert({ name, sort_order }).select().single());
  types.push(row ?? { id: `new:${name}`, name, sort_order, is_system: false });
  count.types++;
}
const typeId = (name: string) => (types.find((t) => t.name.toLowerCase() === name?.toLowerCase()) ?? types.find((t) => t.is_system)!).id;

const { data: lengths } = await db.from("rental_lengths").select("label, minutes").throwOnError();
for (const l of proto.settings?.lengths ?? []) {
  if (lengths!.some((x) => x.minutes === l.mins && x.label === l.label)) continue;
  await write("length", () => db.from("rental_lengths").insert({ label: l.label, minutes: l.mins }));
  count.lengths++;
}

// ---------- Boards ----------
const { data: existing } = await db.from("boards").select("id, name, source_file_name, photo_path, notes, in_repair, deleted_at").throwOnError();
const boardId = new Map<string, string>(); // prototype board id -> app board id

async function uploadPhoto(id: string, protoId: string) {
  const file = join(folder, "photos", `${protoId}.jpg`);
  if (!existsSync(file)) return null;
  const stamp = Date.now(), large = readFileSync(file);
  const thumb = await sharp(large).rotate().resize(400, 400, { fit: "inside", withoutEnlargement: true }).jpeg({ quality: 80 }).toBuffer();
  const paths = { photo_path: `${id}/${stamp}.jpg`, thumb_path: `${id}/${stamp}-thumb.jpg` };
  if (dryRun) return paths;
  for (const [path, body] of [[paths.photo_path, large], [paths.thumb_path, thumb]] as const) {
    const { error } = await db.storage.from("boards").upload(path, body, { contentType: "image/jpeg" });
    if (error) throw new Error(`photo ${path}: ${error.message}`);
  }
  count.photos++;
  return paths;
}

for (const b of proto.boards) {
  const live = existing!.filter((x) => !x.deleted_at);
  const match = live.find((x) => b.file && x.source_file_name === b.file) ?? existing!.find((x) => x.id === b.id);
  if (match) {
    boardId.set(b.id, match.id);
    count.boardsMatched++;
    if (match.name !== b.name) notes.push(`Board "${match.name}" is "${b.name}" in the prototype (kept "${match.name}").`);
    const changes: Record<string, unknown> = { in_repair: b.repair ? 1 : 0 };
    if (b.notes && !match.notes) changes.notes = b.notes;
    if (!match.photo_path) Object.assign(changes, await uploadPhoto(match.id, b.id));
    await write("board", () => db.from("boards").update(changes).eq("id", match.id));
  } else {
    const paths = await uploadPhoto(b.id, b.id);
    await write("board", () => db.from("boards").insert({
      id: b.id, name: b.name, type_id: typeId(b.cat), notes: b.notes ?? "", in_repair: b.repair ? 1 : 0, source_file_name: b.file ?? null, ...paths,
    }));
    boardId.set(b.id, b.id);
    count.boardsNew++;
  }
}

// A board that only lives on in the history: recreate it as deleted so the history keeps its name.
async function historyBoard(h: ProtoHistory) {
  if (!h.boardId) return null;
  if (boardId.has(h.boardId)) return boardId.get(h.boardId)!;
  const found = existing!.find((x) => x.id === h.boardId);
  if (!found) {
    await write("deleted board", () => db.from("boards").insert({ id: h.boardId, name: h.board || "Unknown board", type_id: typeId(h.cat), deleted_at: iso(h.ended) }));
    count.deletedBoards++;
  }
  boardId.set(h.boardId, h.boardId);
  return h.boardId;
}

// ---------- Customers ----------
const customers = new Map<string, string>(); // match key -> customer id
async function customer(name: string, phone = "") {
  name = name.trim() || "Unknown";
  const digits = phone.replace(/\D/g, "");
  const key = digits || `name:${name.toLowerCase()}`;
  if (customers.has(key)) return customers.get(key)!;
  const { data: found } = digits
    ? await db.from("customers").select("id").eq("phone_digits", digits).maybeSingle()
    : await db.from("customers").select("id").ilike("name", name.replace(/[\\%_]/g, "\\$&")).order("created_at", { ascending: false }).limit(1).maybeSingle();
  let id = found?.id as string | undefined;
  if (!id) {
    const row = await write("customer", () => db.from("customers").insert({ name, phone: phone.trim() }).select("id").single());
    id = (row as { id: string } | null)?.id ?? `new:${key}`;
    count.customersNew++;
  }
  customers.set(key, id);
  return id;
}

// ---------- Rentals ----------
const { data: known } = await db.from("rentals").select("id").in("id", [...proto.renters, ...(proto.history ?? [])].map((r) => r.id)).throwOnError();
const imported = new Set(known!.map((r) => r.id));

for (const h of proto.history ?? []) {
  if (imported.has(h.id)) { count.skipped++; continue; }
  const board = await historyBoard(h);
  const customer_id = await customer(h.name, h.phone);
  await write("returned rental", () => db.from("rentals").insert({ id: h.id, customer_id, starts_at: iso(h.since), due_at: iso(h.until ?? h.ended), ended_at: iso(h.ended) }));
  if (board) await write("returned board", () => db.from("rental_items").insert({ rental_id: h.id, board_id: board, assigned_at: iso(h.since), unassigned_at: iso(h.ended) }));
  count.rentalsReturned++;
}

for (const r of proto.renters) {
  if (imported.has(r.id)) { count.skipped++; continue; }
  if (!r.until) notes.push(`${r.name}: no return time in the prototype; set to 1 hour after the start.`);
  const customer_id = await customer(r.name, r.phone);
  await write("active rental", () => db.from("rentals").insert({ id: r.id, customer_id, starts_at: iso(r.since), due_at: iso(r.until ?? r.since + 36e5) }));
  const board = r.boardId && boardId.get(r.boardId);
  if (r.boardId && !board) notes.push(`${r.name}: their board is missing from the prototype's board list; imported without a board.`);
  if (board) {
    try {
      await write("active board", () => db.from("rental_items").insert({ rental_id: r.id, board_id: board, assigned_at: iso(r.since) }));
    } catch (e) {
      notes.push(`${r.name}: couldn't hand out their board (${(e as Error).message}); imported without a board.`);
    }
  }
  count.rentalsActive++;
}

console.log(count);
notes.forEach((n) => console.log("NOTE " + n));
