#!/usr/bin/env python3
"""Seating somebody has to strike the lesson off their course.

A ten-lesson course shows ten boxes on the client card, and a box fills in when
that lesson has been placed on a day. That only works if the session records
which order line the lesson came out of -- being in the session is half the
fact; which of the ten it was is the other half.

Dragging the slot onto the board recorded both. Ticking the same person into
the same session through the participants list recorded only the first, so the
card still read ten empty boxes for a course that was half taught -- and a
school reading that card gives away lessons it has already been paid for.

Both doors now lead to the same room. And taking somebody out again gives the
lesson back rather than leaving the course quietly short.
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
  window.WebSocket = function() {
    this.send = function() {}; this.close = function() {};
  };
"""

# one client on a three-lesson course, and one session of that activity
SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const base = d.products.find(p => !p.gearId && p.ptype !== "rental");
  if (!base) return null;

  const course = JSON.parse(JSON.stringify(base));
  course.id = "prCourse"; course.name = "TEST 3X COURSE";
  course.category = "COURSE TEST"; course.sessions = 3;
  course.sessionsAtBooking = false;
  d.products.push(course);
  d.settings.kinds.push({k: "course_test", l: "COURSE TEST", color: "#2bb673"});

  d.clients = [{id: "cT", name: "Tick Tester", phone: "+507 1", custom: {}}];
  d.bookings = [{id: "bkT", date: today, clientId: "cT",
    payments: [], refunds: [], custom: {}, notes: "", participants: [],
    lines: [{lid: "lT", productId: "prCourse", qty: 1, pax: 1, hours: null,
             price: 300, wanted: today, sessionIds: []}]}];
  d.sessions = [{id: "seT", date: today, time: "09:00", duration: 60,
    title: "COURSE TEST", capacity: 6, minCapacity: 0, category: "COURSE TEST",
    note: "", staffIds: [], participants: [], spot: "", level: "",
    ageFrom: "", ageTo: "", allDay: false, isPublic: true}];
  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def slots(pg):
    """the course rows in the client list: (ticked?, date shown)"""
    return pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll(".cl-slot").forEach(function(r) {
        const t = r.querySelector(".tick");
        const w = r.querySelector(".when");
        out.push([!!(t && t.classList.contains("on")),
                  w ? w.textContent.trim() : ""]);
      });
      return out;
    }""")


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
        pg.wait_for_timeout(2600)

        check("a course and a session were seeded",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2300)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        row = open_client(pg, "Tick Tester")
        check("the course shows its three lessons",
              row is not None and row.locator(".cl-slot").count() == 3,
              "no row" if row is None else str(row.locator(".cl-slot").count()))
        if row is None:
            br.close()
            return 1
        check("and none of them is ticked yet",
              not any(t for t, _ in slots(pg)), str(slots(pg)))

        # --- seat them through the participants list, not by dragging --------
        pg.locator('[data-session-id="seT"]').first.click()
        pg.wait_for_timeout(700)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Open participants list")').first.click()
        pg.wait_for_timeout(800)
        line = pg.locator("#modal label").filter(has_text="Tick Tester").first
        check("the person is offered", line.count() > 0)
        line.locator('input[type=checkbox]').first.check()
        pg.wait_for_timeout(700)
        pg.locator('.modal-f button:has-text("Done")').first.click()
        pg.wait_for_timeout(800)

        stored = pg.evaluate(STORE)
        se = [s for s in stored["sessions"] if s["id"] == "seT"][0]
        check("they are in the session", "c:cT" in se["participants"],
              str(se["participants"]))
        check("and the session says which lesson it was",
              "lT" in (se.get("fromLines") or []), str(se.get("fromLines")))

        open_client(pg, "Tick Tester")
        got = slots(pg)
        ticked = [t for t, _ in got]
        check("exactly one of the three lessons is ticked off",
              ticked.count(True) == 1, str(got))
        check("and it shows the day it landed on",
              any(t and w and w != "—" for t, w in got), str(got))

        # --- taking them out gives the lesson back ---------------------------
        pg.locator('[data-session-id="seT"]').first.click()
        pg.wait_for_timeout(700)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Open participants list")').first.click()
        pg.wait_for_timeout(800)
        line = pg.locator("#modal label").filter(has_text="Tick Tester").first
        line.locator('input[type=checkbox]').first.uncheck()
        pg.wait_for_timeout(700)
        pg.locator('.modal-f button:has-text("Done")').first.click()
        pg.wait_for_timeout(800)

        stored = pg.evaluate(STORE)
        se = [s for s in stored["sessions"] if s["id"] == "seT"][0]
        check("they are out of the session again", "c:cT" not in se["participants"],
              str(se["participants"]))
        check("and the lesson is not still claimed by it",
              "lT" not in (se.get("fromLines") or []), str(se.get("fromLines")))
        open_client(pg, "Tick Tester")
        check("so the course is owed all three again",
              not any(t for t, _ in slots(pg)), str(slots(pg)))

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
