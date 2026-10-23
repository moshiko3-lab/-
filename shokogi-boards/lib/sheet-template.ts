// The "Shokogi Boards" spreadsheet the app creates in the business's Google Drive: the same tabs, columns, colors,
// status highlights and Dashboard formulas as the original sheet. Plain data for the Sheets API.
type Rgb = { red: number; green: number; blue: number };
const rgb = (hex: string): Rgb => {
  const n = parseInt(hex.slice(1), 16);
  return { red: (n >> 16) / 255, green: ((n >> 8) & 255) / 255, blue: (n & 255) / 255 };
};
const BLUE = rgb("#2462eb"), INK = rgb("#1e293a"), MUTED = rgb("#63748a"), LIGHT = rgb("#eef6ff"), WHITE = rgb("#ffffff");
const BAND = rgb("#f8f9fb");
const STATUS = {
  blue: { bg: LIGHT, fg: BLUE }, red: { bg: rgb("#fde1e1"), fg: rgb("#dc2525") },
  amber: { bg: rgb("#fdf3c6"), fg: rgb("#b45208") }, green: { bg: rgb("#dcfbe7"), fg: rgb("#14803c") },
};

export const SHEET_IDS = { Dashboard: 0, "Rented now": 1, History: 2, Boards: 3 } as const;
type TabName = keyof typeof SHEET_IDS;

type Column = { head: string; width: number; center?: boolean; format?: object; bold?: boolean };
const DATE = { numberFormat: { type: "DATE_TIME", pattern: "dd/mm/yyyy hh:mm" } };
const TEXT = { numberFormat: { type: "TEXT" } }; // phone numbers keep their leading zero
const COUNT = { numberFormat: { type: "NUMBER", pattern: '0;-0;"-"' } }; // zero shows as "-"

const COLUMNS: Record<Exclude<TabName, "Dashboard">, Column[]> = {
  "Rented now": [
    { head: "Customer", width: 170 }, { head: "Phone", width: 130, format: TEXT }, { head: "Board", width: 280 },
    { head: "Type", width: 120 }, { head: "Start", width: 140, format: DATE }, { head: "Back by", width: 140, format: DATE },
    { head: "Status", width: 130, center: true },
  ],
  History: [
    { head: "Customer", width: 170 }, { head: "Phone", width: 130, format: TEXT }, { head: "Board", width: 280 },
    { head: "Type", width: 120 }, { head: "Start", width: 140, format: DATE }, { head: "Returned", width: 140, format: DATE },
    { head: "Hours", width: 80, center: true, format: { numberFormat: { type: "NUMBER", pattern: "0.0" } } },
    { head: "Minutes late", width: 110, center: true, format: COUNT },
  ],
  Boards: [
    { head: "Photo", width: 90, center: true }, { head: "Board", width: 300, bold: true }, { head: "Type", width: 120 },
    { head: "Quantity", width: 90, center: true, format: COUNT }, { head: "Available", width: 90, center: true, format: COUNT },
    { head: "Rented", width: 90, center: true, format: COUNT }, { head: "In repair", width: 90, center: true, format: COUNT },
    { head: "Rented by", width: 170 },
    { head: "Times rented", width: 110, center: true, format: { numberFormat: { type: "NUMBER", pattern: "0" } } },
  ],
};

const text = (v: string, format: object = {}) => ({ userEnteredValue: { stringValue: v }, userEnteredFormat: format });
const formula = (v: string, format: object = {}) => ({ userEnteredValue: { formulaValue: v }, userEnteredFormat: format });
const headFormat = (center?: boolean) => ({
  backgroundColorStyle: { rgbColor: BLUE }, padding: { left: 8 }, verticalAlignment: "MIDDLE", ...(center ? { horizontalAlignment: "CENTER" } : {}),
  textFormat: { bold: true, fontSize: 10, foregroundColorStyle: { rgbColor: WHITE } },
});
const textIs = (sheetId: number, column: number, value: string, color: { bg: Rgb; fg: Rgb }) => ({
  ranges: [{ sheetId, startRowIndex: 1, startColumnIndex: column, endColumnIndex: column + 1 }],
  booleanRule: {
    condition: { type: "TEXT_EQ", values: [{ userEnteredValue: value }] },
    format: { backgroundColorStyle: { rgbColor: color.bg }, textFormat: { bold: true, foregroundColorStyle: { rgbColor: color.fg } } },
  },
});
const above0 = (sheetId: number, column: number, color: { bg: Rgb; fg: Rgb }) => ({
  ranges: [{ sheetId, startRowIndex: 1, startColumnIndex: column, endColumnIndex: column + 1 }],
  booleanRule: {
    condition: { type: "NUMBER_GREATER", values: [{ userEnteredValue: "0" }] },
    format: { backgroundColorStyle: { rgbColor: color.bg }, textFormat: { bold: true, foregroundColorStyle: { rgbColor: color.fg } } },
  },
});
const banding = (sheetId: number, width: number, key = "A") => ({
  ranges: [{ sheetId, startRowIndex: 1, startColumnIndex: 0, endColumnIndex: width }],
  booleanRule: { condition: { type: "CUSTOM_FORMULA", values: [{ userEnteredValue: `=AND(ISEVEN(ROW()),$${key}2<>"")` }] }, format: { backgroundColorStyle: { rgbColor: BAND } } },
});

function dataTab(title: Exclude<TabName, "Dashboard">, rowCount: number, tab: Rgb, conditionalFormats: object[]) {
  const columns = COLUMNS[title], sheetId = SHEET_IDS[title];
  return {
    properties: { sheetId, title, tabColorStyle: { rgbColor: tab }, gridProperties: { rowCount, columnCount: columns.length, frozenRowCount: 1 } },
    data: [{
      startRow: 0, startColumn: 0,
      rowData: [{ values: columns.map((c) => text(c.head, headFormat(c.center))) }],
      columnMetadata: columns.map((c) => ({ pixelSize: c.width })),
      rowMetadata: [{ pixelSize: 34 }],
    }],
    conditionalFormats,
  };
}

function dashboard() {
  const label = { backgroundColorStyle: { rgbColor: LIGHT }, padding: { left: 10, top: 6 }, verticalAlignment: "BOTTOM", textFormat: { bold: true, fontSize: 9, foregroundColorStyle: { rgbColor: MUTED } } };
  const big = { backgroundColorStyle: { rgbColor: LIGHT }, padding: { left: 10 }, horizontalAlignment: "LEFT", textFormat: { bold: true, fontSize: 22, foregroundColorStyle: { rgbColor: INK } } };
  const cell = (center: boolean) => ({ padding: { left: 8 }, ...(center ? { horizontalAlignment: "CENTER" } : {}), textFormat: { fontSize: 10, foregroundColorStyle: { rgbColor: INK } } });
  const kpis: [string, string][] = [
    ["Rented now", "=COUNTA('Rented now'!C2:C)"], ["Overdue", "=COUNTIF('Rented now'!G2:G,B4)"], ["Needs a board", "=COUNTIF('Rented now'!G2:G,C4)"],
    ["Available", "=SUM(Boards!E2:E)"], ["In repair", "=SUM(Boards!G2:G)"], ["Rentals logged", "=COUNTA(History!A2:A)"],
    ["Hours on the water", "=ROUND(SUM(History!G2:G),0)"],
  ];
  // Copies per type: the Boards tab's Quantity (D), Rented (F), Available (E) and In repair (G) columns, summed.
  const fleet = (col: string) => `=ARRAYFORMULA(IF($A9:$A24="",,SUMIF(Boards!$C$2:$C,$A9:$A24,Boards!${col}$2:${col})))`;
  return {
    properties: { sheetId: 0, title: "Dashboard", tabColorStyle: { rgbColor: BLUE }, gridProperties: { rowCount: 30, columnCount: 8, hideGridlines: true } },
    data: [{
      startRow: 0, startColumn: 0,
      rowData: [
        { values: [text("Shokogi board rentals", { textFormat: { bold: true, fontSize: 18, foregroundColorStyle: { rgbColor: INK } } })] },
        { values: [text("Last synced from the app", { textFormat: { foregroundColorStyle: { rgbColor: MUTED } } }), { userEnteredFormat: { ...DATE, horizontalAlignment: "LEFT", textFormat: { bold: true } } }] },
        {},
        { values: kpis.map(([name]) => text(name, label)) },
        { values: kpis.map(([, f]) => formula(f, big)) },
        {},
        { values: [text("Fleet by type", { textFormat: { bold: true, fontSize: 12, foregroundColorStyle: { rgbColor: INK } } })] },
        { values: ["Type", "Boards", "Rented", "Available", "In repair"].map((h, i) => text(h, headFormat(i > 0))) },
        { values: [
          formula('=IFERROR(SORT(UNIQUE(FILTER(Boards!C2:C,Boards!C2:C<>""))),"")', cell(false)),
          formula(fleet("D"), cell(true)), formula(fleet("F"), cell(true)), formula(fleet("E"), cell(true)), formula(fleet("G"), cell(true)),
        ] },
      ],
      columnMetadata: [...Array(7).fill({ pixelSize: 150 }), { pixelSize: 100 }],
      rowMetadata: [{ pixelSize: 44 }, {}, {}, {}, { pixelSize: 48 }, {}, {}, { pixelSize: 30 }],
    }],
    conditionalFormats: [
      { ranges: [{ sheetId: 0, startRowIndex: 8, endRowIndex: 24, startColumnIndex: 0, endColumnIndex: 5 }],
        booleanRule: { condition: { type: "CUSTOM_FORMULA", values: [{ userEnteredValue: '=AND($A9<>"",ISEVEN(ROW()))' }] }, format: { backgroundColorStyle: { rgbColor: BAND } } } },
      { ranges: [{ sheetId: 0, startRowIndex: 4, endRowIndex: 5, startColumnIndex: 1, endColumnIndex: 2 }],
        booleanRule: { condition: { type: "NUMBER_GREATER", values: [{ userEnteredValue: "0" }] }, format: { textFormat: { foregroundColorStyle: { rgbColor: STATUS.red.fg } } } } },
    ],
  };
}

// Body for spreadsheets.create.
export function newSpreadsheet() {
  const r = SHEET_IDS["Rented now"], h = SHEET_IDS.History, b = SHEET_IDS.Boards;
  return {
    properties: { title: "Shokogi Boards", locale: "en_GB", timeZone: "America/Panama" },
    sheets: [
      dashboard(),
      dataTab("Rented now", 200, rgb("#c2410b"), [
        textIs(r, 6, "Needs a board", STATUS.amber), textIs(r, 6, "On time", STATUS.blue), textIs(r, 6, "Overdue", STATUS.red), banding(r, 7),
      ]),
      dataTab("History", 1000, MUTED, [
        above0(h, 7, STATUS.red), banding(h, 8),
      ]),
      dataTab("Boards", 200, STATUS.green.fg, [
        above0(b, 4, STATUS.green), above0(b, 5, STATUS.blue), above0(b, 6, STATUS.amber), banding(b, 9, "B"),
      ]),
    ],
  };
}

// Column formats for every data row (re-applied on each sync, so rows added later look the same),
// plus the Dashboard's "Fleet by type" rows, which its formulas fill below the first one.
export function dataFormats() {
  const fleetRows = [0, 1, 2, 3, 4].map((i) => ({
    repeatCell: {
      range: { sheetId: SHEET_IDS.Dashboard, startRowIndex: 8, endRowIndex: 24, startColumnIndex: i, endColumnIndex: i + 1 },
      cell: { userEnteredFormat: { padding: { left: 8 }, ...(i ? { horizontalAlignment: "CENTER" } : {}), textFormat: { fontSize: 10, foregroundColorStyle: { rgbColor: INK } } } },
      fields: "userEnteredFormat(padding,horizontalAlignment,textFormat)",
    },
  }));
  return [...fleetRows, ...(Object.keys(COLUMNS) as (keyof typeof COLUMNS)[]).flatMap((title) =>
    COLUMNS[title].map((c, i) => ({
      repeatCell: {
        range: { sheetId: SHEET_IDS[title], startRowIndex: 1, startColumnIndex: i, endColumnIndex: i + 1 },
        cell: { userEnteredFormat: {
          padding: { left: 8 }, verticalAlignment: "MIDDLE", ...(c.center ? { horizontalAlignment: "CENTER" } : {}), ...c.format,
          ...(c.bold ? { textFormat: { bold: true }, wrapStrategy: "WRAP" } : {}),
        } },
        fields: "userEnteredFormat",
      },
    })))];
}
