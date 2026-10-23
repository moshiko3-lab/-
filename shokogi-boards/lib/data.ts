import type { SupabaseClient } from "@supabase/supabase-js";

export type BoardType = { id: string; name: string; sort_order: number; is_system: boolean };
export type Board = {
  id: string; name: string; type_id: string; notes: string;
  quantity: number; in_repair: number; // identical copies under one name, and how many of them are in repair
  photo_path: string | null; thumb_path: string | null; source_file_name: string | null;
};
export type BoardStats = { times_rented: number; hours_rented: number; last_rented: string };
export type Length = { id: string; label: string; minutes: number };
export type Customer = { id: string; name: string; phone: string };
// An active rental. `boards` are the boards the customer has now, in the order they were handed out.
export type Rental = { id: string; starts_at: string; due_at: string; customer: Customer; boards: string[] };

export type Fleet = {
  types: BoardType[];
  boards: Board[];
  stats: Map<string, BoardStats>;
  lengths: Length[];
  rentals: Rental[];
  rentedBy: Map<string, Rental[]>; // board id -> the rentals it is out on, once per copy
  sheet: { url: string; folder_url: string; email: string } | null; // the connected Google sheet
  sheets: { at: string; error: string | null } | null; // last Google Sheets sync
};

// Everything the screens share, in one round of parallel queries (300 boards and a day's rentals: small).
// Instructors can't read customers (`namesOnly`): their rentals carry the customer's name and no phone.
export async function loadFleet(db: SupabaseClient, namesOnly = false): Promise<Fleet> {
  const [types, boards, stats, lengths, rentals, sheets, names] = await Promise.all([
    db.from("board_types").select("id, name, sort_order, is_system").order("sort_order").order("name").throwOnError(),
    db.from("boards").select("id, name, type_id, notes, quantity, in_repair, photo_path, thumb_path, source_file_name").is("deleted_at", null).throwOnError(),
    db.from("board_stats").select("board_id, times_rented, hours_rented, last_rented").throwOnError(),
    db.from("rental_lengths").select("id, label, minutes").order("minutes").throwOnError(),
    db.from("rentals").select("id, starts_at, due_at, customer_id, customer:customers(id, name, phone), items:rental_items(board_id, assigned_at, unassigned_at)")
      .is("ended_at", null).throwOnError(),
    db.from("app_settings").select("key, value").in("key", ["sheets", "sheets_status"]),
    namesOnly ? db.rpc("open_rental_names").throwOnError() : null,
  ]);
  type Row = Omit<Rental, "boards" | "customer"> & {
    customer_id: string; customer: Customer | null; items: { board_id: string; assigned_at: string; unassigned_at: string | null }[];
  };
  const nameOf = new Map((names?.data as { rental_id: string; name: string }[] | undefined)?.map((n) => [n.rental_id, n.name]));
  const active = (rentals.data as unknown as Row[]).map(({ items, customer_id, customer, ...r }) => ({
    ...r,
    customer: customer ?? { id: customer_id, name: nameOf.get(r.id) ?? "", phone: "" },
    boards: items.filter((i) => !i.unassigned_at).sort((a, b) => a.assigned_at.localeCompare(b.assigned_at)).map((i) => i.board_id),
  }));
  return {
    types: types.data as BoardType[],
    boards: boards.data as Board[],
    stats: new Map((stats.data as (BoardStats & { board_id: string })[]).map(({ board_id, ...s }) => [board_id, s])),
    lengths: lengths.data as Length[],
    rentals: active,
    rentedBy: rentedByBoard(active),
    sheet: (sheets.data?.find((s) => s.key === "sheets")?.value as Fleet["sheet"]) ?? null,
    sheets: (sheets.data?.find((s) => s.key === "sheets_status")?.value as Fleet["sheets"]) ?? null,
  };
}

// Board id -> the rentals that have it now, once per copy (a family with two of the same is listed twice).
export function rentedByBoard(rentals: Rental[]) {
  const map = new Map<string, Rental[]>();
  for (const r of rentals) for (const b of r.boards) map.set(b, [...(map.get(b) ?? []), r]);
  return map;
}

// A board's copies right now: out, in repair, free, and who has them.
export function copies(rentedBy: Fleet["rentedBy"], b: Board) {
  const rentals = rentedBy.get(b.id) ?? [];
  return {
    out: rentals.length, fix: b.in_repair, free: Math.max(0, b.quantity - rentals.length - b.in_repair),
    renters: [...new Set(rentals)],
  };
}

// Overdue = an active rental with a board whose return time has passed.
export const isOverdue = (r: Rental, now: number) => r.boards.length > 0 && Date.parse(r.due_at) < now;

// Words for database LIKE search: lower-cased, phone-like words reduced to digits, wildcards escaped.
export const searchWords = (query: string) =>
  query.toLowerCase().split(/\s+/).filter(Boolean)
    .map((w) => (/^[\d()+-]+$/.test(w) ? w.replace(/\D/g, "") : w).replace(/[\\%_]/g, "\\$&"))
    .filter(Boolean);

// Database rule messages (raised by our triggers and functions) are written for people; anything else gets the fallback.
export const errorText = (e: unknown, fallback: string) =>
  (e as { code?: string })?.code === "P0001" ? (e as Error).message : fallback;
