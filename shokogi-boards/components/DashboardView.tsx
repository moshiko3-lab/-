"use client";

// Dashboard (SPEC 7.1): overdue banner, fleet numbers, every board out now (soonest due first),
// fleet by type and the most rented boards of the last 30 days.
import Link from "next/link";
import { useEffect, useState } from "react";
import { copies, isOverdue } from "@/lib/data";
import { photoUrl } from "@/lib/photos";
import { createClient } from "@/lib/supabase/client";
import { fromPanama, longDate, panamaParts, plural, when } from "@/lib/time";
import { useApp } from "./app";
import { shownTypes } from "./boards";
import { Icon } from "./icons";
import { BoardThumb, RentalStatus, useRentalActions } from "./rentals";

type Top = { board_id: string; name: string; thumb_path: string | null; rentals: number };

export default function DashboardView() {
  const db = createClient();
  const { fleet, now, openBoard, openRental, openPicker } = useApp();
  const actions = useRentalActions();
  const [today, setToday] = useState<number | null>(null);
  const [top, setTop] = useState<Top[]>([]);

  useEffect(() => {
    const midnight = fromPanama({ ...panamaParts(Date.now()), h: 0, mi: 0 }); // "today" starts at midnight in Panama
    db.from("rentals").select("id", { count: "exact", head: true }).gte("starts_at", new Date(midnight).toISOString())
      .then(({ count }) => setToday(count ?? 0));
    db.rpc("most_rented", { p_since: new Date(Date.now() - 30 * 864e5).toISOString() }).then(({ data }) => data && setTop(data as Top[]));
  }, [db, fleet]);

  const header = (
    <div className="top">
      <div><h1>Dashboard</h1><p className="sub">{longDate(new Date(now))}</p></div>
      <Link className="btn primary" href="/rentals"><Icon name="plus" />New rental</Link>
    </div>
  );
  if (!fleet) return <section>{header}<p className="empty">Loading…</p></section>;

  const board = (id: string) => fleet.boards.find((b) => b.id === id);
  const late = fleet.rentals.filter((r) => isOverdue(r, now));
  const count = (list: typeof fleet.boards, what: "out" | "fix" | "free") => list.reduce((n, b) => n + copies(fleet.rentedBy, b)[what], 0);
  const out = fleet.rentals.flatMap((r) => r.boards.map((id, i) => ({ key: `${r.id}:${i}`, rental: r, board: board(id)! })))
    .filter((x) => x.board).sort((a, b) => a.rental.due_at.localeCompare(b.rental.due_at));

  return (
    <section>
      {header}
      {late.length > 0 && (
        <div className="banner">
          <b>{late.length} overdue</b>
          <span>{late.map((r) => `${r.customer.name} (${r.boards.map((b) => board(b)?.name).join(", ")})`).join(", ")}</span>
          <Link className="btn sm" href="/rentals">View rentals</Link>
        </div>
      )}
      <div className="metrics">
        <div><span className="label">Rented now</span><b>{out.length}</b></div>
        <div><span className="label">Available</span><b>{count(fleet.boards, "free")}</b></div>
        <div className={late.length ? "alert" : undefined}><span className="label">Overdue</span><b>{late.length}</b></div>
        <div><span className="label">Waiting for a board</span><b>{fleet.rentals.filter((r) => !r.boards.length).length}</b></div>
        <div><span className="label">In repair</span><b>{count(fleet.boards, "fix")}</b></div>
        <div><span className="label">Rentals today</span><b>{today ?? "—"}</b></div>
      </div>
      <div className="panel">
        <div className="panel-h"><h3>Currently rented</h3><span className="muted">Due back soonest first</span></div>
        <div className="panel-b">
          {out.length ? (
            <div className="grid">
              {out.map(({ key, rental, board: b }) => (
                <div className="board" key={key}>
                  <button className="photo" title="Board details" onClick={() => openBoard(b.id)}>
                    {b.thumb_path ? <img src={photoUrl(b.thumb_path)} alt="" loading="lazy" /> : "No photo"}
                  </button>
                  <div className="body">
                    <button className="who" title="Open rental" onClick={() => openRental(rental.id)}>{rental.customer.name}</button>
                    <div className="name">{b.name}</div>
                    <div className="row"><RentalStatus rental={rental} /><span className="muted">Back {when(rental.due_at)}</span></div>
                    <div className="foot">
                      <button className="btn sm" onClick={() => openPicker(rental.id, b.id)}>Swap board</button>
                      <button className="btn sm" onClick={() => actions.markReturned(rental)}>Mark returned</button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="empty">No boards are rented right now.</p>}
        </div>
      </div>
      <div className="cols">
        <div className="panel">
          <div className="panel-h"><h3>Fleet by type</h3><span className="muted">Rented / in service</span></div>
          <div className="panel-b bars">
            {shownTypes(fleet).map((t) => {
              const list = fleet.boards.filter((b) => b.type_id === t.id);
              const rented = count(list, "out"), inService = list.reduce((n, b) => n + b.quantity - b.in_repair, 0);
              return (
                <div key={t.id}>
                  <span>{t.name}</span>
                  <span className="bar"><i style={{ width: `${inService ? (rented / inService) * 100 : 0}%` }} /></span>
                  <span className="muted">{rented} / {inService}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="panel">
          <div className="panel-h"><h3>Most rented boards</h3><span className="muted">Last 30 days</span></div>
          <div className="panel-b">
            {top.length ? (
              <ol className="top5">
                {top.map((t) => (
                  <li key={t.board_id}>
                    <BoardThumb board={board(t.board_id)} />
                    <span>{t.name}</span>
                    <span className="muted">{plural(t.rentals, "rental")}</span>
                  </li>
                ))}
              </ol>
            ) : <p className="empty">Fills in as rentals are returned.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
