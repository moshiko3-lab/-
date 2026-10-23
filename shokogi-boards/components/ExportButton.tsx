"use client";

// Export to Excel (SPEC 7.10, owner only): one workbook with Rented now, Rental history (with the History
// page's current filters) and Boards. SheetJS loads only when the button is pressed.
import { useState } from "react";
import { dateCell, fitColumns, type Cell } from "@/lib/excel";
import { BOARDS_HEAD, HISTORY_HEAD, RENTED_HEAD, report, type Value } from "@/lib/report";
import { createClient } from "@/lib/supabase/client";
import { panamaParts } from "@/lib/time";
import { useApp } from "./app";
import { historyArgs, type HistoryResult } from "./HistoryView";
import { Icon } from "./icons";

const cell = (v: Value): Cell => (typeof v === "object" ? dateCell(new Date(v.date).toISOString()) : v);

export default function ExportButton() {
  const db = createClient();
  const { fleet, history, toast } = useApp();
  const [busy, setBusy] = useState(false);

  async function exportExcel() {
    if (!fleet) return;
    setBusy(true);
    try {
      const [XLSX, { data, error }] = await Promise.all([import("xlsx"), db.rpc("history_search", historyArgs(history, 1_000_000))]);
      if (error) throw error;
      const now = Date.now();
      const tables = report({ ...fleet, history: (data as HistoryResult).rows, now });
      const wb = XLSX.utils.book_new();
      const add = (head: string[], rows: Value[][], name: string) => {
        const cells = rows.map((r) => r.map(cell));
        const ws = XLSX.utils.aoa_to_sheet([head, ...cells]);
        ws["!cols"] = fitColumns(head, cells);
        XLSX.utils.book_append_sheet(wb, ws, name);
      };
      add(RENTED_HEAD, tables.rented, "Rented now");
      add(HISTORY_HEAD, tables.returned, "Rental history"); // Excel reserves the sheet name "History"
      add(BOARDS_HEAD, tables.boards, "Boards");
      const p = panamaParts(now);
      XLSX.writeFile(wb, `Shokogi-boards-${p.y}-${String(p.m + 1).padStart(2, "0")}-${String(p.d).padStart(2, "0")}.xlsx`);
    } catch (e) {
      console.error("Excel export failed", e);
      toast("Couldn't create the Excel file. Check the connection and try again.", "error");
    }
    setBusy(false);
  }

  return (
    <button className="export" disabled={busy} onClick={exportExcel}>
      <Icon name="download" /><span>{busy ? "Preparing…" : "Export to Excel"}</span>
    </button>
  );
}
