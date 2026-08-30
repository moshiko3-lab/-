#!/usr/bin/env python3
"""An empty hour on the board is where a session goes.

Clicking a blank stretch of a lane opens the session form already filled in
with that day, that hour and that lane -- the activity when the board is
grouped by activity, the instructor when it is grouped by staff. Clicking a
block still opens the block's card, not this.

The board screen also takes the whole window: it is a diary, and an hour of the
day is worth more than a tidy measure.
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

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


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
  d.bookings = [];
  d.sessions = [{id:"seOne", date: today, time:"09:00", duration: 60,
    title:"MORNING SURF", capacity: 6, minCapacity: 0,
    category:(d.settings.kinds[0] || {}).l || "", note:"", staffIds: [],
    participants: [], spot:"", level:"", ageFrom:"", ageTo:"",
    allDay:false, isPublic:true}];
  localStorage.setItem(k, JSON.stringify(d));
  return {category: d.sessions[0].category};
}"""


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

        seeded = pg.evaluate(SEED, today)
        check("a session was seeded", seeded is not None)
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)

        check("the board screen takes the whole window",
              pg.locator(".wrap.wide").count() == 1)
        wide = pg.evaluate("() => document.querySelector('#p-board').clientWidth")
        check("which is wider than the measure the text screens keep",
              wide > 1400, str(wide) + "px")

        blk = pg.locator('[data-session-id="seOne"]').first
        lane = blk.locator("xpath=..")
        box = lane.bounding_box()
        check("the lane is on screen", box is not None)
        if box is None:
            br.close()
            return 1

        # click past the block but clear of the lane's own buttons, which sit
        # at the right edge of an occupied lane
        frac = 0.55
        pg.mouse.click(box["x"] + box["width"] * frac, box["y"] + box["height"] / 2)
        pg.wait_for_timeout(800)
        check("an empty hour opens the session form",
              not pg.locator("#scrim").is_hidden())
        head = (pg.inner_text(".modal-h") or "").lower()
        check("a new one, not the seeded session", "new session" in head, head[:80])

        date_v = pg.locator('#modal input[type=date]').first.input_value()
        time_v = pg.locator('#modal input[type=time]').first.input_value()
        check("on the day you clicked", date_v == today, date_v)
        st = pg.evaluate(STORE)["settings"]
        f0, t0 = int(st.get("boardFrom", 6)), int(st.get("boardTo", 20))
        want = "%02d:00" % (f0 + int(frac * (t0 - f0)))
        check("at the hour you clicked", time_v == want, time_v + " wanted " + want)
        body = (pg.inner_text("#modal") or "")
        check("in the lane you clicked", (seeded["category"] or "") in body,
              seeded["category"])

        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)

        # a block still opens its own card
        blk.click()
        pg.wait_for_timeout(700)
        check("clicking the block still opens its card",
              pg.locator(".sess-pop").count() == 1)
        check("and not the form", pg.locator("#scrim").is_hidden())

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
