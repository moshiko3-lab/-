// POST /api/bloowatch/webhook (SPEC 7.12): a Bloowatch booking becomes a rental waiting for a board, or updates the
// one it made before (matched on bloowatch_booking_id). Needs the shared secret, and the owner must have turned
// Bloowatch on in Settings (off by default). Customers are matched like on the Rentals screen (phone digits, else name).
import { parseBooking } from "@/lib/bloowatch";
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST(request: Request) {
  const secret = process.env.BLOOWATCH_WEBHOOK_SECRET;
  if (!secret || request.headers.get("x-webhook-secret") !== secret) return Response.json({ error: "Not allowed." }, { status: 401 });
  const db = createAdminClient();
  const { data: setting } = await db.from("app_settings").select("value").eq("key", "bloowatch_enabled").maybeSingle();
  if (setting?.value !== true) return Response.json({ error: "Bloowatch is turned off in Settings." }, { status: 409 });

  let booking;
  try {
    booking = parseBooking(await request.json());
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 400 });
  }
  const { data: customer_id, error: customerError } = await db.rpc("upsert_customer", { p_name: booking.name, p_phone: booking.phone });
  if (customerError) return Response.json({ error: customerError.message }, { status: 500 });

  const times = { starts_at: new Date(booking.startsAt).toISOString(), due_at: new Date(booking.dueAt).toISOString() };
  const { data: existing } = await db.from("rentals").select("id, ended_at").eq("bloowatch_booking_id", booking.bookingId).maybeSingle();
  if (existing) {
    if (!existing.ended_at) await db.from("rentals").update({ customer_id, ...times }).eq("id", existing.id).throwOnError();
    return Response.json({ ok: true, rental_id: existing.id, created: false });
  }
  const { data: rental, error } = await db.from("rentals")
    .insert({ customer_id, ...times, source: "bloowatch", bloowatch_booking_id: booking.bookingId }).select("id").single();
  if (error) return Response.json({ error: error.message }, { status: 500 });
  return Response.json({ ok: true, rental_id: rental.id, created: true }, { status: 201 });
}
