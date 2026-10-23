// Nightly backup (SPEC 9): every table as one JSON file, "YYYY-MM-DD.json" (Panama date) in the private "backups"
// bucket, keeping the last 30. Called once a night by the database timer with CRON_SECRET.
// The Google Sheet is the second, human-readable copy.
import type { SupabaseClient } from "@supabase/supabase-js";
import { createAdminClient } from "@/lib/supabase/admin";
import { panamaParts } from "@/lib/time";

const TABLES = ["profiles", "board_types", "boards", "customers", "rental_lengths", "rentals", "rental_items", "app_settings"];
const KEEP = 30;

async function all(db: SupabaseClient, table: string, since?: string) {
  const rows: unknown[] = [];
  for (let from = 0; ; from += 1000) { // the API returns at most 1000 rows per request
    let q = db.from(table).select("*").range(from, from + 999);
    if (since) q = q.gte("at", since);
    const { data, error } = await q;
    if (error) throw new Error(`${table}: ${error.message}`);
    rows.push(...data);
    if (data.length < 1000) return rows;
  }
}

export async function POST(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`) return Response.json({ error: "Not allowed." }, { status: 401 });
  const db = createAdminClient();
  const snapshot: Record<string, unknown> = { taken_at: new Date().toISOString() };
  for (const t of TABLES) snapshot[t] = await all(db, t);
  // ponytail: only the last month of the change log, so 30 copies stay small; the full log stays in the database.
  snapshot.audit_log = await all(db, "audit_log", new Date(Date.now() - 31 * 864e5).toISOString());

  const p = panamaParts(Date.now());
  const name = `${p.y}-${String(p.m + 1).padStart(2, "0")}-${String(p.d).padStart(2, "0")}.json`;
  const bucket = db.storage.from("backups");
  const { error } = await bucket.upload(name, JSON.stringify(snapshot), { contentType: "application/json", upsert: true });
  if (error) return Response.json({ error: error.message }, { status: 500 });

  const { data: files } = await bucket.list("", { sortBy: { column: "name", order: "desc" }, limit: 1000 });
  const old = (files ?? []).map((f) => f.name).filter((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n)).slice(KEEP);
  if (old.length) await bucket.remove(old);
  return Response.json({ ok: true, file: name, removed: old.length });
}
