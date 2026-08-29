#!/usr/bin/env python3
"""The day closing comes out as a spreadsheet that Excel can actually open.

Not "a CSV you copy out of a box" -- a real .xlsx: a zip of the parts Excel
expects, one sheet per part of the day, numbers written as numbers so they can
be summed. The file is built in the page with no library and no network, so it
works on the counter's laptop with the wifi down.

This drives the button, catches the download, and then opens the bytes with
Python's own zipfile and reads the XML back: the sheets are named, the money is
a number, and the client's name is in it.
"""
import datetime as dt
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def build():
    out = os.path.join(tempfile.mkdtemp(), "app.html")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const p = d.products.find(x => !x.gearId && x.ptype !== "rental");
  if (!p) return null;
  d.clients = [{id:"cX", name:"Marta Ruiz", phone:"+507 5", custom:{}}];
  d.bookings = [{id:"bX", date: today, clientId:"cX", ref:"B-1",
    participants: [], refunds: [], custom:{}, notes:"",
    payments: [{id:"pay1", date: today, amount: 137.5, method:"Cash", note:"deposit"}],
    lines: [{lid:"lX", productId: p.id, qty:1, pax:2, hours:null, price:137.5,
             wanted: today, sessionIds: []}]}];
  d.sessions = [{id:"seX", date: today, time:"09:00", duration: 60,
    title:"MORNING", capacity: 6, minCapacity: 0, category: p.category || "",
    note:"", staffIds: [], participants:["c:cX"], spot:"Playa Venao", level:"",
    ageFrom:"", ageTo:"", allDay:false, isPublic:true}];
  d.pos = [{id:"posX", date: today, openedAt:"", openedBy:"", starting: 100,
            closedAt:null, closedBy:"", counted:null, note:""}];
  localStorage.setItem(k, JSON.stringify(d));
  return {product: p.name};
}"""


def main():
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 1680, "height": 1050},
                             accept_downloads=True)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2500)

        seeded = pg.evaluate(SEED, today)
        check("a paid booking, a session and an open till were seeded",
              seeded is not None)
        if seeded is None:
            br.close()
            return 1
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="register"]')
        pg.wait_for_timeout(1400)

        btn = pg.locator("#btn-day-xlsx")
        check("the day closing offers a spreadsheet", btn.count() == 1)
        with pg.expect_download() as dl:
            btn.click()
        got = dl.value
        name = got.suggested_filename
        check("it downloads a file named for the day",
              name == "day-closing-%s.xlsx" % today, name)

        path = os.path.join(tempfile.mkdtemp(), name)
        got.save_as(path)
        size = os.path.getsize(path)
        check("the file has content", size > 1500, str(size) + " bytes")

        check("and it is a zip Excel can open", zipfile.is_zipfile(path))
        if not zipfile.is_zipfile(path):
            br.close()
            return 1
        z = zipfile.ZipFile(path)
        bad = z.testzip()
        check("every part passes its checksum", bad is None, str(bad))
        names = z.namelist()
        for part in ("[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                     "xl/_rels/workbook.xml.rels", "xl/worksheets/sheet1.xml"):
            check("it carries " + part, part in names, str(names))

        wb = z.read("xl/workbook.xml").decode()
        tabs = re.findall(r'<sheet name="([^"]+)"', wb)
        for want in ("Summary", "Payments", "Sold", "Sessions", "Hires", "Drawer"):
            check("a sheet for " + want, want in tabs, str(tabs))

        s1 = z.read("xl/worksheets/sheet1.xml").decode()
        check("the summary names the day", today in s1, s1[:200])
        check("the takings are a number, not text",
              "<v>137.5</v>" in s1, s1[-400:])

        pays = z.read("xl/worksheets/sheet2.xml").decode()
        check("the payment sheet has the client", "Marta Ruiz" in pays, pays[:300])
        check("and the method", "Cash" in pays, pays[:300])

        ses = z.read("xl/worksheets/sheet4.xml").decode()
        check("the sessions sheet has who was in it", "Marta Ruiz" in ses,
              ses[:300])

        # a plain report exports too, from the same one dialog
        pg.click('#tabs button[data-id="clients"]')
        pg.wait_for_timeout(1100)
        pg.locator('#p-clients button:has-text("Export")').first.click()
        pg.wait_for_timeout(700)
        # the buttons are uppercased by the stylesheet
        acts = (pg.inner_text(".modal-f") or "").lower()
        check("a report offers both Excel and CSV",
              "excel" in acts and "csv" in acts, acts)
        with pg.expect_download() as dl2:
            pg.locator('.modal-f button:has-text("Excel")').click()
        check("the report downloads as a workbook",
              dl2.value.suggested_filename.endswith(".xlsx"),
              dl2.value.suggested_filename)

        check("no uncaught errors", not errs, "; ".join(errs[:3]))
        br.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
