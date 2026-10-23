"use client";

// Customer profile (SPEC 7.5): contact details (editable), totals, what they rent now and every rental they made.
import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { fmtDur, when } from "@/lib/time";
import { Modal, useApp } from "./app";
import { Icon } from "./icons";
import { BoardThumb, RentalStatus, useRentalActions } from "./rentals";

type Stats = {
  id: string; name: string; phone: string; email: string; notes: string;
  rentals: number; hours: number; late_returns: number; first_visit: string | null; last_visit: string | null;
};
type Past = { id: string; starts_at: string; due_at: string; ended_at: string; items: { board_id: string; boards: { name: string; type_id: string } }[] };

export default function ProfileDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const db = createClient();
  const { fleet, openRental } = useApp();
  const { updateCustomer } = useRentalActions();
  const [c, setC] = useState<Stats | null>(null);
  const [past, setPast] = useState<Past[]>([]);
  const [editing, setEditing] = useState(false);

  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    db.from("customer_stats").select("id, name, phone, email, notes, rentals, hours, late_returns, first_visit, last_visit").eq("id", id).maybeSingle()
      .then(({ data }) => data ? setC(data as Stats) : close.current());
    db.from("rentals").select("id, starts_at, due_at, ended_at, items:rental_items(board_id, boards(name, type_id))")
      .eq("customer_id", id).not("ended_at", "is", null).order("starts_at", { ascending: false })
      .then(({ data }) => data && setPast(data as unknown as Past[]));
  }, [db, id, fleet]); // fleet changes on every save and live update: reload the totals

  if (!fleet || !c) return null;
  const now = fleet.rentals.filter((r) => r.customer.id === id);
  const counts = new Map<string, number>();
  past.forEach((p) => p.items.forEach((i) => counts.set(i.boards.type_id, (counts.get(i.boards.type_id) ?? 0) + 1)));
  const favorite = [...counts].sort((a, b) => b[1] - a[1])[0]?.[0];

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const changes = Object.fromEntries(["name", "phone", "email", "notes"].map((k) => [k, String(f.get(k)).trim()]));
    if (!changes.name) return;
    if (await updateCustomer(id, changes)) setEditing(false);
  }

  return (
    <Modal id="profDlg" onClose={onClose}>
      <div className="dlg-head">
        <b style={{ flex: 1 }}>Customer profile</b>
        <button className="icon-btn" title="Close" onClick={onClose}><Icon name="x" /></button>
      </div>
      <div className="bd-info" style={{ borderTop: 0 }}>
        {editing ? (
          <form className="editform" onSubmit={save}>
            <label><span className="label">Name</span><input name="name" defaultValue={c.name} required autoFocus /></label>
            <label><span className="label">Phone</span><input name="phone" defaultValue={c.phone} placeholder="Optional" /></label>
            <label><span className="label">Email</span><input name="email" type="email" defaultValue={c.email} placeholder="Optional" /></label>
            <label><span className="label">Notes</span><textarea name="notes" rows={3} defaultValue={c.notes} placeholder="Level, preferences, anything the staff should know" /></label>
            <div className="acts">
              <button className="btn primary">Save changes</button>
              <button type="button" className="btn" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </form>
        ) : (
          <>
            <div className="bd-title"><h2>{c.name}</h2><button className="link" onClick={() => setEditing(true)}>Edit</button></div>
            {(c.phone || c.email) && (
              <p className="contact">
                {c.phone && <a className="tel link" href={`tel:${c.phone}`}><Icon name="phone" />{c.phone}</a>}
                {c.email && <a className="link" href={`mailto:${c.email}`}>{c.email}</a>}
              </p>
            )}
            {c.notes && <p className="bd-notes">{c.notes}</p>}
          </>
        )}
        <div className="metrics sm">
          <div><span className="label">Rentals</span><b>{c.rentals}</b></div>
          <div><span className="label">Hours on the water</span><b>{c.hours}</b></div>
          <div><span className="label">Late returns</span><b>{c.late_returns}</b></div>
          <div><span className="label">Favorite type</span><b>{fleet.types.find((t) => t.id === favorite)?.name ?? "—"}</b></div>
          <div><span className="label">First visit</span><b>{when(c.first_visit)}</b></div>
          <div><span className="label">Last visit</span><b>{when(c.last_visit)}</b></div>
        </div>
        {now.map((r) => (
          <div className="now-rent" key={r.id}>
            <BoardThumb board={fleet.boards.find((b) => b.id === r.boards[0])} />
            <div>
              <span className="label">Renting now</span><br />
              {r.boards.map((b) => fleet.boards.find((x) => x.id === b)?.name).join(", ") || "No board yet"}{" "}
              <span className="muted" style={{ display: "inline" }}>· back {when(r.due_at)}</span><br />
              <RentalStatus rental={r} />
            </div>
            <button className="btn" onClick={() => openRental(r.id)}>Open rental</button>
          </div>
        ))}
        <h3>Rental history <span className="muted">{past.length}</span></h3>
        {past.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Start</th><th>Board</th><th>Duration</th><th>Return</th></tr></thead>
              <tbody>
                {past.map((p) => {
                  const late = Date.parse(p.ended_at) - Date.parse(p.due_at);
                  return (
                    <tr key={p.id}>
                      <td className="muted">{when(p.starts_at)}</td>
                      <td>
                        {p.items.map((i, n) => (
                          <div key={n} className="assigned">
                            <BoardThumb board={fleet.boards.find((b) => b.id === i.board_id)} />{i.boards.name}
                          </div>
                        ))}
                        {!p.items.length && "—"}
                      </td>
                      <td>{fmtDur(Date.parse(p.ended_at) - Date.parse(p.starts_at))}</td>
                      <td>{late > 0 ? <span className="st late">Late {fmtDur(late)}</span> : <span className="st ok">On time</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <p className="empty">No returned rentals yet.</p>}
      </div>
    </Modal>
  );
}
