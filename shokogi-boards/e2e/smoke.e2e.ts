// SPEC section 9 smoke test: log in, create a rental, pick a board, swap, extend, return, find the customer;
// the overdue alert pops on load, "+1 hour" clears it, and a reload with another overdue rental pops it again.
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";
import { createClient } from "@supabase/supabase-js";
import { panamaParts } from "../lib/time";

process.loadEnvFile(".env.local");
const URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
if (!/^http:\/\/(127\.0\.0\.1|localhost)/.test(URL)) throw new Error("The smoke test only runs against the local Supabase.");
const admin = createClient(URL, process.env.SUPABASE_SECRET_KEY!, { auth: { persistSession: false } });
const run = Date.now().toString(36);

// No overdue leftovers from earlier runs: they would pop the alert over the first test.
async function returnEverything() {
  const now = new Date().toISOString();
  const { data } = await admin.from("rentals").select("id").is("ended_at", null);
  const ids = (data ?? []).map((r) => r.id);
  await admin.from("rental_items").update({ unassigned_at: now }).in("rental_id", ids).is("unassigned_at", null);
  await admin.from("rentals").update({ ended_at: now }).in("id", ids);
}
test.beforeAll(returnEverything);
test.afterAll(returnEverything);

async function login(page: Page, as = process.env.LOCAL_TEST_STAFF!) {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(as);
  await page.getByLabel("Password").fill(process.env.LOCAL_TEST_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
}

test("a rental from start to return", async ({ page, browser }) => {
  const name = `E2E ${run}`;
  await login(page);
  await page.getByRole("link", { name: "Rentals" }).click();
  await page.getByPlaceholder("Customer name").fill(name);
  await page.getByPlaceholder("Phone (optional)").fill(`050-${Date.now().toString().slice(-7)}`); // new digits: a new customer
  await page.locator("select[name=minutes]").selectOption({ label: "1 hour" });
  await page.getByRole("button", { name: "Add and choose board" }).click();

  const picker = page.locator("#pickDlg");
  await expect(picker).toContainText(`Choose a board for ${name}`);
  await picker.getByRole("searchbox").fill("9'6 all around");
  await picker.locator(".pick").first().click();
  const row = page.locator("tbody tr", { hasText: name });
  await expect(row).toContainText("LONGBOARD 9'6 ALL AROUND TORQ");

  await row.getByRole("button", { name: "Change" }).click();
  await expect(picker).toContainText(`Swap board for ${name}`);
  await picker.getByRole("searchbox").fill("the gem");
  await picker.locator(".pick").first().click();
  await expect(row).toContainText("LONGBOARD THE GEM 9'1 FIREWIRE");
  await expect(row).not.toContainText("9'6 ALL AROUND");

  // Extend to tomorrow, same time, with the calendar.
  const tomorrow = panamaParts(Date.now() + 864e5);
  await row.locator(".dt").click();
  const cal = page.locator(".cal");
  if (tomorrow.d === 1) await cal.getByRole("button", { name: "Next month" }).click();
  await cal.locator(".cal-g button:not(.out)", { hasText: new RegExp(`^${tomorrow.d}$`) }).click();
  await cal.getByRole("button", { name: "Apply" }).click();
  await expect(row.locator(".st")).toHaveText(/^1d [01]h left$/); // the 1-hour rental, a day later

  await row.getByRole("button", { name: "Mark returned" }).click();
  await page.locator("dialog.ask").getByRole("button", { name: "Mark returned" }).click();
  await expect(row).toContainText("Needs a board"); // time left: waits for another board
  await expect(row.getByRole("button", { name: /Mark returned|Finish rental/ })).toHaveCount(0); // ending early is the owner's

  // The owner finishes it early.
  const ownerPage = await (await browser.newContext()).newPage();
  await login(ownerPage, process.env.LOCAL_TEST_OWNER);
  await ownerPage.getByRole("link", { name: "Rentals" }).click();
  await ownerPage.locator("tbody tr", { hasText: name }).getByRole("button", { name: "Finish rental" }).click();
  await ownerPage.locator("dialog.ask").getByRole("button", { name: "Finish rental" }).click();
  await expect(ownerPage.locator("tbody tr", { hasText: name })).toHaveCount(0);

  await page.getByRole("link", { name: "Customers" }).click();
  await page.getByPlaceholder("Search name or phone").fill(name);
  await expect(page.locator("tbody tr", { hasText: name }).locator("td").nth(1)).toHaveText("1");

  await page.getByRole("link", { name: "History" }).click();
  const returned = page.locator("tbody tr", { hasText: name });
  await expect(returned).toContainText("LONGBOARD THE GEM 9'1 FIREWIRE");
  await expect(returned).toContainText("Asaf"); // finished by the owner
  await expect(page.getByRole("button", { name: "Export to Excel" })).toHaveCount(0); // owner only
  await expect(returned.getByRole("button", { name: "Changes" })).toHaveCount(0); // owner only

  // The owner sees who changed this rental, step by step.
  await ownerPage.getByRole("link", { name: "History" }).click();
  await ownerPage.locator("tbody tr", { hasText: name }).getByRole("button", { name: "Changes" }).click();
  const trail = ownerPage.locator("#trailDlg li");
  await expect(trail).toHaveText([
    /Danacreated the rental$/,
    /Danahanded out LONGBOARD 9'6 ALL AROUND TORQ$/,
    /Danatook back LONGBOARD 9'6 ALL AROUND TORQ, handed out LONGBOARD THE GEM 9'1 FIREWIRE$/,
    /Danachanged the return time to /,
    /Danatook back LONGBOARD THE GEM 9'1 FIREWIRE$/,
    /Asaf \(test\)finished the rental early$/,
  ]);
});

test("Excel export (owner), following the History filters", async ({ page }) => {
  await returnEverything(); // the overdue alert from the previous test would cover the button
  const name = `Excel ${run}`;
  const { data: c } = await admin.from("customers").insert({ name, phone: `05${Date.now().toString().slice(-8)}` }).select().single().throwOnError();
  const starts = "2026-10-18T14:00:00Z", ends = "2026-10-18T17:30:00Z"; // 09:00-12:30 in Panama, due 11:00
  await admin.from("rentals").insert({ customer_id: c!.id, starts_at: starts, due_at: "2026-10-18T16:00:00Z", ended_at: ends }).throwOnError();

  await login(page, process.env.LOCAL_TEST_OWNER);
  await page.getByRole("link", { name: "History" }).click();
  await page.getByPlaceholder("Search customer, phone or board").fill(name);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Export to Excel" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^Shokogi-boards-\d{4}-\d{2}-\d{2}\.xlsx$/);

  const XLSX = await import("xlsx");
  const wb = XLSX.read(await readFile(await download.path()), { cellNF: true });
  expect(wb.SheetNames).toEqual(["Rented now", "Rental history", "Boards"]);
  const history = XLSX.utils.sheet_to_json<Record<string, unknown>>(wb.Sheets["Rental history"]);
  expect(history).toHaveLength(1); // only what the History page shows
  expect(history[0]).toMatchObject({ Customer: name, Hours: 3.5, "Minutes late": 90 });
  const start = wb.Sheets["Rental history"].E2;
  expect(start.t).toBe("n"); // a real Excel date, in Panama time
  expect(start.v).toBeCloseTo(46313 + 9 / 24, 6); // 18 Oct 2026, 09:00
  expect(start.z).toBe("dd/mm/yyyy hh:mm");
  expect(XLSX.utils.sheet_to_json(wb.Sheets.Boards).length).toBeGreaterThan(0);
});

// A rental handed out three hours ago that was due an hour ago, made directly in the database.
async function overdueRental(name: string) {
  const { data: boards } = await admin.from("boards").select("id").is("deleted_at", null).eq("in_repair", 0);
  const { data: out } = await admin.from("rental_items").select("board_id").is("unassigned_at", null);
  const busy = new Set((out ?? []).map((i) => i.board_id));
  const board = boards!.find((b) => !busy.has(b.id))!;
  const { data: c } = await admin.from("customers").insert({ name }).select().single().throwOnError();
  const { data: r } = await admin.from("rentals").insert({
    customer_id: c!.id, starts_at: new Date(Date.now() - 3 * 36e5).toISOString(), due_at: new Date(Date.now() - 36e5).toISOString(),
  }).select().single().throwOnError();
  await admin.from("rental_items").insert({ rental_id: r!.id, board_id: board.id, assigned_at: r!.starts_at }).throwOnError();
}

test("the overdue alert", async ({ page }) => {
  const [a, b] = [`Late A ${run}`, `Late B ${run}`];
  await overdueRental(a);
  await login(page);
  const alert = page.locator("#lateDlg");
  await expect(alert).toBeVisible();
  await expect(page).toHaveTitle("(1) Overdue · Shokogi Boards");
  await alert.locator(".late-row", { hasText: a }).getByRole("button", { name: "+1 hour" }).click();
  await expect(alert).toBeHidden(); // nothing overdue any more
  await expect(page).toHaveTitle("Shokogi Boards");

  await overdueRental(b);
  await page.reload();
  await expect(alert).toBeVisible();
  await expect(alert).toContainText(b);
  await expect(alert).not.toContainText(a);
});

test("settings: staff accounts, rental lengths and board types", async ({ page, browser }) => {
  await returnEverything();
  const kai = `kai${run}`.toLowerCase(), temp = "Temp-pass-123", own = "My-own-pass-456";
  await login(page, process.env.LOCAL_TEST_OWNER);
  await page.getByRole("link", { name: "Settings" }).click();

  // Add a staff member with a temporary password.
  const staff = page.locator(".staff");
  await staff.getByPlaceholder("Name, e.g. Dana", { exact: true }).fill("Kai");
  await staff.getByPlaceholder("Username, e.g. dana").fill(kai);
  await staff.getByPlaceholder("Temporary password (8+ characters)").fill(temp);
  await staff.getByRole("button", { name: "Add person" }).click();
  await expect(staff.locator(".set-row", { hasText: kai })).toContainText("Active");

  // Kai logs in with it and must choose their own password first.
  const kaiPage = await (await browser.newContext()).newPage();
  await kaiPage.goto("/login");
  await kaiPage.getByLabel("Username or email").fill(kai);
  await kaiPage.getByLabel("Password").fill(temp);
  await kaiPage.getByRole("button", { name: "Sign in" }).click();
  await expect(kaiPage.getByText("Choose your own password to continue")).toBeVisible();
  await kaiPage.getByLabel("New password").fill(own);
  await kaiPage.getByLabel("Repeat it").fill(own);
  await kaiPage.getByRole("button", { name: "Save password" }).click();
  await expect(kaiPage.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await expect(kaiPage.getByRole("link", { name: "Settings" })).toHaveCount(0); // staff

  // The owner deactivates Kai: Kai can't log in any more.
  await staff.locator(".set-row", { hasText: kai }).getByRole("button", { name: "Deactivate" }).click();
  await page.locator("dialog.ask").getByRole("button", { name: "Deactivate" }).click();
  await expect(staff.locator(".set-row", { hasText: kai })).toContainText("Deactivated");
  const again = await (await browser.newContext()).newPage();
  await again.goto("/login");
  await again.getByLabel("Username or email").fill(kai);
  await again.getByLabel("Password").fill(own);
  await again.getByRole("button", { name: "Sign in" }).click();
  await expect(again.locator("p.error")).toHaveText("This account is deactivated. Ask the owner.");

  // A rental length of 2.5 hours shows as such and is offered for new rentals.
  const label = `Sunset ${run}`;
  const add = page.locator("form.set-add", { has: page.getByPlaceholder("New length, e.g. Sunset session") });
  await add.getByPlaceholder("New length, e.g. Sunset session").fill(label);
  await add.getByLabel("Amount").fill("2.5");
  await add.getByRole("button", { name: "Add" }).click();
  const row = page.locator(".set-row", { has: page.locator(`input[value="${label}"]`) });
  await expect(row.getByLabel("Amount")).toHaveValue("2.5");
  await expect(row.getByLabel("Unit")).toHaveValue("60");
  await page.getByRole("link", { name: "Rentals" }).click();
  await expect(page.locator("select[name=minutes] option", { hasText: label })).toHaveAttribute("value", "150");
  await page.getByRole("link", { name: "Settings" }).click();
  await page.locator(".set-row", { has: page.locator(`input[value="${label}"]`) }).getByTitle("Remove").click();
  await expect(page.locator(`input[value="${label}"]`)).toHaveCount(0);

  // Board types: "Other" is refused, a new type can be renamed and removed.
  await page.getByPlaceholder("New type, e.g. SUP").fill("other");
  await page.getByRole("button", { name: "Add type" }).click();
  await expect(page.locator(".toast", { hasText: '"Other" is built in.' })).toBeVisible();
  await page.getByPlaceholder("New type, e.g. SUP").fill(`SUP ${run}`);
  await page.getByRole("button", { name: "Add type" }).click();
  const type = page.locator(`input[aria-label="Type name"][value="SUP ${run}"]`);
  await type.fill(`Paddle ${run}`);
  await type.press("Enter");
  const renamed = page.locator(".set-row", { has: page.locator(`input[value="Paddle ${run}"]`) });
  await expect(renamed).toContainText("0 boards");
  await renamed.getByTitle("Remove type").click();
  await expect(renamed).toHaveCount(0);
});

test("Google Sheets: Connect sends the owner to Google, asking only for the app's own files", async ({ page }) => {
  await returnEverything();
  await login(page, process.env.LOCAL_TEST_OWNER);
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("link", { name: "Connect Google Sheets" })).toHaveAttribute("href", "/api/google/connect");
  const res = await page.request.get("/api/google/connect", { maxRedirects: 0 }); // the button's target, as this owner
  const google = new globalThis.URL(res.headers().location); // `URL` here is the database address
  expect(google.origin + google.pathname).toBe("https://accounts.google.com/o/oauth2/v2/auth");
  expect(google.searchParams.get("scope")).toBe("openid email https://www.googleapis.com/auth/drive.file");
  expect(google.searchParams.get("access_type")).toBe("offline");
  expect(google.searchParams.get("redirect_uri")).toBe("http://localhost:3000/api/google/callback");

  // Coming back with someone else's (or a stale) request is refused.
  await page.goto("/api/google/callback?state=forged&code=x");
  await expect(page.locator(".toast", { hasText: "took too long" })).toBeVisible();
  await expect(page).toHaveURL(/\/settings$/);
});

test("Bloowatch: a booking becomes a rental only when turned on, and updates it instead of duplicating", async ({ request }) => {
  const secret = process.env.BLOOWATCH_WEBHOOK_SECRET!;
  const booking = { booking_id: `BW-${run}`, name: `Booker ${run}`, phone: `07${Date.now().toString().slice(-8)}`,
    starts_at: new Date().toISOString(), due_at: new Date(Date.now() + 2 * 36e5).toISOString() };
  const post = (body: object, key = secret) => request.post("/api/bloowatch/webhook", { data: body, headers: { "x-webhook-secret": key } });

  expect((await post(booking, "wrong")).status()).toBe(401);
  await admin.from("app_settings").upsert({ key: "bloowatch_enabled", value: false });
  expect((await post(booking)).status()).toBe(409); // off by default
  await admin.from("app_settings").upsert({ key: "bloowatch_enabled", value: true });
  try {
    expect((await post({ ...booking, due_at: "soon" })).status()).toBe(400);
    expect((await post(booking)).status()).toBe(201);
    const later = new Date(Date.now() + 3 * 36e5).toISOString();
    expect((await post({ ...booking, due_at: later })).status()).toBe(200);
    const { data } = await admin.from("rentals").select("source, due_at, ended_at").eq("bloowatch_booking_id", booking.booking_id);
    expect(data).toHaveLength(1);
    expect(data![0]).toMatchObject({ source: "bloowatch", ended_at: null });
    expect(Date.parse(data![0].due_at)).toBe(Date.parse(later));
  } finally {
    await admin.from("app_settings").upsert({ key: "bloowatch_enabled", value: false });
    await returnEverything();
  }
});

test("an instructor's phone: open rentals only, hand out, swap and return, nothing else", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const name = `Instructor E2E ${run}`;
  const phone = `050-${Date.now().toString().slice(-7)}`;
  const { data: c } = await admin.from("customers").insert({ name, phone }).select().single().throwOnError();
  await admin.from("rentals").insert({ customer_id: c!.id, due_at: new Date(Date.now() + 36e5).toISOString() }).throwOnError();

  await page.goto("/login");
  await page.getByLabel("Username or email").fill(process.env.LOCAL_TEST_INSTRUCTOR!);
  await page.getByLabel("Password").fill(process.env.LOCAL_TEST_PASSWORD!);
  await page.getByRole("button", { name: "Sign in" }).click();
  const card = page.locator(".ins-card", { hasText: name });
  await expect(card).toBeVisible();
  await expect(card).not.toContainText(phone.slice(-7));
  await expect(page.getByRole("navigation")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390); // no sideways scrolling

  const search = page.getByRole("searchbox", { name: "Search by name" });
  await search.fill("nobody like this");
  await expect(card).toHaveCount(0);
  await expect(page.getByText("Nobody matches your search.")).toBeVisible();
  await search.fill(name.toLowerCase());
  await expect(card).toBeVisible();

  await expect(card.getByRole("button")).toHaveText(["Choose board"]); // no board yet: the only button
  await card.getByRole("button", { name: "Choose board" }).click();
  const picker = page.locator("#pickDlg");
  await picker.getByRole("searchbox").fill("9'6 all around");
  await picker.locator(".pick").first().click();
  await expect(card).toContainText("LONGBOARD 9'6 ALL AROUND TORQ");
  await card.getByRole("button", { name: "Swap" }).click();
  await picker.getByRole("searchbox").fill("the gem");
  await picker.locator(".pick").first().click();
  await expect(card).toContainText("LONGBOARD THE GEM 9'1 FIREWIRE");
  await expect(card).not.toContainText("9'6 ALL AROUND");
  await expect(card.getByRole("button")).toHaveText(["Swap", "Mark returned"]); // the only buttons once it has a board

  await card.getByRole("button", { name: "Mark returned" }).click();
  await page.locator(".ask").getByRole("button", { name: "Mark returned" }).click();
  await expect(card.getByRole("button", { name: "Choose board" })).toBeVisible(); // time left: back under "Needs a board"
  await expect(card).not.toContainText("THE GEM");

  await page.goto("/customers"); // every address shows the same one screen
  await expect(page.locator(".ins")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Customers" })).toHaveCount(0);
});
