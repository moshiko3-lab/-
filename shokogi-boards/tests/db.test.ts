// Rules the database itself enforces (SPEC sections 3-4). Runs against the LOCAL Supabase only
// (`npx supabase start`); `npx supabase db reset` wipes what these tests leave behind.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { afterAll, beforeAll, expect, test } from "vitest";
import { loginEmail } from "../lib/login";

process.loadEnvFile(".env.local");
const URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!;
if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(URL)) throw new Error("DB tests only run against the local Supabase.");

const noSession = { auth: { persistSession: false } };
const admin = createClient(URL, process.env.SUPABASE_SECRET_KEY!, noSession);
const run = Date.now().toString(36);
const password = crypto.randomUUID();

async function user(login: string, role: "owner" | "staff" | "instructor", active = true) {
  const email = loginEmail(login);
  const { data, error } = await admin.auth.admin.createUser({ email, password, email_confirm: true, user_metadata: { name: login } });
  if (error) throw error;
  await admin.from("profiles").update({ role, active }).eq("id", data.user.id).throwOnError();
  const db = createClient(URL, KEY, noSession);
  const { error: signInError } = await db.auth.signInWithPassword({ email, password });
  if (signInError) throw signInError;
  return { db, id: data.user.id };
}

let owner: { db: SupabaseClient; id: string };
let staff: { db: SupabaseClient; id: string };
let inactive: { db: SupabaseClient; id: string };
let instructor: { db: SupabaseClient; id: string };
let otherId: string;

async function newBoard(name = `TEST ${run} ${crypto.randomUUID().slice(0, 6)}`) {
  const { data } = await staff.db.from("boards").insert({ name, type_id: otherId }).select().single().throwOnError();
  return data!;
}
async function newRental() {
  const { data: c } = await staff.db.from("customers").insert({ name: `Test ${run}` }).select().single().throwOnError();
  const { data } = await staff.db.from("rentals").insert({ customer_id: c!.id, due_at: new Date(Date.now() + 36e5).toISOString() })
    .select().single().throwOnError();
  return data!;
}

// Leave the local app usable for clicking around: return the test rentals and remove the test boards.
afterAll(async () => {
  const now = new Date().toISOString();
  const ids = [owner.id, staff.id];
  const { data: open } = await admin.from("rentals").select("id").is("ended_at", null).in("created_by", ids);
  const rentals = (open ?? []).map((r) => r.id);
  await admin.from("rental_items").update({ unassigned_at: now }).in("rental_id", rentals).is("unassigned_at", null);
  await admin.from("rentals").update({ ended_at: now }).in("id", rentals);
  await admin.from("boards").update({ deleted_at: now }).like("name", `TEST ${run}%`);
});

beforeAll(async () => {
  owner = await user(`owner-${run}@example.com`, "owner");
  staff = await user(`staff${run}`, "staff"); // logs in with a username
  inactive = await user(`gone${run}`, "staff", false);
  instructor = await user(`ins${run}`, "instructor");
  otherId = (await admin.from("board_types").select("id").eq("is_system", true).single()).data!.id;
});

test("signed-out visitors and inactive accounts see nothing", async () => {
  const { error } = await createClient(URL, KEY, noSession).from("board_types").select();
  expect(error?.code).toBe("42501");
  expect((await inactive.db.from("board_types").select()).data).toEqual([]);
});

test("defaults: 5 types plus Other, 8 rental lengths", async () => {
  const { data: types } = await staff.db.from("board_types").select("name, is_system").order("sort_order");
  expect(types!.map((t) => t.name)).toEqual(["Softboard", "Longboard", "Midlength", "Funboard", "Shortboard", "Other"]);
  const { data: lengths } = await staff.db.from("rental_lengths").select("minutes").order("minutes");
  expect(lengths!.map((l) => l.minutes)).toEqual([60, 120, 180, 240, 1440, 2880, 4320, 10080]);
});

test("only the owner manages types; Other can't be renamed, deleted or duplicated", async () => {
  expect((await staff.db.from("board_types").insert({ name: `SUP ${run}` })).error?.code).toBe("42501");
  expect((await owner.db.from("board_types").insert({ name: "other" })).error).not.toBeNull();
  expect((await owner.db.from("board_types").insert({ name: "LONGBOARD" })).error?.code).toBe("23505");
  expect((await owner.db.from("board_types").update({ name: "Misc" }).eq("id", otherId).select()).data).toEqual([]);
  expect((await owner.db.from("board_types").delete().eq("id", otherId).select()).data).toEqual([]);
});

test("deleting a type moves its boards to Other", async () => {
  const { data: type } = await owner.db.from("board_types").insert({ name: `SUP ${run}` }).select().single().throwOnError();
  const board = await newBoard();
  await staff.db.from("boards").update({ type_id: type!.id }).eq("id", board.id).throwOnError();
  await owner.db.from("board_types").delete().eq("id", type!.id).throwOnError();
  expect((await staff.db.from("boards").select("type_id").eq("id", board.id).single()).data!.type_id).toBe(otherId);
});

test("staff can't delete boards; the owner can, but not while rented", async () => {
  const board = await newBoard();
  const del = { deleted_at: new Date().toISOString() };
  expect((await staff.db.from("boards").update(del).eq("id", board.id)).error?.message).toMatch(/Only the owner/);
  const rental = await newRental();
  await staff.db.from("rental_items").insert({ rental_id: rental.id, board_id: board.id }).throwOnError();
  expect((await owner.db.from("boards").update(del).eq("id", board.id)).error?.message).toMatch(/rented/);
  expect((await staff.db.from("boards").update({ in_repair: 1 }).eq("id", board.id)).error?.message).toMatch(/rented/);
  await staff.db.from("rental_items").update({ unassigned_at: new Date().toISOString() }).eq("board_id", board.id).throwOnError();
  await owner.db.from("boards").update(del).eq("id", board.id).throwOnError();
});

test("a single board goes to one rental at a time: two devices can't hand out the same board", async () => {
  const board = await newBoard();
  const [a, b] = [await newRental(), await newRental()];
  await staff.db.from("rental_items").insert({ rental_id: a.id, board_id: board.id }).throwOnError();
  expect((await staff.db.from("rental_items").insert({ rental_id: b.id, board_id: board.id })).error?.message).toMatch(/just taken/);
  // After a swap (old item closed) the board can go to the other rental, and the trail is kept.
  await staff.db.from("rental_items").update({ unassigned_at: new Date().toISOString() }).eq("rental_id", a.id).throwOnError();
  await staff.db.from("rental_items").insert({ rental_id: b.id, board_id: board.id }).throwOnError();
  expect((await staff.db.from("rental_items").select().eq("board_id", board.id)).data).toHaveLength(2);
});

test("board stats count finished hand-outs and respect permissions", async () => {
  const board = await newBoard();
  const rental = await newRental();
  const start = new Date(Date.now() - 2 * 36e5).toISOString();
  await staff.db.from("rental_items").insert({ rental_id: rental.id, board_id: board.id, assigned_at: start }).throwOnError();
  expect((await staff.db.from("board_stats").select().eq("board_id", board.id)).data).toEqual([]); // still out
  await staff.db.from("rental_items").update({ unassigned_at: new Date().toISOString() }).eq("board_id", board.id).throwOnError();
  const { data } = await staff.db.from("board_stats").select("times_rented, hours_rented").eq("board_id", board.id).single();
  expect(data).toEqual({ times_rented: 1, hours_rented: 2 });
  expect((await inactive.db.from("board_stats").select()).data).toEqual([]);
});

test("boards in repair can't be handed out", async () => {
  const board = await newBoard();
  await staff.db.from("boards").update({ in_repair: 1 }).eq("id", board.id).throwOnError();
  const rental = await newRental();
  expect((await staff.db.from("rental_items").insert({ rental_id: rental.id, board_id: board.id })).error?.message).toMatch(/not available/);
});

test("customers: phone digits are derived and unique", async () => {
  const digits = String(Date.now()).slice(-9);
  const pretty = `05${digits.slice(0, 1)}-${digits.slice(1, 4)}-${digits.slice(4)}`;
  const { data } = await staff.db.from("customers").insert({ name: "Dana", phone: pretty }).select().single().throwOnError();
  expect(data!.phone_digits).toBe(`05${digits}`);
  expect((await staff.db.from("customers").insert({ name: "Dana again", phone: `05${digits}` })).error?.code).toBe("23505");
});

test("at least one rental length always exists", async () => {
  expect((await owner.db.from("rental_lengths").delete().gt("minutes", 0)).error?.message).toMatch(/at least one/);
  expect((await staff.db.from("rental_lengths").select()).data).toHaveLength(8);
});

test("every change lands in the audit log with who did it; only the owner reads it", async () => {
  const board = await newBoard();
  await staff.db.from("boards").update({ notes: "Ding on the rail" }).eq("id", board.id).throwOnError();
  expect((await staff.db.from("audit_log").select()).data).toEqual([]);
  const { data } = await owner.db.from("audit_log").select().eq("entity_id", board.id).eq("action", "update").single();
  expect(data!.actor_id).toBe(staff.id);
  expect(data!.details).toEqual({ before: { notes: "" }, after: { notes: "Ding on the rail" } });
});

// ---------- Rental actions (SPEC section 4) ----------

const rpc = async (fn: string, args: Record<string, unknown>) => {
  const { data, error } = await staff.db.rpc(fn, args);
  if (error) throw error;
  return data;
};

test("new rentals find the customer by phone digits, or by name when there is no phone", async () => {
  const digits = String(Date.now()).slice(-8);
  const a = await rpc("create_rental", { p_name: "Noa", p_phone: `05-${digits.slice(0, 4)}-${digits.slice(4)}`, p_minutes: 60 });
  const b = await rpc("create_rental", { p_name: "Noa B.", p_phone: `05${digits}`, p_minutes: 60 });
  const c = await rpc("create_rental", { p_name: `Walk-in ${run}`, p_phone: "", p_minutes: 60 });
  const d = await rpc("create_rental", { p_name: `  WALK-IN ${run} `, p_phone: null, p_minutes: 60 });
  const { data } = await staff.db.from("rentals").select("id, customer_id, due_at, starts_at").in("id", [a, b, c, d]);
  const customer = (id: string) => data!.find((r) => r.id === id)!.customer_id;
  expect(customer(a)).toBe(customer(b));
  expect(customer(c)).toBe(customer(d));
  expect(customer(a)).not.toBe(customer(c));
  const r = data!.find((x) => x.id === a)!;
  expect(Date.parse(r.due_at) - Date.parse(r.starts_at)).toBe(60 * 60000);
  await expect(rpc("create_rental", { p_name: " ", p_phone: "", p_minutes: 60 })).rejects.toThrow(/needs a name/);
});

test("swap keeps the trail, return closes every board at the same moment", async () => {
  const [b1, b2, b3] = [await newBoard(), await newBoard(), await newBoard()];
  const rental = await rpc("create_rental", { p_name: `Family ${run}`, p_phone: "", p_minutes: 120 });
  await rpc("assign_board", { p_rental: rental, p_board: b1.id });
  await rpc("assign_board", { p_rental: rental, p_board: b2.id }); // a family: several boards on one rental
  await rpc("assign_board", { p_rental: rental, p_board: b3.id, p_replace: b1.id }); // swap b1 -> b3
  const current = async () => (await staff.db.from("rental_items").select("board_id").eq("rental_id", rental).is("unassigned_at", null)).data!.map((i) => i.board_id).sort();
  expect(await current()).toEqual([b2.id, b3.id].sort());
  // Someone else can't take b2 while it's out, and the failed swap changes nothing.
  const other = await rpc("create_rental", { p_name: `Other ${run}`, p_phone: "", p_minutes: 60 });
  await expect(rpc("assign_board", { p_rental: rental, p_board: b2.id, p_replace: b3.id })).rejects.toThrow(/just taken/);
  await expect(rpc("assign_board", { p_rental: other, p_board: b2.id })).rejects.toThrow(/just taken/);
  expect(await current()).toEqual([b2.id, b3.id].sort());

  await admin.from("rentals").update({ due_at: new Date(Date.now() - 6e4).toISOString() }).eq("id", rental).throwOnError(); // time is up
  await rpc("return_rental", { p_rental: rental });
  const { data: r } = await staff.db.from("rentals").select("ended_at, ended_by").eq("id", rental).single();
  expect(r!.ended_by).toBe(staff.id);
  const { data: items } = await staff.db.from("rental_items").select("board_id, unassigned_at").eq("rental_id", rental);
  expect(items).toHaveLength(3);
  expect(items!.filter((i) => i.board_id !== b1.id).every((i) => Date.parse(i.unassigned_at) === Date.parse(r!.ended_at))).toBe(true);
  await expect(rpc("return_rental", { p_rental: rental })).rejects.toThrow(/already returned/);
  await expect(rpc("assign_board", { p_rental: rental, p_board: b1.id })).rejects.toThrow(/already ended/);
});

test("returning with time left keeps the rental for another board; when the time is up it ends on its own", async () => {
  const board = await newBoard();
  const rental = await rpc("create_rental", { p_name: `Early ${run}`, p_phone: "", p_minutes: 120 });
  await rpc("assign_board", { p_rental: rental, p_board: board.id });
  await rpc("return_rental", { p_rental: rental });
  const state = async () => (await staff.db.from("rentals").select("ended_at, ended_by").eq("id", rental).single()).data!;
  expect((await state()).ended_at).toBeNull(); // still open, waiting for a board
  const { data: item } = await staff.db.from("rental_items").select("unassigned_at").eq("rental_id", rental).single();
  expect(item!.unassigned_at).not.toBeNull();

  // Time up: the timer ends it as returned when the board came back (so not late), by whoever took it back.
  await admin.from("rentals").update({ due_at: new Date(Date.now() - 6e4).toISOString() }).eq("id", rental).throwOnError();
  await admin.rpc("end_finished_rentals").throwOnError();
  expect(await state()).toEqual({ ended_at: item!.unassigned_at, ended_by: staff.id });
  expect((await staff.db.rpc("end_finished_rentals")).error).not.toBeNull(); // the timer's job only

  // Ending early is the owner's "Finish rental": Mark returned again changes nothing, staff can't finish it or end
  // it directly, and the owner's finish counts as returned when the boards came back.
  const other = await rpc("create_rental", { p_name: `Done ${run}`, p_phone: "", p_minutes: 120 });
  await rpc("assign_board", { p_rental: other, p_board: board.id });
  await rpc("return_rental", { p_rental: other });
  const { data: back } = await staff.db.from("rental_items").select("unassigned_at").eq("rental_id", other).single();
  await rpc("return_rental", { p_rental: other });
  const ended = async () => (await staff.db.from("rentals").select("ended_at").eq("id", other).single()).data!.ended_at;
  expect(await ended()).toBeNull();
  await expect(rpc("finish_rental", { p_rental: other })).rejects.toThrow(/Only the owner/);
  expect((await staff.db.from("rentals").update({ ended_at: new Date().toISOString() }).eq("id", other)).error?.message).toMatch(/Only the owner/);
  await owner.db.rpc("finish_rental", { p_rental: other }).throwOnError();
  expect(await ended()).toBe(back!.unassigned_at);
});

test("a rental's changes, oldest first, by whom: the owner sees them, staff don't", async () => {
  const [b1, b2] = [await newBoard(), await newBoard()];
  const name = `Trail ${run}`;
  const rental = await rpc("create_rental", { p_name: name, p_phone: "", p_minutes: 60 });
  await rpc("assign_board", { p_rental: rental, p_board: b1.id });
  await rpc("assign_board", { p_rental: rental, p_board: b2.id, p_replace: b1.id });
  const { data: c } = await staff.db.from("rentals").select("customer_id").eq("id", rental).single();
  await staff.db.from("customers").update({ phone: `07${String(Date.now()).slice(-8)}` }).eq("id", c!.customer_id).throwOnError();
  await owner.db.from("rentals").update({ due_at: new Date(Date.now() - 6e4).toISOString() }).eq("id", rental).throwOnError();
  await rpc("return_rental", { p_rental: rental });

  const { data } = await owner.db.rpc("rental_changes", { p_rental: rental });
  expect(data.map((x: { entity: string; action: string; actor_id: string }) => `${x.entity} ${x.action} ${x.actor_id === owner.id ? "owner" : "staff"}`)).toEqual([
    "rentals insert staff", "rental_items insert staff", // created, handed out b1
    "rental_items update staff", "rental_items insert staff", // swap b1 -> b2
    "customers update staff", "rentals update owner", // phone edited, return time changed
    "rental_items update staff", "rentals update staff", // returned
  ]);
  expect((await staff.db.rpc("rental_changes", { p_rental: rental })).data).toEqual([]);
});

test("several copies of one board: out until none is free, repairs and quantity leave room for the ones out", async () => {
  const board = await newBoard();
  await staff.db.from("boards").update({ quantity: 3 }).eq("id", board.id).throwOnError();
  const family = await rpc("create_rental", { p_name: `Copies ${run}`, p_phone: "", p_minutes: 60 });
  const other = await rpc("create_rental", { p_name: `Copies2 ${run}`, p_phone: "", p_minutes: 60 });
  await rpc("assign_board", { p_rental: family, p_board: board.id });
  await rpc("assign_board", { p_rental: family, p_board: board.id }); // a family takes two of the same
  await staff.db.from("boards").update({ in_repair: 1 }).eq("id", board.id).throwOnError(); // the third goes to repair
  await expect(rpc("assign_board", { p_rental: other, p_board: board.id })).rejects.toThrow(/just taken/);
  expect((await staff.db.from("boards").update({ in_repair: 2 }).eq("id", board.id)).error?.message).toMatch(/rented/);
  expect((await staff.db.from("boards").update({ quantity: 2 }).eq("id", board.id)).error?.message).toMatch(/3 of these boards/);
  const out = async () => (await staff.db.from("rental_items").select("id").eq("board_id", board.id).is("unassigned_at", null)).data!.length;
  await rpc("remove_board", { p_rental: family, p_board: board.id }); // takes back one copy only
  expect(await out()).toBe(1);
  // Two devices taking the last free copy at the same moment: exactly one gets it.
  const tries = await Promise.allSettled([family, other].map((r) => rpc("assign_board", { p_rental: r, p_board: board.id })));
  expect(tries.filter((t) => t.status === "fulfilled")).toHaveLength(1);
  expect(await out()).toBe(2);
});

test("customer totals: rentals, late returns, renting now", async () => {
  const name = `Stats ${run}`;
  const r1 = await rpc("create_rental", { p_name: name, p_phone: "", p_minutes: 60 });
  await admin.from("rentals").update({ due_at: new Date(Date.now() - 6e4).toISOString() }).eq("id", r1).throwOnError();
  await rpc("return_rental", { p_rental: r1 }); // returned late
  await rpc("create_rental", { p_name: name, p_phone: "", p_minutes: 60 }); // out now
  const { data } = await staff.db.from("customer_stats").select("rentals, late_returns, renting_now").ilike("name", name).single();
  expect(data).toEqual({ rentals: 2, late_returns: 1, renting_now: true });
  expect((await createClient(URL, KEY, noSession).rpc("create_rental", { p_name: "x", p_phone: "", p_minutes: 60 })).error).not.toBeNull();
});

// ---------- History and most rented (SPEC 7.8, 7.1) ----------

test("history: boards brought back, who returned it, search, dates and totals", async () => {
  const [b1, b2, b3] = [await newBoard(), await newBoard(), await newBoard()];
  const who = `Hist${run}`;
  const r1 = await rpc("create_rental", { p_name: who, p_phone: "", p_minutes: 60 });
  await rpc("assign_board", { p_rental: r1, p_board: b1.id });
  await rpc("assign_board", { p_rental: r1, p_board: b3.id, p_replace: b1.id }); // swapped out mid-rental
  await rpc("assign_board", { p_rental: r1, p_board: b2.id });
  await admin.from("rentals").update({ due_at: new Date(Date.now() - 6e4).toISOString() }).eq("id", r1).throwOnError();
  await rpc("return_rental", { p_rental: r1 }); // late
  const r2 = await rpc("create_rental", { p_name: who, p_phone: "", p_minutes: 60 });
  await owner.db.rpc("finish_rental", { p_rental: r2 }).throwOnError(); // on time, no board

  const search = async (words: string[], from: string | null = null) =>
    (await staff.db.rpc("history_search", { p_from: from, p_to: null, p_words: words })).data;
  const all = await search([who.toLowerCase()]);
  expect(all).toMatchObject({ rentals: 2, late: 1 });
  const row = all.rows.find((r: { id: string }) => r.id === r1);
  expect(row.boards.map((b: { id: string }) => b.id).sort()).toEqual([b2.id, b3.id].sort()); // b1 was swapped out
  expect(row.ended_by).toBe(`staff${run}`);
  expect(row.search).toBeUndefined();
  expect((await search([who.toLowerCase(), b1.name.toLowerCase()])).rentals).toBe(1); // swapped boards are searchable
  expect((await search([who.toLowerCase()], new Date(Date.now() + 864e5).toISOString())).rentals).toBe(0);

  const { data: top } = await staff.db.rpc("most_rented", { p_since: new Date(Date.now() - 6e4).toISOString() });
  expect(top.length).toBeLessThanOrEqual(5);
  expect((await inactive.db.rpc("history_search", { p_from: null, p_to: null, p_words: [] })).data.rentals).toBe(0);
});

// ---------- Staff accounts (SPEC 3, 7.9) ----------

test("staff accounts: login shown without the hidden domain, password change flag, always an active owner", async () => {
  const { data: me } = await staff.db.from("profiles").select("login, must_change_password").eq("id", staff.id).single();
  expect(me).toEqual({ login: `staff${run}`, must_change_password: false });

  await admin.from("profiles").update({ must_change_password: true }).eq("id", staff.id).throwOnError();
  await rpc("password_changed", {});
  expect((await staff.db.from("profiles").select("must_change_password").eq("id", staff.id).single()).data!.must_change_password).toBe(false);

  expect((await staff.db.from("profiles").update({ role: "owner" }).eq("id", staff.id).select()).data).toEqual([]); // staff can't promote themselves
  const { error } = await admin.from("profiles").update({ active: false }).eq("role", "owner");
  expect(error?.message).toMatch(/at least one active owner/);
  expect((await owner.db.from("profiles").select("active").eq("id", owner.id).single()).data!.active).toBe(true);
});

// ---------- Instructors (migration 20261027000000_instructors) ----------

test("instructors hand out one board, swap and take back boards and mark returned, and nothing else", async () => {
  const [b1, b2, b3] = [await newBoard(), await newBoard(), await newBoard()];
  const phone = `05${String(Date.now()).slice(-8)}`;
  const rental = await rpc("create_rental", { p_name: `Ins ${run}`, p_phone: phone, p_minutes: 60 });
  const other = await rpc("create_rental", { p_name: `Ins2 ${run}`, p_phone: "", p_minutes: 60 });
  const ins = async (fn: string, args: Record<string, unknown> = {}) => {
    const { data, error } = await instructor.db.rpc(fn, args);
    if (error) throw error;
    return data;
  };
  await ins("assign_board", { p_rental: rental, p_board: b1.id });
  await ins("assign_board", { p_rental: rental, p_board: b2.id, p_replace: b1.id });
  await expect(ins("assign_board", { p_rental: rental, p_board: b1.id })).rejects.toThrow(/already has a board/); // one board each
  const { error: direct } = await instructor.db.from("rental_items").insert({ rental_id: rental, board_id: b1.id });
  expect(direct?.message).toMatch(/already has a board/);
  await rpc("assign_board", { p_rental: rental, p_board: b1.id }); // the desk adds a second board
  await ins("assign_board", { p_rental: rental, p_board: b3.id, p_replace: b1.id }); // instructors still swap on a family
  await ins("remove_board", { p_rental: rental, p_board: b3.id });
  await ins("remove_board", { p_rental: rental, p_board: b2.id });
  await rpc("assign_board", { p_rental: other, p_board: b2.id });
  await expect(ins("assign_board", { p_rental: rental, p_board: b2.id })).rejects.toThrow(/just taken/); // the guard sees the board

  // Customers by name only, and only on open rentals.
  expect((await instructor.db.from("customers").select()).data).toEqual([]);
  expect(await ins("open_rental_names")).toContainEqual({ rental_id: rental, name: `Ins ${run}` });

  // No new rentals, return times, boards, settings or change log.
  await expect(ins("create_rental", { p_name: `Nope ${run}`, p_phone: "", p_minutes: 60 })).rejects.toThrow();
  expect((await instructor.db.from("rentals").update({ due_at: new Date().toISOString() }).eq("id", rental).select()).data).toEqual([]);
  expect((await instructor.db.from("boards").update({ notes: "x" }).eq("id", b1.id).select()).data).toEqual([]);
  expect((await instructor.db.from("boards").insert({ name: `TEST ${run} ins`, type_id: otherId })).error?.code).toBe("42501");
  expect((await instructor.db.from("app_settings").select()).data).toEqual([]);
  expect((await instructor.db.from("audit_log").select()).data).toEqual([]);

  await expect(ins("finish_rental", { p_rental: other })).rejects.toThrow(/Only the owner/);
  await ins("assign_board", { p_rental: rental, p_board: b1.id });
  await admin.from("rentals").update({ due_at: new Date(Date.now() - 6e4).toISOString() }).eq("id", rental).throwOnError(); // time is up
  await ins("return_rental", { p_rental: rental });
  expect((await staff.db.from("rentals").select("ended_by").eq("id", rental).single()).data!.ended_by).toBe(instructor.id);
  expect((await instructor.db.from("rentals").select().eq("id", rental)).data).toEqual([]); // ended rentals are out of sight
  await expect(ins("assign_board", { p_rental: rental, p_board: b1.id })).rejects.toThrow(/already ended/);
  expect((await inactive.db.rpc("return_rental", { p_rental: other })).error?.message).toMatch(/Sign in/);
});
