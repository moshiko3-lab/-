"use client";

// The instructors' screen, made for a phone on the beach: every open rental as a card, customers waiting for a
// board first. Three buttons only (owner's request): Choose board for a customer without one, Swap on each board,
// Mark returned. The database also keeps instructors to boards and returns: one board per rental, no customers,
// rentals or settings (migrations 20261027000000_instructors, 20261028000000_instructor_one_board).
import { useState } from "react";
import { matcher } from "@/lib/boards";
import { isOverdue, type Rental } from "@/lib/data";
import { photoUrl } from "@/lib/photos";
import { when } from "@/lib/time";
import { useApp } from "./app";
import { RentalStatus, useRentalActions } from "./rentals";
import SignOut from "./SignOut";

export default function InstructorView() {
  const { me, fleet } = useApp();
  const [query, setQuery] = useState("");
  const name = (id: string) => fleet?.boards.find((b) => b.id === id)?.name ?? "";
  const has = matcher(query);
  const list = (fleet?.rentals ?? [])
    .filter((r) => has(`${r.customer.name} ${r.boards.map(name).join(" ")}`))
    .sort((a, b) => a.due_at.localeCompare(b.due_at));
  const waiting = list.filter((r) => !r.boards.length);
  const out = list.filter((r) => r.boards.length);

  return (
    <div className="ins">
      <header className="ins-top">
        <div className="brand"><span className="logo">S</span><div><b>Shokogi</b><small>{me.name}</small></div></div>
        <SignOut />
      </header>
      <main>
        {!fleet ? <p className="empty">Loading…</p> : !fleet.rentals.length ? (
          <p className="empty ins-empty">No open rentals right now. New bookings show up here on their own.</p>
        ) : <>
          <input type="search" className="ins-search" placeholder="Search by name" aria-label="Search by name" enterKeyHint="search"
            value={query} onChange={(e) => setQuery(e.target.value)} />
          {!list.length && <p className="empty ins-empty">Nobody matches your search.</p>}
          <Group title="Needs a board" rentals={waiting} />
          <Group title="Out now" rentals={out} />
        </>}
      </main>
    </div>
  );
}

function Group({ title, rentals }: { title: string; rentals: Rental[] }) {
  if (!rentals.length) return null;
  return (
    <section>
      <div className="group"><h2>{title}</h2><span className="muted">{rentals.length}</span></div>
      <div className="ins-list">{rentals.map((r) => <Card key={r.id} rental={r} />)}</div>
    </section>
  );
}

function Card({ rental: r }: { rental: Rental }) {
  const { fleet, now, openPicker } = useApp();
  const actions = useRentalActions();
  const board = (id: string) => fleet!.boards.find((b) => b.id === id);

  return (
    <article className={`ins-card${!r.boards.length ? " wait" : isOverdue(r, now) ? " late" : ""}`}>
      <div className="ins-head">
        <h3>{r.customer.name}</h3>
        {r.boards.length > 0 && <RentalStatus rental={r} />}
      </div>
      <p className="muted">{Date.parse(r.starts_at) > now && <>Starts {when(r.starts_at)} · </>}{r.boards.length ? "Back by" : "Rental until"} {when(r.due_at)}</p>
      {r.boards.map((id, i) => {
        const b = board(id);
        return (
          <div className="ins-board" key={`${id}:${i}`}>
            {b?.thumb_path ? <img className="thumb" src={photoUrl(b.thumb_path)} alt="" loading="lazy" /> : <span className="thumb" />}
            <b>{b?.name}</b>
            <button className="btn" onClick={() => openPicker(r.id, id)}>Swap</button>
          </div>
        );
      })}
      {r.boards.length
        ? <button className="btn primary" onClick={() => actions.markReturned(r)}>Mark returned</button>
        : <button className="btn primary" onClick={() => openPicker(r.id)}>Choose board</button>}
    </article>
  );
}
