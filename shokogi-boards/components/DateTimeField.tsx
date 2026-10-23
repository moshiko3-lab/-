"use client";

// Custom date-time picker (SPEC section 8): Monday-first month grid in Panama time, today underlined,
// hour + minute selects (5-minute steps that keep an exact minute like 48), Apply / Cancel.
// The date-only kind (History filters) picks a day straight away and has Today / Clear.
// Opens below the field (above when there's no room), works inside dialogs, closes on outside click and Esc.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { fromPanama, panamaParts, TZ, whenFull, type Parts } from "@/lib/time";
import { Icon } from "./icons";

const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
const two = (n: number) => String(n).padStart(2, "0");

function options(count: number, step: number, current: number) {
  const values = Array.from({ length: count / step }, (_, i) => i * step);
  if (!values.includes(current)) values.push(current); // keep an exact minute like 48
  return values.sort((a, b) => a - b).map((v) => <option key={v} value={v}>{two(v)}</option>);
}

type Kind = "datetime" | "date";
const midnight = (p: { y: number; m: number; d: number }) => fromPanama({ y: p.y, m: p.m, d: p.d, h: 0, mi: 0 });

function Calendar({ kind, anchor, value, onApply, onClose }: {
  kind: Kind; anchor: HTMLElement; value: number | null; onApply: (ms: number | null) => void; onClose: () => void;
}) {
  const start = panamaParts(value ?? Date.now());
  const [month, setMonth] = useState({ y: start.y, m: start.m });
  const [day, setDay] = useState(start);
  const [time, setTime] = useState({ h: start.h, mi: start.mi });
  const box = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const place = () => {
      const r = anchor.getBoundingClientRect(), cal = box.current!;
      const below = r.bottom + 4 + cal.offsetHeight <= innerHeight;
      cal.style.top = `${below ? r.bottom + 4 : Math.max(8, r.top - cal.offsetHeight - 4)}px`;
      cal.style.left = `${Math.max(8, Math.min(r.left, innerWidth - cal.offsetWidth - 8))}px`;
    };
    place();
    addEventListener("resize", place);
    addEventListener("scroll", place, true);
    return () => { removeEventListener("resize", place); removeEventListener("scroll", place, true); };
  }, [anchor, month]);

  useEffect(() => {
    const outside = (e: PointerEvent) => !box.current!.contains(e.target as Node) && !anchor.contains(e.target as Node) && onClose();
    // Esc closes the calendar only, not the dialog underneath.
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } };
    document.addEventListener("pointerdown", outside);
    addEventListener("keydown", esc, true);
    return () => { document.removeEventListener("pointerdown", outside); removeEventListener("keydown", esc, true); };
  }, [anchor, onClose]);

  const today = panamaParts(Date.now());
  const offset = (new Date(Date.UTC(month.y, month.m, 1)).getUTCDay() + 6) % 7; // Monday on or before the 1st
  const days = Array.from({ length: 42 }, (_, i) => {
    const t = new Date(Date.UTC(month.y, month.m, 1 - offset + i));
    return { y: t.getUTCFullYear(), m: t.getUTCMonth(), d: t.getUTCDate() };
  });
  const same = (a: { y: number; m: number; d: number }, b: { y: number; m: number; d: number }) => a.y === b.y && a.m === b.m && a.d === b.d;
  const shift = (n: number) => setMonth(({ y, m }) => ({ y: m + n < 0 ? y - 1 : m + n > 11 ? y + 1 : y, m: (m + n + 12) % 12 }));

  return (
    <div className="cal" ref={box} role="dialog" aria-label="Choose date and time">
      <div className="cal-h">
        <button type="button" className="icon-btn" aria-label="Previous month" onClick={() => shift(-1)}><Icon name="left" /></button>
        <b>{new Date(Date.UTC(month.y, month.m, 1)).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" })}</b>
        <button type="button" className="icon-btn" aria-label="Next month" onClick={() => shift(1)}><Icon name="right" /></button>
      </div>
      <div className="cal-g">
        {WEEKDAYS.map((w) => <span key={w}>{w}</span>)}
        {days.map((d) => (
          <button key={`${d.y}-${d.m}-${d.d}`} type="button" onClick={() => kind === "date" ? onApply(midnight(d)) : setDay({ ...day, ...d })}
            className={[d.m !== month.m && "out", same(d, today) && "now", (kind === "datetime" || value) && same(d, day) && "sel"].filter(Boolean).join(" ")}>
            {d.d}
          </button>
        ))}
      </div>
      {kind === "datetime" && <div className="cal-t">
        <span className="label">Time</span>
        <select aria-label="Hour" value={time.h} onChange={(e) => setTime({ ...time, h: +e.target.value })}>{options(24, 1, time.h)}</select>
        <b>:</b>
        <select aria-label="Minute" value={time.mi} onChange={(e) => setTime({ ...time, mi: +e.target.value })}>{options(60, 5, time.mi)}</select>
      </div>}
      <div className="cal-f">
        {kind === "datetime" ? <>
          <button type="button" className="btn sm ghost" onClick={onClose}>Cancel</button>
          <button type="button" className="btn sm primary" onClick={() => onApply(fromPanama({ ...day, ...time } as Parts))}>Apply</button>
        </> : <>
          <button type="button" className="btn sm ghost" onClick={() => onApply(null)}>Clear</button>
          <button type="button" className="btn sm" onClick={() => onApply(midnight(today))}>Today</button>
        </>}
      </div>
    </div>
  );
}

const dayText = (ms: number | null) => ms ? new Date(ms).toLocaleDateString("en-GB", { timeZone: TZ, day: "numeric", month: "short", year: "numeric" }) : "Any date";

export default function DateTimeField({ kind = "datetime", value, onPick, title, label }: {
  kind?: Kind; value: number | null; onPick: (ms: number | null) => void; title?: string; label?: string;
}) {
  const [open, setOpen] = useState(false);
  const field = useRef<HTMLButtonElement>(null);
  return (
    <>
      <button type="button" className="dt" ref={field} title={title} aria-label={label} aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="cal" /><span>{kind === "date" ? dayText(value) : whenFull(value)}</span>
      </button>
      {open && <Calendar kind={kind} anchor={field.current!} value={value} onClose={() => setOpen(false)} onApply={(ms) => { setOpen(false); onPick(ms); }} />}
    </>
  );
}
