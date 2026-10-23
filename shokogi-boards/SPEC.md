# Shokogi Boards: build specification

Production version of the board-rental tool for **Shokogi surf club, Playa Venao, Panama**.
A working prototype already exists in `prototype/`. It is the reference for every screen, behaviour
and visual detail described here. This spec turns it into real, multi-user, cloud-hosted software.

---

## 0. Read this first (instructions for Claude Code)

1. Read this whole file, then open `prototype/index.html` and `prototype/server.js`. Run the prototype
   (`cd prototype && node server.js`, then open http://127.0.0.1:5050) with the data in `migration/`
   copied next to it, and click through every page before writing code. Where this spec is silent,
   copy the prototype's behaviour and look.
2. The owner is **not a developer**. Talk to him in **Hebrew**, short and plain. When he must do
   something (create an account, paste a key, click Allow), give numbered click-by-click steps.
   The **app UI stays in English**.
3. Ask before anything that needs his accounts, passwords, payments, DNS, or sharing data.
   Never put secrets in the repo or in client code.
4. Build in the phases of section 10. Finish each phase with its checks passing (tests + the app
   running in a browser) and a 3-line Hebrew summary to the owner before starting the next.
5. Prefer boring, well-known tools. No feature beyond this spec without asking.

---

## 1. Product in one paragraph

Customers book board rentals in **Bloowatch** (the club's booking system). Staff at the desk (and on
the beach with phones) use this app to see who is renting, hand each customer a specific board,
swap or return boards, and see which boards are out, overdue, available or in repair. The owner also
gets customer and board history, Excel export and a live Google Sheets mirror. Bloowatch has no API
access yet; when it does, rentals should arrive automatically (section 7.12).

---

## 2. Decisions already made

| Topic | Decision |
|---|---|
| Kind of software | Cloud web app, installable on phones/tablets as a PWA |
| Users | Owner (admin) + staff, each with their own login |
| Framework | Next.js (App Router) + TypeScript, deployed on **Vercel** |
| Database, auth, files | **Supabase**: Postgres, Auth (email + password), Storage, Realtime |
| Styling | Tailwind CSS with the design tokens in section 8 (or CSS modules; match the prototype exactly) |
| Time zone | **America/Panama** for every displayed time and every "today" boundary |
| UI language | English. Chat with the owner: Hebrew |
| Date format | `19 Oct, 17:30` in lists, `19 Oct 2026, 17:30` in date fields |

---

## 3. Users and permissions

| Action | Owner | Staff | Instructor |
|---|---|---|---|
| Dashboard, Rentals, Customers, Boards, History (view) | yes | yes | no |
| Assign / swap / remove board, mark returned | yes | yes | yes |
| Create rental, extend or change the return time | yes | yes | no |
| Edit customer name, phone, notes | yes | yes | no |
| Send board to repair / back in service, replace board photo, edit board notes | yes | yes | no |
| Add boards, import photo folder, rename / change type of a board | yes | yes | no |
| Delete board | yes | no | no |
| Settings (rental lengths, board types), staff accounts, Google Sheets, Bloowatch | yes | no | no |
| Export to Excel | yes | no | no |

- No public sign-up. The owner creates staff accounts in **Settings > Staff** (name, email,
  role, temporary password; staff change it on first login). Deactivating a user blocks login
  but keeps their history.
- **Instructors** see one screen, built for phones and tablets: every open rental (customers waiting for a board
  first), customer by name only (no phone). Three buttons only: "Choose board" (customers without a board; one board per rental, a further board is added at the desk), "Swap" on each board, "Mark returned".
- Enforce permissions in the database with **Row Level Security**, not only in the UI.
- Every change is written to an **audit log** (who, what, when, before/after). Show the actor's
  name on rental history rows ("Returned by Dana").

---

## 4. Data model (Postgres)

```
profiles        id (= auth.users.id) · name · role ('owner'|'staff'|'instructor') · active · created_at
board_types     id · name (unique, case-insensitive) · sort_order · is_system (true only for "Other")
boards          id · name · type_id → board_types · notes · in_repair (bool)
                · photo_path · thumb_path · source_file_name (for re-import matching)
                · created_at · deleted_at (soft delete, so history keeps working)
customers       id · name · phone · phone_digits (digits only; unique when not empty)
                · email · notes · created_at
rental_lengths  id · label · minutes (> 0) · sort by minutes · at least one must exist
rentals         id · customer_id · starts_at · due_at · ended_at (null = active)
                · source ('manual'|'bloowatch') · bloowatch_booking_id (unique, nullable)
                · notes · created_by · ended_by · created_at
rental_items    id · rental_id · board_id · assigned_at · unassigned_at (null = current)
                · assigned_by · unassigned_by
audit_log       id · actor_id · action · entity · entity_id · details (jsonb) · at
app_settings    key · value (jsonb)   e.g. google_sheet_id, sheets_enabled, bloowatch_enabled
```

Rules:
- A board is **rented** when it has a current `rental_item` on an active rental. Enforce "one
  current item per board" with a partial unique index, so two devices can't hand out the same
  board. If it happens, show "This board was just taken by someone else" and refresh the picker.
- **Overdue** = active rental with `due_at < now()`.
- A rental may hold **several boards** (families and groups). The UI flows below show one board
  per rental like the prototype, plus "Add another board" (see open question 1).
- Swapping a board = close the current item (`unassigned_at`) and open a new one, so the full
  swap trail is kept and each board's history shows every customer who used it.
- Returning = set `ended_at`, close all current items.
- Customers: when creating a rental, match an existing customer by `phone_digits`
  (so "050-123-4567" = "0501234567"), otherwise by exact name (case-insensitive) when no phone;
  otherwise create a new customer. Offer autocomplete while typing name or phone.
- "Other" board type always exists, can't be renamed or deleted. Deleting a type moves its boards
  to Other (confirm first). Renaming a type is just a rename (boards reference the id).
- Default board types: Softboard, Longboard, Midlength, Funboard, Shortboard (+ Other).
- Default rental lengths: 1 hour, 2 hours, 3 hours, Half day (4 hours), 1 day, 2 days, 3 days, 1 week.

---

## 5. Photos

- Upload from the browser. **iPhone HEIC must work** in every browser: decode with `heic-to`
  (`heicTo({ blob, type: 'bitmap' })`, see `shrink()` in the prototype) when the file name or type is
  HEIC/HEIF, otherwise `createImageBitmap`. Call `bitmap.close()` after drawing, or a 95-photo
  import runs out of memory.
- Store two JPEGs per board in a Supabase Storage bucket: **large** (max 1600 px, quality 0.85)
  and **thumb** (max 400 px). Use the thumb in grids and tables, the large one in Board details.
- The board-photo bucket may be public-read (surfboard photos only; needed for `=IMAGE()` in
  Google Sheets). Everything else stays private.
- Cache-bust when a photo is replaced.

---

## 6. Board import from a photo folder

The owner photographed every board; each file name is the board name. Real examples are in
`migration/` (from `~/Downloads/Archive`, 95 HEIC files). Rules, all covered by unit tests:

- Folder picker (`<input type=file webkitdirectory>`); keep image files and HEIC/HEIF (Windows gives
  HEIC an empty MIME type). Skip `.DS_Store` and other non-images.
- Board name = file name without extension, trailing spaces and dots removed, inner spaces collapsed.
  `"FUNBOARD 6'10 SWOLLOW TORQ  .HEIC"` → `FUNBOARD 6'10 SWOLLOW TORQ`.
- The owner made duplicate models unique with trailing spaces/dots; those are different physical
  boards: name them `NAME`, `NAME #2`, `NAME #3`, `NAME #4`.
- Re-importing a file with the same original file name updates that board's photo (match on
  `source_file_name`), it does not create a duplicate.
- Type detection, first match wins:
  1. The file name's **first word** (split on space, `_`, `-`; at least 3 letters) against each
     type's first word: `FUNBOARD-SHORT 6'4 TORQ` → Funboard, `SHORTBOARD-FISH 5'4` → Shortboard,
     `MIDLENGTH 7'6 TORQ HYBRID-SOFT` → Midlength, `SUP 10'6` → SUP (custom type),
     a type renamed to `Fun / Mini-Mal` still matches `FUNBOARD`.
  2. Keywords anywhere in the name, then in the folder path: soft|foam → Softboard, long → Longboard,
     mid → Midlength, fun|mini|malibu → Funboard, short|fish → Shortboard (only if that type exists).
  3. Otherwise **Other**.
- Show progress ("Importing 12 of 95") and, at the end, "Done: X new boards, Y updated" plus the
  names of files that could not be read.
- Real import of the 95 photos took ~2 s per photo in Chrome; keep it sequential or limit to 3 at a time.

---

## 7. Screens and features

Layout: dark left sidebar (logo square "S", "Shokogi / Board rentals"), nav: **Dashboard, Rentals,
Customers, Boards, History, Settings** (Settings owner-only). Red counter next to Rentals = overdue
count. Bottom of sidebar: Google Sheets status ("Synced 14:32" / "Not connected") and
"Export to Excel" (owner). On phones the sidebar becomes a top bar with horizontally scrolling nav.

### 7.1 Dashboard
- Title + today's date. Primary button "New rental".
- Overdue banner (red left border): "2 overdue", names and boards, button "View rentals".
- Metrics strip: Rented now · Available · Overdue (red when > 0) · Waiting for a board · In repair ·
  Rentals today.
- "Currently rented": cards sorted by due time (overdue first). Card: board photo (click → Board
  details), customer name (click → Rental window), board name, status countdown, "Back 19 Oct, 17:30",
  buttons "Swap board" and "Mark returned".
- "Fleet by type": rented / in service per type, thin bars.
- "Most rented boards": top 5 in the last 30 days with thumbnail and count.

### 7.2 Rentals
- New rental form: Customer name (autocomplete existing customers), Phone (optional), Rental length
  (from Settings). "Add and choose board" creates the rental and immediately opens the Board picker.
- Table: Customer (click → Rental window; phone under it) · Board (thumb → Board details, name,
  "Change · Remove") or "Choose board" · Start · Back by (date-time field) · Status · "Mark returned".
  Customers still without a board first (amber left marker), then by due time. Search by customer,
  phone or board.
- "Mark returned" (shown only with boards out) takes the boards back. With time left the rental stays under "Needs a
  board" until its due time (the customer may take another board, e.g. one a day on a 3-day rental); once the time is
  up it ends. A database timer ends rentals whose time is up with no board out, as returned when their boards came
  back. Ending a rental early is "Finish rental", owner only (rentals table and Rental window); the database refuses
  anyone else (owner's request, migrations 20261029000000 and 20261031000000).
- Countdowns update every 30 s without re-rendering inputs: "1h 15m left", "Overdue 20m" (red),
  "Needs a board" (amber).

### 7.3 Board picker (modal)
Available, in-service boards only, grouped by type, photo grid, search where every word must match
(`torq 7'6` finds `MIDLENGTH 7'6 TORQ`). Title "Choose a board for X" or "Swap board for X".
Clicking a board assigns it and closes the picker.

### 7.4 Rental window (active rental)
Board photo (click → Board details) · name + "Edit" · phone (tel: link) · Board / Start / Back by /
Status · buttons Swap board, Remove board, Mark returned · (owner) "Changes": who did what and when on this rental
(created, handed out, swapped, took back, return time, returned; one line per action) · "Earlier rentals" list + "Full profile"
link. Edit mode: name, phone, back by (date-time picker) with Save / Cancel; background refreshes
must not wipe a form being edited.

### 7.5 Customers
- Metrics: Customers · Returning customers (more than 1 rental) · Renting now. Search name/phone.
- Table: Customer + phone · Rentals · Hours · Late returns · Last visit · Status. Renting now first,
  then most recent visit. Row click → Profile.
- Profile modal: name, phone, email, notes (editable); metrics Rentals · Hours on the water ·
  Late returns · Favorite type · First visit · Last visit; "Renting now" block with "Open rental";
  rental history table (start, board thumb + name → Board details, duration, On time / Late Xm).

### 7.6 Boards
- "Import photo folder" (section 6) and collapsible "Add a single board" (type, name, photo).
- Search + segmented filter: All · Available · Rented · In repair (with counts). Grouped by type.
- Card: photo (click → Board details), name, status (Available / Rented, customer / In repair),
  "Rented N times", type dropdown, Repair or "Back in service", Delete (owner, not when rented).

### 7.7 Board details (modal)
Large photo; name + "Edit"; notes; metrics Type · Status · Rented by (link to Rental window) ·
Times rented · Hours rented · Last rented; buttons Replace photo, Send to repair / Back in service,
Delete board; edit mode (name, type, notes, photo); rental history table (start, customer, duration,
on time / late), including boards swapped out mid-rental.

### 7.8 History
Search; From / To date fields (custom calendar, date-only, Today / Clear); metrics Rentals ·
Hours on the water · Average rental · Returned late; table Customer · Board (link) · Start ·
Returned · Duration · Return status · Returned by · (owner) "Changes", which opens that rental's change trail.

### 7.9 Settings (owner)
- **Rental lengths**: inline-editable rows (label, amount, unit days/hours/minutes; 150 min shows as
  2.5 hours, 90 as 1.5 hours, 1440 as 1 day), add, remove (keep at least one), sorted by duration,
  changes save on blur.
- **Board types**: rename inline (reject empty, duplicate case-insensitive, "Other"), add, remove
  (confirm "7 boards of type Longboard will move to Other"), board count per type, "Other" row fixed.
- **Staff**: list, invite, change role, deactivate.
- **Google Sheets** (7.11) and **Bloowatch** (7.12) connection panels.

### 7.10 Export to Excel (owner)
One `.xlsx` (SheetJS) named `Shokogi-boards-YYYY-MM-DD.xlsx` with sheets **Rented now**, **History**
(respects History filters), **Boards**. Dates as real Excel dates: write the serial number yourself,
`(ms - tzOffsetMs) / 86400000 + 25569`, format `dd/mm/yyyy hh:mm`; SheetJS's own Date handling is
36 seconds off. Column widths fitted to content.

### 7.11 Google Sheets mirror (one-way: app → sheet)
- Spreadsheet already exists and is formatted: **"Shokogi Boards"**,
  ID `<SHEET_ID>` (the real id is not written down here: this repository is public, and a
  link-shared sheet would be findable by anyone who read it — keep it in the environment),
  tabs **Dashboard** (formulas, don't overwrite),
  **Rented now**, **History**, **Boards**, time zone America/Panama. Keep its columns, colors and
  conditional formats (see the prototype's `google-sheets-sync.gs` for the exact columns).
- Replace the prototype's Apps Script with a **server-side** sync using a Google service account
  (Sheets API). Owner shares the sheet with the service account email (give him the steps).
- Write rows under the headers, clear old rows, keep phone numbers as text (leading zero).
  Boards tab column A: `=IMAGE("<public thumb url>")`.
- Trigger: debounced ~5 s after any change, plus a Vercel Cron every 10 minutes (keeps "Overdue"
  current). Show last sync time / error in the sidebar.

### 7.12 Bloowatch integration (prepare, don't guess)
No API access yet. Build a small adapter interface and a protected webhook endpoint
`POST /api/bloowatch/webhook` (shared secret) that would create/update a rental from a booking
(`source = 'bloowatch'`, `bloowatch_booking_id`, customer upsert by phone, starts/due from the
booking). Keep it behind the `bloowatch_enabled` setting, off by default. Do not invent Bloowatch
endpoints; when the owner gets their docs, implement against them.

### 7.13 Live updates across devices
Use Supabase Realtime so the desk computer and phones see changes within seconds. No "refresh to see".

### 7.14 Overdue alert (explicit owner request)
- A modal **"N rentals overdue"** (red top border) pops up **every time the app is opened** while at
  least one rental is overdue, and again **whenever another rental becomes overdue** while the app is
  open (checked every 30 s and on Realtime updates).
- One row per overdue rental: board thumb (→ Board details), customer name (→ Rental window) and
  phone, board name, "Overdue 1h 20m · was due 19 Oct, 17:30", buttons **+30 min**, **+1 hour**
  (new due time = now + that), **Mark returned** (with confirm).
- "Remind me later" / X closes it for the current visit only. It stops appearing only when each
  overdue rental is returned or extended to a future time. It never interrupts another open dialog;
  it waits until that one closes.
- Browser tab title shows the count: `(2) Overdue · Shokogi Boards`; the sidebar Rentals counter and
  dashboard banner stay as in 7.1.
- Same behavior on phones (PWA). Push notifications to phones are a later idea (section 13).

---

## 8. Design system (match `prototype/index.html`)

The owner explicitly wants it to look professional and **not AI-made**:
- **No rounded corners anywhere** (radius 0). **No emoji** anywhere. No gradients, no decorative
  shadows (only dialogs, calendar and toasts get a shadow). Hairline borders.
- Font **IBM Plex Sans** (400/500/600), tabular numbers. Small uppercase labels with letter spacing.
- Colors: accent `#1a56db` (hover `#1e429f`), ink `#111827`, text `#1f2937`, muted `#6b7280`,
  faint `#9ca3af`, line `#e5e7eb`, strong line `#d1d5db`, page `#f4f5f7`, panels white,
  sidebar `#0b1220`, green `#047857`, red `#b91c1c`, amber `#b45309`.
- Status = 7 px square marker + text in the status color (not tinted pills).
- Line icons (24 px viewBox, stroke 1.75, square caps, miter joins), copy them from the prototype.
- **Custom date-time picker** (no native browser picker): Monday-first month grid, today underlined,
  selected day filled accent, prev/next month, hour select + minute select in 5-min steps that also
  keeps an exact minute (e.g. 48), Apply / Cancel. Date-only variant with Today / Clear. Opens below
  the field (above when there's no room), stays on screen, works inside dialogs, closes on outside
  click and Esc.
- **Custom confirm dialogs and toasts** instead of `alert / confirm / prompt` (the in-app browser in
  the prototype blocked `prompt()`). Destructive confirms focus Cancel so Enter doesn't delete.
  Resolve confirm promises from the button clicks, not from the dialog `close` event (it can arrive
  late in background tabs; we hit this bug).
- Dialogs can stack (Rental window → Board details → Customer profile) and Esc closes the top one.
- Responsive down to 360 px wide with no horizontal page scroll; wide tables scroll inside their panel.
  Big enough tap targets for phones on the beach.

---

## 9. Quality, security, operations

- **Tests** (Vitest): type detection with the real file names in `migration/file-names.txt`;
  `#2/#3` naming; customer matching by phone digits; time-left / overdue formatting; rental length
  unit display; Excel date serials; "one current item per board" constraint. **Playwright** smoke
  test: log in, create rental, pick board, swap, extend, return, see it in History and Customers;
  an overdue rental makes the alert pop on load, "+1 hour" clears it, reload with another overdue
  rental pops it again.
- RLS on every table; service-role key server-side only; secrets in Vercel env vars.
- Panama time everywhere (server and client). "Rentals today" uses Panama midnight.
- Backups: nightly job exporting a JSON snapshot of all tables to a private Storage bucket,
  keep 30 days. The Google Sheet is a second, human-readable copy.
- Error handling: every failed save shows a toast and leaves the UI consistent; never lose data
  silently.
- Scale target: 300 boards, 50 rentals a day, several years of history, fast on a phone.

---

## 10. Build phases (each ends with checks + a Hebrew summary to the owner)

1. **Foundation**: Next.js + Supabase project, schema + RLS + seed (default types and lengths),
   owner login, layout/sidebar/design tokens, deploy a preview to Vercel.
   *Check*: owner logs in on the deployed URL from his phone.
2. **Boards**: photo upload (HEIC), folder import, cards, filters, Board details, edit, repair, delete.
   *Check*: the type detection tests pass for all 95 names in `migration/file-names.txt`
   (Funboard 20 · Longboard 7 · Midlength 19 · Shortboard 49), and importing a few real HEIC photos
   from the owner's `~/Downloads/Archive` works in Chrome and Safari.
3. **Rentals + Customers**: new rental with autocomplete, picker, swap/remove/return/extend,
   date-time picker, Rental window, Customers page + Profile, countdowns, overdue alert (7.14), Realtime.
4. **Dashboard + History**, Excel export.
5. **Settings + Staff + audit log**.
6. **Migration** of the real data (section 11) and **Google Sheets** server-side sync.
7. **PWA** (manifest, icons, add to home screen), final responsive pass, Bloowatch stub,
   owner walkthrough in Hebrew (how to log in, add staff, daily use).

---

## 11. Migrating the prototype data

`migration/data.json` is a snapshot of the prototype's live data (19 Oct 2026) and
`migration/photos/<boardId>.jpg` are its photos (max 800 px). Before the final import, ask the owner
for a fresh `data.json` + `photos/` from the prototype folder, since he keeps using it.

Prototype format:
```
boards:   [{ id, name, cat, file, photo (cache-bust number), repair?, notes? }]
renters:  [{ id, name, phone, boardId|null, since (ms), until (ms) }]          // active rentals
history:  [{ id, name, phone, boardId, board (name), cat, since, until, ended }] // returned rentals
settings: { cats: [type names], lengths: [{ label, mins }] }
```
Write an idempotent script (`scripts/import-prototype.ts`) that creates types and lengths, boards
(upload large + thumb from the photo; keep `file` as `source_file_name`), customers (dedupe by phone
digits, else name), active rentals with their item, and past rentals with `ended_at`. Report counts.
The original full-resolution HEIC photos are in the owner's `~/Downloads/Archive`; offer to
re-import them through the folder import for sharper large photos.

---

## 12. Open questions (ask the owner when you reach them)

1. When a family rents several boards, is that one booking in Bloowatch or several? (Data model
   supports both; decide the UI.)
2. Bloowatch API access: does he have docs / a key yet?
3. Staff names and emails for their accounts.
4. Custom domain (e.g. boards.shokogi.com) or the default vercel.app address?

## 13. Discussed ideas, not in v1 (ask before building any)

Push notifications to staff phones for overdue rentals · WhatsApp reminder button for overdue customers · deposit field (passport / cash / card left) ·
damage report on return (photo + note, board goes to repair) · QR sticker per board for scan-to-rent ·
prices, daily revenue and revenue per board · maintenance reminders · daily summary to the owner ·
other equipment (wetsuits, leashes, SUP) · Spanish UI for local staff.
