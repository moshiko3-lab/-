import { cache } from "react";
import { createClient } from "./supabase/server";

// Instructors only hand out, swap and take back boards and mark rentals returned (see InstructorView).
export type Role = "owner" | "staff" | "instructor";
export type Profile = { id: string; name: string; role: Role; active: boolean; must_change_password: boolean };

// The signed-in person's profile, looked up once per request. null when signed out or without a profile.
export const getProfile = cache(async (): Promise<Profile | null> => {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  const id = data?.claims.sub;
  if (!id) return null;
  const { data: profile } = await supabase.from("profiles").select("id, name, role, active, must_change_password").eq("id", id).maybeSingle();
  return profile;
});
