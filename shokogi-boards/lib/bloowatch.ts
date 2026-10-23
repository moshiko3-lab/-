// Bloowatch bookings. A booking arrives as a neutral `Booking` and becomes (or updates) a rental; `applyBooking` is
// the one place that happens, used by both the webhook and the timer.
//
// What Bloowatch is, so the shape below makes sense:
//
// * No API key. Signing in is the owner's dashboard email and password posted to /api/auth/login/, which returns a
//   token sent back as `Authorization: Token <t>`. That credential is the whole account -- it reads customers, takes
//   payments and deletes bookings -- so it lives in `private_settings`, which only the server's full-access key can
//   read, and never reaches the browser.
// * No webhooks and no "changed since". Every filter spelling was tried against the live API and silently ignored,
//   returning the full 27,500-order count. Unknown parameters are dropped rather than refused, so a filter can look
//   like it works while fetching everything. Polling is the only option, and a cancellation can only be noticed by a
//   booking no longer appearing.
// * `status` on a hire is the string "booked" on all 15,103 of them, for ever, including hires from months ago that
//   plainly came back. Bloowatch records no pickup and no return. That is the half this app exists to hold.
// * `date=` on /rents/ is the one honoured filter, and it does not mean "active on". It answers with the hires
//   spanning that day *and* the ones that ended the day before, after which they disappear -- so a board two days
//   late had already fallen out of the answer. BACK_DAYS is why the window reaches backwards.
import type { SupabaseClient } from "@supabase/supabase-js";

export type Booking = {
  bookingId: string; name: string; phone: string; startsAt: string; dueAt: string;
  unitName?: string; orderId?: number; orderStatus?: string;
};

export type Credentials = { url: string; email: string; password: string; school?: number };

const SCHOOL = 127;
// A hire whose time is up stays in the answer for one more day and then vanishes. Asked only about today, the boards
// that are most overdue are exactly the ones that would be missing.
const BACK_DAYS = 14;
const GEAR = "gear"; // the three tipi families are accommodation; a guest in a tipi is not a missing board

export function parseBooking(body: unknown): Booking {
  const b = (body ?? {}) as Record<string, unknown>;
  const text = (k: string) => (typeof b[k] === "string" ? (b[k] as string).trim() : "");
  const booking = { bookingId: text("booking_id"), name: text("name"), phone: text("phone"), startsAt: text("starts_at"), dueAt: text("due_at") };
  if (!booking.bookingId || !booking.name) throw new Error("booking_id and name are required.");
  if (Number.isNaN(Date.parse(booking.startsAt)) || Number.isNaN(Date.parse(booking.dueAt))) throw new Error("starts_at and due_at must be dates (ISO 8601).");
  if (Date.parse(booking.dueAt) <= Date.parse(booking.startsAt)) throw new Error("due_at must be after starts_at.");
  return booking;
}

/** Bloowatch's own date format ("Wed, 21 Oct 2026 11:14:00 -0500") as ISO 8601, or "" if it cannot be read. */
export function toIso(stamp: unknown): string {
  if (typeof stamp !== "string" || !stamp.trim()) return "";
  const ms = Date.parse(stamp);
  return Number.isNaN(ms) ? "" : new Date(ms).toISOString();
}

/** Panama, always: the store is in Venao and "today" there is what decides which hires are open. */
function panamaToday(at = new Date()): Date {
  return new Date(at.getTime() - 5 * 3600_000);
}

function ymd(d: Date): string {
  return d.toISOString().slice(0, 10);
}

class Client {
  private token = "";
  constructor(private readonly c: Credentials) {}
  private get base() { return this.c.url.replace(/\/+$/, ""); }
  private get school() { return this.c.school ?? SCHOOL; }

  async signIn() {
    const r = await fetch(`${this.base}/api/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ username: this.c.email, password: this.c.password }),
    });
    const body = r.ok ? await r.json().catch(() => ({})) : {};
    const token = (body as { token?: string }).token;
    // Never echo the response: a failed sign-in can carry the submitted values back.
    if (!token) throw new Error(`Bloowatch sign-in failed (HTTP ${r.status}). Check the email and password in Settings.`);
    this.token = token;
  }

  async get(path: string, params: Record<string, string> = {}) {
    const url = new URL(`${this.base}/api${path}`);
    for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
    // Without an explicit JSON Accept header some routes answer with HTML, which then fails to parse.
    const r = await fetch(url, { headers: { Authorization: `Token ${this.token}`, Accept: "application/json" } });
    if (!r.ok) throw new Error(`Bloowatch ${path} returned HTTP ${r.status}.`);
    return r.json();
  }

  /** One day's hires. Bloowatch pages; 200 is far above a day's worth here, and the guard stops a runaway. */
  async hiresOn(date: string) {
    const rows: Record<string, unknown>[] = [];
    for (let page = 1; page <= 10; page++) {
      const body = await this.get(`/schools/${this.school}/rents/`, { date, page_size: "200", page: String(page), ordering: "-id" });
      const batch = (body?.results ?? []) as Record<string, unknown>[];
      rows.push(...batch);
      if (!body?.next || !batch.length) break;
    }
    return rows;
  }

  /** The customer's phone, which a hire row does not carry. Cached: one guest usually takes several boards. */
  async phoneOf(id: unknown, cache: Map<number, string>) {
    if (typeof id !== "number") return "";
    if (!cache.has(id)) {
      try {
        const c = await this.get(`/schools/${this.school}/customers/${id}/`);
        cache.set(id, String(c?.phone ?? "").trim());
      } catch {
        cache.set(id, ""); // a missing number is not a reason to drop the hire: the match falls back to the name
      }
    }
    return cache.get(id) ?? "";
  }
}

/** Every board hire Bloowatch still has open, as bookings this app can file. */
export async function fetchBookings(creds: Credentials): Promise<{ bookings: Booking[]; skipped: number }> {
  const client = new Client(creds);
  await client.signIn();

  const today = panamaToday();
  const phones = new Map<number, string>();
  const seen = new Set<number>();
  const bookings: Booking[] = [];
  let skipped = 0;

  for (let i = 0; i <= BACK_DAYS; i++) {
    const day = ymd(new Date(today.getTime() - i * 86400_000));
    for (const row of await client.hiresOn(day)) {
      const id = row.id as number;
      if (seen.has(id)) continue; // a long hire shows up on every day it spans
      seen.add(id);

      const info = (row.rental_unit_info ?? {}) as Record<string, unknown>;
      const family = (info.rental ?? {}) as Record<string, unknown>;
      if (family.rental_type !== GEAR) continue;

      const who = ((row.customers ?? []) as Record<string, unknown>[])[0] ?? {};
      const name = String(who.customer_name ?? "").trim();
      const startsAt = toIso(row.starting_time);
      const dueAt = toIso(row.ending_time);
      // Exactly what parseBooking refuses, caught here so one bad hire cannot fail the whole run.
      if (!name || !startsAt || !dueAt || Date.parse(dueAt) <= Date.parse(startsAt)) { skipped++; continue; }

      bookings.push({
        bookingId: String(id), // the hire, never the order: one order can carry several boards
        name,
        phone: await client.phoneOf(who.customer, phones),
        startsAt, dueAt,
        unitName: String(info.name ?? ""),
        orderId: row.order_id as number,
        orderStatus: String(row.order_status ?? ""),
      });
    }
  }
  bookings.sort((a, b) => a.startsAt.localeCompare(b.startsAt));
  return { bookings, skipped };
}

/* ------------------------------ filing a booking ------------------------------ */
// One place where a booking becomes a rental, used by both the webhook and the timer.

export async function applyBooking(db: SupabaseClient, booking: Booking) {
  const { data: customer_id, error: customerError } = await db.rpc("upsert_customer", { p_name: booking.name, p_phone: booking.phone });
  if (customerError) throw new Error(customerError.message);

  const times = { starts_at: new Date(booking.startsAt).toISOString(), due_at: new Date(booking.dueAt).toISOString() };
  const { data: existing } = await db.from("rentals").select("id, ended_at").eq("bloowatch_booking_id", booking.bookingId).maybeSingle();
  if (existing) {
    // A rental the desk already finished is left finished: the timer must never reopen one.
    if (!existing.ended_at) await db.from("rentals").update({ customer_id, ...times }).eq("id", existing.id).throwOnError();
    return { id: existing.id as string, created: false };
  }
  const { data: rental, error } = await db.from("rentals")
    .insert({ customer_id, ...times, source: "bloowatch", bloowatch_booking_id: booking.bookingId }).select("id").single();
  if (error) throw new Error(error.message);
  return { id: rental.id as string, created: true };
}

const CANCELLED_NOTE = "Cancelled in Bloowatch — board still out.";

/** Drop the rentals whose bookings Bloowatch no longer has. Pass every live id; a cancellation has no other signal. */
export async function reconcile(db: SupabaseClient, activeIds: string[]) {
  const { data: ours, error } = await db
    .from("rentals").select("id, bloowatch_booking_id, notes, rental_items(id)")
    .eq("source", "bloowatch").is("ended_at", null).is("rental_items.unassigned_at", null);
  if (error) throw new Error(error.message);

  const live = new Set(activeIds);
  const gone = (ours ?? []).filter((r) => r.bloowatch_booking_id && !live.has(r.bloowatch_booking_id));
  // A board that is physically out is never removed, whatever Bloowatch says: the booking may be cancelled, the
  // board is still with the customer, and the desk has to get it back.
  const kept = gone.filter((r) => (r.rental_items ?? []).length > 0);
  const removable = gone.filter((r) => (r.rental_items ?? []).length === 0);

  // Removed, not ended: a hire that was cancelled never happened, and ending it would file it in History with hours.
  if (removable.length) {
    const { error: delError } = await db.from("rentals").delete().in("id", removable.map((r) => r.id));
    if (delError) throw new Error(delError.message);
  }
  // Noted once. A note appended every minute would bury everything else in it.
  for (const r of kept.filter((r) => !(r.notes ?? "").includes(CANCELLED_NOTE))) {
    await db.from("rentals").update({ notes: [r.notes, CANCELLED_NOTE].filter(Boolean).join(" ") }).eq("id", r.id);
  }
  return { removed: removable.length, kept: kept.map((r) => r.bloowatch_booking_id as string) };
}

/** The whole run: sign in, read, file, subtract, and leave a status the sidebar can show. */
export async function syncAndRecord(db: SupabaseClient) {
  const at = new Date().toISOString();
  try {
    const { data: row } = await db.from("private_settings").select("value").eq("key", "bloowatch").maybeSingle();
    const creds = row?.value as Credentials | undefined;
    if (!creds?.url || !creds?.email || !creds?.password) throw new Error("Bloowatch is not connected yet — add the login in Settings.");

    const { bookings, skipped } = await fetchBookings(creds);
    let created = 0;
    for (const b of bookings) if ((await applyBooking(db, b)).created) created++;
    const { removed, kept } = await reconcile(db, bookings.map((b) => b.bookingId));

    const count = bookings.length;
    await db.from("app_settings").upsert({ key: "bloowatch_status", value: { at, error: null, count, created, removed, kept, skipped } });
    return { ok: true as const, count, created, removed, kept, skipped };
  } catch (e) {
    const error = (e as Error).message;
    await db.from("app_settings").upsert({ key: "bloowatch_status", value: { at, error } });
    return { ok: false as const, error };
  }
}
