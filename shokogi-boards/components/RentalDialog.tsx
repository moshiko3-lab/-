"use client";

// Rental window (SPEC 7.4): the customer's active rental with its boards, actions, and earlier rentals.
// Edit mode changes name, phone and return time; background refreshes never wipe a form being edited.
import { useEffect, useState } from "react";
import { photoUrl } from "@/lib/photos";
import { createClient } from "@/lib/supabase/client";
import { fmtDur, when } from "@/lib/time";
import { Modal, useApp } from "./app";
import DateTimeField from "./DateTimeField";
import RentalChanges from "./RentalChanges";
import { Icon } from "./icons";
import { RentalStatus, useRentalActions } from "./rentals";

type Past = { id: string; starts_at: string; ended_at: string; items: { boards: { name: string } }[] };

export default function RentalDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const db = createClient();
  const { me, fleet, openBoard, openPicker, openProfile } = useApp();
  const actions = useRentalActions();
  const [editing, setEditing] = useState(false);
  const [due, setDue] = useState(0);
  const [past, setPast] = useState<{ list: Past[]; count: number }>({ list: [], count: 0 });
  const rental = fleet?.rentals.find((r) => r.id === id);
  const customerId = rental?.customer.id;

  useEffect(() => { if (fleet && !rental) onClose(); }, [fleet, rental, onClose]); // returned, maybe on another device

  useEffect(() => {
    if (!customerId) return;
    db.from("rentals").select("id, starts_at, ended_at, items:rental_items(boards(name))", { count: "exact" })
      .eq("customer_id", customerId).not("ended_at", "is", null).order("starts_at", { ascending: false }).limit(10)
      .then(({ data, count }) => data && setPast({ list: data as unknown as Past[], count: count ?? 0 }));
  }, [db, customerId, fleet]);

  if (!fleet || !rental) return null;
  const boards = rental.boards.map((b) => fleet.boards.find((x) => x.id === b)).filter((b) => !!b);
  const typeName = (typeId: string) => fleet.types.find((t) => t.id === typeId)?.name;
  const first = boards[0];

  function startEdit() {
    setDue(Date.parse(rental!.due_at));
    setEditing(true);
  }
  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const name = String(f.get("name")).trim(), phone = String(f.get("phone")).trim();
    if (!name) return;
    const c = rental!.customer;
    if (name !== c.name || phone !== c.phone) if (!(await actions.updateCustomer(c.id, { name, phone }))) return;
    if (due !== Date.parse(rental!.due_at)) if (!(await actions.setDue(rental!, due))) return;
    setEditing(false);
  }

  return (
    <Modal id="custDlg" onClose={onClose}>
      <div className="dlg-head">
        <b style={{ flex: 1 }}>Rental</b>
        <button className="icon-btn" title="Close" onClick={onClose}><Icon name="x" /></button>
      </div>
      <div className="cust">
        {first
          ? <button className="photo" title="Board details" onClick={() => openBoard(first.id)}>{first.photo_path ? <img src={photoUrl(first.photo_path)} alt="" /> : "No photo"}</button>
          : <div className="photo">No board yet</div>}
        <div>
          {editing ? (
            <form className="editform" onSubmit={save}>
              <label><span className="label">Name</span><input name="name" defaultValue={rental.customer.name} required autoFocus /></label>
              <label><span className="label">Phone</span><input name="phone" defaultValue={rental.customer.phone} placeholder="Optional" /></label>
              <label><span className="label">Back by</span><DateTimeField value={due} onPick={(ms) => ms && setDue(ms)} /></label>
              <div className="acts">
                <button className="btn primary">Save changes</button>
                <button type="button" className="btn" onClick={() => setEditing(false)}>Cancel</button>
              </div>
            </form>
          ) : (
            <>
              <h2>{rental.customer.name}<button className="link" title="Edit name, phone or return time" onClick={startEdit}>Edit</button></h2>
              {rental.customer.phone
                ? <a className="tel" href={`tel:${rental.customer.phone}`}><Icon name="phone" />{rental.customer.phone}</a>
                : <span className="muted">No phone number</span>}
              <dl>
                <dt>{boards.length > 1 ? "Boards" : "Board"}</dt>
                <dd>
                  {boards.length ? boards.map((b, i) => (
                    <div key={`${b.id}:${i}`} className="rental-board">
                      {b.name} <span className="muted" style={{ display: "inline" }}>{typeName(b.type_id)}</span>
                      {boards.length > 1 && (
                        <div className="links">
                          <button className="link" onClick={() => openPicker(rental.id, b.id)}>Swap</button><span className="muted"> · </span>
                          <button className="link danger" onClick={() => actions.remove(rental, b.id)}>Remove</button>
                        </div>
                      )}
                    </div>
                  )) : "—"}
                </dd>
                <dt>Start</dt><dd>{when(rental.starts_at)}</dd>
                <dt>Back by</dt><dd>{when(rental.due_at)}</dd>
                <dt>Status</dt><dd><RentalStatus rental={rental} /></dd>
              </dl>
              <div className="acts">
                {boards.length === 0 && <button className="btn primary" onClick={() => openPicker(rental.id)}>Choose board</button>}
                {boards.length === 1 && <>
                  <button className="btn primary" onClick={() => openPicker(rental.id, boards[0].id)}>Swap board</button>
                  <button className="btn" onClick={() => actions.remove(rental, boards[0].id)}>Remove board</button>
                </>}
                {boards.length > 0 && <button className="btn" onClick={() => openPicker(rental.id)}>Add another board</button>}
                {boards.length > 0 && <button className="btn" onClick={() => actions.markReturned(rental)}>Mark returned</button>}
                {me.role === "owner" && <button className="btn" onClick={() => actions.finish(rental)}>Finish rental</button>}
              </div>
            </>
          )}
          {me.role === "owner" && <><h3>Changes</h3><RentalChanges rentalId={rental.id} /></>}
          <h3>Earlier rentals <span className="muted">{past.count}</span> <button className="link" onClick={() => openProfile(rental.customer.id)}>Full profile</button></h3>
          {past.list.length ? (
            <ul className="past">
              {past.list.map((p) => (
                <li key={p.id}>
                  <span className="muted">{when(p.starts_at)}</span>
                  <span>{p.items.map((i) => i.boards.name).join(", ") || "—"}</span>
                  <span className="muted">{fmtDur(Date.parse(p.ended_at) - Date.parse(p.starts_at))}</span>
                </li>
              ))}
            </ul>
          ) : <p className="empty">First rental with us.</p>}
        </div>
      </div>
    </Modal>
  );
}
