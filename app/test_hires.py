#!/usr/bin/env python3
"""Boards out on hire, and when they are due back.

Seeds three hires directly into the store -- one finished hours ago, one due in
minutes, one with hours left -- and checks the screen calls each what it is. A
board an hour late is a board somebody else is waiting for, so getting these
three apart is the whole point of the column.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))

fails = []

# The app does not draw until somebody has signed in. These tests are about
# what is behind that door, so they open the way a device that already signed
# in opens: with a session in hand and the network stubbed out. test_gate is
# the one that checks the door itself.
SIGNED_IN = """
  try {
    localStorage.setItem("shokogi.cloud.session", JSON.stringify({
      access_token: "test", refresh_token: "test", email: "test@shokogi",
      expires_at: Date.now() + 36e5}));
  } catch (e) {}
  window.fetch = function() {
    return Promise.resolve(new Response("[]", {status: 200,
      headers: {"Content-Type": "application/json"}}));
  };
  // and no socket reaching out of a test: the live connection has its own,
  // in test_cloud, where the test holds the other end of it
  window.WebSocket = function() {
    this.readyState = 0;
    this.send = function() {};
    this.close = function() {};
  };
"""


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


def low(pg, sel):
    return (pg.inner_text(sel) or "").lower()


def main():
    # The three states this test is about -- overdue, due soon, hours left --
    # are read against the clock, so the clock is pinned. Run this at half past
    # midnight without it and "three hours ago" lands on yesterday evening,
    # nothing is overdue, and the failure says nothing about the app.
    anchor = dt.datetime.combine(dt.date.today(), dt.time(14, 0))
    today = anchor.date().isoformat()
    now = anchor

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1500, "height": 1000}).new_page()
        pg.add_init_script(SIGNED_IN)
        pg.clock.set_fixed_time(anchor)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2200)

        # three hires on the same day: overdue, due in ~15 min, and hours left
        seeded = pg.evaluate(
            """([today, late, soon, later]) => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          const gear = d.gear.find(g => (g.units||[]).length >= 3);
          if (!gear) return null;
          // This test counts: one overdue board, and none once it is back. A
          // build made with a clients file arrives carrying seventy-six real
          // hires, plenty of them long past their hour, so the day has to be
          // this test's own before any of the counting means anything.
          d.bookings = [];
          const client = {id:"cHire", name:"Hire Tester", email:"", phone:"",
                          custom:{}};
          d.clients.push(client);
          const prod = d.products.find(p => p.gearId === gear.id) || d.products[0];
          const mk = (lid, unit, time, hours) => ({
            lid, productId: prod.id, qty: 1, pax: 1, hours,
            price: 20, wanted: today, time, unitId: unit.id, sessionIds: []
          });
          d.bookings.push({
            id:"bHire", date: today, clientId: client.id, participants: [],
            payments: [], refunds: [], custom: {}, notes: "",
            lines: [ mk("lnLate", gear.units[0], late, 1),
                     mk("lnSoon", gear.units[1], soon, 1),
                     mk("lnLater", gear.units[2], later, 6) ]
          });
          localStorage.setItem(k, JSON.stringify(d));
          return {gear: gear.name, units: gear.units.slice(0,3).map(u => u.name)};
        }""",
            [today,
             (now - dt.timedelta(hours=3)).strftime("%H:%M"),
             (now - dt.timedelta(minutes=45)).strftime("%H:%M"),
             (now - dt.timedelta(minutes=30)).strftime("%H:%M")])
        check("three hires seeded", seeded is not None,
              "no gear with three units in the catalogue")
        if seeded is None:
            b.close()
            return 1

        pg.reload()
        pg.wait_for_timeout(2000)
        pg.click('#tabs button[data-id="schedule"]')
        pg.wait_for_timeout(700)
        pg.click('#p-schedule button:has-text("Rental")')
        pg.wait_for_timeout(900)

        txt = low(pg, "#p-schedule")
        check("the hires table is drawn", "out on hire" in txt, txt[:200])
        check("it names the boards", seeded["units"][0].lower() in txt, txt[:300])
        check("it shows a due-back column", "due back" in txt)

        rows = pg.locator("#p-schedule table tbody tr")
        by_unit = {}
        for i in range(rows.count()):
            cells = rows.nth(i).inner_text().lower()
            for u in seeded["units"]:
                if u.lower() in cells:
                    by_unit[u] = cells
        check("all three hires listed", len(by_unit) == 3, str(list(by_unit)))

        late_row = by_unit.get(seeded["units"][0], "")
        soon_row = by_unit.get(seeded["units"][1], "")
        later_row = by_unit.get(seeded["units"][2], "")
        check("a hire that ended hours ago reads overdue", "overdue" in late_row,
              late_row[:120])
        check("and says how late it is", "late" in late_row, late_row[:120])
        check("a hire ending shortly reads due soon", "due soon" in soon_row,
              soon_row[:120])
        check("a hire with hours left just reads out",
              "out" in later_row and "overdue" not in later_row and
              "due soon" not in later_row, later_row[:120])
        check("and says how long is left", "left" in later_row, later_row[:120])
        check("the header counts the overdue one", "1 overdue" in txt, txt[:250])

        # marking one back takes it off the overdue count and frees the board
        pg.locator("#p-schedule table tbody tr", has_text=seeded["units"][0]) \
          .locator('button:has-text("Returned")').first.click()
        pg.wait_for_timeout(900)
        txt = low(pg, "#p-schedule")
        check("a returned board reads back", "back" in txt, txt[:250])
        check("and drops out of the overdue count", "1 overdue" not in txt, txt[:250])

        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        bk = [x for x in stored["bookings"] if x["id"] == "bHire"][0]
        ln = [x for x in bk["lines"] if x["lid"] == "lnLate"][0]
        check("the return is recorded on the line", bool(ln.get("returnedAt")),
              json.dumps(ln)[:160])

        check("no uncaught errors", not errs, "; ".join(errs[:3]))
        b.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
