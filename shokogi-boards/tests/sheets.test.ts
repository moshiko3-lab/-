import { expect, test } from "vitest";
import { excelSerial } from "../lib/excel";
import { BOARDS_HEAD, HISTORY_HEAD, RENTED_HEAD, report } from "../lib/report";
import { dataFormats, newSpreadsheet } from "../lib/sheet-template";
import { cellData, tabRequests } from "../lib/sheets";

test("sheet cells: text stays text, dates are real dates, formulas stay formulas, blanks clear", () => {
  expect(cellData("0526785196")).toEqual({ userEnteredValue: { stringValue: "0526785196" } }); // keeps the leading zero
  expect(cellData("+1 415 555 0134")).toEqual({ userEnteredValue: { stringValue: "+1 415 555 0134" } }); // not a formula
  expect(cellData(3.5)).toEqual({ userEnteredValue: { numberValue: 3.5 } });
  const t = Date.UTC(2026, 9, 19, 22, 30);
  expect(cellData({ date: t })).toEqual({ userEnteredValue: { numberValue: excelSerial(t) } }); // the column shows it as a date
  expect(cellData({ formula: '=IMAGE("x")' })).toEqual({ userEnteredValue: { formulaValue: '=IMAGE("x")' } });
  expect(cellData(null)).toEqual({});
  expect(cellData("")).toEqual({});
});

test("a tab is rewritten in one go: data, then every old row below is cleared", () => {
  const [update] = tabRequests(7, 5, [["a", 1], ["b", 2]], 2) as { updateCells: { rows: { values: object[] }[] } }[];
  expect(update.updateCells.rows).toHaveLength(4); // rows 2-5 of a 5-row tab
  expect(update.updateCells.rows[2].values).toEqual([{}, {}]);
});

test("a tab grows when there are more rows than it has", () => {
  const rows = Array.from({ length: 6 }, (_, i) => [`r${i}`]);
  const [grow, update, height] = tabRequests(3, 4, rows, 1, 90) as Record<string, { length?: number; rows?: unknown[]; range?: { endIndex: number } }>[];
  expect(grow.appendDimension.length).toBe(3); // header + 6 rows = 7 > 4
  expect(update.updateCells.rows).toHaveLength(6);
  expect(height.updateDimensionProperties.range!.endIndex).toBe(7);
});

test("the new spreadsheet has the original's tabs, headers, time zone and status colors", () => {
  const s = newSpreadsheet();
  expect(s.properties).toMatchObject({ title: "Shokogi Boards", timeZone: "America/Panama", locale: "en_GB" });
  expect(s.sheets.map((t) => t.properties.title)).toEqual(["Dashboard", "Rented now", "History", "Boards"]);
  const heads = (i: number) => (s.sheets[i].data[0].rowData[0] as { values: { userEnteredValue: { stringValue: string } }[] }).values.map((v) => v.userEnteredValue.stringValue);
  expect(heads(1)).toEqual(RENTED_HEAD);
  expect(heads(2)).toEqual(HISTORY_HEAD);
  expect(heads(3)).toEqual(["Photo", ...BOARDS_HEAD]);
  const rules = JSON.stringify(s.sheets.map((t) => t.conditionalFormats));
  for (const status of ["Overdue", "On time", "Needs a board"]) expect(rules).toContain(`"${status}"`);
  const boardsTab = JSON.stringify(s.sheets[3].conditionalFormats);
  for (const column of [4, 5, 6]) expect(boardsTab).toContain(`"startColumnIndex":${column}`); // Available, Rented, In repair
  const formats = JSON.stringify(dataFormats());
  expect(formats).toContain('"TEXT"'); // phone columns
  expect(formats).toContain("dd/mm/yyyy hh:mm");
});

test("the Boards tab counts identical copies: quantity, available, rented, in repair, who has them", () => {
  const board = { id: "b", name: "SOFTBOARD 8'0", type_id: "t", notes: "", quantity: 4, in_repair: 1, photo_path: null, thumb_path: null, source_file_name: null };
  const rental = (id: string, name: string, boards: string[]) => ({ id, starts_at: "", due_at: "", customer: { id, name, phone: "" }, boards });
  const { boards } = report({
    rentals: [rental("r1", "Dana", ["b", "b"]), rental("r2", "Kai", [])], boards: [board],
    types: [{ id: "t", name: "Softboard", sort_order: 0, is_system: false }], stats: new Map(), history: [], now: 0,
  });
  expect(boards).toEqual([["SOFTBOARD 8'0", "Softboard", 4, 1, 2, 1, "Dana", 0]]); // a family with two of the same
  expect(boards[0]).toHaveLength(BOARDS_HEAD.length);
});
