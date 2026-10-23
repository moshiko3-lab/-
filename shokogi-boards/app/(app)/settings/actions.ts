"use server";

// Staff accounts (SPEC 3, 7.9). Owner only, checked here on the server; the database also keeps at least one
// active owner. Deactivating bans the login but keeps the person's name on their history.
// Profile changes go through the owner's own session (`db`), so the change log names the owner;
// only the login itself (create, ban, password) needs the full-access `admin` client.
import { getProfile, type Role } from "@/lib/auth";
import { loginEmail } from "@/lib/login";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

type Result = { error?: string };
const FOREVER = "876000h"; // 100 years

type Clients = { db: Awaited<ReturnType<typeof createClient>>; admin: ReturnType<typeof createAdminClient> };
async function asOwner(action: (c: Clients) => Promise<Result>): Promise<Result> {
  const me = await getProfile();
  if (me?.role !== "owner" || !me.active) return { error: "Only the owner can manage staff." };
  try {
    return await action({ db: await createClient(), admin: createAdminClient() });
  } catch (e) {
    return { error: (e as Error).message || "Something went wrong. Try again." };
  }
}

const passwordProblem = (p: string) => (p.length < 8 ? "The password needs at least 8 characters." : undefined);

export async function createStaff(name: string, login: string, role: Role, password: string): Promise<Result> {
  name = name.trim();
  login = login.trim().toLowerCase();
  if (!name) return { error: "Enter the person's name." };
  if (!login.includes("@") && !/^[a-z0-9._-]{2,30}$/.test(login)) return { error: "Usernames use letters, numbers, dots and dashes (2-30 characters)." };
  const problem = passwordProblem(password);
  if (problem) return { error: problem };
  return asOwner(async ({ db, admin }) => {
    const { data, error } = await admin.auth.admin.createUser({ email: loginEmail(login), password, email_confirm: true, user_metadata: { name } });
    if (error) return { error: /already/i.test(error.message) ? "That username is already taken." : error.message };
    await db.from("profiles").update({ name, role, active: true, must_change_password: true }).eq("id", data.user.id).throwOnError();
    return {};
  });
}

export async function setRole(id: string, role: Role): Promise<Result> {
  return asOwner(async ({ db }) => {
    const { error } = await db.from("profiles").update({ role }).eq("id", id);
    return error ? { error: error.message } : {};
  });
}

export async function setActive(id: string, active: boolean): Promise<Result> {
  return asOwner(async ({ db, admin }) => {
    const { error } = await db.from("profiles").update({ active }).eq("id", id);
    if (error) return { error: error.message };
    const { error: banError } = await admin.auth.admin.updateUserById(id, { ban_duration: active ? "none" : FOREVER });
    return banError ? { error: banError.message } : {};
  });
}

export async function resetPassword(id: string, password: string): Promise<Result> {
  const problem = passwordProblem(password);
  if (problem) return { error: problem };
  return asOwner(async ({ db, admin }) => {
    const { error } = await admin.auth.admin.updateUserById(id, { password });
    if (error) return { error: error.message };
    await db.from("profiles").update({ must_change_password: true }).eq("id", id).throwOnError();
    return {};
  });
}
