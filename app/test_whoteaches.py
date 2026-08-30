#!/usr/bin/env python3
"""A session is named after an activity, and only its own crew can take it.

Two rules on the session form.

The title is picked, not typed: the activities the school runs and the products
it sells are the options, and choosing one names the session and files it under
the right calendar in the same move. Anything else is still possible, one
option down.

And the crew: a foil tow does not go to somebody whose card does not say foil.
The list offers only the crew who carry the activity, somebody already on the
session who does not carry it is marked rather than hidden, ticking them back
on is refused, saving with them on is refused, and dropping the session on
their row of the board is refused too. The fix is on their card in Crew, and
there is no button here that goes round it.
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


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  d.settings.kinds.push({k:"foil_t", l:"FOIL TEST", color:"#7b61ff"});
  d.settings.kinds.push({k:"surf_t", l:"SURF TEST", color:"#2bb673"});

  d.staff = [
    {id:"stFoil", name:"Fiona Foil", role:"Instructor", phone:"", email:"",
     activities:["FOIL TEST"], langs:["en"], pos:1, seasonFrom:"", seasonTo:"",
     onPlanning:true},
    {id:"stSurf", name:"Sam Surf", role:"Instructor", phone:"", email:"",
     activities:["SURF TEST"], langs:["en"], pos:2, seasonFrom:"", seasonTo:"",
     onPlanning:true}];

  // a foil session that came in with the wrong instructor already on it
  d.bookings = [];
  d.sessions = [{id:"seFoil", date: today, time:"08:00", duration: 90,
    title:"FOIL TEST", capacity: 6, minCapacity: 1, category:"FOIL TEST",
    note:"", staffIds:["stSurf"], participants: [], spot:"", level:"",
    ageFrom:"", ageTo:"", allDay:false, isPublic:true}];
  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


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

        check("two instructors and a foil session were seeded",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        # ---- the title is a picker -------------------------------------
        pg.click('#p-board button:has-text("+ Session")')
        pg.wait_for_timeout(800)
        pick = pg.locator("#modal select").first
        check("the title is chosen from a list", pick.count() == 1)
        opts = pick.locator("option").all_inner_texts()
        check("the activities are offered", "FOIL TEST" in opts, str(opts[:6]))
        check("the products are too",
              any("SURF LESSON" in o.upper() for o in opts), str(len(opts)) + " options")
        check("and anything else is the last option",
              opts[-1].startswith("Something else"), opts[-1])

        pick.select_option(label="FOIL TEST")
        pg.wait_for_timeout(500)
        # the labels are uppercased by the stylesheet, as theirs are, so every
        # comparison here is on lowercase text
        cal = pg.locator("#modal .fld").filter(
            has_text="Activity calendar").locator("select").first
        check("choosing one files it under that calendar",
              cal.input_value() == "FOIL TEST", cal.input_value())
        body = (pg.inner_text("#modal") or "").lower()
        check("only that activity's crew is offered",
              "fiona foil" in body and "sam surf" not in body, body[-400:])
        check("and it says how many are not", "do not carry foil test" in body,
              body[-300:])
        check("with no way round it", "show all crew" not in body,
              body[-300:])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)

        # ---- the wrong instructor already on a session -------------------
        pg.locator('[data-session-id="seFoil"]').first.click()
        pg.wait_for_timeout(600)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Edit session")').first.click()
        pg.wait_for_timeout(800)
        body = (pg.inner_text("#modal") or "").lower()
        check("somebody already on it who does not carry it is shown",
              "sam surf" in body, body[-400:])
        check("and marked", "not foil test" in body, body[-400:])

        pg.locator('#modal button:has-text("Save")').first.click()
        pg.wait_for_timeout(700)
        check("saving with them on is refused",
              not pg.locator("#scrim").is_hidden())
        check("and it says what to do",
              "not set up for foil test" in (pg.inner_text("#toast") or "").lower(),
              pg.inner_text("#toast"))

        # take them off, put the right one on, and it saves
        labs = pg.locator("#modal label")
        for i in range(labs.count()):
            t = (labs.nth(i).inner_text() or "").lower()
            if "sam surf" in t:
                labs.nth(i).locator("input[type=checkbox]").uncheck()
            elif "fiona foil" in t:
                labs.nth(i).locator("input[type=checkbox]").check()
        pg.wait_for_timeout(400)
        pg.locator('#modal button:has-text("Save")').first.click()
        pg.wait_for_timeout(900)
        check("with the right instructor it saves", pg.locator("#scrim").is_hidden())
        stored = pg.evaluate(STORE)
        se = [x for x in stored["sessions"] if x["id"] == "seFoil"][0]
        check("and it is the foil instructor on it", se["staffIds"] == ["stFoil"],
              str(se["staffIds"]))

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
