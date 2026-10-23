// Shokogi Boards -> Google Sheets sync.
// Paste this into the sheet (Extensions > Apps Script) and deploy it as a Web app.
// The app sends its data here after every change; this script writes it into the tabs.
const TOKEN = '3bc19f78c09bf77ce468897a'; // must match SHEET_TOKEN in index.html

function doGet() {
  return reply({ ok: true, message: 'Shokogi sync is running.' });
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(60000); // one sync at a time
  try {
    const p = JSON.parse(e.postData.contents);
    if (p.token !== TOKEN) return reply({ ok: false, error: 'Wrong token' });
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    writeRows(ss.getSheetByName('Rented now'), 1, p.rented);
    writeRows(ss.getSheetByName('History'), 1, p.history);
    const boards = ss.getSheetByName('Boards');
    writeRows(boards, 2, p.boards); // column A holds the photos
    if (p.boards.length) boards.setRowHeights(2, p.boards.length, 90);
    if (p.photos) writePhotos(boards, p.photos);
    ss.getSheetByName('Dashboard').getRange('B2').setValue(new Date());
    return reply({ ok: true, url: ss.getUrl() });
  } catch (err) {
    return reply({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

// Replaces everything under the header row, from column `col` to the last header column.
// Dates arrive as {date: milliseconds}.
function writeRows(sheet, col, rows) {
  const width = sheet.getLastColumn() - col + 1;
  if (sheet.getMaxRows() > 1) sheet.getRange(2, col, sheet.getMaxRows() - 1, width).clearContent();
  if (!rows.length) return;
  const missing = rows.length + 1 - sheet.getMaxRows();
  if (missing > 0) sheet.insertRowsAfter(sheet.getMaxRows(), missing);
  sheet.getRange(2, col, rows.length, width)
    .setValues(rows.map(r => r.map(v => v && v.date !== undefined ? new Date(v.date) : v)));
}

// photos[i] is a small JPEG (base64) for data row i, or '' when that board has no photo.
function writePhotos(sheet, photos) {
  sheet.getImages().forEach(img => img.remove());
  if (sheet.getMaxRows() > 1) sheet.getRange(2, 1, sheet.getMaxRows() - 1, 1).clearContent();
  photos.forEach((b64, i) => {
    if (!b64) return;
    try {
      const image = SpreadsheetApp.newCellImage().setSourceUrl('data:image/jpeg;base64,' + b64).build();
      sheet.getRange(i + 2, 1).setValue(image);
    } catch (err) {
      // Fallback: a picture placed over the cell instead of inside it.
      const img = sheet.insertImage(Utilities.newBlob(Utilities.base64Decode(b64), 'image/jpeg'), 1, i + 2, 4, 3);
      const k = 84 / img.getHeight();
      img.setHeight(84).setWidth(Math.round(img.getWidth() * k));
    }
  });
}

function reply(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
