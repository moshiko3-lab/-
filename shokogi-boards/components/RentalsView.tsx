"use client";

// Rentals page (SPEC 7.2): new rental with customer autocomplete, then the board picker; table of active
// rentals (customers still without a board first, then by return time) with board changes, return time and return.
import { useEffect, useState } from "react";
import { matcher } from "@/lib/boards";
import type { Customer } from "@/lib/data";
import { createClient } from "@/lib/supabase/client";
import { when } from "@/lib/time";
import { useApp } from "./app";
import DateTimeField from "./DateTimeField";
import { BoardThumb, RentalStatus, useRentalActions } from "./rentals";

const like = (s: string) => `%${s.replace(/[\\%_]/g, "\\$&")}%`;

// Existing customers matching what's typed in the name or phone field (phone: by digits, so dashes don't matter).
function useSuggestions(text: string, by: "name" | "phone") {
  const db = createClient();
  const [list, setList] = useState<Customer[]>([]);
  useEffect(() => {
    const q = text.trim(), digits = q.replace(/\D/g, "");
    if (by === "name" ? q.length < 2 : digits.length < 3) return setList([]);
    const timer = setTimeout(async () => {
      const base = db.from("customers").select("id, name, phone").order("created_at", { ascending: false }).limit(6);
      const { data } = await (by === "name" ? base.ilike("name", like(q)) : base.like("phone_digits", like(digits)));
      setList((data as Customer[]) ?? []);
    }, 150);
    return () => clearTimeout(timer);
  }, [db, text, by]);
  return list;
}

function SuggestInput({ by, value, onChange, onChoose, ...input }: {
  by: "name" | "phone"; value: string; onChange: (v: string) => void; onChoose: (c: Customer) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const list = useSuggestions(value, by);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const show = open && list.length > 0;
  const choose = (c: Customer) => { onChoose(c); setOpen(false); };
  function keys(e: React.KeyboardEvent) {
    if (!show) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (a + (e.key === "ArrowDown" ? 1 : list.length - 1)) % list.length);
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(list[active]);
    } else if (e.key === "Escape") setOpen(false);
  }
  return (
    <div className="suggest">
      <input {...input} value={value} autoComplete="off" role="combobox" aria-expanded={show} aria-autocomplete="list"
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(-1); }}
        onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={keys} />
      {show && (
        <ul role="listbox">
          {list.map((c, i) => (
            <li key={c.id}>
              {/* mousedown keeps the focus in the field, so the list doesn't close before the click lands */}
              <button type="button" className={i === active ? "on" : undefined} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(c)}>
                {c.name}{c.phone && <span className="muted">{c.phone}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function RentalsView() {
  const { me, fleet, openPicker, openRental } = useApp();
  const actions = useRentalActions();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [minutes, setMinutes] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  if (!fleet) return <section><div className="top"><div><h1>Rentals</h1></div></div><p className="empty">Loading…</p></section>;

  const choose = (c: Customer) => { setName(c.name); setPhone(c.phone); };
  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !minutes) return;
    setBusy(true);
    const id = await actions.create(name.trim(), phone.trim(), +minutes);
    setBusy(false);
    if (!id) return;
    setName(""); setPhone(""); setMinutes("");
    openPicker(id); // straight on to choosing the board
  }

  const board = (id: string) => fleet.boards.find((b) => b.id === id);
  const has = matcher(query);
  const list = fleet.rentals
    .filter((r) => has(`${r.customer.name} ${r.customer.phone} ${r.boards.map((b) => board(b)?.name).join(" ")}`))
    .sort((a, b) => (a.boards.length ? 1 : 0) - (b.boards.length ? 1 : 0) || a.due_at.localeCompare(b.due_at));

  return (
    <section>
      <div className="top"><div><h1>Rentals</h1><p className="sub">Add the customer, then choose their board.</p></div></div>
      <form className="panel form" id="addRenter" onSubmit={add}>
        <SuggestInput by="name" name="name" placeholder="Customer name" required autoFocus value={name} onChange={setName} onChoose={choose} />
        <SuggestInput by="phone" name="phone" placeholder="Phone (optional)" inputMode="tel" value={phone} onChange={setPhone} onChoose={choose} />
        <select name="minutes" required value={minutes} onChange={(e) => setMinutes(e.target.value)}>
          <option value="">Rental length</option>
          {fleet.lengths.map((l) => <option key={l.id} value={l.minutes}>{l.label}</option>)}
        </select>
        <button className="btn primary" disabled={busy}>Add and choose board</button>
      </form>
      <div className="toolbar" style={{ marginTop: 18 }}>
        <input type="search" placeholder="Search customer, phone or board" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      {list.length ? (
        <div className="panel table-wrap">
          <table>
            <thead><tr><th>Customer</th><th>Board</th><th>Start</th><th>Back by</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id} className={r.boards.length ? undefined : "wait"}>
                  <td>
                    <button className="who" title="Details and edit" onClick={() => openRental(r.id)}>{r.customer.name}</button>
                    <span className="muted">{r.customer.phone}</span>
                  </td>
                  <td>
                    {r.boards.length ? (
                      <>
                        {r.boards.map((id, i) => (
                          <div className="assigned" key={`${id}:${i}`}>
                            <BoardThumb board={board(id)} />
                            <div>
                              {board(id)?.name}
                              <div className="links">
                                <button className="link" onClick={() => openPicker(r.id, id)}>Change</button><span className="muted"> · </span>
                                <button className="link danger" onClick={() => actions.remove(r, id)}>Remove</button>
                              </div>
                            </div>
                          </div>
                        ))}
                        <button className="link add-board" onClick={() => openPicker(r.id)}>Add another board</button>
                      </>
                    ) : <button className="btn sm primary" onClick={() => openPicker(r.id)}>Choose board</button>}
                  </td>
                  <td className="muted">{when(r.starts_at)}</td>
                  <td><DateTimeField value={Date.parse(r.due_at)} title="Change to extend the rental" onPick={(ms) => ms && actions.setDue(r, ms)} /></td>
                  <td><RentalStatus rental={r} /></td>
                  <td>
                    <div className="cell-acts">
                      {r.boards.length > 0 && <button className="btn sm" onClick={() => actions.markReturned(r)}>Mark returned</button>}
                      {me.role === "owner" && <button className="btn sm" onClick={() => actions.finish(r)}>Finish rental</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p className="empty">{fleet.rentals.length ? "No rentals match your search." : "No active rentals. Add one above."}</p>}
    </section>
  );
}
