#!/usr/bin/env python3
"""The app on a phone.

A fourteen-hour grid on a four-inch screen is a grid nobody reads, and that is
what the board was: it simply did not appear. On a narrow screen the same day
is drawn as a list -- the hour, the session, who is taking it, who is in it --
and the hires the same way, grouped by board with how long is left.

Checked at 390x844, which is a phone people actually hold, and then back at a
laptop width to be sure the grid returns.
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

        check("the day is drawn as a list", pg.locator(".dayrow").count() >= 1,
              str(pg.locator(".dayrow").count()) + " rows")
        check("and not as the wide grid",
              pg.locator("[data-session-id]").count() == 0)

        row = (pg.locator(".dayrow").first.inner_text() or "").lower()
        check("a row carries the hour", "08:30" in row, row[:120])
        check("and the session", "dawn patrol" in row, row[:120])
        check("and who is in it", "ana phone" in row, row[:120])
        if seeded["staff"]:
            check("and who is taking it", seeded["staff"].lower() in row, row[:160])

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

        # tapping a row opens the session
        pg.locator(".dayrow").first.click()
        pg.wait_for_timeout(700)
        check("tapping a row opens the session card",
              pg.locator(".sess-pop").count() == 1)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)

        # the hires read the same way
        pg.locator('#p-board button[data-tab="rental"]').click()
        pg.wait_for_timeout(1200)
        hire = (pg.inner_text("#p-board") or "").lower()
        check("the hires are a list too", "ana phone" in hire and "a-one" in hire,
              hire[:200])
        check("with how long is left", "left" in hire or "late" in hire,
              hire[:200])
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
