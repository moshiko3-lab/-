import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Refreshes the login session on every page request and sends signed-out visitors to /login.
// Real permission checks happen in the database (Row Level Security), not here.
export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(list, headers) {
        list.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        list.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        Object.entries(headers).forEach(([key, value]) => response.headers.set(key, value));
      },
    },
  });
  const { data } = await supabase.auth.getClaims();
  const signedIn = !!data?.claims;
  if (request.nextUrl.pathname === "/privacy") return response; // public, for Google's consent screen
  if (signedIn !== (request.nextUrl.pathname === "/login")) return response;

  // Signed out away from /login, or signed in on /login: redirect, keeping any refreshed session cookies.
  const redirect = NextResponse.redirect(new URL(signedIn ? "/" : "/login", request.url));
  response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
  return redirect;
}

export const config = {
  matcher: ["/((?!api/|_next/static|_next/image|icons/|icon\\.svg|apple-icon\\.png|manifest\\.webmanifest|favicon\\.ico).*)"],
};
