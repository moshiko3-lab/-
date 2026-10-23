// Back from Google: keep the lasting access server-side, create the folder + sheet in that account's Drive
// (or reuse the one made for it before), fill it once, and return to Settings.
import { cookies } from "next/headers";
import { getProfile } from "@/lib/auth";
import { exchangeCode } from "@/lib/google";
import { ensureSheet, syncAndRecord } from "@/lib/sheets";
import { createAdminClient } from "@/lib/supabase/admin";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const back = (result: string) => Response.redirect(new URL(`/settings?google=${encodeURIComponent(result)}`, request.url));
  if ((await getProfile())?.role !== "owner") return Response.redirect(new URL("/", request.url));
  const jar = await cookies();
  const state = jar.get("google_state")?.value;
  jar.delete({ name: "google_state", path: "/api/google" });
  if (!state || state !== url.searchParams.get("state")) return back("expired");
  if (url.searchParams.get("error")) return back("cancelled"); // "Cancel" on Google's screen
  try {
    const { refresh_token, email, access_token } = await exchangeCode(url.searchParams.get("code") ?? "", `${url.origin}${url.pathname}`);
    const db = createAdminClient();
    await db.from("private_settings").upsert({ key: "google", value: { refresh_token, email } }).throwOnError();
    await ensureSheet(db, access_token, email);
    await syncAndRecord(db);
    return back("connected");
  } catch (e) {
    console.error("Google connect failed", e);
    return back("failed");
  }
}
