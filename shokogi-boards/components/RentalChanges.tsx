"use client";

// Who changed a rental and what, oldest first (owner only: the change log is the owner's). Changes made by one
// action (a swap, a return) share a moment and a person, so they show as one line.
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { when } from "@/lib/time";
import { useApp } from "./app";

type Change = {
  id: number; at: string; actor_id: string | null; action: string; entity: string; entity_id: string;
  details: { after?: Record<string, unknown> | null } | null;
};

const FIELD: Record<string, string> = { due_at: "return time", starts_at: "start time", customer_id: "customer" };

export default function RentalChanges({ rentalId }: { rentalId: string }) {
  const db = createClient();
  const { me, fleet } = useApp();
  const [changes, setChanges] = useState<Change[] | null>(null);
  const [people, setPeople] = useState(new Map<string, string>());
  const owner = me.role === "owner";
  useEffect(() => {
    if (owner) db.rpc("rental_changes", { p_rental: rentalId }).then(({ data }) => data && setChanges(data as Change[]));
  }, [db, owner, rentalId, fleet]); // fleet: reload after every change anywhere
  useEffect(() => {
    if (owner) db.from("profiles").select("id, name").then(({ data }) => data && setPeople(new Map(data.map((p) => [p.id, p.name]))));
  }, [db, owner]);
  if (!owner) return null;

  // A hand-out's board is in its insert; taking it back only records the time.
  const boardOf = new Map((changes ?? []).filter((c) => c.entity === "rental_items" && c.action === "insert")
    .map((c) => [c.entity_id, c.details?.after?.board_id]));
  const board = (itemId: string) => fleet?.boards.find((b) => b.id === boardOf.get(itemId))?.name ?? "a board";

  let due: unknown; // the return time so far: ending before it is the owner's "Finish rental"
  function what(c: Change) {
    const a = c.details?.after ?? {};
    const keys = Object.keys(a).filter((k) => !k.endsWith("_by") && k !== "phone_digits"); // who did it is shown apart
    if (c.entity === "rentals" && c.action === "insert") return a.source === "bloowatch" ? "booking came in from Bloowatch" : "created the rental";
    if (c.entity === "rentals" && a.ended_at)
      return !c.actor_id ? "ended it automatically" : Date.parse(c.at) < Date.parse(String(due)) ? "finished the rental early" : "marked it returned";
    if (c.entity === "rentals" && keys.length === 1 && a.due_at) return `changed the return time to ${when(a.due_at as string)}`;
    if (c.entity === "rentals") return `changed the ${keys.map((k) => FIELD[k] ?? k.replace(/_/g, " ")).join(", ")}`;
    if (c.entity === "rental_items" && c.action === "insert") return `handed out ${board(c.entity_id)}`;
    if (c.entity === "rental_items" && a.unassigned_at) return `took back ${board(c.entity_id)}`;
    if (c.entity === "customers") return `edited the customer's ${keys.join(", ").replace(/_/g, " ")}`;
    return null;
  }

  const END = ["marked it returned", "finished the rental early", "ended it automatically"]; // says it all for its moment
  const lines: { key: number; at: string; who: string; what: string }[] = [];
  for (const c of changes ?? []) {
    const text = what(c);
    if (c.entity === "rentals" && c.details?.after?.due_at) due = c.details.after.due_at;
    if (!text) continue;
    const who = c.actor_id ? people.get(c.actor_id) ?? "Someone" : "System";
    const last = lines.at(-1);
    if (last && last.at === c.at && last.who === who) {
      last.what = END.includes(text) ? text : END.includes(last.what) ? last.what : `${last.what}, ${text}`;
    } else lines.push({ key: c.id, at: c.at, who, what: text });
  }

  return lines.length ? (
    <ul className="trail">
      {lines.map((l) => <li key={l.key}><span className="muted">{when(l.at)}</span><b>{l.who}</b><span>{l.what}</span></li>)}
    </ul>
  ) : <p className="empty trail-empty">{changes ? "No changes recorded." : "Loading…"}</p>;
}
