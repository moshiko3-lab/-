// Settings > Google Sheets > Disconnect (owner only). The sheet stays in the business's Drive; the app just stops
// writing to it and gives up its access.
import { getProfile } from "@/lib/auth";
import { getConnection, revoke } from "@/lib/google";
import { createAdminClient } from "@/lib/supabase/admin";

export async function POST() {
  if ((await getProfile())?.role !== "owner") return Response.json({ error: "Only the owner can do this." }, { status: 403 });
  const db = createAdminClient();
  const connection = await getConnection(db);
  if (connection) await revoke(connection);
  await db.from("private_settings").delete().eq("key", "google");
  await db.from("app_settings").delete().in("key", ["sheets", "sheets_status"]);
  return Response.json({ ok: true });
}
