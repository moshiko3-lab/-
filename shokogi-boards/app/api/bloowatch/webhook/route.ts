// POST /api/bloowatch/webhook (SPEC 7.12): one Bloowatch booking becomes a rental waiting for a board, or updates
// the one it made before (matched on bloowatch_booking_id). Needs the shared secret, and the owner must have turned
// Bloowatch on in Settings (off by default). Customers are matched like on the Rentals screen (phone digits, else name).
//
// The filing itself is `applyBooking` in lib/bloowatch.ts, shared with the timer in ../sync, so there is one place
// where a booking turns into a rental. This route is the push door: it is here for anything that wants to file a
// single booking without waiting for the next minute's pull.
import { applyBooking, parseBooking } from "@/lib/bloowatch";
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

  try {
    const { id, created } = await applyBooking(db, booking);
    return Response.json({ ok: true, rental_id: id, created }, { status: created ? 201 : 200 });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
