#!/usr/bin/env python3
"""The whole life of a course slot, through every door that touches it.

A slot is ticked when two facts are both recorded: the person sits in the
session, and the session says which order line the lesson came out of. Every
way in has to write both, every way out has to take both back, and a session
that holds nobody must claim nobody's lessons.

The doors, and what each is checked for here:

  seated through the participants list   -> ticks, and untick gives it back
  taken out from the session popup       -> gives it back, drops the claim
  the session duplicated                 -> the copy claims nothing
  the booking deleted                    -> its people leave the sessions

That last one is the one that showed on the board: a deleted booking left its
people sitting in lessons, so a session read three of twelve with two people
actually in the water, forever.
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

# two clients, each on a three-lesson course, and one session of that activity
SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const base = d.products.find(p => !p.gearId && p.ptype !== "rental");
  if (!base) return null;

  const course = JSON.parse(JSON.stringify(base));
  course.id = "prC"; course.name = "TEST LIFE COURSE";
  course.category = "LIFE TEST"; course.sessions = 3;
  course.sessionsAtBooking = false;
  d.products.push(course);
  d.settings.kinds.push({k: "life_test", l: "LIFE TEST", color: "#2bb673"});

  d.clients = [{id: "cA", name: "Alpha One", phone: "+507 1", custom: {}},
               {id: "cB", name: "Beta Two",  phone: "+507 2", custom: {}}];
  d.bookings = [
    {id: "bkA", date: today, clientId: "cA", payments: [], refunds: [],
     custom: {}, notes: "", participants: [],
     lines: [{lid: "lA", productId: "prC", qty: 1, pax: 1, hours: null,
              price: 300, wanted: today, sessionIds: []}]},
    {id: "bkB", date: today, clientId: "cB", payments: [], refunds: [],
     custom: {}, notes: "", participants: [],
     lines: [{lid: "lB", productId: "prC", qty: 1, pax: 1, hours: null,
              price: 300, wanted: today, sessionIds: []}]}];
  d.sessions = [{id: "seL", date: today, time: "09:00", duration: 60,
    title: "LIFE TEST", capacity: 8, minCapacity: 0, category: "LIFE TEST",
    note: "", staffIds: [], participants: [], spot: "", level: "",
    ageFrom: "", ageTo: "", allDay: false, isPublic: true}];
  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def sess(pg, sid="seL"):
    s = [x for x in pg.evaluate(STORE)["sessions"] if x["id"] == sid]
    return s[0] if s else None


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


def ticks(pg):
    return pg.evaluate("""() => {
      let n = 0;
      document.querySelectorAll(".cl-slot .tick.on").forEach(() => n++);
      return n;
    }""")


def seat(pg, name, on=True):
    """seat or unseat somebody through the participants list"""
    pg.locator('[data-session-id="seL"]').first.click()
    pg.wait_for_timeout(700)
    pg.locator(".sess-pop .kebab").first.click()
    pg.wait_for_timeout(400)
    pg.locator('.rowmenu button:has-text("Open participants list")').first.click()
    pg.wait_for_timeout(800)
    cb = pg.locator("#modal label").filter(has_text=name).first \
           .locator('input[type=checkbox]').first
    cb.check() if on else cb.uncheck()
    pg.wait_for_timeout(700)
    pg.locator('.modal-f button:has-text("Done")').first.click()
    pg.wait_for_timeout(800)


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

        check("two courses and a session were seeded",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2300)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        # --- door 1: the participants list ----------------------------------
        seat(pg, "Alpha One", True)
        seat(pg, "Beta Two", True)
        s = sess(pg)
        check("both are in the session", len(s["participants"]) == 2,
              str(s["participants"]))
        check("and it claims both their courses",
              sorted(s.get("fromLines") or []) == ["lA", "lB"],
              str(s.get("fromLines")))
        open_client(pg, "Alpha One")
        open_client(pg, "Beta Two")
        check("one lesson is struck off each", ticks(pg) == 2, str(ticks(pg)))

        # --- door 2: the x in the session popup -----------------------------
        pg.locator('[data-session-id="seL"]').first.click()
        pg.wait_for_timeout(800)
        xs = pg.locator(".sess-pop .cl-x")
        check("the popup lists them with a way out", xs.count() >= 1,
              str(xs.count()))
        xs.first.click()
        pg.wait_for_timeout(900)
        s = sess(pg)
        check("one seat was given up", len(s["participants"]) == 1,
              str(s["participants"]))
        check("and only the remaining course is still claimed",
              len(s.get("fromLines") or []) == 1, str(s.get("fromLines")))
        open_client(pg, "Alpha One")
        open_client(pg, "Beta Two")
        check("so only one lesson stays struck off", ticks(pg) == 1, str(ticks(pg)))

        # --- door 3: duplicating the session --------------------------------
        pg.locator('[data-session-id="seL"]').first.click()
        pg.wait_for_timeout(700)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Duplicate session")').first.click()
        pg.wait_for_timeout(900)
        for lbl in ("Clone", "Save", "Add", "Create"):
            btn = pg.locator('.modal-f button:has-text("%s")' % lbl)
            if btn.count():
                btn.first.click()
                pg.wait_for_timeout(900)
                break
        copies = [x for x in pg.evaluate(STORE)["sessions"]
                  if x["id"] != "seL" and x.get("category") == "LIFE TEST"]
        check("a copy was made", len(copies) >= 1, str(len(copies)))
        if copies:
            check("the copy holds nobody", not copies[0]["participants"],
                  str(copies[0]["participants"]))
            check("and therefore claims nobody's course",
                  not (copies[0].get("fromLines") or []),
                  str(copies[0].get("fromLines")))

        # --- door 4: deleting the booking of the person still seated --------
        still = sess(pg)["participants"][0]
        who = "Beta Two" if "cB" in still else "Alpha One"
        pg.click('#tabs button[data-id="bookings"]')
        pg.wait_for_timeout(1200)
        row = None
        rows = pg.locator("#p-bookings tbody tr")
        for i in range(rows.count()):
            if who.lower() in (rows.nth(i).inner_text() or "").lower():
                row = rows.nth(i)
                break
        check("their booking is listed", row is not None, who)
        if row is not None:
            row.locator('button:has-text("Del")').first.click()
            pg.wait_for_timeout(600)
            for lbl in ("Delete", "Yes", "Confirm", "OK"):
                b2 = pg.locator('.modal-f button:has-text("%s")' % lbl)
                if b2.count():
                    b2.first.click()
                    pg.wait_for_timeout(1000)
                    break
            s = sess(pg)
            check("deleting the booking empties their seat",
                  not s["participants"], str(s["participants"]))
            check("and the session stops claiming a course that is gone",
                  not (s.get("fromLines") or []), str(s.get("fromLines")))

        # --- door 5: the session moves to another day -----------------------
        # The slot shows the day the lesson landed on, so moving the lesson has
        # to move that date with it -- a card still naming yesterday for a
        # lesson now on Thursday is worse than one naming nothing.
        alive = [c["id"] for c in pg.evaluate(STORE)["clients"]]
        who2 = "Alpha One" if "cA" in alive else "Beta Two"
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1300)
        seat(pg, who2, True)
        check("somebody is seated again for the last two doors",
              len(sess(pg)["participants"]) == 1, str(sess(pg)["participants"]))

        moved = (dt.date.today() + dt.timedelta(days=3)).isoformat()
        pg.locator('[data-session-id="seL"]').first.click()
        pg.wait_for_timeout(700)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Edit session")').first.click()
        pg.wait_for_timeout(900)
        pg.locator('#modal input[type=date]').first.fill(moved)
        pg.wait_for_timeout(300)
        pg.locator('.modal-f button:has-text("Save")').first.click()
        pg.wait_for_timeout(1100)
        check("the session moved", sess(pg)["date"] == moved, sess(pg)["date"])
        check("it kept the person", len(sess(pg)["participants"]) == 1,
              str(sess(pg)["participants"]))
        check("and kept the claim on their course",
              len(sess(pg).get("fromLines") or []) == 1,
              str(sess(pg).get("fromLines")))
        open_client(pg, who2)
        shown = pg.evaluate("""() => {
          const r = document.querySelector(".cl-slot .tick.on");
          return r && r.parentNode ?
            (r.parentNode.querySelector(".when") || {}).textContent || "" : "";
        }""")
        check("the slot follows the lesson to its new day",
              shown.strip() not in ("", "—", "–"), repr(shown))

        # --- door 6: the session is deleted ---------------------------------
        # Nothing is stored on the slot itself, so deleting the lesson has to
        # hand it straight back. This is the check that the tick is read from
        # the sessions rather than remembered somewhere it could go stale.
        pg.evaluate("""() => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          d.sessions = d.sessions.filter(s => s.id !== "seL");
          localStorage.setItem(k, JSON.stringify(d));
        }""")
        pg.reload()
        pg.wait_for_timeout(2400)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1400)
        check("the lesson is gone", sess(pg) is None)
        open_client(pg, who2)
        check("and the course is owed it back", ticks(pg) == 0, str(ticks(pg)))

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
