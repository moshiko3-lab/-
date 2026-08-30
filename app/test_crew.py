#!/usr/bin/env python3
"""The crew card, and the rule it exists to enforce.

Bloowatch words it on the staff page itself: "only staff that have the
corresponding activity here in their profile will be proposed for the
session". So a photographer is not offered for a surf lesson -- but the
counter can still put anyone on, because a school runs on exceptions.

Also here: the hours-this-month figure their staff list carries, the position
that hand-orders the board, and a crew member taken off the planning.
"""
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
  const kinds = (d.settings && d.settings.kinds) || [];
  if (kinds.length < 2) return null;
  const A = kinds[0].l, B = kinds[1].l;

  d.staff.push({id:"stA", name:"Ana Surfs", role:"Instructor",
    activities:[A], langs:["Spanish","English"], pos:1, onPlanning:true});
  d.staff.push({id:"stB", name:"Beto Shoots", role:"Instructor",
    activities:[B], langs:["Hebrew"], pos:2, onPlanning:true});
  d.staff.push({id:"stC", name:"Cee Parked", role:"Instructor",
    activities:[], langs:[], pos:null, onPlanning:false});

  // an hour of Ana's time this month, for the hours column
  d.sessions.push({id:"seH", date: today, time:"08:00", duration: 90,
    title:"Hours test", capacity: 6, minCapacity: 0, category: A, note:"",
    staffIds:["stA"], participants: [], spot:"", level:"", ageFrom:"",
    ageTo:"", allDay:false, isPublic:true});

  // a board whose service date has gone by
  if (d.gear.length) {
    const g = d.gear[0];
    g.units = g.units || [];
    if (g.units.length) g.units[0].nextCheck = "2020-01-01";
  }
  localStorage.setItem(k, JSON.stringify(d));
  return {a: A, b: B};
}"""


def main():
    import datetime as dt
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2400)

        seeded = pg.evaluate(SEED, today)
        check("two activity calendars to test with", seeded is not None)
        if seeded is None:
            b.close()
            return 1
        pg.reload()
        pg.wait_for_timeout(2200)

        # --- the crew table ---
        pg.click('#tabs button[data-id="crew"]')
        pg.wait_for_timeout(1200)
        crew = low(pg, "#p-crew")
        check("the crew list names the activities", seeded["a"].lower() in crew,
              crew[:220])
        check("and the languages", "spanish" in crew, crew[:220])
        check("hours this month are counted", "01:30" in crew, crew[:400])
        check("someone off the planning is marked", "off the board" in crew,
              crew[:400])

        # --- the rule, in the session form ---
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1400)
        pg.click('#p-board button:has-text("+ Session")')
        pg.wait_for_timeout(900)
        pg.select_option('.modal select:below(:text("Activity calendar"))',
                         label=seeded["a"])
        pg.wait_for_timeout(700)
        dlg = low(pg, ".modal")
        check("the crew for this activity are offered", "ana surfs" in dlg, dlg[:300])
        check("the ones who do not do it are not", "beto shoots" not in dlg,
              dlg[:300])
        # and there is no way round it: the fix for a missing instructor is
        # the activity on their card in Crew, not a button here
        check("with no way to reach the rest", "show all crew" not in dlg,
              dlg[:400])
        check("it says how many are not offered", "do not carry" in dlg,
              dlg[:400])

        # switching the calendar re-reads the rule
        pg.select_option('.modal select:below(:text("Activity calendar"))',
                         label=seeded["b"])
        pg.wait_for_timeout(700)
        dlg = low(pg, ".modal")
        check("changing the calendar changes who is offered",
              "beto shoots" in dlg and "ana surfs" not in dlg, dlg[:300])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)

        # --- the board leaves out the parked crew member ---
        pg.select_option('#p-board select', value="staff|1")
        pg.wait_for_timeout(1300)
        board = low(pg, "#p-board")
        check("the board has a lane for the working crew", "ana surfs" in board,
              board[:300])
        check("and none for the parked one", "cee parked" not in board,
              board[:300])

        # --- gear service dates ---
        pg.click('#tabs button[data-id="gear"]')
        pg.wait_for_timeout(1200)
        gear = low(pg, "#p-gear")
        check("the gear list has a service column", "service due" in gear,
              gear[:300])

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
