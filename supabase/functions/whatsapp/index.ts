/* ===================== the school's WhatsApp, answered =====================

   One Edge Function, four doors:

     GET  /whatsapp/webhook   Meta's one-off "is this really you" handshake
     POST /whatsapp/webhook   every message and delivery report Meta sends us
     POST /whatsapp/send      the manager, sending a message somebody typed
     POST /whatsapp/tick      the clock: work out what is due, then send it
     GET  /whatsapp/health    what is configured and what is still missing

   Why a function at all, when the app talks to Postgres directly everywhere
   else: the Meta token can send messages to anyone in the world as the school.
   It cannot be in the page, it cannot be in the database, and every device
   that signs in can read both. So it is a secret on this function, and this
   function is the only thing that ever holds it. A browser can ask for a
   message to be sent; it can never send one itself.

   Nothing here trusts what it is given. /send checks the caller is signed in
   and belongs to the school. /webhook checks Meta's signature over the raw
   body. /tick checks a shared secret. All three then work from the database,
   not from the request.

   Deploy:  supabase functions deploy whatsapp --no-verify-jwt
   (--no-verify-jwt because Meta's webhook cannot carry a Supabase token; the
   checks above are done here, per door, rather than at the gate.)
*/

const GRAPH = Deno.env.get("WA_GRAPH_VERSION") || "v21.0";
const TOKEN = Deno.env.get("WA_TOKEN") || "";
const PHONE_ID = Deno.env.get("WA_PHONE_ID") || "";
const VERIFY = Deno.env.get("WA_VERIFY_TOKEN") || "";
const APP_SECRET = Deno.env.get("WA_APP_SECRET") || "";
const TICK_SECRET = Deno.env.get("WA_TICK_SECRET") || "";
const SCHOOL = Deno.env.get("WA_SCHOOL") || "shokogi";

const SB_URL = Deno.env.get("SUPABASE_URL") || "";
const SB_ANON = Deno.env.get("SUPABASE_ANON_KEY") || "";
const SB_SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const CORS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-wa-secret",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json" },
  });
}

/* ------------------------------ the database ------------------------------
   Plain PostgREST with the service key. No SDK: one dependency less to go
   stale, and the calls are three lines. The service key bypasses the row
   policies, which is exactly why nothing here ever takes a school name from
   the caller -- it is the one in the environment, always. */
async function db(path: string, opts: RequestInit & { prefer?: string } = {}) {
  const headers: Record<string, string> = {
    apikey: SB_SERVICE,
    Authorization: `Bearer ${SB_SERVICE}`,
    "Content-Type": "application/json",
  };
  if (opts.prefer) headers["Prefer"] = opts.prefer;
  const r = await fetch(`${SB_URL}/rest/v1/${path}`, { ...opts, headers });
  const text = await r.text();
  if (!r.ok) throw new Error(`db ${r.status}: ${text.slice(0, 300)}`);
  if (!text) return null;
  try { return JSON.parse(text); } catch { return null; }
}

async function rows(table: string, query: string): Promise<any[]> {
  const out = await db(`${table}?${query}`);
  return Array.isArray(out) ? out : [];
}

/* every record of one of the app's collections, unwrapped from its row */
async function collection(name: string): Promise<any[]> {
  const out: any[] = [];
  let from = 0;
  for (;;) {
    const page = await rows(
      name,
      `school=eq.${encodeURIComponent(SCHOOL)}&deleted=is.false` +
        `&select=data&order=id.asc&offset=${from}&limit=1000`,
    );
    page.forEach((r) => r.data && out.push(r.data));
    if (page.length < 1000) break;
    from += 1000;
  }
  return out;
}

const DEFAULTS = {
  tz: "America/Panama",
  bookingUrl: "",
  reminders: { on: false, hoursBefore: 18, template: "session_reminder", lang: "en", quietFrom: 21, quietTo: 7 },
  brief: { on: false, at: "07:00", days: [0, 1, 2, 3, 4, 5, 6], to: [] as any[], template: "daily_brief", lang: "en" },
  bot: { on: false, hours: "", greeting: "", handover: "", rules: [] as any[] },
};

async function config(): Promise<any> {
  const r = await rows("wa_config", `school=eq.${encodeURIComponent(SCHOOL)}&select=data&limit=1`);
  const got = (r[0] && r[0].data) || {};
  return {
    ...DEFAULTS, ...got,
    reminders: { ...DEFAULTS.reminders, ...(got.reminders || {}) },
    brief: { ...DEFAULTS.brief, ...(got.brief || {}) },
    bot: { ...DEFAULTS.bot, ...(got.bot || {}) },
  };
}

/* ------------------------------ numbers ------------------------------
   Everything is kept the way Meta keeps it: digits, no plus, no spaces. A
   number the school typed as "+507 6000 0000" and the same number arriving
   from a webhook have to be the same row, or a reply lands in a second
   conversation nobody is looking at. */
function waId(raw: string, countryCode = "507"): string {
  let d = String(raw || "").replace(/\D+/g, "");
  if (!d) return "";
  d = d.replace(/^00/, "");
  /* a local number, written the way a local writes it */
  if (d.length <= 8 && countryCode) d = countryCode + d;
  return d;
}

/* ------------------------------ clocks ------------------------------
   Sessions are written down in the school's own time -- "the nine o'clock" --
   and the server thinks in UTC. Panama does not move its clocks, but the code
   should not depend on that, so the offset is asked for rather than assumed. */
function tzOffset(at: Date, tz: string): number {
  const f = new Intl.DateTimeFormat("en-US", {
    timeZone: tz, hour12: false, year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const p: Record<string, number> = {};
  f.formatToParts(at).forEach((x) => { if (x.type !== "literal") p[x.type] = Number(x.value); });
  const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour % 24, p.minute, p.second);
  return asUtc - at.getTime();
}
function localToUtc(dateStr: string, timeStr: string, tz: string): Date {
  const [y, m, d] = String(dateStr).split("-").map(Number);
  const [hh, mm] = String(timeStr || "00:00").split(":").map(Number);
  const guess = Date.UTC(y, (m || 1) - 1, d || 1, hh || 0, mm || 0);
  return new Date(guess - tzOffset(new Date(guess), tz));
}
function localParts(at: Date, tz: string) {
  const f = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz, hour12: false, year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", weekday: "short",
  });
  const p: Record<string, string> = {};
  f.formatToParts(at).forEach((x) => { if (x.type !== "literal") p[x.type] = x.value; });
  const dow = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(p.weekday);
  return {
    date: `${p.year}-${p.month}-${p.day}`,
    hour: Number(p.hour) % 24,
    minute: Number(p.minute),
    dow: dow < 0 ? 0 : dow,
  };
}
function addDays(dateStr: string, n: number): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return t.toISOString().slice(0, 10);
}

/* --------------------------- talking to Meta ---------------------------
   Two shapes and no more. A free-form message, which WhatsApp allows only
   within 24 hours of the customer's own last message, and a template, which
   is the only thing that goes outside that window and has to have been
   approved by Meta beforehand.

   Template parameters cannot contain a newline or a tab -- Meta rejects the
   whole message rather than the character -- so anything going into one is
   flattened first. That is why the morning brief reads as one line of stops
   when it goes out as a template and as a proper list when it goes out inside
   the window. */
function flat(s: string): string {
  return String(s == null ? "" : s).replace(/[\r\n\t]+/g, " · ").replace(/\s{4,}/g, "   ").trim();
}

async function graph(body: unknown): Promise<{ ok: boolean; id?: string; error?: string }> {
  if (!TOKEN || !PHONE_ID) return { ok: false, error: "not connected: WA_TOKEN or WA_PHONE_ID is not set" };
  let r: Response;
  try {
    r = await fetch(`https://graph.facebook.com/${GRAPH}/${PHONE_ID}/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    return { ok: false, error: `could not reach Meta: ${(e as Error).message}` };
  }
  const text = await r.text();
  let j: any = null;
  try { j = JSON.parse(text); } catch { /* Meta answered with something else */ }
  if (!r.ok) {
    const m = j && j.error ? `${j.error.message}${j.error.error_data?.details ? " — " + j.error.error_data.details : ""}` : text.slice(0, 300);
    return { ok: false, error: `Meta refused it (${r.status}): ${m}` };
  }
  return { ok: true, id: j?.messages?.[0]?.id };
}

function textMessage(to: string, body: string) {
  return { messaging_product: "whatsapp", recipient_type: "individual", to,
           type: "text", text: { preview_url: true, body } };
}
function templateMessage(to: string, name: string, lang: string, params: string[]) {
  const t: any = { name, language: { code: lang || "en" } };
  if (params && params.length) {
    t.components = [{ type: "body", parameters: params.map((p) => ({ type: "text", text: flat(p) })) }];
  }
  return { messaging_product: "whatsapp", recipient_type: "individual", to, type: "template", template: t };
}

/* ---------------------------- the conversation ---------------------------- */
async function contact(id: string): Promise<any | null> {
  const r = await rows("wa_contacts",
    `school=eq.${encodeURIComponent(SCHOOL)}&wa_id=eq.${encodeURIComponent(id)}&limit=1`);
  return r[0] || null;
}
async function saveContact(patch: Record<string, unknown>) {
  await db("wa_contacts?on_conflict=school,wa_id", {
    method: "POST",
    prefer: "resolution=merge-duplicates,return=minimal",
    body: JSON.stringify([{ school: SCHOOL, ...patch }]),
  });
}
async function logMessage(m: Record<string, unknown>) {
  await db("wa_messages?on_conflict=id", {
    method: "POST",
    prefer: "resolution=merge-duplicates,return=minimal",
    body: JSON.stringify([{ school: SCHOOL, ...m }]),
  });
}
function windowOpen(c: any | null): boolean {
  if (!c || !c.last_in) return false;
  return Date.now() - Date.parse(c.last_in) < 24 * 3600 * 1000 - 60000;
}

/* One place decides how a message goes out, so every path obeys the same
   rules: never to somebody who opted out, free-form inside the window, the
   template outside it, and a plain sentence back when neither is possible. */
async function send(to: string, opts: {
  text?: string; template?: string; lang?: string; params?: string[]; force?: boolean;
}): Promise<{ ok: boolean; id?: string; error?: string; how?: string }> {
  const id = waId(to);
  if (!id) return { ok: false, error: "no number" };
  const c = await contact(id);
  if (c && c.opted_out && !opts.force) return { ok: false, error: "this number asked us to stop writing" };

  let body: unknown, how: string;
  if (opts.text && windowOpen(c)) {
    body = textMessage(id, opts.text); how = "text";
  } else if (opts.template) {
    body = templateMessage(id, opts.template, opts.lang || "en", opts.params || []); how = "template";
  } else if (opts.text) {
    return { ok: false, error:
      "outside the 24-hour window: WhatsApp only allows an approved template here, and none is set" };
  } else {
    return { ok: false, error: "nothing to send" };
  }

  const res = await graph(body);
  const now = new Date().toISOString();
  await logMessage({
    id: res.id || `local:${id}:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
    wa_id: id, direction: "out", kind: how,
    body: how === "text" ? opts.text : (opts.params || []).join(" · "),
    template: how === "template" ? opts.template : null,
    status: res.ok ? "sent" : "failed", error: res.error || null,
    created_at: now, updated_at: now,
  });
  if (res.ok) await saveContact({ wa_id: id, last_out: now });
  return { ...res, how };
}

/* ------------------------------- the bot -------------------------------
   Rules the school writes, then a short built-in fallback. It is deliberately
   not clever: it answers what it recognises and hands over what it does not,
   because a wrong answer sent in the school's name to a customer is worse
   than no answer at all. */
const STOP_WORDS = ["stop", "unsubscribe", "baja", "cancelar suscripcion", "הסר"];
const HUMAN_WORDS = ["human", "agent", "person", "persona", "humano", "נציג"];

function botReply(cfg: any, incoming: string): string | null {
  const t = String(incoming || "").toLowerCase().trim();
  if (!t) return null;
  for (const rule of cfg.bot.rules || []) {
    const words: string[] = rule.match || rule.words || [];
    if (words.some((w: string) => w && t.includes(String(w).toLowerCase()))) return rule.reply || null;
  }
  const has = (...w: string[]) => w.some((x) => t.includes(x));
  if (has("book", "reserve", "reserva", "booking")) {
    return (cfg.bookingUrl
      ? `You can book here: ${cfg.bookingUrl}`
      : "Tell us the day and how many of you there are and we will put you down.");
  }
  if (has("hour", "time", "horario", "hora", "open")) return cfg.bot.hours || null;
  return cfg.bot.greeting || null;
}

async function handleInbound(value: any, cfg: any) {
  const profile = value?.contacts?.[0]?.profile?.name || null;
  for (const m of value?.messages || []) {
    const from = waId(m.from);
    const body = m.text?.body || m.button?.text || m.interactive?.list_reply?.title ||
                 m.interactive?.button_reply?.title || "";
    const at = m.timestamp ? new Date(Number(m.timestamp) * 1000).toISOString() : new Date().toISOString();

    await logMessage({ id: m.id, wa_id: from, direction: "in", kind: m.type || "text",
                       body: body || `(${m.type})`, status: "received", raw: m, created_at: at, updated_at: at });

    const before = await contact(from);
    const patch: Record<string, unknown> = { wa_id: from, last_in: at,
      unread: ((before?.unread || 0) + 1), name: profile || before?.name || null };

    const low = body.toLowerCase().trim();
    if (STOP_WORDS.some((w) => low === w || low.startsWith(w + " "))) {
      patch.opted_out = true;
      await saveContact(patch);
      await send(from, { text: "You will not hear from us again. Send START to turn messages back on.", force: true });
      continue;
    }
    if (low === "start" && before?.opted_out) {
      patch.opted_out = false;
      await saveContact(patch);
      await send(from, { text: "You are back on. We will write when there is something to say." });
      continue;
    }
    if (HUMAN_WORDS.some((w) => low.includes(w))) {
      patch.needs_human = true;
      patch.bot_until = new Date(Date.now() + 12 * 3600 * 1000).toISOString();
      await saveContact(patch);
      if (cfg.bot.on && cfg.bot.handover) await send(from, { text: cfg.bot.handover });
      continue;
    }
    await saveContact(patch);

    /* the bot stands down for anyone waiting on a person */
    const paused = before?.bot_until && Date.parse(before.bot_until) > Date.now();
    if (!cfg.bot.on || paused || before?.opted_out) continue;
    const reply = botReply(cfg, body);
    if (reply) await send(from, { text: reply });
  }

  /* delivery reports: the same message, further along */
  for (const s of value?.statuses || []) {
    if (!s.id) continue;
    const patch: Record<string, unknown> = { status: s.status, updated_at: new Date().toISOString() };
    if (s.errors?.length) patch.error = s.errors[0].title || s.errors[0].message || null;
    try {
      await db(`wa_messages?id=eq.${encodeURIComponent(s.id)}`, {
        method: "PATCH", prefer: "return=minimal", body: JSON.stringify(patch),
      });
    } catch { /* a report for a message we never wrote down is not a problem */ }
  }
}

/* --------------------------- who a seat belongs to ---------------------------
   The board seats people by reference: "c:<client>" is a saved client,
   "p:<booking>:<person>" is somebody named on a booking who was never one.
   Both have to end at a phone number or there is nobody to remind. */
function seatPerson(ref: string, clients: any[], bookings: any[]): { name: string; phone: string } | null {
  if (typeof ref !== "string") return null;
  if (ref.startsWith("c:") || ref.indexOf(":") < 0) {
    const id = ref.startsWith("c:") ? ref.slice(2) : ref;
    const c = clients.find((x) => x.id === id);
    return c ? { name: c.name || "", phone: c.phone || "" } : null;
  }
  if (ref.startsWith("p:")) {
    const [, bid, pid] = ref.split(":");
    const bk = bookings.find((x) => x.id === bid);
    if (!bk) return null;
    const p = (bk.participants || []).find((x: any) => x.pid === pid);
    if (!p) return null;
    if (p.phone) return { name: p.name || "", phone: p.phone };
    const c = clients.find((x) => x.id === (p.clientId || bk.clientId));
    return { name: p.name || (c && c.name) || "", phone: (c && c.phone) || "" };
  }
  return null;
}

async function queue(job: Record<string, unknown>) {
  /* the unique dedupe is what makes the planner safe to run every five
     minutes: a job already queued is ignored, not queued again */
  await db("wa_jobs?on_conflict=school,dedupe", {
    method: "POST",
    prefer: "resolution=ignore-duplicates,return=minimal",
    body: JSON.stringify([{ school: SCHOOL, ...job }]),
  });
}

/* ------------------------------ the reminders ------------------------------ */
async function planReminders(cfg: any, now: Date): Promise<number> {
  const r = cfg.reminders;
  if (!r.on) return 0;
  const tz = cfg.tz;
  const today = localParts(now, tz).date;
  const horizon = addDays(today, 3);

  const [sessions, clients, bookings] = await Promise.all([
    collection("sessions"), collection("clients"), collection("bookings"),
  ]);
  let made = 0;

  for (const s of sessions) {
    if (!s || !s.date || s.date < today || s.date > horizon) continue;
    if (s.cancelled) continue;
    const start = localToUtc(s.date, s.time || "09:00", tz);
    if (start.getTime() <= now.getTime()) continue;

    let sendAt = new Date(start.getTime() - (Number(r.hoursBefore) || 18) * 3600 * 1000);
    if (sendAt.getTime() < now.getTime()) {
      /* worked out late -- send now, unless the session is nearly on top of
         them, in which case a reminder is no longer a reminder */
      if (start.getTime() - now.getTime() < 60 * 60 * 1000) continue;
      sendAt = now;
    }
    /* nobody wants the school at half past eleven at night */
    const at = localParts(sendAt, tz);
    const qf = Number(r.quietFrom), qt = Number(r.quietTo);
    if (!isNaN(qf) && !isNaN(qt) && (at.hour >= qf || at.hour < qt)) {
      const day = at.hour >= qf ? addDays(at.date, 1) : at.date;
      const moved = localToUtc(day, `${String(qt).padStart(2, "0")}:00`, tz);
      if (moved.getTime() < start.getTime()) sendAt = moved;
    }

    for (const ref of s.participants || []) {
      const who = seatPerson(ref, clients, bookings);
      if (!who || !who.phone) continue;
      const id = waId(who.phone);
      if (!id) continue;
      const when = `${s.date} at ${s.time || "09:00"}`;
      const title = s.title || s.category || "your session";
      await queue({
        dedupe: `rem:${s.id}:${id}`,
        wa_id: id, kind: "reminder", run_after: sendAt.toISOString(),
        payload: {
          template: r.template, lang: r.lang,
          params: [who.name || "there", title, when],
          text: `Hi ${who.name || "there"} — a reminder that ${title} is on ${when}.` +
                " See you on the water. — Shokogi",
          sessionId: s.id, date: s.date,
        },
      });
      made++;
    }
  }
  return made;
}

/* ------------------------------ the morning brief ------------------------------
   WhatsApp's own API cannot post into a group -- there is no group endpoint on
   the Cloud API at all -- so "the Shokogi group at seven" is the same message
   to each person on the list, sent individually. Which is arguably what you
   want anyway: an instructor who is not working today can be left off it. */
function briefText(sessions: any[], staff: any[], dateStr: string): string {
  const day = sessions
    .filter((s) => s && s.date === dateStr && !s.cancelled)
    .sort((a, b) => String(a.time || "").localeCompare(String(b.time || "")));
  if (!day.length) return `${dateStr} — nothing on the board today.`;
  const name = (id: string) => (staff.find((x) => x.id === id) || {}).name || "";
  const lines = day.map((s) => {
    const crew = (s.staffIds || []).map(name).filter(Boolean).join(", ");
    const seats = `${(s.participants || []).length}/${s.capacity || 0}`;
    return `${s.time || "--:--"} ${s.title || s.category || "Session"} · ${seats}` +
           (crew ? ` · ${crew}` : " · unassigned");
  });
  const pax = day.reduce((a, s) => a + (s.participants || []).length, 0);
  return `${dateStr} — ${day.length} session${day.length === 1 ? "" : "s"}, ${pax} on the water\n` +
         lines.join("\n");
}

async function planBrief(cfg: any, now: Date): Promise<number> {
  const b = cfg.brief;
  if (!b.on || !(b.to || []).length) return 0;
  const tz = cfg.tz;
  const here = localParts(now, tz);
  if (!(b.days || []).includes(here.dow)) return 0;

  const due = localToUtc(here.date, b.at || "07:00", tz);
  if (due.getTime() > now.getTime() + 6 * 3600 * 1000) return 0;   /* not yet today */
  if (now.getTime() - due.getTime() > 6 * 3600 * 1000) return 0;   /* long past: not worth waking anyone */

  const [sessions, staff] = await Promise.all([collection("sessions"), collection("staff")]);
  const text = briefText(sessions, staff, here.date);
  let made = 0;
  for (const raw of b.to || []) {
    const id = waId(typeof raw === "string" ? raw : (raw.phone || raw.wa_id || ""));
    if (!id) continue;
    await queue({
      dedupe: `brief:${here.date}:${id}`,
      wa_id: id, kind: "brief", run_after: due.toISOString(),
      payload: { template: b.template, lang: b.lang,
                 params: [here.date, text.split("\n").slice(1).join(" · ") || "nothing on the board"],
                 text },
    });
    made++;
  }
  return made;
}

/* ------------------------------ sending what is due ------------------------------ */
async function drain(limit = 40): Promise<{ sent: number; failed: number }> {
  const due = await rows("wa_jobs",
    `school=eq.${encodeURIComponent(SCHOOL)}&state=eq.queued` +
    `&run_after=lte.${encodeURIComponent(new Date().toISOString())}` +
    `&order=run_after.asc&limit=${limit}`);
  let sent = 0, failed = 0;
  for (const job of due) {
    const p = job.payload || {};
    const res = await send(job.wa_id, {
      text: p.text, template: p.template, lang: p.lang, params: p.params,
    });
    /* Not connected is a setup problem, not this message's problem: leave it
       where it is without spending an attempt, so the queue is still there
       when the token is finally set rather than three tries into failed. */
    const setup = !res.ok && /not connected/.test(res.error || "");
    const patch: Record<string, unknown> = {
      state: res.ok ? "sent" : (!setup && job.attempts >= 2 ? "failed" : "queued"),
      attempts: (job.attempts || 0) + (setup ? 0 : 1),
      error: res.error || null,
      run_after: res.ok ? job.run_after
        : new Date(Date.now() + 15 * 60 * 1000).toISOString(),
    };
    /* these two never get better by being tried again */
    if (!res.ok && /opted|window/.test(res.error || "")) patch.state = "skipped";
    await db(`wa_jobs?id=eq.${job.id}`, { method: "PATCH", prefer: "return=minimal",
                                          body: JSON.stringify(patch) });
    res.ok ? sent++ : failed++;
  }
  return { sent, failed };
}

/* ------------------------------ who is asking ------------------------------
   /send and /health are for the manager, and the manager is a page anyone can
   open. So: a real Supabase token, and a row in members putting that person in
   this school. Both, every time. */
async function caller(req: Request): Promise<{ ok: boolean; email?: string; why?: string }> {
  const auth = req.headers.get("Authorization") || "";
  const token = auth.replace(/^Bearer\s+/i, "");
  if (!token) return { ok: false, why: "not signed in" };
  const r = await fetch(`${SB_URL}/auth/v1/user`, {
    headers: { apikey: SB_ANON, Authorization: `Bearer ${token}` },
  });
  if (!r.ok) return { ok: false, why: "the sign-in was not accepted" };
  const user = await r.json();
  const member = await rows("members", `user_id=eq.${user.id}&select=school&limit=1`);
  if (!member.length || member[0].school !== SCHOOL) {
    return { ok: false, why: "this account is not a member of the school" };
  }
  return { ok: true, email: user.email };
}

/* Meta signs the raw body with the app secret. Verifying it is what stops
   anyone who finds the webhook address from being able to put words in a
   customer's mouth -- and from making the bot answer them. */
async function signed(raw: string, header: string | null): Promise<boolean> {
  if (!APP_SECRET) return true;          /* not set: the verify token is all there is */
  if (!header) return false;
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(APP_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw));
  const hex = Array.from(new Uint8Array(mac)).map((b) => b.toString(16).padStart(2, "0")).join("");
  const given = header.replace(/^sha256=/, "").trim().toLowerCase();
  if (given.length !== hex.length) return false;
  let diff = 0;
  for (let i = 0; i < hex.length; i++) diff |= hex.charCodeAt(i) ^ given.charCodeAt(i);
  return diff === 0;
}

/* ------------------------------ the doors ------------------------------ */
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const url = new URL(req.url);
  const door = url.pathname.replace(/^.*\/whatsapp\/?/, "").replace(/\/+$/, "") || "health";

  try {
    /* ---- Meta's handshake: it asks once, with the token we gave it ---- */
    if (door === "webhook" && req.method === "GET") {
      const mode = url.searchParams.get("hub.mode");
      const tok = url.searchParams.get("hub.verify_token");
      const challenge = url.searchParams.get("hub.challenge") || "";
      if (mode === "subscribe" && VERIFY && tok === VERIFY) {
        return new Response(challenge, { status: 200, headers: { "Content-Type": "text/plain" } });
      }
      return new Response("no", { status: 403 });
    }

    /* ---- everything Meta sends us ---- */
    if (door === "webhook" && req.method === "POST") {
      const raw = await req.text();
      if (!(await signed(raw, req.headers.get("x-hub-signature-256")))) {
        return new Response("bad signature", { status: 401 });
      }
      let body: any = {};
      try { body = JSON.parse(raw); } catch { /* answer 200 anyway: see below */ }
      const cfg = await config();
      for (const entry of body.entry || []) {
        for (const ch of entry.changes || []) {
          if (ch.field !== "messages") continue;
          try { await handleInbound(ch.value, cfg); }
          catch (e) { console.error("inbound", (e as Error).message); }
        }
      }
      /* Meta retries anything that is not a 200, for days. Whatever went wrong
         in here, it went wrong with a message we already have -- so say yes,
         and let the log carry the problem. */
      return new Response("ok", { status: 200 });
    }

    /* ---- the manager, sending something a person typed ---- */
    if (door === "send" && req.method === "POST") {
      const who = await caller(req);
      if (!who.ok) return json({ error: who.why }, 401);
      const b = await req.json().catch(() => ({}));
      if (!b.to) return json({ error: "no number to send to" }, 400);
      const res = await send(String(b.to), {
        text: b.text ? String(b.text) : undefined,
        template: b.template ? String(b.template) : undefined,
        lang: b.lang, params: b.params,
      });
      if (res.ok) {
        await saveContact({ wa_id: waId(String(b.to)), unread: 0 });
        return json({ ok: true, id: res.id, how: res.how });
      }
      return json({ ok: false, error: res.error }, 200);
    }

    /* ---- the clock ---- */
    if (door === "tick") {
      const given = req.headers.get("x-wa-secret") || url.searchParams.get("secret") || "";
      const bySecret = !!TICK_SECRET && given === TICK_SECRET;
      const byUser = bySecret ? { ok: true } : await caller(req);
      if (!bySecret && !byUser.ok) return json({ error: "not allowed" }, 401);
      const cfg = await config();
      const now = new Date();
      const reminders = await planReminders(cfg, now);
      const brief = await planBrief(cfg, now);
      const out = await drain();
      return json({ ok: true, queued: { reminders, brief }, ...out });
    }

    /* ---- what is set up and what is not ---- */
    if (door === "health") {
      const who = await caller(req);
      if (!who.ok) return json({ error: who.why }, 401);
      const cfg = await config();
      const state: any = {
        connected: !!(TOKEN && PHONE_ID),
        token: !!TOKEN, phoneId: !!PHONE_ID, verifyToken: !!VERIFY,
        appSecret: !!APP_SECRET, tickSecret: !!TICK_SECRET,
        graph: GRAPH, school: SCHOOL, config: cfg,
      };
      if (TOKEN && PHONE_ID) {
        try {
          const r = await fetch(
            `https://graph.facebook.com/${GRAPH}/${PHONE_ID}?fields=display_phone_number,verified_name,quality_rating`,
            { headers: { Authorization: `Bearer ${TOKEN}` } });
          const j = await r.json();
          if (r.ok) state.number = j;
          else state.numberError = j?.error?.message || `HTTP ${r.status}`;
        } catch (e) { state.numberError = (e as Error).message; }
      }
      const pending = await rows("wa_jobs",
        `school=eq.${encodeURIComponent(SCHOOL)}&state=eq.queued&select=id&limit=200`);
      state.queued = pending.length;
      return json(state);
    }

    return json({ error: `no such door: ${door}` }, 404);
  } catch (e) {
    console.error(door, (e as Error).message);
    return json({ error: (e as Error).message }, 500);
  }
});
