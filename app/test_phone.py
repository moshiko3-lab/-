#!/usr/bin/env python3
"""The app on a phone.

The board is the board on every screen: the same hours, the same tide drawn
over them, the same blocks to drag. On a phone it scrolls sideways inside its
own panel -- what it must never do is drag the whole page with it, which is
what it used to do, and which took the fixed header and its buttons off the
screen.

The list is still there as a second way of reading the same day, one hand on
the beach; it is a choice that is remembered, not something a screen width
decides.

Checked at 390x844, which is a phone people actually hold.
"""
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))
PHONE = {"width": 390, "height": 844}

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
  const now = new Date();
  const today = now.getFullYear() + "-" +
    String(now.getMonth()+1).padStart(2,"0") + "-" +
    String(now.getDate()).padStart(2,"0");
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const hire = d.products.find(p => p.gearId);
  const staff = d.staff[0];
  d.gear = [{id:"gA", name:"TEST RACK", description:"", units:[
    {id:"uA1", name:"A-ONE", maxPax:1, lastCheck:"", nextCheck:"", notes:""}]}];
  if (hire) hire.gearId = "gA";
  d.clients = [{id:"cA", name:"Ana Phone", phone:"+507 1", custom:{}}];
  d.sessions = [{id:"seP", date: today, time:"08:30", duration: 90,
    title:"DAWN PATROL", capacity: 6, minCapacity: 0,
    category:(d.settings.kinds[0]||{}).l || "", note:"", spot:"Playa Venao",
    staffIds: staff ? [staff.id] : [], participants:["c:cA"],
    level:"", ageFrom:"", ageTo:"", allDay:false, isPublic:true}];
  d.bookings = [{id:"bA", date: today, clientId:"cA", payments: [], refunds: [],
    custom:{}, notes:"", participants: [],
    lines: hire ? [{lid:"lA", productId: hire.id, qty:1, pax:1, hours:2,
                    price:40, wanted: today, time:"09:00", unitId:"uA1",
                    unitName:"A-ONE", sessionIds: []}] : []}];
  localStorage.setItem(k, JSON.stringify(d));
  return {today: today, staff: staff ? staff.name : ""};
}"""


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        ctx = br.new_context(viewport=PHONE, device_scale_factor=3,
                             is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        page = build()
        pg.goto("file://" + page)
        pg.wait_for_timeout(2600)
        seeded = pg.evaluate(SEED)
        pg.reload()
        pg.wait_for_timeout(2400)

        # the tabs are a bottom bar on a phone, not a side rail
        rail = pg.evaluate("""() => {
          const r = document.querySelector('aside.rail').getBoundingClientRect();
          return {top: r.top, height: r.height, width: r.width};
        }""")
        check("the tab rail sits along the bottom",
              rail["top"] > 700 and rail["width"] > 300, str(rail))

        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        check("the board is the grid, as it is on a laptop",
              pg.locator("[data-session-id]").count() >= 1,
              str(pg.locator("[data-session-id]").count()) + " blocks")
        blk = (pg.locator("[data-session-id]").first.inner_text() or "").lower()
        check("a block names its session", "dawn patrol" in blk, blk[:120])
        check("the tide is drawn over the hours",
              pg.locator("#p-board svg").count() >= 1)
        check("and the hours are there",
              "08:00" in (pg.inner_text("#p-board") or ""),
              (pg.inner_text("#p-board") or "")[:200])

        # the same day the other way, and the choice is remembered
        pg.click("#btn-layout")
        pg.wait_for_timeout(900)
        check("the list is one button away", pg.locator(".dayrow").count() >= 1,
              str(pg.locator(".dayrow").count()) + " rows")
        row = (pg.locator(".dayrow").first.inner_text() or "").lower()
        check("a row carries the hour", "08:30" in row, row[:120])
        check("and who is in it", "ana phone" in row, row[:120])
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1200)
        check("and the choice survives a reload", pg.locator(".dayrow").count() >= 1,
              str(pg.locator(".dayrow").count()) + " rows")
        pg.click("#btn-layout")
        pg.wait_for_timeout(1000)
        check("back to the board", pg.locator("[data-session-id]").count() >= 1)

        # nothing may push the page sideways: that is what made it unreadable
        over = pg.evaluate("""() => {
          const w = document.documentElement.clientWidth;
          const bad = [];
          document.querySelectorAll('#p-board *').forEach(n => {
            const r = n.getBoundingClientRect();
            if (r.width > 0 && r.right > w + 2 &&
                getComputedStyle(n).overflowX !== 'auto') bad.push(
              (n.className || n.tagName) + ' ' + Math.round(r.right));
          });
          return {w: w, bad: bad.slice(0, 5),
                  scroll: document.documentElement.scrollWidth};
        }""")
        check("the board fits the screen",
              over["scroll"] <= over["w"] + 2, str(over))

        # tapping a block opens the session card
        pg.locator("[data-session-id]").first.click()
        pg.wait_for_timeout(700)
        check("tapping a block opens the session card",
              pg.locator(".sess-pop").count() == 1)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)

        # the hires read the same way
        pg.locator('#p-board button[data-tab="rental"]').click()
        pg.wait_for_timeout(1200)
        hire = (pg.inner_text("#p-board") or "").lower()
        check("the hire board is a grid too, with the rack down the side",
              "a-one" in hire and pg.locator("[data-unit-id]").count() >= 1,
              hire[:200])
        check("and the hire is a block on it",
              pg.locator("[data-hire-line]").count() >= 1,
              str(pg.locator("[data-hire-line]").count()))
        check("and it fits too",
              pg.evaluate("() => document.documentElement.scrollWidth <= "
                          "document.documentElement.clientWidth + 2"))

        # the till is the other screen a phone has to be able to use
        pg.click('#tabs button[data-id="bookings"]')
        pg.wait_for_timeout(1200)
        pg.click("#btn-newbooking")
        pg.wait_for_timeout(1200)
        check("the till fits the screen",
              pg.evaluate("() => document.documentElement.scrollWidth <= "
                          "document.documentElement.clientWidth + 2"),
              str(pg.evaluate("() => document.documentElement.scrollWidth")))

        check("no uncaught errors", not errs, "; ".join(errs[:3]))

        # and the grid comes back on a laptop
        wide = br.new_context(viewport={"width": 1440, "height": 900}).new_page()
        wide.add_init_script(SIGNED_IN)
        wide.goto("file://" + page)
        wide.wait_for_timeout(2400)
        wide.click('#tabs button[data-id="board"]')
        wide.wait_for_timeout(1500)
        check("a laptop still gets the grid",
              wide.locator("[data-session-id]").count() >= 1,
              str(wide.locator("[data-session-id]").count()))
        br.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
