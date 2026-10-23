// The three tables shared by the Excel export and the Google Sheets mirror: Rented now, history, Boards.
// Dates come out as { date: ms }; each writer turns them into its own date cells.
import { byName } from "./boards";
import { copies, rentedByBoard, type Board, type BoardStats, type BoardType, type Rental } from "./data";

export type Value = string | number | { date: number };
export type ReturnedRental = {
  starts_at: string; due_at: string; ended_at: string; customer: string; phone: string;
  boards: { id: string; name: string; type: string }[];
};
export type ReportInput = {
  rentals: Rental[]; boards: Board[]; types: BoardType[]; stats: Map<string, BoardStats>; history: ReturnedRental[]; now: number;
};

const at = (t: string) => ({ date: Date.parse(t) });
export const minutesLate = (h: ReturnedRental) => Math.round(Math.max(0, Date.parse(h.ended_at) - Date.parse(h.due_at)) / 6e4);

export const RENTED_HEAD = ["Customer", "Phone", "Board", "Type", "Start", "Back by", "Status"];
export const HISTORY_HEAD = ["Customer", "Phone", "Board", "Type", "Start", "Returned", "Hours", "Minutes late"];
export const BOARDS_HEAD = ["Board", "Type", "Quantity", "Available", "Rented", "In repair", "Rented by", "Times rented"];

export function report({ rentals, boards, types, stats, history, now }: ReportInput) {
  const board = (id: string) => boards.find((b) => b.id === id);
  const type = (id?: string) => types.find((t) => t.id === id)?.name ?? "";
  const rentedBy = rentedByBoard(rentals);

  // One row per board out (a family is several rows); customers still waiting get one row without a board.
  const rented: Value[][] = [...rentals].sort((a, b) => a.due_at.localeCompare(b.due_at)).flatMap((r) => {
    const status = !r.boards.length ? "Needs a board" : Date.parse(r.due_at) < now ? "Overdue" : "On time";
    const row = (name: string, typeName: string): Value[] =>
      [r.customer.name, r.customer.phone, name, typeName, at(r.starts_at), at(r.due_at), status];
    return r.boards.length ? r.boards.map((id) => row(board(id)?.name ?? "", type(board(id)?.type_id))) : [row("", "")];
  });

  const returned: Value[][] = history.map((h) => [
    h.customer, h.phone, h.boards.map((b) => b.name).join(", "), [...new Set(h.boards.map((b) => b.type))].join(", "),
    at(h.starts_at), at(h.ended_at), Math.round(((Date.parse(h.ended_at) - Date.parse(h.starts_at)) / 36e5) * 10) / 10, minutesLate(h),
  ]);

  const fleet = [...boards].sort(byName);
  // One row per board; a board with several identical copies counts them.
  const boardRows: Value[][] = fleet.map((b) => {
    const c = copies(rentedBy, b);
    return [b.name, type(b.type_id), b.quantity, c.free, c.out, c.fix, c.renters.map((r) => r.customer.name).join(", "), stats.get(b.id)?.times_rented ?? 0];
  });

  return { rented, returned, boards: boardRows, fleet };
}
