// Settings > Google Sheets > Connect (owner only): off to Google to choose the business account and allow access.
import { cookies } from "next/headers";
import { getProfile } from "@/lib/auth";
import { consentUrl, googleReady } from "@/lib/google";

export async function GET(request: Request) {
  const settings = new URL("/settings", request.url);
  if ((await getProfile())?.role !== "owner") return Response.redirect(new URL("/", request.url));
  if (!googleReady()) return Response.redirect(`${settings}?google=not-set-up`);
  const state = crypto.randomUUID(); // checked on the way back, so nobody else can finish a connection for us
  (await cookies()).set("google_state", state, { httpOnly: true, secure: true, sameSite: "lax", maxAge: 600, path: "/api/google" });
  return Response.redirect(consentUrl(new URL("/api/google/callback", request.url).toString(), state));
}
