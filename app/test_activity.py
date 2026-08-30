#!/usr/bin/env python3
"""A slot only goes in a session of its own activity.

A foil tow is not a surf lesson. The board would happily drop a FOIL slot on a
SURF PACK block, which is how somebody ends up towed behind a boat on a lesson
they never bought. The rule is the same wherever a seat is taken: dragging on
the board, ticking the participants list, and the till's session picker, which
only ever offers sessions of the matching activity.
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


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const base = d.products.find(p => !p.gearId && p.ptype !== "rental");
  if (!base) return null;

  const foil = JSON.parse(JSON.stringify(base));
  foil.id = "prFoil"; foil.name = "TEST FOIL TOW";
  foil.category = "FOIL TEST"; foil.sessions = 3;
  foil.sessionsAtBooking = false;
  d.products.push(foil);

  // activity calendars live in the settings as kinds, labelled by their name
  d.settings.kinds.push({k:"foil_test", l:"FOIL TEST", color:"#7b61ff"});
  d.settings.kinds.push({k:"surf_test", l:"SURF TEST", color:"#2bb673"});

  d.clients = [];
  d.bookings = [];
  d.sessions = [];
  [["cFoil","Foil One"],["cFoil2","Foil Two"]].forEach(([id, name], i) => {
    d.clients.push({id: id, name: name, phone:"+507 " + i, custom:{}});
    d.bookings.push({id:"b" + id, date: today, clientId: id,
      payments: [], refunds: [], custom:{}, notes:"", participants: [],
      lines: [{lid:"l" + id, productId:"prFoil", qty:1, pax:1, hours:null,
               price: 90, wanted: today, sessionIds: []}]});
  });

  d.sessions.push({id:"seSurfT", date: today, time:"09:00", duration: 60,
    title:"SURF TEST", capacity: 6, minCapacity: 0, category:"SURF TEST",
    note:"", staffIds: [], participants: [], spot:"", level:"",
    ageFrom:"", ageTo:"", allDay:false, isPublic:true});
  d.sessions.push({id:"seFoilT", date: today, time:"11:00", duration: 60,
    title:"FOIL TEST", capacity: 6, minCapacity: 0, category:"FOIL TEST",
    note:"", staffIds: [], participants: [], spot:"", level:"",
    ageFrom:"", ageTo:"", allDay:false, isPublic:true});

  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def open_client(pg, name):
    rows = pg.locator(".cl-row")
    for i in range(rows.count()):
        r = rows.nth(i)
        if name.lower() in (r.inner_text() or "").lower():
            if r.locator(".cl-slot").count() == 0:
                r.locator(".cl-caret").click()
                pg.wait_for_timeout(700)
            return r
    return None


def drag(pg, slot, block):
    a, bx = slot.bounding_box(), block.bounding_box()
    if not a or not bx:
        return False
    pg.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(bx["x"] + 25, bx["y"] + bx["height"] / 2, steps=14)
    pg.mouse.up()
    pg.wait_for_timeout(900)
    return True


def main():
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2500)

        check("a foil product and two activities were seeded",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        surf = pg.locator('[data-session-id="seSurfT"]').first
        foil = pg.locator('[data-session-id="seFoilT"]').first
        check("both sessions are on the board",
              surf.count() > 0 and foil.count() > 0)

        row = open_client(pg, "Foil One")
        check("the foil client's three slots are there",
              row is not None and row.locator(".cl-slot").count() == 3,
              "no row" if row is None else str(row.locator(".cl-slot").count()))
        if row is None:
            b.close()
            return 1
        slot = row.locator(".cl-slot").first

        # the wrong activity refuses it
        check("there is somewhere to drop it", drag(pg, slot, surf))
        stored = pg.evaluate(STORE)
        seats = {s["id"]: s["participants"] for s in stored["sessions"]}
        check("a foil slot is refused by a surf session",
              not seats.get("seSurfT"), str(seats.get("seSurfT")))
        check("and it says why",
              "foil test" in low(pg, "#toast") and "surf test" in low(pg, "#toast"),
              pg.inner_text("#toast"))

        # the right one takes it
        row = open_client(pg, "Foil One")
        slot = row.locator(".cl-slot").first
        drag(pg, slot, pg.locator('[data-session-id="seFoilT"]').first)
        stored = pg.evaluate(STORE)
        seats = {s["id"]: s["participants"] for s in stored["sessions"]}
        check("the foil session takes it", seats.get("seFoilT") == ["c:cFoil"],
              str(seats.get("seFoilT")))

        # the participants list follows the same rule
        pg.locator('[data-session-id="seSurfT"]').first.click()
        pg.wait_for_timeout(600)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Open participants list")').first.click()
        pg.wait_for_timeout(700)
        line = pg.locator("#modal label").filter(has_text="Foil Two").first
        check("the surf session lists the people", line.count() > 0)
        cb = line.locator('input[type=checkbox]').first
        cb.click()          # not .check(): the tick is meant not to stick
        pg.wait_for_timeout(600)
        stored = pg.evaluate(STORE)
        seats = {s["id"]: s["participants"] for s in stored["sessions"]}
        check("ticking a foil client into a surf session is refused",
              not seats.get("seSurfT"), str(seats.get("seSurfT")))
        check("and the tick springs back", not cb.is_checked())
        check("and it says what they are owed",
              "foil test" in low(pg, "#toast"), pg.inner_text("#toast"))
        pg.locator('.modal-f button:has-text("Done")').first.click()
        pg.wait_for_timeout(500)

        # the till's picker only offers the matching activity
        pg.click("#btn-newbooking")
        pg.wait_for_timeout(1200)
        tile = pg.locator(".pos-tile").filter(has_text="TEST FOIL TOW").first
        check("the foil product is on the till", tile.count() > 0)
        tile.click()
        pg.wait_for_timeout(900)
        cards = pg.locator(".cfg-ses")
        check("adding it asks which sessions", cards.count() > 0,
              str(cards.count()))
        offered = [cards.nth(i).get_attribute("title") or ""
                   for i in range(cards.count())]
        check("the picker offers the foil session",
              any("FOIL TEST" in t for t in offered), str(offered[:4]))
        check("and not the surf one",
              not any("SURF TEST" in t for t in offered), str(offered[:4]))

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
