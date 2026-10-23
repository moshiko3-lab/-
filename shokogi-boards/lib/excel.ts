// Excel export helpers (SPEC 7.10). Dates go in as Excel serial numbers in Panama time:
// SheetJS's own Date handling is 36 seconds off.
const PANAMA_OFFSET = 5 * 36e5; // UTC-5 all year, see lib/time.ts

export const excelSerial = (ms: number) => (ms - PANAMA_OFFSET) / 864e5 + 25569;

export type Cell = string | number | { t: "n"; v: number; z: string };
export const dateCell = (t: string | null | undefined): Cell =>
  t ? { t: "n", v: excelSerial(Date.parse(t)), z: "dd/mm/yyyy hh:mm" } : "";

// Column widths fitted to the longest value (dates show as 16 characters).
export const fitColumns = (head: string[], rows: Cell[][]) =>
  head.map((h, i) => ({ wch: Math.max(h.length, ...rows.map((r) => (typeof r[i] === "object" ? 16 : String(r[i]).length))) + 2 }));
