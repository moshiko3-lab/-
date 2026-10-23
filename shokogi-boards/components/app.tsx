"use client";

// App-wide state and UI: who is signed in, the shared data (kept live across devices), a 30-second clock,
// toasts, confirm questions, the dialog stack and the overdue alert. Custom dialogs instead of
// alert/confirm/prompt (SPEC section 8).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import type { Profile } from "@/lib/auth";
import { isOverdue, loadFleet, type Fleet } from "@/lib/data";
import { createClient } from "@/lib/supabase/client";
import BoardDialog from "./BoardDialog";
import OverdueAlert from "./OverdueAlert";
import Picker from "./Picker";
import ProfileDialog from "./ProfileDialog";
import RentalDialog from "./RentalDialog";

type Ask = { title: string; text?: string; ok?: string; danger?: boolean };
// History filters live here so they survive leaving the page, and the Excel export uses the same ones.
export type HistoryFilter = { query: string; from: number | null; to: number | null };
type Dialog = { kind: "board" | "rental" | "profile"; id: string } | { kind: "picker"; id: string; replace?: string };
type App = {
  me: Profile;
  fleet: Fleet | null;
  now: number;
  refresh: () => Promise<void>;
  toast: (msg: string, kind?: "error" | "") => void;
  ask: (q: Ask) => Promise<boolean>;
  openBoard: (id: string) => void;
  openRental: (id: string) => void;
  openProfile: (customerId: string) => void;
  openPicker: (rentalId: string, replace?: string) => void;
  history: HistoryFilter;
  setHistory: (f: HistoryFilter) => void;
  scheduleSync: () => void;
  syncNow: () => Promise<void>;
};

const AppContext = createContext<App | null>(null);
export const useApp = () => useContext(AppContext)!;

// A native modal <dialog>: stacks on top of open ones, Esc closes the top one, a click on the backdrop closes it.
// The element marked data-autofocus gets the focus when it opens.
export function Modal({ id, className, onClose, onCancel, children }: {
  id?: string; className?: string; onClose: () => void; onCancel?: (e: React.SyntheticEvent) => void; children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current!;
    if (!d.open) d.showModal();
    d.querySelector<HTMLElement>("[data-autofocus]")?.focus();
  }, []);
  return (
    <dialog ref={ref} id={id} className={className} onClose={onClose} onCancel={onCancel}
      onClick={(e) => e.target === ref.current && ref.current.close()}>
      {children}
    </dialog>
  );
}

export function AppProvider({ me, children }: { me: Profile; children: React.ReactNode }) {
  const db = createClient();
  const path = usePathname();
  const [fleet, setFleet] = useState<Fleet | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [toasts, setToasts] = useState<{ id: number; msg: string; kind: string }[]>([]);
  const [question, setQuestion] = useState<(Ask & { resolve: (yes: boolean) => void }) | null>(null);
  const [dialogs, setDialogs] = useState<(Dialog & { key: number })[]>([]);
  const [alertOpen, setAlertOpen] = useState(false);
  const [history, setHistory] = useState<HistoryFilter>({ query: "", from: null, to: null });
  const toastBox = useRef<HTMLDivElement>(null);
  const loads = useRef(0);
  const alerted = useRef(new Set<string>()); // overdue rentals already shown during this visit

  const toast = useCallback((msg: string, kind: "error" | "" = "") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const refresh = useCallback(async () => {
    const n = ++loads.current;
    try {
      const f = await loadFleet(db, me.role === "instructor");
      if (n === loads.current) setFleet(f); // an older, slower load never overwrites a newer one
    } catch {
      toast("Couldn't load the latest data. Check the connection.", "error");
    }
  }, [db, toast, me.role]);

  // Live updates (SPEC 7.13): any change on any device reloads the shared data within a second.
  // Also on returning to the tab, since a sleeping phone can miss messages.
  useEffect(() => {
    refresh();
    let timer: ReturnType<typeof setTimeout>;
    const soon = () => { clearTimeout(timer); timer = setTimeout(refresh, 300); };
    const channel = db.channel("changes").on("postgres_changes", { event: "*", schema: "public" }, soon).subscribe();
    const visible = () => document.visibilityState === "visible" && refresh();
    document.addEventListener("visibilitychange", visible);
    const clock = setInterval(() => setNow(Date.now()), 30000); // countdowns and overdue checks
    return () => {
      clearTimeout(timer);
      clearInterval(clock);
      document.removeEventListener("visibilitychange", visible);
      db.removeChannel(channel);
    };
  }, [db, refresh]);

  // Re-shown on every change so the toasts sit above any open dialog.
  useEffect(() => {
    const box = toastBox.current!;
    if (box.matches(":popover-open")) box.hidePopover();
    if (toasts.length) box.showPopover();
  }, [toasts]);

  const ask = useCallback((q: Ask) => new Promise<boolean>((resolve) => setQuestion({ ...q, resolve })), []);
  // Answered from the buttons (and Esc), never from the dialog's "close" event, which can arrive late.
  const answer = (yes: boolean) => { question?.resolve(yes); setQuestion(null); };

  // Opening a dialog that is already open brings it back to the top instead of stacking a copy.
  const open = useCallback((d: Dialog) => setDialogs((all) => {
    const i = all.findIndex((x) => x.kind === d.kind && x.id === d.id && d.kind !== "picker");
    return i >= 0 ? all.slice(0, i + 1) : [...all, { ...d, key: Date.now() + Math.random() }];
  }), []);
  const openBoard = useCallback((id: string) => open({ kind: "board", id }), [open]);
  const openRental = useCallback((id: string) => open({ kind: "rental", id }), [open]);
  const openProfile = useCallback((id: string) => open({ kind: "profile", id }), [open]);
  const openPicker = useCallback((id: string, replace?: string) => open({ kind: "picker", id, replace }), [open]);
  const close = (key: number) => setDialogs((all) => all.filter((x) => x.key !== key));

  // Overdue alert (SPEC 7.14): pops up when the app opens with anything overdue, and again whenever another
  // rental runs late (or runs late again after an extension). It never interrupts another open dialog, it waits.
  // Not for instructors: it offers extensions, which aren't theirs to give; their cards show overdue in red.
  const late = fleet ? fleet.rentals.filter((r) => isOverdue(r, now)) : [];
  const lateKeys = late.map((r) => `${r.id}@${r.due_at}`).join();
  const instructor = me.role === "instructor";
  useEffect(() => {
    if (!lateKeys || instructor) return setAlertOpen(false);
    if (alertOpen || dialogs.length || question) return;
    const keys = lateKeys.split(",");
    if (keys.some((k) => !alerted.current.has(k))) {
      keys.forEach((k) => alerted.current.add(k));
      setAlertOpen(true);
    }
  }, [lateKeys, instructor, alertOpen, dialogs.length, question]);

  // Tab title shows the count; re-applied after each navigation, which resets the title.
  useEffect(() => {
    document.title = late.length ? `(${late.length}) Overdue · Shokogi Boards` : "Shokogi Boards";
  }, [late.length, path]);

  // Google Sheets: the device that made a change asks for a sync ~5 s later (several quick changes, one sync).
  const syncTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const syncNow = useCallback(async () => {
    clearTimeout(syncTimer.current);
    await fetch("/api/sheets/sync", { method: "POST" }).catch(() => null); // the result arrives through sheets_status
  }, []);
  const scheduleSync = useCallback(() => {
    clearTimeout(syncTimer.current);
    syncTimer.current = setTimeout(syncNow, 5000);
  }, [syncNow]);

  const value = useMemo(() => ({ me, fleet, now, refresh, toast, ask, openBoard, openRental, openProfile, openPicker, history, setHistory, scheduleSync, syncNow }),
    [me, fleet, now, refresh, toast, ask, openBoard, openRental, openProfile, openPicker, history, scheduleSync, syncNow]);
  return (
    <AppContext.Provider value={value}>
      {children}
      {alertOpen && <OverdueAlert onClose={() => setAlertOpen(false)} />}
      {dialogs.map((d) => {
        const onClose = () => close(d.key);
        if (d.kind === "picker") return <Picker key={d.key} rentalId={d.id} replace={d.replace} onClose={onClose} />;
        if (d.kind === "board") return <BoardDialog key={d.key} id={d.id} onClose={onClose} />;
        if (d.kind === "rental") return <RentalDialog key={d.key} id={d.id} onClose={onClose} />;
        return <ProfileDialog key={d.key} id={d.id} onClose={onClose} />;
      })}
      {question && (
        <Modal className="ask" onClose={() => answer(false)} onCancel={(e) => { e.preventDefault(); answer(false); }}>
          <form onSubmit={(e) => { e.preventDefault(); answer(true); }}>
            <h3>{question.title}</h3>
            {question.text && <p>{question.text}</p>}
            <div className="ask-f">{/* OK comes first in the markup so Enter confirms; destructive questions focus Cancel */}
              <button className={`btn primary${question.danger ? " danger" : ""}`} data-autofocus={question.danger ? undefined : true}>
                {question.ok ?? "OK"}
              </button>
              <button type="button" className="btn" data-autofocus={question.danger ? true : undefined} onClick={() => answer(false)}>Cancel</button>
            </div>
          </form>
        </Modal>
      )}
      <div id="toasts" popover="manual" ref={toastBox}>
        {toasts.map((t) => <div key={t.id} className={`toast ${t.kind}`} role="status">{t.msg}</div>)}
      </div>
    </AppContext.Provider>
  );
}
