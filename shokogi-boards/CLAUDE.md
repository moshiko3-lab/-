# Shokogi Boards

@AGENTS.md

Board-rental desk app for the Shokogi surf club (Playa Venao, Panama). Live: https://shokogi-boards.vercel.app.
Next.js 16 (App Router) + Supabase (Postgres, Row Level Security, Auth, Storage, Realtime), hosted on Vercel.
Full spec: `SPEC.md`. Owner guide (Hebrew): `OWNER-GUIDE.he.md`.

## Rules

- Talk to the owner in Hebrew, short and simple: he is not a developer. The app's own text stays in English.
- Never put a secret (API key, password, token) in the repo, in browser code, in a chat or in a file. Server secrets
  live in Vercel's environment variables, in Supabase, or in the server-only table `private_settings`.
  `.env.local` is for local values only and is gitignored.
- No real customer data in the repo. `migration/` (the prototype's real data) is gitignored and stays on Asaf's Mac.
- Only the main session on Asaf's Mac changes the live site: `vercel deploy --prod`, `supabase db push`, and anything
  run against the live database. Everyone else works on a branch and pushes it.
- A database change is a new file in `supabase/migrations/`; never edit one that is already applied.
- Keep the code style: small and plain, comments say why. Times are Panama time (UTC-5, see `lib/time.ts`).

## Where things are

- `app/`: pages and API routes (`app/api/...`). `components/`: the screens. `lib/`: shared logic (`lib/data.ts`
  loads what every screen shares). `supabase/migrations/`: tables, permissions and the rules the database enforces.
  `tests/`: Vitest (some run against the local database). `e2e/`: Playwright, in a real browser.
- A rental is a customer plus `starts_at` / `due_at`; staff hand it boards (`rental_items`). A board has `quantity`
  identical copies, `in_repair` of them in repair. One Bloowatch booking is one rental (a family can take several boards).

## Local setup

1. Node 24 and Docker (Docker Desktop, or Colima on a Mac).
2. `npm install`
3. `npx supabase start` (a local Supabase in Docker), then `npx supabase status` for its address and keys.
4. `cp .env.example .env.local` and fill it in: the local address and keys from step 3, test logins (any values),
   random strings for `CRON_SECRET` and `BLOOWATCH_WEBHOOK_SECRET`, placeholders for the Google values.
5. `node scripts/seed-local.mts --activity`: the test logins, the club's 95 boards (no photos) and sample rentals.
6. `npm run dev`, open http://localhost:3000 and sign in with `LOCAL_TEST_OWNER` / `LOCAL_TEST_PASSWORD`.

Checks before handing work back: `npx tsc --noEmit`, `npm test`, `npm run e2e`, `npm run build`. All must pass.

## Current task: Bloowatch through its API (for the agent on the business computer)

Goal: every Bloowatch booking for board rentals shows up in the app on its own, as a rental waiting for a board
("Needs a board", with the customer's name, phone, start and end). It is updated when the booking changes and
goes away when the booking is cancelled.

Already in place:
- `lib/bloowatch.ts`: `Booking`, a neutral shape, and `parseBooking`, which validates it.
- `app/api/bloowatch/webhook/route.ts`: takes one booking (header `x-webhook-secret`) and creates or updates the
  rental matched on `rentals.bloowatch_booking_id` (`source = 'bloowatch'`). The customer comes from the
  `upsert_customer` database function (same phone digits, else same name). Works only while
  `app_settings.bloowatch_enabled` is true.
- Settings > Bloowatch (`components/SettingsView.tsx`): the on/off switch, owner only.
- The pattern to copy for a server-side pull is Google Sheets: `lib/google.ts` keeps its secret in
  `private_settings`; `app/api/sheets/sync/route.ts` is called by a database timer with `CRON_SECRET`;
  `syncAndRecord` in `lib/sheets.ts` stores `app_settings.sheets_status` = {at, error}, which the sidebar shows.

To build:
1. In `lib/bloowatch.ts`, a small client for the real Bloowatch API (endpoints from the docs you use; don't guess)
   that maps a Bloowatch booking to `Booking` (add what's missing, such as the number of boards and cancelled).
   Only board-rental bookings: ask the owner which Bloowatch products count.
2. Move the create/update code out of the webhook route into one shared function, used by both.
3. `app/api/bloowatch/sync/route.ts`, with the same guard as the sheets sync (`CRON_SECRET` or a signed-in member).
   It fetches recent bookings, creates or updates their rentals and stores `app_settings.bloowatch_status` =
   {at, error, count}. Running it twice must change nothing.
4. A cancelled booking: if no board was handed out yet, remove its rental; if boards are out, keep it and add a note.
   Ask the owner which future bookings should appear (for example only today's).
5. Settings > Bloowatch: an "API key" field (owner only) with Save. A server action stores the key in
   `private_settings` under `bloowatch`. It is never sent back to the browser: show only its last 4 characters.
   Add "Test connection" and the last sync status, and show sync errors in the sidebar like Google Sheets does.
6. Tests: a unit test of the mapping with a made-up booking (no real customer data). Existing tests keep passing.

Left to the main session: the database timer (every 5 minutes, calling `/api/bloowatch/sync`) and the deploy.

Changed since this task was written (already live; pull `main` first, then branch):
- Migrations run up to `20261031000000`; name new ones after it, or `supabase db push` refuses them.
- A third role, `instructor` (`components/InstructorView.tsx`): sees open rentals by customer name only.
- "Mark returned" only takes the boards back; a rental with time left stays open under "Needs a board". The timer
  `end-finished-rentals` (pg_cron, every minute) ends rentals whose time is up with no board out, and ending one
  early is the owner's "Finish rental" (a trigger refuses anyone else). Server code with the full-access key isn't
  affected, so a cancelled booking can still end its rental; don't reopen a rental the timer ended.
- The owner sees each rental's changes (`rental_changes`), so Bloowatch updates show there as "System".
When done, push the branch `bloowatch-api` and tell the owner it's ready. After the deploy, paste the API key into
Settings > Bloowatch on the live site in that computer's browser, with the owner signed in. Never write the key
anywhere else.
