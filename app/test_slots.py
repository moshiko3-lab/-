#!/usr/bin/env python3
"""The client list's session slots.

Their panel is a list of slots, not of names: open a client and a three-lesson
course gives three rows -- 1/3, 2/3, 3/3 -- each dragged onto its own session.
One draggable per person is what a single lesson needs; a course needs one per
session or it can only ever be scheduled once.

Hires are not slots. A board is not something a person attends.
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


def low(pg, sel):
    return (pg.inner_text(sel) or "").lower()


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const course = d.products.find(p => (p.sessions||1) >= 3
                   && p.ptype !== "rental" && !p.gearId);
  const hire = d.products.find(p => p.gearId);
  if (!course || !hire) return null;
  const gear = d.gear.find(g => g.id === hire.gearId);

  // a course for two named people: slots = sessions x people
  d.clients.push({id:"cCourse", name:"Course Client", phone:"+507 1", custom:{}});
  d.bookings.push({id:"bCourse", date: today, clientId:"cCourse",
    payments: [], refunds: [], custom:{}, notes:"",
    participants: [{pid:"p1", name:"Ana", custom:{}},
                   {pid:"p2", name:"Beto", custom:{}}],
    lines: [{lid:"lCourse", productId: course.id, qty:1, pax:2, hours:null,
             price: 180, wanted: today, sessionIds: []}]});

  // and a hire, which must not appear at all
  d.clients.push({id:"cHire", name:"Hire Client", custom:{}});
  d.bookings.push({id:"bHire", date: today, clientId:"cHire",
    participants: [], payments: [], refunds: [], custom:{}, notes:"",
    lines: [{lid:"lHire", productId: hire.id, qty:1, pax:1, hours:1, price:20,
             wanted: today, time:"09:00",
             unitId: gear && gear.units[0] ? gear.units[0].id : "",
             sessionIds: []}]});

  // three sessions to drop onto
  ["07:00","09:00","11:00"].forEach((t, i) => {
    d.sessions.push({id:"seT"+i, date: today, time: t, duration: 60,
      title:"Slot target "+(i+1), capacity: 8, minCapacity: 0, category:"",
      note:"", staffIds: [], participants: [], spot:"", level:"",
      ageFrom:"", ageTo:"", allDay:false, isPublic:true});
  });
  localStorage.setItem(k, JSON.stringify(d));
  return {course: course.name, sessions: course.sessions || 1};
}"""


def main():
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
        check("a multi-session course and a hire were seeded", seeded is not None,
              "no course with 3+ sessions in the catalogue")
        if seeded is None:
            b.close()
            return 1

        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)

        panel = low(pg, "#p-board")
        check("the course client is listed", "course client" in panel, panel[:200])
        check("the hire client is not", "hire client" not in panel, panel[:200])

        # open the course client
        rows = pg.locator(".cl-row")
        opened = False
        for i in range(rows.count()):
            if "course client" in (rows.nth(i).inner_text() or "").lower():
                rows.nth(i).locator(".cl-caret").click()
                opened = True
                break
        check("the row opens", opened)
        pg.wait_for_timeout(900)

        want = seeded["sessions"] * 2          # sessions x two participants
        slots = pg.locator(".cl-slot")
        check("one slot per session per person", slots.count() == want,
              f"{slots.count()} slots, expected {want}")
        first = (slots.first.inner_text() or "").replace("\n", " ")
        check("a slot names the person and its place in the course",
              "ana" in first.lower() and "/" + str(seeded["sessions"]) in first,
              first)
        check("the product is named above them",
              "course" in low(pg, ".cl-prod"), pg.inner_text(".cl-prod")[:80])
        check("nothing is scheduled yet", "!" in low(pg, ".cl-mark"),
              pg.inner_text(".cl-mark"))

        # drag one slot onto a session; only that one should land
        target = pg.locator('[data-session-id]').filter(has_text="Slot target").first
        box_t = target.bounding_box()
        box_s = slots.first.bounding_box()
        check("there is somewhere to drop it", box_t is not None and box_s is not None)
        if box_t and box_s:
            pg.mouse.move(box_s["x"] + box_s["width"] / 2, box_s["y"] + box_s["height"] / 2)
            pg.mouse.down()
            pg.mouse.move(box_t["x"] + 30, box_t["y"] + box_t["height"] / 2, steps=12)
            pg.mouse.up()
            pg.wait_for_timeout(1100)

            stored = pg.evaluate(
                "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
            seated = [s for s in stored["sessions"]
                      if s["id"].startswith("seT") and s["participants"]]
            check("the drag seated exactly one session", len(seated) == 1,
                  f"{len(seated)} sessions have people")
            if seated:
                check("with exactly one person in it",
                      len(seated[0]["participants"]) == 1,
                      str(seated[0]["participants"]))
                check("and the line is linked to it",
                      "lCourse" in (seated[0].get("fromLines") or []),
                      str(seated[0].get("fromLines")))

            # reopen and count what is left to place
            pg.click('#tabs button[data-id="board"]')
            pg.wait_for_timeout(1200)
            for i in range(pg.locator(".cl-row").count()):
                r = pg.locator(".cl-row").nth(i)
                if "course client" in (r.inner_text() or "").lower():
                    if r.locator(".cl-slot").count() == 0:
                        r.locator(".cl-caret").click()
                        pg.wait_for_timeout(800)
                    break
            done = pg.locator(".cl-slot.on")
            check("one slot now reads as scheduled", done.count() == 1,
                  f"{done.count()} scheduled")
            check("and shows the day it landed on",
                  "—" not in (done.first.inner_text() or ""),
                  done.first.inner_text().replace("\\n", " ") if done.count() else "")

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
