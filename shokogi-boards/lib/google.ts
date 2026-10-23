// "Connect Google Sheets" (SPEC 7.11): the owner signs in once with the business's Google account and allows the
// app to create and edit ITS OWN files there (drive.file: it can't see anything else in that Drive). Google then
// gives a refresh token, kept server-side in private_settings, that lets the server sync without anyone signed in.
// Needs a Google OAuth client (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET), registered once in Google Cloud. Server only.
import type { SupabaseClient } from "@supabase/supabase-js";

const SCOPES = ["openid", "email", "https://www.googleapis.com/auth/drive.file"];
const TOKEN_URL = "https://oauth2.googleapis.com/token";

export const googleReady = () => !!process.env.GOOGLE_CLIENT_ID && !!process.env.GOOGLE_CLIENT_SECRET;

export function consentUrl(redirectUri: string, state: string) {
  const q = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID!, redirect_uri: redirectUri, response_type: "code", scope: SCOPES.join(" "),
    access_type: "offline", prompt: "consent", state, // offline + consent: Google always sends a refresh token
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${q}`;
}

async function token(params: Record<string, string>) {
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    body: new URLSearchParams({ client_id: process.env.GOOGLE_CLIENT_ID!, client_secret: process.env.GOOGLE_CLIENT_SECRET!, ...params }),
  });
  const body = await res.json();
  if (!res.ok) throw Object.assign(new Error(body.error_description ?? body.error ?? "Google refused the request."), { code: body.error });
  return body as { access_token: string; refresh_token?: string; id_token?: string };
}

// After the owner allowed access: the lasting connection and the Google account it belongs to.
export async function exchangeCode(code: string, redirectUri: string) {
  const t = await token({ code, redirect_uri: redirectUri, grant_type: "authorization_code" });
  if (!t.refresh_token) throw new Error("Google didn't grant lasting access. Try connecting again.");
  const claims = JSON.parse(Buffer.from(t.id_token!.split(".")[1], "base64url").toString()); // straight from Google over TLS
  return { refresh_token: t.refresh_token, email: claims.email as string, access_token: t.access_token };
}

export type Connection = { refresh_token: string; email: string };

export async function getConnection(db: SupabaseClient) {
  const { data } = await db.from("private_settings").select("value").eq("key", "google").maybeSingle();
  return (data?.value as Connection | undefined) ?? null;
}

// A short-lived access token. If the business removed the app's access in their Google account, says so plainly.
export async function accessToken(c: Connection) {
  try {
    return (await token({ refresh_token: c.refresh_token, grant_type: "refresh_token" })).access_token;
  } catch (e) {
    if ((e as { code?: string }).code === "invalid_grant") throw new Error("Google access was removed. Connect Google Sheets again in Settings.");
    throw e;
  }
}

export async function revoke(c: Connection) {
  await fetch(`https://oauth2.googleapis.com/revoke?token=${encodeURIComponent(c.refresh_token)}`, { method: "POST" }).catch(() => null);
}
