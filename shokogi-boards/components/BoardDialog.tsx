"use client";

// Board details (SPEC 7.7): large photo, details, edit, repair, delete and every rental of this board,
// including hand-outs that ended in a swap.
import { useEffect, useRef, useState } from "react";
import { copies } from "@/lib/data";
import { photoUrl } from "@/lib/photos";
import { createClient } from "@/lib/supabase/client";
import { fmtDur, when } from "@/lib/time";
import { Modal, useApp } from "./app";
import { BoardStatus, RepairButtons, useBoardActions } from "./boards";
import { Icon } from "./icons";

type Use = {
  id: string; assigned_at: string; unassigned_at: string;
  rentals: { ended_at: string | null; due_at: string; customers: { name: string; phone: string } };
};

function ReturnStatus({ use }: { use: Use }) {
  const { ended_at, due_at } = use.rentals;
  const swapped = !ended_at || Date.parse(ended_at) !== Date.parse(use.unassigned_at); // a return closes every board at ended_at exactly
  if (swapped) return <span className="muted">Swapped out</span>;
  const late = Date.parse(ended_at) - Date.parse(due_at);
  return late > 0 ? <span className="st late">Late {fmtDur(late)}</span> : <span className="st ok">On time</span>;
}

export default function BoardDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const db = createClient();
  const { me, fleet, openRental } = useApp();
  const actions = useBoardActions();
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uses, setUses] = useState<Use[]>([]);
  const picker = useRef<HTMLInputElement>(null);
  const board = fleet?.boards.find((b) => b.id === id);

  useEffect(() => { if (fleet && !board) onClose(); }, [fleet, board, onClose]); // just deleted

  useEffect(() => {
    db.from("rental_items").select("id, assigned_at, unassigned_at, rentals(ended_at, due_at, customers(name, phone))")
      .eq("board_id", id).not("unassigned_at", "is", null).order("assigned_at", { ascending: false })
      .then(({ data }) => data && setUses(data as unknown as Use[]));
  }, [db, id, fleet]);

  if (!fleet || !board) return null;
  const type = fleet.types.find((t) => t.id === board.type_id);
  const { out, renters } = copies(fleet.rentedBy, board);
  const stats = fleet.stats.get(board.id);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const name = String(f.get("name")).trim();
    if (!name) return;
    await actions.update(board!, { name, type_id: String(f.get("type")), quantity: Number(f.get("quantity")) || 1, notes: String(f.get("notes")).trim() });
    setEditing(false);
  }
  async function pickPhoto(file?: File) {
    if (!file) return;
    setBusy(true);
    await actions.setPhoto(board!, file);
    setBusy(false);
  }

  const photoButton = (
    <button type="button" className="btn" disabled={busy} onClick={() => picker.current!.click()}>
      {busy ? "Saving photo…" : board.photo_path ? "Replace photo" : "Add photo"}
    </button>
  );

  return (
    <Modal id="boardDlg" onClose={onClose}>
      <div className="dlg-head">
        <b style={{ flex: 1 }}>Board details</b>
        <button className="icon-btn" title="Close" onClick={onClose}><Icon name="x" /></button>
      </div>
      <div className="bd-photo">{board.photo_path ? <img src={photoUrl(board.photo_path)} alt="" /> : "No photo"}</div>
      <div className="bd-info">
        {editing ? (
          <form className="editform" onSubmit={save}>
            <label><span className="label">Board name</span><input name="name" defaultValue={board.name} required autoFocus /></label>
            <label><span className="label">Type</span>
              <select name="type" defaultValue={board.type_id}>{fleet.types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
            </label>
            <label><span className="label">Quantity</span>
              <input name="quantity" type="number" min={1} max={999} defaultValue={board.quantity} required title="How many identical boards you have" />
            </label>
            <label><span className="label">Notes</span>
              <textarea name="notes" rows={3} defaultValue={board.notes} placeholder="Condition, dings, fins, anything the staff should know" />
            </label>
            <div className="acts">
              <button className="btn primary">Save changes</button>
              {photoButton}
              <button type="button" className="btn" onClick={() => setEditing(false)}>Cancel</button>
            </div>
          </form>
        ) : (
          <>
            <div className="bd-title">
              <h2>{board.name}{board.quantity > 1 && <span className="muted qty"> ×{board.quantity}</span>}</h2>
              <button className="link" title="Edit name, type, notes or photo" onClick={() => setEditing(true)}>Edit</button>
            </div>
            {board.notes && <p className="bd-notes">{board.notes}</p>}
            <div className="metrics sm">
              <div><span className="label">Type</span><b>{type?.name}</b></div>
              <div><span className="label">Status</span><b><BoardStatus fleet={fleet} board={board} /></b></div>
              <div><span className="label">Rented by</span><b>{renters.length ? renters.map((r, i) => <span key={r.id}>{i > 0 && ", "}
                <button className="who" title="Open rental" onClick={() => openRental(r.id)}>{r.customer.name}</button></span>) : "—"}</b></div>
              <div><span className="label">Times rented</span><b>{stats?.times_rented ?? 0}</b></div>
              <div><span className="label">Hours rented</span><b>{stats?.hours_rented ?? 0}</b></div>
              <div><span className="label">Last rented</span><b>{when(stats?.last_rented)}</b></div>
            </div>
            <div className="acts">
              {photoButton}
              <RepairButtons fleet={fleet} board={board} />
              {!out && me.role === "owner" && <button className="btn danger" onClick={() => actions.remove(board)}>Delete board</button>}
            </div>
          </>
        )}
        <h3>Rental history <span className="muted">{uses.length}</span></h3>
        {uses.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Start</th><th>Customer</th><th>Duration</th><th>Return</th></tr></thead>
              <tbody>
                {uses.map((u) => (
                  <tr key={u.id}>
                    <td className="muted">{when(u.assigned_at)}</td>
                    <td><b>{u.rentals.customers.name}</b><span className="muted">{u.rentals.customers.phone}</span></td>
                    <td>{fmtDur(Date.parse(u.unassigned_at) - Date.parse(u.assigned_at))}</td>
                    <td><ReturnStatus use={u} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="empty">No returned rentals yet.</p>}
      </div>
      {/* A file chooser can't open from behind a modal dialog, so the input lives inside it. */}
      <input ref={picker} type="file" accept="image/*,.heic,.heif" hidden
        onChange={(e) => { pickPhoto(e.target.files?.[0]); e.target.value = ""; }} />
    </Modal>
  );
}
