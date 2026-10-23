import { createClient } from "@supabase/supabase-js";

// Full-access client for server code only (staff accounts). The secret key is a server environment variable
// and never reaches the browser; every caller checks that the signed-in person is an active owner first.
export const createAdminClient = () =>
  createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.SUPABASE_SECRET_KEY!, { auth: { persistSession: false } });
