"use client";

// History (SPEC 7.8): every returned rental, newest first, with search, From / To dates (on the start time)
// and totals for the filtered rentals. The table shows the latest 300; totals and the Excel export cover all.
import { useEffect, useState } from "react";
import { searchWords } from "@/lib/data";
import { createClient } from "@/lib/supabase/client";
import { fmtDur, when } from "@/lib/time";
import { Modal, useApp, type HistoryFilter } from "./app";
import DateTimeField from "./DateTimeField";
import { Icon } from "./icons";
import RentalChanges from "./RentalChanges";

const LIMIT = 300;
export type HistoryRow = {
  id: string; starts_at: string; due_at: string; ended_at: string; customer: string; phone: string;
  ended_by: string | null; boards: { id: string; name: string; type: string }[];
};
export type HistoryResult = { rentals: number; hours: number; average_minutes: number; late: number; rows: HistoryRow[] };

// The same filters as RPC arguments; "To" includes that whole day.
export const historyArgs = (f: HistoryFilter, limit: number) => ({
  p_from: f.from ? new Date(f.from).toISOString() : null,
  p_to: f.to ? new Date(f.to + 864e5).toISOString() : null,
  p_words: searchWords(f.query),
  p_limit: limit,
});
export const lateBy = (r: HistoryRow) => Math.max(0, Date.parse(r.ended_at) - Date.parse(r.due_at));

export default function HistoryView() {
  const db = createClient();
  const { me, fleet, history: f, setHistory, openBoard } = useApp();
  const [result, setResult] = useState<HistoryResult | null>(null);
  const [trail, setTrail] = useState<HistoryRow | null>(null); // the owner's "Changes" window
  const owner = me.role === "owner";

  useEffect(() => {
    const timer = setTimeout(() => {
      db.rpc("history_search", historyArgs(f, LIMIT)).then(({ data }) => data && setResult(data as HistoryResult));
    }, 150);
    return () => clearTimeout(timer);
  }, [db, f, fleet]); // fleet changes whenever a rental is returned anywhere

  const known = (id: string) => fleet?.boards.some((b) => b.id === id);
  const filtered = !!(f.query.trim() || f.from || f.to);
  return (
    <section>
      <div className="top"><div><h1>History</h1><p className="sub">Every returned rental.</p></div></div>
      <div className="toolbar">
        <input type="search" placeholder="Search customer, phone or board" value={f.query} onChange={(e) => setHistory({ ...f, query: e.target.value })} />
        <label><span className="label">From</span><DateTimeField kind="date" label="From date" value={f.from} onPick={(from) => setHistory({ ...f, from })} /></label>
        <label><span className="label">To</span><DateTimeField kind="date" label="To date" value={f.to} onPick={(to) => setHistory({ ...f, to })} /></label>
      </div>
      <div className="metrics">
        <div><span className="label">Rentals</span><b>{result?.rentals ?? "—"}</b></div>
        <div><span className="label">Hours on the water</span><b>{result?.hours ?? "—"}</b></div>
        <div><span className="label">Average rental</span><b>{result?.rentals ? fmtDur(result.average_minutes * 60000) : "—"}</b></div>
        <div><span className="label">Returned late</span><b>{result?.late ?? "—"}</b></div>
      </div>
      {!result ? <p className="empty">Loading…</p> : result.rows.length ? (
        <>
          <div className="panel table-wrap">
            <table>
              <thead><tr><th>Customer</th><th>Board</th><th>Start</th><th>Returned</th><th>Duration</th><th>Return</th><th>Returned by</th>{owner && <th></th>}</tr></thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.id}>
                    <td><b>{r.customer}</b><span className="muted">{r.phone}</span></td>
                    <td>
                      {r.boards.length ? r.boards.map((b, i) => (
                        <div key={`${b.id}:${i}`} className="hist-board">
                          {known(b.id) ? <button className="who" title="Board details" onClick={() => openBoard(b.id)}>{b.name}</button> : b.name}
                          <span className="muted">{b.type}</span>
                        </div>
                      )) : "—"}
                    </td>
                    <td className="muted">{when(r.starts_at)}</td>
                    <td className="muted">{when(r.ended_at)}</td>
                    <td>{fmtDur(Date.parse(r.ended_at) - Date.parse(r.starts_at))}</td>
                    <td>{lateBy(r) ? <span className="st late">Late {fmtDur(lateBy(r))}</span> : <span className="st ok">On time</span>}</td>
                    <td className="muted">{r.ended_by ?? "—"}</td>
                    {owner && <td><button className="link" onClick={() => setTrail(r)}>Changes</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.rows.length < result.rentals && (
            <p className="muted" style={{ marginTop: 10 }}>Showing the {LIMIT} most recent. Narrow the dates or search to see older ones; Export to Excel includes them all.</p>
          )}
        </>
      ) : <p className="empty">{filtered ? "No rentals in this range." : "Returned rentals will show up here."}</p>}
      {trail && (
        <Modal id="trailDlg" onClose={() => setTrail(null)}>
          <div className="dlg-head">
            <b style={{ flex: 1 }}>Changes · {trail.customer}, {when(trail.starts_at)}</b>
            <button className="icon-btn" title="Close" onClick={() => setTrail(null)}><Icon name="x" /></button>
          </div>
          <RentalChanges rentalId={trail.id} />
        </Modal>
      )}
    </section>
  );
}
