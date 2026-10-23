"use client";

// "N rentals overdue" (SPEC 7.14). When it appears is decided in the app provider; this is the window itself.
import { isOverdue } from "@/lib/data";
import { plural, timeLeft, when } from "@/lib/time";
import { Modal, useApp } from "./app";
import { Icon } from "./icons";
import { BoardThumb, useRentalActions } from "./rentals";

export default function OverdueAlert({ onClose }: { onClose: () => void }) {
  const { fleet, now, openRental } = useApp();
  const actions = useRentalActions();
  if (!fleet) return null;
  const late = fleet.rentals.filter((r) => isOverdue(r, now)).sort((a, b) => a.due_at.localeCompare(b.due_at));
  const board = (id: string) => fleet.boards.find((b) => b.id === id);

  return (
    <Modal id="lateDlg" onClose={onClose}>
      <div className="dlg-head">
        <b style={{ flex: 1 }}>{plural(late.length, "rental")} overdue</b>
        <button className="icon-btn" title="Close" onClick={onClose}><Icon name="x" /></button>
      </div>
      {late.map((r) => (
        <div className="late-row" key={r.id}>
          <BoardThumb board={board(r.boards[0])} />
          <div>
            <button className="who" title="Open rental" onClick={() => openRental(r.id)}>{r.customer.name}</button>
            {r.customer.phone && <span className="muted" style={{ display: "inline" }}> · {r.customer.phone}</span>}
            <div>{r.boards.map((b) => board(b)?.name).join(", ")}</div>
            <span className="st late">{timeLeft(Date.parse(r.due_at), now)}</span>{" "}
            <span className="muted" style={{ display: "inline" }}>· was due {when(r.due_at)}</span>
          </div>
          <div className="acts">
            <button className="btn sm" title="New return time: 30 minutes from now" onClick={() => actions.extend(r, 30)}>+30 min</button>
            <button className="btn sm" title="New return time: 1 hour from now" onClick={() => actions.extend(r, 60)}>+1 hour</button>
            <button className="btn sm primary" onClick={() => actions.markReturned(r)}>Mark returned</button>
          </div>
        </div>
      ))}
      <div className="late-f">
        <span className="muted">This reminder comes back every time the app opens, until each board is returned or the rental is extended.</span>
        <button className="btn" onClick={onClose}>Remind me later</button>
      </div>
    </Modal>
  );
}
