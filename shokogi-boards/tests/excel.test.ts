import { expect, test } from "vitest";
import { dateCell, excelSerial, fitColumns } from "../lib/excel";

test("Excel dates are serial numbers in Panama time", () => {
  const t = Date.UTC(2026, 9, 19, 22, 30); // 19 Oct 2026, 17:30 in Panama
  expect(excelSerial(t)).toBeCloseTo(46314.729166666664, 9); // = (17:30 local - 30 Dec 1899) in days
  expect(excelSerial(Date.UTC(1970, 0, 1, 5))).toBe(25569); // Panama midnight, 1 Jan 1970
  expect(dateCell(new Date(t).toISOString())).toEqual({ t: "n", v: excelSerial(t), z: "dd/mm/yyyy hh:mm" });
  expect(dateCell(null)).toBe("");
});

test("column widths fit the content", () => {
  expect(fitColumns(["Board", "Start"], [["LONGBOARD 9'1", dateCell("2026-10-19T22:30:00Z")]])).toEqual([{ wch: 15 }, { wch: 18 }]);
});
