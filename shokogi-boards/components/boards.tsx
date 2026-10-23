"use client";

// Pieces shared by the Boards page and Board details: status label, repair buttons and the board actions.
import { copies, errorText, type Board, type Fleet } from "@/lib/data";
import { setBoardPhoto } from "@/lib/photos";
import { createClient } from "@/lib/supabase/client";
import { useApp } from "./app";

export type BoardState = "free" | "out" | "fix";
// Types in order; "Other" only when it has boards.
export const shownTypes = (fleet: Fleet) => fleet.types.filter((t) => !t.is_system || fleet.boards.some((b) => b.type_id === t.id));
// How many copies of a board are in a state; a board with several copies can be in more than one.
export const inState = (fleet: Fleet, b: Board, state: BoardState) => copies(fleet.rentedBy, b)[state];

export function BoardStatus({ fleet, board, withName }: { fleet: Fleet; board: Board; withName?: boolean }) {
  const { out, fix, free, renters } = copies(fleet.rentedBy, board);
  const names = renters.map((r) => r.customer.name).join(", ");
  if (board.quantity > 1) return <>
    <span className={`st ${free ? "ok" : out ? "busy" : "fix"}`} title={out ? `Rented: ${names}` : undefined}>{free} of {board.quantity} available</span>
    {fix > 0 && <> <span className="st fix">{fix} in repair</span></>}
  </>;
  if (out) return <span className="st busy" title={names}>{withName ? `Rented, ${names}` : "Rented"}</span>;
  return fix ? <span className="st fix">In repair</span> : <span className="st ok">Available</span>;
}

// Repair moves one copy at a time; only free copies can go, so a single rented board shows neither button.
export function RepairButtons({ fleet, board, small }: { fleet: Fleet; board: Board; small?: boolean }) {
  const actions = useBoardActions();
  const { free, fix } = copies(fleet.rentedBy, board);
  const cls = small ? "btn sm" : "btn", one = board.quantity > 1 ? "One board at a time" : undefined;
  return <>
    {fix > 0 && <button className={cls} title={one} onClick={() => actions.update(board, { in_repair: fix - 1 })}>Back in service</button>}
    {free > 0 && <button className={cls} title={one} onClick={() => actions.update(board, { in_repair: fix + 1 })}>{small ? "Repair" : "Send to repair"}</button>}
  </>;
}

// Every action refreshes the data afterwards and shows a toast when the save failed, so the screen never lies.
export function useBoardActions() {
  const db = createClient();
  const { refresh, toast, ask, scheduleSync } = useApp();
  async function run(action: () => PromiseLike<unknown>, failed: string) {
    try {
      await action();
    } catch (e) {
      toast(errorText(e, failed), "error");
    }
    scheduleSync();
    await refresh();
  }
  return {
    update: (b: Board, changes: Partial<Board>) =>
      run(() => db.from("boards").update(changes).eq("id", b.id).throwOnError(), "Couldn't save the board. Check the connection and try again."),
    setPhoto: (b: Board, file: File) =>
      run(() => setBoardPhoto(db, b, file), "Couldn't save this photo. HEIC photos need an internet connection to convert."),
    async remove(b: Board) {
      if (!(await ask({ title: "Delete board", text: `Delete "${b.name}"? It disappears from the fleet; its rental history is kept.`, ok: "Delete board", danger: true }))) return false;
      await run(() => db.from("boards").update({ deleted_at: new Date().toISOString() }).eq("id", b.id).throwOnError(), "Couldn't delete the board.");
      return true;
    },
  };
}
