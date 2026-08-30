#!/usr/bin/env python3
"""The hire board: which board is with whom, until when, and moving them.

The list says what is late. It does not say what is free at four o'clock, and
that is what a shop asks all day. So the rental tab draws the boards down one
side and the day across the top: a lane per board, a block per hire, as wide as
the hire is long.

Dragging a block along its lane changes the hour it went out; dragging it onto
another lane puts that person on another board. A board already out at that
hour refuses, because two people cannot take the same board at once -- and a
product that goes out on softboards does not move onto a foil.
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


SEED = """() => {
  // the page's own idea of today, not the test runner's: a run that crosses
  // midnight would otherwise seed a day the board is not looking at
  const now = new Date();
  const today = now.getFullYear() + "-" +
    String(now.getMonth()+1).padStart(2,"0") + "-" +
    String(now.getDate()).padStart(2,"0");
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const hire = d.products.find(p => p.gearId);
  if (!hire) return null;

  // Their own rack is two hundred and sixty boards, which is the right thing
  // for the app and the wrong thing for a test: a lane a hundred rows down
  // cannot be dragged onto. Two small racks, and every lane is on the screen.
  d.gear = [
    {id:"gA", name:"TEST RACK A", description:"", units:[
      {id:"uA1", name:"A-ONE", maxPax:1, lastCheck:"", nextCheck:"", notes:""},
      {id:"uA2", name:"A-TWO", maxPax:1, lastCheck:"", nextCheck:"", notes:""},
      {id:"uA3", name:"A-THREE", maxPax:1, lastCheck:"", nextCheck:"", notes:""}]},
    {id:"gB", name:"TEST RACK B", description:"", units:[
      {id:"uB1", name:"B-ONE", maxPax:1, lastCheck:"", nextCheck:"", notes:""}]}];
  hire.gearId = "gA";

  d.clients = [{id:"cA", name:"Ana Board", custom:{}},
               {id:"cB", name:"Beto Board", custom:{}}];
  d.bookings = [
    {id:"bA", date: today, clientId:"cA", payments: [], refunds: [],
     custom:{}, notes:"", participants: [],
     lines: [{lid:"lA", productId: hire.id, qty:1, pax:1, hours:2, price:40,
              wanted: today, time:"09:00", unitId:"uA1", unitName:"A-ONE",
              sessionIds: []}]},
    {id:"bB", date: today, clientId:"cB", payments: [], refunds: [],
     custom:{}, notes:"", participants: [],
     lines: [{lid:"lB", productId: hire.id, qty:1, pax:1, hours:2, price:40,
              wanted: today, time:"09:00", unitId:"uA2", unitName:"A-TWO",
              sessionIds: []}]}];
  d.sessions = [];
  localStorage.setItem(k, JSON.stringify(d));
  return {today: today, gear:"TEST RACK A", u0:"uA1", u1:"uA2", u2:"uA3",
          u0n:"A-ONE", u2n:"A-THREE", otherUnit:"uB1", otherName:"TEST RACK B"};
}"""


STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def line_of(store, lid):
    for b in store["bookings"]:
        for l in b.get("lines", []):
            if l.get("lid") == lid:
                return l
    return None


def drag_to(pg, block, lane, at=0.5):
    # with two hundred boards a lane can be far below the fold, and a drag to
    # a point off the window lands somewhere else entirely
    lane.scroll_into_view_if_needed()
    pg.wait_for_timeout(250)
    block.scroll_into_view_if_needed()
    pg.wait_for_timeout(250)
    a, b = block.bounding_box(), lane.bounding_box()
    pg.mouse.move(a["x"] + 12, a["y"] + a["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(b["x"] + b["width"] * at, b["y"] + b["height"] / 2, steps=14)
    pg.mouse.up()
    pg.wait_for_timeout(900)


def main():
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2500)

        seeded = pg.evaluate(SEED)
        check("two hires on two boards were seeded", seeded is not None)
        if seeded is None:
            br.close()
            return 1
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1200)
        pg.locator('#p-board button[data-tab="rental"]').click()
        pg.wait_for_timeout(1300)

        lanes = pg.locator("[data-unit-id]")
        check("there is a lane for every board", lanes.count() == 3,
              str(lanes.count()) + " lanes")
        board = (pg.inner_text("#p-board") or "").lower()
        check("the gear names the group", seeded["gear"].lower() in board,
              board[:200])
        check("a free board says so", "free" in board, board[:200])

        blk = pg.locator('[data-hire-line="lA"]')
        check("the hire is a block on its board's lane", blk.count() == 1)
        txt = (blk.first.inner_text() or "").lower()
        check("with who has it", "ana" in txt, txt)
        check("and from when to when", "09:00" in txt and "11:00" in txt, txt)

        # --- onto a board that is taken: refused ---------------------------
        busy = pg.locator('[data-unit-id="%s"]' % seeded["u1"]).first
        drag_to(pg, blk.first, busy, at=0.25)
        line = line_of(pg.evaluate(STORE), "lA")
        check("a board already out will not take a second person",
              line["unitId"] == seeded["u0"], str(line["unitId"]))
        check("and it says who has it",
              "beto" in (pg.inner_text("#toast") or "").lower(),
              pg.inner_text("#toast"))

        # --- onto a free board: moves --------------------------------------
        free = pg.locator('[data-unit-id="%s"]' % seeded["u2"]).first
        drag_to(pg, pg.locator('[data-hire-line="lA"]').first, free, at=0.5)
        line = line_of(pg.evaluate(STORE), "lA")
        check("a free board takes the person", line["unitId"] == seeded["u2"],
              str(line["unitId"]))
        check("and the board's name follows",
              line.get("unitName") == seeded["u2n"], str(line.get("unitName")))
        check("the hour it landed on is kept", line.get("time", "") != "09:00",
              str(line.get("time")))

        # --- a board of the wrong kind: refused ----------------------------
        # the other gear is only drawn once every board is shown
        # the second rack is only drawn once every board is shown
        pg.locator('#p-board button:has-text("Show every board")').first.click()
        pg.wait_for_timeout(1200)
        check("showing every board brings the other rack in",
              pg.locator("[data-unit-id]").count() == 4,
              str(pg.locator("[data-unit-id]").count()) + " lanes")
        if seeded["otherUnit"]:
            wrong = pg.locator('[data-unit-id="%s"]' % seeded["otherUnit"]).first
            if wrong.count():
                drag_to(pg, pg.locator('[data-hire-line="lA"]').first, wrong)
                line = line_of(pg.evaluate(STORE), "lA")
                check("a board of another kind is refused",
                      line["unitId"] == seeded["u2"], str(line["unitId"]))

        # --- clicking opens the hire ---------------------------------------
        pg.locator('[data-hire-line="lA"]').first.click()
        pg.wait_for_timeout(700)
        check("clicking a hire opens it", not pg.locator("#scrim").is_hidden())
        dlg = (pg.inner_text("#modal") or "").lower()
        check("naming the person and the board",
              "ana" in dlg and seeded["u2n"].lower() in dlg, dlg[:200])
        pg.locator('.modal-f button:has-text("Mark it back")').first.click()
        pg.wait_for_timeout(800)
        line = line_of(pg.evaluate(STORE), "lA")
        check("and it can be marked back from there",
              bool(line.get("returnedAt")), str(line.get("returnedAt")))

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
