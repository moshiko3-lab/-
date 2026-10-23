// Runs the Bloowatch pull. Called every minute by a database timer (with CRON_SECRET), and by a signed-in member
// from Settings to check the connection. Running it twice changes nothing.
//
// A timer and not a webhook because Bloowatch has none, and polling and not a change feed because every
// "changed since" filter it offers is silently ignored (see lib/bloowatch.ts). Every minute is as live as the
// bookings can be known: a hire entered in Bloowatch is a rental here within the minute.
import { getProfile } from "@/lib/auth";
import { syncAndRecord } from "@/lib/bloowatch";
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST(request: Request) {
  const secret = process.env.CRON_SECRET;
  const fromTimer = !!secret && request.headers.get("authorization") === `Bearer ${secret}`;
  if (!fromTimer && !(await getProfile())?.active) return Response.json({ error: "Sign in first." }, { status: 401 });

  const db = createAdminClient();
  // The owner's own switch, off by default: turning Bloowatch off has to actually stop it, timer included.
  const { data: setting } = await db.from("app_settings").select("value").eq("key", "bloowatch_enabled").maybeSingle();
  if (setting?.value !== true) return Response.json({ error: "Bloowatch is turned off in Settings." }, { status: 409 });

  const result = await syncAndRecord(db);
  return Response.json(result, { status: result.ok ? 200 : 502 });
}
