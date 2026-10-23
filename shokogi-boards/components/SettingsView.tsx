"use client";

// Settings (SPEC 7.9, owner only): rental lengths, board types, staff accounts and the change log.
// Rows save when a field is left (blur), like the prototype.
import { useCallback, useEffect, useState } from "react";
import { setActive, setRole, createStaff, resetPassword } from "@/app/(app)/settings/actions";
import type { Role } from "@/lib/auth";
import { errorText } from "@/lib/data";
import { lengthUnit, toMinutes, UNITS } from "@/lib/lengths";
import { createClient } from "@/lib/supabase/client";
import { plural, when } from "@/lib/time";
import { useApp } from "./app";
import { Icon } from "./icons";

type Person = { id: string; name: string; login: string; role: Role; active: boolean };
type Change = { id: number; at: string; actor_id: string | null; action: string; entity: string; entity_id: string; details: { before?: Record<string, unknown> | null; after?: Record<string, unknown> | null } };

// Settings changes show in Google Sheets too (type names), so each save also asks for a sync.
function useSyncedApp() {
  const app = useApp();
  return { ...app, refresh: () => { app.scheduleSync(); return app.refresh(); } };
}

// ---------- Rental lengths ----------

function Lengths() {
  const db = createClient();
  const { fleet, refresh, toast } = useSyncedApp();
  if (!fleet) return null;

  async function save(row: HTMLElement, id: string, old: { label: string; minutes: number }) {
    const get = (f: string) => (row.querySelector(`[data-field=${f}]`) as HTMLInputElement).value;
    const minutes = toMinutes(+get("amount"), +get("unit"));
    const label = get("label").trim() || old.label;
    if (!(minutes > 0)) { toast("A rental length needs an amount above zero.", "error"); return refresh(); }
    if (label === old.label && minutes === old.minutes) return;
    const { error } = await db.from("rental_lengths").update({ label, minutes }).eq("id", id);
    if (error) toast("Couldn't save the rental length.", "error");
    await refresh();
  }
  async function remove(id: string) {
    const { error } = await db.from("rental_lengths").delete().eq("id", id);
    if (error) toast(errorText(error, "Couldn't remove the rental length."), "error");
    await refresh();
  }
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget, f = new FormData(form);
    const label = String(f.get("label")).trim(), minutes = toMinutes(+String(f.get("amount")), +String(f.get("unit")));
    if (!label || !(minutes > 0)) return;
    const { error } = await db.from("rental_lengths").insert({ label, minutes });
    if (error) toast("Couldn't add the rental length.", "error");
    else form.reset();
    await refresh();
  }

  return (
    <div className="panel">
      <div className="panel-h"><h3>Rental lengths</h3><span className="muted">Offered when adding a rental</span></div>
      <div className="panel-b">
        {fleet.lengths.map((l) => {
          const unit = lengthUnit(l.minutes);
          return ( // keyed by the saved values, so a save (or a change on another device) shows the stored row
            <div className="set-row" key={`${l.id}-${l.label}-${l.minutes}`} onBlur={(e) => {
              const row = e.currentTarget;
              if (!row.contains(e.relatedTarget as Node)) save(row, l.id, l); // left the whole row
            }}>
              <input data-field="label" defaultValue={l.label} aria-label="Label" />
              <input data-field="amount" type="number" min="0" step="any" defaultValue={l.minutes / unit} aria-label="Amount" />
              <select data-field="unit" defaultValue={unit} aria-label="Unit">{UNITS.map(([u, name]) => <option key={u} value={u}>{name}</option>)}</select>
              <button className="icon-btn" title="Remove" onClick={() => remove(l.id)}><Icon name="x" /></button>
            </div>
          );
        })}
        <form className="form set-add" onSubmit={add}>
          <input name="label" placeholder="New length, e.g. Sunset session" required />
          <input name="amount" type="number" min="0" step="any" defaultValue="1" required aria-label="Amount" />
          <select name="unit" defaultValue="60" aria-label="Unit">{UNITS.map(([u, name]) => <option key={u} value={u}>{name}</option>)}</select>
          <button className="btn primary">Add</button>
        </form>
      </div>
    </div>
  );
}

// ---------- Board types ----------

function Types() {
  const db = createClient();
  const { fleet, refresh, toast, ask } = useSyncedApp();
  if (!fleet) return null;
  const types = fleet.types.filter((t) => !t.is_system);
  const other = fleet.types.find((t) => t.is_system)!;
  const count = (id: string) => fleet.boards.filter((b) => b.type_id === id).length;
  const problem = (name: string, except?: string) =>
    !name ? "A type needs a name." : name.toLowerCase() === "other" ? `"Other" is built in.`
      : fleet.types.some((t) => t.id !== except && t.name.toLowerCase() === name.toLowerCase()) ? `There is already a type called ${name}.` : null;

  async function rename(input: HTMLInputElement, id: string, old: string) {
    const name = input.value.trim();
    if (name === old) return;
    const p = problem(name, id);
    if (p) { toast(p, "error"); input.value = old; return; }
    const { error } = await db.from("board_types").update({ name }).eq("id", id);
    if (error) { toast("Couldn't rename the type.", "error"); input.value = old; }
    await refresh();
  }
  async function remove(id: string, name: string) {
    const n = count(id);
    if (n && !(await ask({ title: "Remove board type", text: `${plural(n, "board")} of type ${name} will move to Other.`, ok: "Remove type", danger: true }))) return;
    const { error } = await db.from("board_types").delete().eq("id", id);
    if (error) toast("Couldn't remove the type.", "error");
    await refresh();
  }
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget, name = String(new FormData(form).get("name")).trim();
    const p = problem(name);
    if (p) return toast(p, "error");
    const sort_order = Math.max(0, ...types.map((t) => t.sort_order)) + 1; // new types go last, before Other
    const { error } = await db.from("board_types").insert({ name, sort_order });
    if (error) toast("Couldn't add the type.", "error");
    else form.reset();
    await refresh();
  }

  return (
    <div className="panel">
      <div className="panel-h"><h3>Board types</h3><span className="muted">Group, filter and import boards</span></div>
      <div className="panel-b">
        {types.map((t) => (
          <div className="set-row" key={`${t.id}-${t.name}`}>
            <input defaultValue={t.name} aria-label="Type name" onBlur={(e) => rename(e.currentTarget, t.id, t.name)}
              onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
            <span className="muted">{plural(count(t.id), "board")}</span>
            <button className="icon-btn" title="Remove type" onClick={() => remove(t.id, t.name)}><Icon name="x" /></button>
          </div>
        ))}
        <div className="set-row fixed">
          <span>Other <span className="muted" style={{ display: "inline" }}>(always there, for boards without a type)</span></span>
          <span className="muted">{plural(count(other.id), "board")}</span><span style={{ width: 32 }} />
        </div>
        <form className="form set-add" onSubmit={add}>
          <input name="name" placeholder="New type, e.g. SUP" required />
          <button className="btn primary">Add type</button>
        </form>
      </div>
    </div>
  );
}

// ---------- Staff ----------

function Staff({ people, reload }: { people: Person[]; reload: () => void }) {
  const { me, toast, ask } = useApp();
  const [resetting, setResetting] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: Promise<{ error?: string }>, done?: string) {
    setBusy(true);
    const { error } = await action;
    setBusy(false);
    if (error) toast(error, "error");
    else if (done) toast(done);
    reload();
    return !error;
  }
  async function add(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget, f = new FormData(form);
    const name = String(f.get("name")).trim(), login = String(f.get("login")).trim().toLowerCase();
    const ok = await run(createStaff(name, login, f.get("role") as Role, String(f.get("password"))),
      `${name} can log in now with "${login}" and the temporary password, then chooses their own.`);
    if (ok) form.reset();
  }
  async function deactivate(p: Person) {
    if (await ask({ title: "Deactivate account", text: `${p.name} won't be able to log in. Their name stays on the rentals they handled.`, ok: "Deactivate", danger: true }))
      run(setActive(p.id, false));
  }
  async function reset(e: React.FormEvent<HTMLFormElement>, p: Person) {
    e.preventDefault();
    if (await run(resetPassword(p.id, String(new FormData(e.currentTarget).get("password"))), `${p.name} logs in with the new temporary password, then chooses their own.`))
      setResetting(null);
  }

  return (
    <div className="panel staff">
      <div className="panel-h"><h3>Staff</h3><span className="muted">Each person logs in with their own username and password. Instructors only hand out and take back boards.</span></div>
      <div className="panel-b">
        {people.map((p) => (
          <div key={p.id}>
            <div className="set-row">
              <span className="person"><b>{p.name}</b><span className="muted">{p.login}</span></span>
              <select value={p.role} disabled={busy || p.id === me.id} aria-label="Role" onChange={(e) => run(setRole(p.id, e.target.value as Person["role"]))}>
                <option value="staff">Staff</option>
                <option value="instructor">Instructor</option>
                <option value="owner">Owner</option>
              </select>
              {p.active ? <span className="st ok">Active</span> : <span className="st fix">Deactivated</span>}
              {p.id !== me.id && <>
                <button className="btn sm" disabled={busy} onClick={() => setResetting(resetting === p.id ? null : p.id)}>Reset password</button>
                {p.active
                  ? <button className="btn sm danger" disabled={busy} onClick={() => deactivate(p)}>Deactivate</button>
                  : <button className="btn sm" disabled={busy} onClick={() => run(setActive(p.id, true))}>Reactivate</button>}
              </>}
            </div>
            {resetting === p.id && (
              <form className="form set-add" onSubmit={(e) => reset(e, p)}>
                <input name="password" type="text" minLength={8} required autoFocus autoComplete="off" placeholder={`New temporary password for ${p.name}`} />
                <button className="btn primary" disabled={busy}>Save password</button>
                <button type="button" className="btn" onClick={() => setResetting(null)}>Cancel</button>
              </form>
            )}
          </div>
        ))}
        <form className="form set-add" onSubmit={add}>
          <input name="name" placeholder="Name, e.g. Dana" required />
          <input name="login" placeholder="Username, e.g. dana" required autoCapitalize="none" autoCorrect="off" spellCheck={false} autoComplete="off" />
          <select name="role" defaultValue="staff" aria-label="Role"><option value="staff">Staff</option><option value="instructor">Instructor</option><option value="owner">Owner</option></select>
          <input name="password" type="text" minLength={8} required autoComplete="off" placeholder="Temporary password (8+ characters)" />
          <button className="btn primary" disabled={busy}>Add person</button>
        </form>
      </div>
    </div>
  );
}

// ---------- Google Sheets ----------

const CONNECT_RESULT: Record<string, [string, "" | "error"]> = {
  connected: ['Google Sheets is connected. The sheet is in the "Shokogi Boards" folder of that Google Drive.', ""],
  cancelled: ["Connecting Google Sheets was cancelled.", "error"],
  expired: ["That took too long. Click Connect again.", "error"],
  failed: ["Couldn't connect Google Sheets. Try again.", "error"],
  "not-set-up": ["Google Sheets can't be connected yet: the app's one-time Google registration is missing.", "error"],
};

function GoogleSheets({ ready }: { ready: boolean }) {
  const { fleet, toast, ask, syncNow, refresh } = useApp();
  const [busy, setBusy] = useState(false);
  useEffect(() => { // back from Google with ?google=…
    const result = new URLSearchParams(location.search).get("google");
    if (!result) return;
    const [message, kind] = CONNECT_RESULT[result] ?? CONNECT_RESULT.failed;
    toast(message, kind);
    history.replaceState(null, "", "/settings");
  }, [toast]);

  const sheet = fleet?.sheet, status = fleet?.sheets;
  async function disconnect() {
    if (!(await ask({ title: "Disconnect Google Sheets", text: "The sheet stays in Google Drive, but the app stops updating it.", ok: "Disconnect", danger: true }))) return;
    setBusy(true);
    const res = await fetch("/api/google/disconnect", { method: "POST" });
    setBusy(false);
    if (!res.ok) toast("Couldn't disconnect. Try again.", "error");
    await refresh();
  }
  async function sync() {
    setBusy(true);
    await syncNow();
    setBusy(false);
  }

  return (
    <div className="panel sheets-panel">
      <div className="panel-h"><h3>Google Sheets</h3><span className="muted">A live copy of the rentals in Google Drive</span></div>
      <div className="panel-b">
        {sheet ? (
          <>
            <p>Connected to <b>{sheet.email}</b>. The sheet updates a few seconds after every change, and every 10 minutes.</p>
            <p className={status?.error ? "st late" : "muted"}>
              {!status ? "Not synced yet." : status.error ? `Last sync failed: ${status.error}` : `Last synced ${when(status.at)}.`}
            </p>
            <div className="acts">
              <a className="btn primary" href={sheet.url} target="_blank" rel="noopener">Open sheet</a>
              <a className="btn" href={sheet.folder_url} target="_blank" rel="noopener">Open folder</a>
              <button className="btn" disabled={busy} onClick={sync}>Sync now</button>
              <button className="btn danger" disabled={busy} onClick={disconnect}>Disconnect</button>
            </div>
          </>
        ) : (
          <>
            <p>Do this once, on the business computer: click Connect, choose the business&apos;s Google account and allow access.
              The app creates a &quot;Shokogi Boards&quot; folder with the sheet in that Google Drive and keeps it up to date.</p>
            <div className="acts">
              {ready ? <a className="btn primary" href="/api/google/connect">Connect Google Sheets</a>
                : <span className="muted">Not available yet: the app&apos;s one-time Google registration is missing.</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ---------- Bloowatch ----------

function Bloowatch() {
  const db = createClient();
  const { toast } = useApp();
  const [on, setOn] = useState<boolean | null>(null);
  useEffect(() => {
    db.from("app_settings").select("value").eq("key", "bloowatch_enabled").maybeSingle().then(({ data }) => setOn(data?.value === true));
  }, [db]);
  async function toggle() {
    const { error } = await db.from("app_settings").upsert({ key: "bloowatch_enabled", value: !on });
    if (error) toast("Couldn't change the Bloowatch setting.", "error");
    else setOn(!on);
  }
  return (
    <div className="panel sheets-panel">
      <div className="panel-h"><h3>Bloowatch</h3><span className="muted">Bookings arriving as rentals</span></div>
      <div className="panel-b">
        <p>Once Bloowatch gives API access, its bookings can arrive here on their own, as rentals waiting for a board. Until then, leave it off.</p>
        {/* `on` is loaded in the browser, so the address (which needs `location`) is never rendered on the server */}
        <p className="muted">{on === null ? "…" : `${on ? "On" : "Off"} · Booking address: ${location.origin}/api/bloowatch/webhook`}</p>
        <div className="acts"><button className="btn" disabled={on === null} onClick={toggle}>{on ? "Turn off" : "Turn on"}</button></div>
      </div>
    </div>
  );
}

// ---------- Change log ----------

const ENTITY: Record<string, string> = {
  boards: "board", board_types: "board type", customers: "customer", rental_lengths: "rental length",
  rentals: "rental", rental_items: "board hand-out", profiles: "staff account", app_settings: "setting",
};
const FIELD: Record<string, string | null> = {
  in_repair: "repair", due_at: "return time", type_id: "type", deleted_at: "deleted", photo_path: "photo", thumb_path: null,
  ended_at: "returned", unassigned_at: "taken back", must_change_password: null, login: null,
};

function describe(c: Change, boardName: (id: unknown) => string | undefined, personName: (id: string) => string | undefined) {
  const before = c.details?.before ?? {}, after = c.details?.after ?? {};
  if (c.entity === "rentals" && c.action === "update" && after.ended_at) return "marked a rental returned";
  if (c.entity === "profiles" && c.action === "update" && after.must_change_password === false && Object.keys(after).length === 1) return "changed their password";
  if (c.entity === "profiles" && after.must_change_password === true && !("active" in after) && c.action === "update") return `set a temporary password for ${personName(c.entity_id) ?? "someone"}`;
  if (c.entity === "rental_items" && c.action === "insert") return `handed out ${boardName(after.board_id) ?? "a board"}`;
  const name = (after.name ?? before.name ?? after.label ?? before.label
    ?? (c.entity === "boards" ? boardName(c.entity_id) : c.entity === "profiles" ? personName(c.entity_id) : undefined)) as string | undefined;
  const verb = { insert: "added", update: "changed", delete: "removed" }[c.action] ?? c.action;
  const fields = c.action === "update"
    ? Object.keys(after).map((k) => (k in FIELD ? FIELD[k] : k.replace(/_/g, " "))).filter(Boolean).join(", ") : "";
  return `${verb} ${ENTITY[c.entity] ?? c.entity}${name ? ` ${name}` : ""}${fields ? ` (${fields})` : ""}`;
}

function ChangeLog({ people }: { people: Person[] }) {
  const db = createClient();
  const { fleet } = useApp();
  const [changes, setChanges] = useState<Change[]>([]);
  useEffect(() => {
    db.from("audit_log").select("id, at, actor_id, action, entity, entity_id, details").order("at", { ascending: false }).limit(100)
      .then(({ data }) => data && setChanges(data as Change[]));
  }, [db, fleet]);
  const who = (id: string | null) => (id ? people.find((p) => p.id === id)?.name ?? "Someone" : "System");
  const boardName = (id: unknown) => fleet?.boards.find((b) => b.id === id)?.name;

  return (
    <div className="panel">
      <div className="panel-h"><h3>Change log</h3><span className="muted">The latest 100 changes, by whom</span></div>
      {changes.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>When</th><th>Who</th><th>What</th></tr></thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.id}><td className="muted">{when(c.at)}</td><td>{who(c.actor_id)}</td><td>{describe(c, boardName, (id) => people.find((p) => p.id === id)?.name)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="panel-b"><p className="empty">Changes show up here.</p></div>}
    </div>
  );
}

export default function SettingsView({ googleReady }: { googleReady: boolean }) {
  const db = createClient();
  const [people, setPeople] = useState<Person[]>([]);
  const reload = useCallback(() => {
    db.from("profiles").select("id, name, login, role, active").order("active", { ascending: false }).order("name")
      .then(({ data }) => data && setPeople(data as Person[]));
  }, [db]);
  useEffect(reload, [reload]);

  return (
    <section>
      <div className="top"><div><h1>Settings</h1><p className="sub">Rental lengths, board types and staff. Changes save automatically.</p></div></div>
      <div className="cols" style={{ marginTop: 0 }}>
        <Lengths />
        <Types />
      </div>
      <Staff people={people} reload={reload} />
      <GoogleSheets ready={googleReady} />
      <Bloowatch />
      <ChangeLog people={people} />
    </section>
  );
}
