// Local development data: the test logins from .env.local and the prototype's boards (with their photos when the
// private migration/ folder is on this computer; without it, the same boards without photos).
// Local Supabase only. Run after `npx supabase db reset`: node scripts/seed-local.mts [--no-boards] [--activity]
import { createClient } from "@supabase/supabase-js";
import { existsSync, readFileSync } from "node:fs";

process.loadEnvFile(".env.local");
const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(url)) throw new Error("seed-local only runs against the local Supabase.");
const admin = createClient(url, process.env.SUPABASE_SECRET_KEY!, { auth: { persistSession: false } });

const logins: [string, string, "owner" | "staff" | "instructor"][] = [
  [process.env.LOCAL_TEST_OWNER!, "Asaf (test)", "owner"],
  [`${process.env.LOCAL_TEST_STAFF}@staff.shokogi.invalid`, "Dana", "staff"],
  [`${process.env.LOCAL_TEST_INSTRUCTOR}@staff.shokogi.invalid`, "Kai", "instructor"],
];
const { data: users } = await admin.auth.admin.listUsers({ perPage: 10000 }); // the tests leave many logins behind
for (const [email, name, role] of logins) {
  let id = users.users.find((u) => u.email === email)?.id;
  if (!id) {
    const { data, error } = await admin.auth.admin.createUser({ email, password: process.env.LOCAL_TEST_PASSWORD!, email_confirm: true, user_metadata: { name } });
    if (error) throw error;
    id = data.user.id;
  }
  await admin.from("profiles").update({ name, role, active: true }).eq("id", id).throwOnError();
}

const { data: types } = await admin.from("board_types").select("id, name, is_system").throwOnError();
const typeId = (name: string) => (types!.find((t) => t.name === name) ?? types!.find((t) => t.is_system))!.id;
const proto: { boards: { id: string; name: string; cat: string; file: string }[] } = JSON.parse(readFileSync("tests/fixtures/prototype-boards.json", "utf8"));
let added = 0;
for (const b of process.argv.includes("--no-boards") ? [] : proto.boards) {
  const { data: exists } = await admin.from("boards").select("id").eq("id", b.id).maybeSingle();
  if (exists) continue;
  const photo = `migration/photos/${b.id}.jpg`;
  let path: string | null = null;
  if (existsSync(photo)) {
    path = `${b.id}/seed.jpg`; // the prototype's 800 px photo serves as both sizes locally
    const { error } = await admin.storage.from("boards").upload(path, readFileSync(photo), { contentType: "image/jpeg", upsert: true });
    if (error) throw error;
  }
  await admin.from("boards").insert({ id: b.id, name: b.name, type_id: typeId(b.cat), source_file_name: b.file, photo_path: path, thumb_path: path }).throwOnError();
  added++;
}
console.log(`Logins ready; ${added} boards added (${proto.boards.length} in the prototype).`);

// `--activity`: a few rentals to look at — out now (a family, one overdue, one waiting for a board)
// and returned ones over the last days, some late.
if (process.argv.includes("--activity")) {
  const H = 36e5, now = Date.now();
  const ago = (h: number) => new Date(now - h * H).toISOString();
  const { data: free } = await admin.from("boards").select("id").is("deleted_at", null).order("name").limit(20);
  let next = 0;
  async function rental(name: string, phone: string, start: number, due: number, boards: number, returned?: number) {
    const digits = phone.replace(/\D/g, "");
    const found = digits
      ? await admin.from("customers").select("id").eq("phone_digits", digits).maybeSingle()
      : await admin.from("customers").select("id").eq("name", name).limit(1).maybeSingle();
    const customer = found.data ?? (await admin.from("customers").insert({ name, phone }).select("id").single().throwOnError()).data;
    const { data: r } = await admin.from("rentals").insert({ customer_id: customer!.id, starts_at: ago(start), due_at: ago(due), ended_at: returned === undefined ? null : ago(returned) }).select().single().throwOnError();
    for (let i = 0; i < boards; i++)
      await admin.from("rental_items").insert({ rental_id: r!.id, board_id: free![next++ % free!.length].id, assigned_at: ago(start), unassigned_at: returned === undefined ? null : ago(returned) }).throwOnError();
  }
  await rental("Cohen family", "052-111-2233", 1, -2, 2);
  await rental("Mike Turner", "+1 415 555 0134", 3, 1, 1);
  await rental("Lucia Gómez", "6612-3344", 0.1, -1, 0);
  await rental("Mike Turner", "+1 415 555 0134", 50, 48, 1, 47.5);
  await rental("Noa Levi", "054-777-8899", 30, 28, 1, 27);
  await rental("Noa Levi", "054-777-8899", 6, 4, 1, 4.2);
  await rental("Tom", "", 26, 25, 1, 23);
  console.log("Sample rentals added.");
}
