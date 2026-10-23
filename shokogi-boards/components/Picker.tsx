"use client";

// Board picker (SPEC 7.3): boards with a free copy, grouped by type, search where every word must match.
// Clicking a board hands it out (or swaps it) and closes the picker.
import { useEffect, useState } from "react";
import { byName, matcher } from "@/lib/boards";
import { copies } from "@/lib/data";
import { photoUrl } from "@/lib/photos";
import { Modal, useApp } from "./app";
import { shownTypes } from "./boards";
import { Icon } from "./icons";
import { useRentalActions } from "./rentals";

export default function Picker({ rentalId, replace, onClose }: { rentalId: string; replace?: string; onClose: () => void }) {
  const { fleet } = useApp();
  const actions = useRentalActions();
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const rental = fleet?.rentals.find((r) => r.id === rentalId);
  useEffect(() => { if (fleet && !rental) onClose(); }, [fleet, rental, onClose]); // returned meanwhile

  if (!fleet || !rental) return null;
  const name = rental.customer.name;
  const title = replace ? `Swap board for ${name}` : rental.boards.length ? `Add a board for ${name}` : `Choose a board for ${name}`;
  const touch = matchMedia("(pointer: coarse)").matches; // phones: start on the title, so no keyboard covers the boards
  const has = matcher(query);
  const left = (b: (typeof fleet.boards)[number]) => copies(fleet.rentedBy, b).free;
  const free = fleet.boards.filter((b) => left(b) > 0 && has(b.name)).sort(byName);
  const groups = shownTypes(fleet).map((t) => ({ type: t, boards: free.filter((b) => b.type_id === t.id) })).filter((g) => g.boards.length);

  async function pick(boardId: string) {
    setBusy(true);
    const ok = await actions.assign(rental!, boardId, replace);
    setBusy(false);
    if (ok) onClose(); // otherwise someone else just took it: the refreshed list stays open
  }

  return (
    <Modal id="pickDlg" onClose={onClose}>
      <div className="dlg-head">
        <b tabIndex={-1} data-autofocus={touch || undefined}>{title}</b>
        <input type="search" placeholder="Search, e.g. torq 7'6" value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="icon-btn" title="Close" onClick={onClose}><Icon name="x" /></button>
      </div>
      <div id="pickList" aria-busy={busy}>
        {groups.length ? groups.map(({ type, boards }) => (
          <div key={type.id}>
            <div className="group"><h2>{type.name}</h2><span className="muted">{boards.reduce((n, b) => n + left(b), 0)} available</span></div>
            <div className="grid">
              {boards.map((b) => (
                <button key={b.id} className="pick" disabled={busy} onClick={() => pick(b.id)}>
                  <div className="photo">{b.thumb_path ? <img src={photoUrl(b.thumb_path)} alt="" loading="lazy" /> : "No photo"}</div>
                  <b>{b.name}{b.quantity > 1 && <span className="muted qty"> · {left(b)} of {b.quantity} free</span>}</b>
                </button>
              ))}
            </div>
          </div>
        )) : <p className="empty" style={{ paddingTop: 18 }}>No available boards match.</p>}
      </div>
    </Modal>
  );
}
