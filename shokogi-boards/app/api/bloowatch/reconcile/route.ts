// POST /api/bloowatch/reconcile (CLAUDE.md task, step 4): the full set of bookings Bloowatch still has, so the ones it
// no longer has can go. Bloowatch offers no webhooks and no "changed since" filter, so a cancellation cannot be
// detected as an event -- the only honest signal is that a booking stopped appearing in the live set. Same shared
// secret and the same owner switch as the webhook. Send it right after the batch of /api/bloowatch/webhook calls,
// never before: run first it would close a rental a moment before it is resent.
//
// Not named `sync`: that path is reserved for the puller in step 3, which fetches from Bloowatch itself behind
// CRON_SECRET. This is the opposite direction -- it is told what is live by the side that holds the Bloowatch
// credentials, and only subtracts.
//
// A rental that already has a board out is never removed, whatever Bloowatch says. The booking may be cancelled; the
// board is still with the customer, and the desk has to get it back. Those are kept, noted, and returned in `kept`.
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST(request: Request) {
  const secret = process.env.BLOOWATCH_WEBHOOK_SECRET;
  if (!secret || request.headers.get("x-webhook-secret") !== secret) return Response.json({ error: "Not allowed." }, { status: 401 });
  const db = createAdminClient();
  const { data: setting } = await db.from("app_settings").select("value").eq("key", "bloowatch_enabled").maybeSingle();
  if (setting?.value !== true) return Response.json({ error: "Bloowatch is turned off in Settings." }, { status: 409 });

  let active: string[];
  try {
    const body = (await request.json()) as { active?: unknown };
    if (!Array.isArray(body.active)) throw new Error("active must be an array of booking ids.");
    active = body.active.map(String).filter(Boolean);
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 400 });
  }

  // Every open rental this integration created. Bloowatch-sourced only: a rental the desk typed in by hand is nobody's
  // business here, and a finished one is already history.
  const { data: ours, error } = await db
    .from("rentals")
    .select("id, bloowatch_booking_id, notes, rental_items(id)")
    .eq("source", "bloowatch")
    .is("ended_at", null)
    .is("rental_items.unassigned_at", null);
  if (error) return Response.json({ error: error.message }, { status: 500 });

  const live = new Set(active);
  const gone = (ours ?? []).filter((r) => r.bloowatch_booking_id && !live.has(r.bloowatch_booking_id));
  const kept = gone.filter((r) => (r.rental_items ?? []).length > 0);
  const removable = gone.filter((r) => (r.rental_items ?? []).length === 0);

  if (removable.length) {
    const { error: delError } = await db.from("rentals").delete().in("id", removable.map((r) => r.id));
    if (delError) return Response.json({ error: delError.message }, { status: 500 });
  }

  // The kept ones need to say why they are still here, or the desk sees a rental Bloowatch no longer has and no
  // reason for it. Written once: a note appended every five minutes would bury everything else in it.
  const NOTE = "Cancelled in Bloowatch — board still out.";
  const toNote = kept.filter((r) => !(r.notes ?? "").includes(NOTE));
  for (const r of toNote) {
    await db.from("rentals").update({ notes: [r.notes, NOTE].filter(Boolean).join(" ") }).eq("id", r.id);
  }

  // Removed, not ended: the hire never happened, so it does not belong in History with hours against it.
  return Response.json({
    ok: true,
    active: live.size,
    removed: removable.length,
    kept: kept.map((r) => r.bloowatch_booking_id),
  });
}
