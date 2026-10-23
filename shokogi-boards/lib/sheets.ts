// Google Sheets mirror (SPEC 7.11): the app's tables, written one way into a "Shokogi Boards" spreadsheet that the
// app creates (inside a "Shokogi Boards" folder) in the Google Drive of the account connected in Settings. Server only.
//
// Each sync is ONE batchUpdate, so it is all-or-nothing: data rows are written under the headers and every older
// row below is cleared in the same request. Text stays text (phone numbers keep their leading zero), dates are
// real dates in the sheet's Panama time zone, and the Boards tab gets =IMAGE() of each board's thumb.
import type { SupabaseClient } from "@supabase/supabase-js";
import { loadFleet } from "./data";
import { excelSerial } from "./excel";
import { accessToken, getConnection } from "./google";
import { photoUrl } from "./photos";
import { BOARDS_HEAD, report, type ReturnedRental, type Value } from "./report";
import { dataFormats, newSpreadsheet, SHEET_IDS } from "./sheet-template";

const SHEETS = "https://sheets.googleapis.com/v4/spreadsheets";
const DRIVE = "https://www.googleapis.com/drive/v3/files";
export type SheetInfo = { spreadsheet_id: string; url: string; folder_url: string; email: string };

type Cell = Value | { formula: string } | null;
export function cellData(v: Cell) {
  if (v === null || v === "") return {}; // clears the cell
  if (typeof v === "number") return { userEnteredValue: { numberValue: v } };
  if (typeof v === "string") return { userEnteredValue: { stringValue: v } };
  if ("formula" in v) return { userEnteredValue: { formulaValue: v.formula } };
  return { userEnteredValue: { numberValue: excelSerial(v.date) } }; // shown as a date by the column's format
}

// Rows under the header of one tab: grows the tab when needed, then writes the data and blanks out the rest.
export function tabRequests(sheetId: number, rowCount: number, rows: Cell[][], width: number, rowHeight?: number) {
  const requests: object[] = [];
  const needed = rows.length + 1;
  if (needed > rowCount) requests.push({ appendDimension: { sheetId, dimension: "ROWS", length: needed - rowCount } });
  const all = Array.from({ length: Math.max(rowCount, needed) - 1 }, (_, i) => rows[i] ?? Array<Cell>(width).fill(null));
  requests.push({ updateCells: { start: { sheetId, rowIndex: 1, columnIndex: 0 }, rows: all.map((r) => ({ values: r.map(cellData) })), fields: "userEnteredValue" } });
  if (rowHeight && rows.length)
    requests.push({ updateDimensionProperties: { range: { sheetId, dimension: "ROWS", startIndex: 1, endIndex: needed }, properties: { pixelSize: rowHeight }, fields: "pixelSize" } });
  return requests;
}

async function google(url: string, token: string, init: RequestInit = {}) {
  const res = await fetch(url, { ...init, headers: { authorization: `Bearer ${token}`, "content-type": "application/json" } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error?.message ?? `Google answered ${res.status}`);
  return body;
}

// The connected account's sheet: the one already made for it, or a new folder + sheet in its Drive.
export async function ensureSheet(db: SupabaseClient, token: string, email: string): Promise<SheetInfo> {
  const { data } = await db.from("app_settings").select("value").eq("key", "sheets").maybeSingle();
  const current = data?.value as SheetInfo | undefined;
  if (current?.email === email && (await google(`${SHEETS}/${current.spreadsheet_id}?fields=spreadsheetId`, token).then(() => true, () => false)))
    return current;

  const folder = await google(DRIVE, token, { method: "POST", body: JSON.stringify({ name: "Shokogi Boards", mimeType: "application/vnd.google-apps.folder" }) });
  const sheet = await google(SHEETS, token, { method: "POST", body: JSON.stringify(newSpreadsheet()) });
  const { parents } = await google(`${DRIVE}/${sheet.spreadsheetId}?fields=parents`, token);
  await google(`${DRIVE}/${sheet.spreadsheetId}?addParents=${folder.id}&removeParents=${(parents ?? []).join(",")}`, token, { method: "PATCH", body: "{}" });
  const info = { spreadsheet_id: sheet.spreadsheetId, url: sheet.spreadsheetUrl, folder_url: `https://drive.google.com/drive/folders/${folder.id}`, email };
  await db.from("app_settings").upsert({ key: "sheets", value: info }).throwOnError();
  return info;
}

// `db` must see everything (the server's full-access client).
export async function syncSheets(db: SupabaseClient) {
  const connection = await getConnection(db);
  const { data: sheetRow } = await db.from("app_settings").select("value").eq("key", "sheets").maybeSingle();
  if (!connection || !sheetRow) throw new Error("Google Sheets is not connected yet.");
  const sheet = sheetRow.value as SheetInfo;

  const [fleet, history] = await Promise.all([
    loadFleet(db),
    db.rpc("history_search", { p_from: null, p_to: null, p_words: [], p_limit: 1_000_000 }),
  ]);
  if (history.error) throw new Error(history.error.message);
  const now = Date.now();
  const tables = report({ ...fleet, history: (history.data as { rows: ReturnedRental[] }).rows, now });

  const token = await accessToken(connection);
  const api = `${SHEETS}/${sheet.spreadsheet_id}`;
  const meta = await google(`${api}?fields=sheets.properties(sheetId,gridProperties.rowCount)`, token);
  // ponytail: tabs are found by the ids the app gave them; a tab deleted by hand stops the sync with Google's message.
  const rows = (id: number) => meta.sheets.find((s: { properties: { sheetId: number } }) => s.properties.sheetId === id)?.properties.gridProperties.rowCount ?? 1;
  const boardRows: Cell[][] = tables.fleet.map((b, i) => [b.thumb_path ? { formula: `=IMAGE("${photoUrl(b.thumb_path)}")` } : null, ...tables.boards[i]]);
  const requests = [
    ...tabRequests(SHEET_IDS["Rented now"], rows(SHEET_IDS["Rented now"]), tables.rented, 7),
    ...tabRequests(SHEET_IDS.History, rows(SHEET_IDS.History), tables.returned, 8),
    ...tabRequests(SHEET_IDS.Boards, rows(SHEET_IDS.Boards), boardRows, BOARDS_HEAD.length + 1, 90),
    ...dataFormats(),
    { updateCells: { start: { sheetId: SHEET_IDS.Dashboard, rowIndex: 1, columnIndex: 1 }, rows: [{ values: [cellData({ date: now })] }], fields: "userEnteredValue" } },
  ];
  await google(`${api}:batchUpdate`, token, { method: "POST", body: JSON.stringify({ requests }) });
  return { rented: tables.rented.length, history: tables.returned.length, boards: boardRows.length };
}

// Sync and record the outcome in app_settings "sheets_status", which the sidebar shows on every device.
export async function syncAndRecord(db: SupabaseClient) {
  const at = new Date().toISOString();
  try {
    const counts = await syncSheets(db);
    await db.from("app_settings").upsert({ key: "sheets_status", value: { at, error: null } });
    return { ok: true as const, ...counts };
  } catch (e) {
    const error = (e as Error).message;
    await db.from("app_settings").upsert({ key: "sheets_status", value: { at, error } });
    return { ok: false as const, error };
  }
}
