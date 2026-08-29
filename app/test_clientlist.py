#!/usr/bin/env python3
"""The board's client list: who is on the water that day.

Two things the school corrected, both of which put the wrong names on the
board. A lesson bought on Monday for Thursday belongs to Thursday, not to the
day the money changed hands. And a board hire is not an activity -- it lives on
the Rental tab with its return time, and must never appear here.
"""
import datetime as dt
import os
import subprocess
import sys
import tempfile

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


def low(pg, sel):
    return (pg.inner_text(sel) or "").lower()


def main():
    today = dt.date.today()
    booked_on = (today - dt.timedelta(days=3)).isoformat()
    happens_on = today.isoformat()

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2400)

        seeded = pg.evaluate(
            """([bookedOn, happensOn]) => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          const lesson = d.products.find(p => p.ptype !== "rental" && !p.gearId);
          const hire = d.products.find(p => p.gearId);
          if (!lesson || !hire) return null;
          const gear = d.gear.find(g => g.id === hire.gearId);
          const unit = gear && (gear.units||[])[0];

          d.clients.push({id:"cLesson", name:"Lesson Person", custom:{}});
          d.clients.push({id:"cHire", name:"Hire Person", custom:{}});

          // bought three days ago, happening today
          d.bookings.push({id:"bLesson", date: bookedOn, clientId:"cLesson",
            participants: [], payments: [], refunds: [], custom:{}, notes:"",
            lines: [{lid:"lnA", productId: lesson.id, qty:1, pax:1, hours:null,
                     price: 50, wanted: happensOn, sessionIds: []}]});
          // a hire today: belongs on the rental tab, never on the client list
          d.bookings.push({id:"bHire", date: happensOn, clientId:"cHire",
            participants: [], payments: [], refunds: [], custom:{}, notes:"",
            lines: [{lid:"lnB", productId: hire.id, qty:1, pax:1, hours:1,
                     price: 20, wanted: happensOn, time:"09:00",
                     unitId: unit ? unit.id : "", sessionIds: []}]});
          localStorage.setItem(k, JSON.stringify(d));
          return {lesson: lesson.name, hire: hire.name};
        }""", [booked_on, happens_on])
        check("a lesson and a hire were seeded", seeded is not None,
              "no product pair to use")
        if seeded is None:
            b.close()
            return 1

        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)

        rail = low(pg, "#p-board .panel:has-text('Client list')") \
            if pg.locator("#p-board .panel:has-text('Client list')").count() \
            else low(pg, "#p-board")
        check("the lesson bought days ago shows on the day it happens",
              "lesson person" in rail, rail[:250])
        check("the hire is not on the client list",
              "hire person" not in rail, rail[:250])

        # and it is on the rental tab, where it belongs
        pg.click('#p-board button:has-text("Rental")')
        pg.wait_for_timeout(1200)
        rent = low(pg, "#p-board")
        check("the hire is on the rental tab", "hire person" in rent, rent[:250])
        check("with a due-back time", "due back" in rent, rent[:250])

        # a day with nothing says so in the right words
        pg.click('#p-board button:has-text("Activities")')
        pg.wait_for_timeout(900)
        # Every activity goes, not just this test's own: a build made with a
        # clients file carries a hundred real bookings, and "empty" has to mean
        # empty. The hire stays, because the point is that it is not counted.
        pg.evaluate("""() => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          const hire = new Set(d.products
            .filter(p => p.ptype === "rental" || p.gearId)
            .map(p => p.id));
          d.bookings = d.bookings.filter(b =>
            (b.lines || []).length && (b.lines || []).every(l => hire.has(l.productId)));
          localStorage.setItem(k, JSON.stringify(d));
        }""")
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)
        txt = low(pg, "#p-board")
        check("an empty day points at the rental tab",
              "no activity booked" in txt or "everyone on the water" in txt,
              txt[:250])

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
