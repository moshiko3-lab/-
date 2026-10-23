"use client";

// Pieces shared by every screen that shows rentals: status with countdown, board thumbnails, rental actions.
import { errorText, type Board, type Rental } from "@/lib/data";
import { photoUrl } from "@/lib/photos";
import { createClient } from "@/lib/supabase/client";
import { timeLeft, when } from "@/lib/time";
import { useApp } from "./app";

// "1h 15m left" / "Overdue 20m" (red) / "Needs a board" (amber). `now` ticks every 30 s in the app provider.
export function RentalStatus({ rental }: { rental: Rental }) {
  const { now } = useApp();
  if (!rental.boards.length) return <span className="st wait">Needs a board</span>;
  const due = Date.parse(rental.due_at);
  return <span className={`st ${due < now ? "late" : "busy"}`}>{timeLeft(due, now)}</span>;
}

export function BoardThumb({ board }: { board?: Board }) {
  const { openBoard } = useApp();
  if (!board) return <span className="thumb" />;
  return (
    <button className="thumb-btn" title="Board details" onClick={() => openBoard(board.id)}>
      {board.thumb_path ? <img className="thumb" src={photoUrl(board.thumb_path)} alt="" loading="lazy" /> : <span className="thumb" />}
    </button>
  );
}

// Every action refreshes the shared data afterwards and shows a toast when the save failed.
export function useRentalActions() {
  const db = createClient();
  const { refresh: reload, toast, ask, scheduleSync } = useApp();
  const refresh = () => { scheduleSync(); return reload(); }; // every rental change also goes to Google Sheets
  async function run(action: () => PromiseLike<{ error: unknown }>, failed: string) {
    const { error } = await action();
    if (error) toast(errorText(error, failed), "error");
    await refresh();
    return !error;
  }
  return {
    async create(name: string, phone: string, minutes: number) {
      const { data, error } = await db.rpc("create_rental", { p_name: name, p_phone: phone, p_minutes: minutes });
      if (error) toast(errorText(error, "Couldn't add the rental. Check the connection and try again."), "error");
      await refresh();
      return error ? null : (data as string);
    },
    // false when its last free copy was just handed out on another device; the caller keeps the picker open.
    async assign(rental: Rental, boardId: string, replace?: string) {
      const { error } = await db.rpc("assign_board", { p_rental: rental.id, p_board: boardId, p_replace: replace ?? null });
      if (error) toast(errorText(error, "Couldn't save the board. Check the connection and try again."), "error");
      await refresh();
      return !error;
    },
    remove: (rental: Rental, boardId: string) =>
      run(() => db.rpc("remove_board", { p_rental: rental.id, p_board: boardId }), "Couldn't remove the board."),
    setDue: (rental: Rental, ms: number) =>
      run(() => db.from("rentals").update({ due_at: new Date(ms).toISOString() }).eq("id", rental.id), "Couldn't change the return time."),
    extend: (rental: Rental, minutes: number) =>
      run(() => db.from("rentals").update({ due_at: new Date(Date.now() + minutes * 60000).toISOString() }).eq("id", rental.id),
        "Couldn't extend the rental."),
    // For rentals with boards out. The boards come back; with time left the customer stays under "Needs a board"
    // until the rental ends (they may take another board), once the time is up it ends (return_rental decides the same).
    async markReturned(rental: Rental) {
      const one = rental.boards.length === 1, name = rental.customer.name;
      const text = Date.parse(rental.due_at) > Date.now()
        ? `${one ? "The board becomes" : "The boards become"} available. ${name} has time until ${when(rental.due_at)}, so they stay under "Needs a board" until then.`
        : `End ${name}'s rental? It moves to History and ${one ? "the board becomes" : "the boards become"} available.`;
      if (!(await ask({ title: "Mark as returned", text, ok: "Mark returned" }))) return false;
      return run(() => db.rpc("return_rental", { p_rental: rental.id }), "Couldn't mark the rental as returned.");
    },
    // Owner only: the rental moves to History now, time left or not.
    async finish(rental: Rental) {
      const left = Date.parse(rental.due_at) > Date.now() ? `, although they have time until ${when(rental.due_at)}` : "";
      const boards = rental.boards.length ? " Their boards become available." : "";
      if (!(await ask({ title: "Finish rental", text: `${rental.customer.name}'s rental moves to History now${left}.${boards}`, ok: "Finish rental", danger: true }))) return false;
      return run(() => db.rpc("finish_rental", { p_rental: rental.id }), "Couldn't finish the rental.");
    },
    async updateCustomer(customerId: string, changes: Partial<{ name: string; phone: string; email: string; notes: string }>) {
      const { error } = await db.from("customers").update(changes).eq("id", customerId);
      if ((error as { code?: string } | null)?.code === "23505") toast("Another customer already has this phone number.", "error");
      else if (error) toast("Couldn't save the customer. Check the connection and try again.", "error");
      await refresh();
      return !error;
    },
  };
}
