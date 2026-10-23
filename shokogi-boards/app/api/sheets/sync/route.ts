// Runs the Google Sheets sync. Called a few seconds after changes by the device that made them, and every
// 10 minutes by a database timer (with CRON_SECRET) so "Overdue" stays current.
import { getProfile } from "@/lib/auth";
import { syncAndRecord } from "@/lib/sheets";
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST(request: Request) {
  const secret = process.env.CRON_SECRET;
  const fromTimer = !!secret && request.headers.get("authorization") === `Bearer ${secret}`;
  if (!fromTimer && !(await getProfile())?.active) return Response.json({ error: "Sign in first." }, { status: 401 });
  const db = createAdminClient();
  const { data } = await db.from("app_settings").select("key").eq("key", "sheets").maybeSingle();
  if (!data) return Response.json({ error: "Google Sheets is not connected yet." }, { status: 503 });
  const result = await syncAndRecord(db);
  return Response.json(result, { status: result.ok ? 200 : 502 });
}
