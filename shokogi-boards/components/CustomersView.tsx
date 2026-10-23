"use client";

// Customers page (SPEC 7.5): totals, search by name or phone, everyone who rented. Renting now first, then
// most recent visit. Runs in the database so it stays fast after years of customers.
import { useEffect, useState } from "react";
import { searchWords } from "@/lib/data";
import { createClient } from "@/lib/supabase/client";
import { when } from "@/lib/time";
import { useApp } from "./app";
import { RentalStatus } from "./rentals";

const LIMIT = 200;
type Row = { id: string; name: string; phone: string; rentals: number; hours: number; late_returns: number; last_visit: string | null };

export default function CustomersView() {
  const db = createClient();
  const { fleet, openProfile } = useApp();
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [totals, setTotals] = useState({ all: 0, returning: 0, now: 0 });

  useEffect(() => {
    const timer = setTimeout(async () => {
      let req = db.from("customer_stats").select("id, name, phone, rentals, hours, late_returns, last_visit")
        .order("renting_now", { ascending: false }).order("last_visit", { ascending: false, nullsFirst: false }).limit(LIMIT);
      for (const w of searchWords(query)) req = req.like("search", `%${w}%`);
      const { data } = await req;
      if (data) setRows(data as Row[]);
    }, 150);
    return () => clearTimeout(timer);
  }, [db, query, fleet]);

  useEffect(() => {
    const count = (filter?: (q: ReturnType<typeof base>) => ReturnType<typeof base>) => (filter ? filter(base()) : base()).then((r) => r.count ?? 0);
    const base = () => db.from("customer_stats").select("id", { count: "exact", head: true });
    Promise.all([count(), count((q) => q.gt("rentals", 1)), count((q) => q.eq("renting_now", true))])
      .then(([all, returning, now]) => setTotals({ all, returning, now }));
  }, [db, fleet]);

  const active = (id: string) => fleet?.rentals.find((r) => r.customer.id === id);
  return (
    <section>
      <div className="top"><div><h1>Customers</h1><p className="sub">Everyone who has rented, matched by phone number (or by name when there is none).</p></div></div>
      <div className="metrics">
        <div><span className="label">Customers</span><b>{totals.all}</b></div>
        <div><span className="label">Returning customers</span><b>{totals.returning}</b></div>
        <div><span className="label">Renting now</span><b>{totals.now}</b></div>
      </div>
      <div className="toolbar"><input type="search" placeholder="Search name or phone" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
      {!rows ? <p className="empty">Loading…</p> : rows.length ? (
        <>
          <div className="panel table-wrap">
            <table>
              <thead><tr><th>Customer</th><th>Rentals</th><th>Hours</th><th>Late returns</th><th>Last visit</th><th>Status</th></tr></thead>
              <tbody>
                {rows.map((c) => {
                  const r = active(c.id);
                  return (
                    <tr key={c.id} className="clickable" onClick={() => openProfile(c.id)}>
                      <td><button className="who">{c.name}</button><span className="muted">{c.phone}</span></td>
                      <td>{c.rentals}</td>
                      <td>{c.hours}</td>
                      <td>{c.late_returns ? <span className="st late">{c.late_returns}</span> : <span className="muted">0</span>}</td>
                      <td className="muted">{when(c.last_visit)}</td>
                      <td>{r ? <RentalStatus rental={r} /> : <span className="muted">—</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {rows.length === LIMIT && <p className="muted" style={{ marginTop: 10 }}>Showing the {LIMIT} most recent customers. Search to find anyone else.</p>}
        </>
      ) : <p className="empty">{query ? "No customers match your search." : "Customers appear here after their first rental."}</p>}
    </section>
  );
}
