#!/usr/bin/env python3
"""Two brothers on the same course go into the same lesson in one drag.

Dragging students in one at a time is the same drag two, three, four times over
-- and the school books families and groups all day. The empty box on a slot
that has not been placed is now a way of saying "this one too": tick as many as
are going in together, from one course or from four different ones, and
dragging any of them carries the whole set.

The box never means two things at once: a lesson already placed shows a green
tick instead and cannot be dragged at all. And every refusal that guards a
single drag still guards each member of the group on its own -- capacity, the
activity, and being somewhere else at that hour -- so a group drop puts in
whoever can go and says plainly who could not.
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

# three students on the same course, one session with room for two of them
SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const base = d.products.find(p => !p.gearId && p.ptype !== "rental");
  if (!base) return null;

  const course = JSON.parse(JSON.stringify(base));
  course.id = "prG"; course.name = "5X GROUP COURSE";
  course.category = "GROUP TEST"; course.sessions = 5;
  course.sessionsAtBooking = false;
  d.products.push(course);
  d.settings.kinds.push({k: "group_test", l: "GROUP TEST", color: "#2bb673"});

  d.clients = [];
  d.bookings = [];
  [["cG1", "Gina One"], ["cG2", "Gino Two"], ["cG3", "Gary Three"]]
    .forEach(function(p, i) {
      d.clients.push({id: p[0], name: p[1], phone: "+507 " + i, custom: {}});
      d.bookings.push({id: "bk" + p[0], date: today, clientId: p[0],
        payments: [], refunds: [], custom: {}, notes: "", participants: [],
        lines: [{lid: "l" + p[0], productId: "prG", qty: 1, pax: 1,
                 hours: null, price: 300, wanted: today, sessionIds: []}]});
    });

  // room for two only, so the third is turned away and says so
  d.sessions = [{id: "seG", date: today, time: "09:00", duration: 60,
    title: "GROUP TEST", capacity: 2, minCapacity: 0, category: "GROUP TEST",
    note: "", staffIds: [], participants: [], spot: "", level: "",
    ageFrom: "", ageTo: "", allDay: false, isPublic: true}];
  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def seats(pg):
    s = [x for x in pg.evaluate(STORE)["sessions"] if x["id"] == "seG"]
    return s[0]["participants"] if s else []


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


def first_slot(pg, name):
    """the row has to be on screen: with several clients open the list is
    longer than its panel, and a drag that starts off the fold hits nothing"""
    r = open_client(pg, name)
    if r is None:
        return None
    sl = r.locator(".cl-slot").first
    try:
        sl.scroll_into_view_if_needed(timeout=3000)
        pg.wait_for_timeout(250)
    except Exception:
        pass
    return sl


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

        check("three students on one course were seeded",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2400)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        # --- tick three, from three different courses -----------------------
        for who in ("Gina One", "Gino Two", "Gary Three"):
            sl = first_slot(pg, who)
            check("%s has a lesson to place" % who, sl is not None and sl.count() > 0)
            sl.locator(".tick").first.click()
            pg.wait_for_timeout(500)

        picked = pg.locator(".cl-slot .tick.pick").count()
        check("all three are ticked and shown as picked", picked == 3, str(picked))
        check("and none of them counts as done",
              pg.locator(".cl-slot .tick.on").count() == 0,
              str(pg.locator(".cl-slot .tick.on").count()))

        # --- drag one of them: the whole set goes ---------------------------
        sl = first_slot(pg, "Gina One")
        blk = pg.locator('[data-session-id="seG"]').first
        a, b = sl.bounding_box(), blk.bounding_box()
        check("there is something to drag and somewhere to drop",
              bool(a) and bool(b))
        pg.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
        pg.mouse.down()
        pg.mouse.move(a["x"] + 40, a["y"] + 10, steps=4)
        ghost = pg.evaluate("""() => {
          const g = [...document.querySelectorAll("body > div")]
            .filter(n => n.style.position === "fixed" && n.style.zIndex === "80");
          return g.length ? g[0].textContent : "";
        }""")
        check("the drag says how many are coming", "3" in ghost, repr(ghost))
        pg.mouse.move(b["x"] + 25, b["y"] + b["height"] / 2, steps=14)
        pg.mouse.up()
        pg.wait_for_timeout(1100)

        got = seats(pg)
        check("the session took as many as it had room for", len(got) == 2,
              str(got))
        said = (pg.inner_text("#toast") or "").lower()
        check("and it says who was left out",
              "left out" in said and "full" in said, said or "(nothing said)")

        # each of the two that went in is struck off their own course
        stored = pg.evaluate(STORE)
        se = [x for x in stored["sessions"] if x["id"] == "seG"][0]
        check("both courses are credited, not one twice",
              len(se.get("fromLines") or []) == 2, str(se.get("fromLines")))

        check("the ticks are spent once they land",
              pg.locator(".cl-slot .tick.pick").count() == 0,
              str(pg.locator(".cl-slot .tick.pick").count()))

        # --- one that is not ticked still drags alone -----------------------
        pg.evaluate("""() => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          const s = d.sessions.find(x => x.id === "seG");
          s.capacity = 6;
          localStorage.setItem(k, JSON.stringify(d));
        }""")
        pg.reload()
        pg.wait_for_timeout(2400)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1400)
        before = len(seats(pg))
        # whoever the full session turned away is the one still draggable --
        # which of the three that is depends on the order the group goes in,
        # so ask rather than assume
        inside = seats(pg)
        left = [n for i, n in [("cG1", "Gina One"), ("cG2", "Gino Two"),
                               ("cG3", "Gary Three")]
                if ("c:" + i) not in inside]
        check("somebody was left out to drag on their own", len(left) == 1,
              str(left) + " of " + str(inside))
        sl = first_slot(pg, left[0])
        blk = pg.locator('[data-session-id="seG"]').first
        a, b = sl.bounding_box(), blk.bounding_box()
        pg.mouse.move(a["x"] + a["width"] / 2, a["y"] + a["height"] / 2)
        pg.mouse.down()
        pg.mouse.move(b["x"] + 25, b["y"] + b["height"] / 2, steps=14)
        pg.mouse.up()
        pg.wait_for_timeout(1100)
        check("the one left out still drags on their own",
              len(seats(pg)) == before + 1, "%d then %d" % (before, len(seats(pg))))

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
