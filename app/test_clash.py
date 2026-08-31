#!/usr/bin/env python3
"""One person cannot be in two lessons at the same hour.

The school spotted this in the session picker: a course offering 07:30 and
08:00 as two of its ten lessons, when a lesson runs an hour. Pick both and the
same person is in the water twice at once -- which in practice means an
instructor standing on the beach waiting for somebody who is not coming.

Gear has been protected from this since the rental board was built: a board
cannot go out to two people at once. A person had no such check anywhere.

Now every way of seating somebody asks the same question, and refuses in the
same words. Touching at the edges is deliberately allowed: an eight o'clock
hour and a nine o'clock hour are two lessons, not a clash, and a school that
could not book those back to back would be worse off than before.
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

# the school's own shape: an hour-long lesson at 07:30, 08:00 and 09:00
SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const base = d.products.find(p => !p.gearId && p.ptype !== "rental");
  if (!base) return null;

  const course = JSON.parse(JSON.stringify(base));
  course.id = "prX"; course.name = "10X CLASH COURSE";
  course.category = "CLASH TEST"; course.sessions = 10;
  course.sessionsAtBooking = false;
  d.products.push(course);
  d.settings.kinds.push({k: "clash_test", l: "CLASH TEST", color: "#e04b78"});

  d.clients = [{id: "cX", name: "Clash Client", phone: "+507 5", custom: {}}];
  d.bookings = [{id: "bkX", date: today, clientId: "cX",
    payments: [], refunds: [], custom: {}, notes: "", participants: [],
    lines: [{lid: "lX", productId: "prX", qty: 1, pax: 1, hours: null,
             price: 600, wanted: today, sessionIds: []}]}];

  // 07:30 overlaps 08:00; 08:00 and 09:00 only touch
  d.sessions = [["seEarly", "07:30"], ["seMid", "08:00"], ["seLate", "09:00"]]
    .map(function(p) {
      return {id: p[0], date: today, time: p[1], duration: 60,
        title: "CLASH TEST", capacity: 12, minCapacity: 0,
        category: "CLASH TEST", note: "", staffIds: [], participants: [],
        spot: "", level: "", ageFrom: "", ageTo: "", allDay: false,
        isPublic: true};
    });
  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def seated_in(pg, sid):
    s = [x for x in pg.evaluate(STORE)["sessions"] if x["id"] == sid]
    return bool(s) and "c:cX" in s[0]["participants"]


def seat(pg, sid, name="Clash Client"):
    """try to seat somebody through the participants list of one session"""
    pg.locator('[data-session-id="%s"]' % sid).first.click()
    pg.wait_for_timeout(700)
    pg.locator(".sess-pop .kebab").first.click()
    pg.wait_for_timeout(400)
    pg.locator('.rowmenu button:has-text("Open participants list")').first.click()
    pg.wait_for_timeout(800)
    pg.locator("#modal label").filter(has_text=name).first \
      .locator('input[type=checkbox]').first.click()
    pg.wait_for_timeout(800)
    txt = (pg.inner_text("#toast") or "").lower()
    pg.locator('.modal-f button:has-text("Done")').first.click()
    pg.wait_for_timeout(700)
    return txt


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

        check("three hour-long lessons were seeded",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2400)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1500)

        # --- the 08:00 is taken ---------------------------------------------
        seat(pg, "seMid")
        check("they are in the eight o'clock", seated_in(pg, "seMid"))

        # --- 07:30 overlaps it and must be refused --------------------------
        said = seat(pg, "seEarly")
        check("the half-seven is refused", not seated_in(pg, "seEarly"))
        check("and it says where they already are",
              "already in" in said and "08:00" in said, said or "(nothing said)")

        # --- 09:00 only touches, and must be allowed ------------------------
        seat(pg, "seLate")
        check("the nine o'clock is allowed — it only touches",
              seated_in(pg, "seLate"))

        # --- the picker the school was looking at ---------------------------
        # nothing is in the book while a booking is being typed, so the picker
        # has to ask the same question of what has been chosen on the line
        pg.evaluate("""() => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          d.sessions.forEach(s => { s.participants = []; });
          localStorage.setItem(k, JSON.stringify(d));
        }""")
        pg.reload()
        pg.wait_for_timeout(2400)
        # the picker lives in the booking flow: start one and add the course
        pg.click("#btn-newbooking")
        pg.wait_for_timeout(1400)
        pg.locator(".pos-tile").filter(has_text="10X CLASH COURSE").first.click()
        pg.wait_for_timeout(1200)

        cards = pg.locator(".cfg-ses")
        check("the picker offers the lessons", cards.count() >= 3,
              str(cards.count()))

        def card_at(t):
            for i in range(cards.count()):
                if t in (cards.nth(i).inner_text() or ""):
                    return cards.nth(i)
            return None

        c8 = card_at("08:00")
        check("the eight o'clock is offered", c8 is not None)
        if c8 is not None:
            c8.click()
            pg.wait_for_timeout(800)
            c730 = card_at("07:30")
            check("the half-seven is dimmed once eight is chosen",
                  c730 is not None and
                  (c730.evaluate("e => e.style.opacity") or "1") != "1",
                  c730.evaluate("e => e.style.opacity") if c730 else "no card")
            c730.click()
            pg.wait_for_timeout(800)
            said = (pg.inner_text("#toast") or "").lower()
            check("and clicking it is refused in words",
                  "same hour" in said, said or "(nothing said)")
            chosen = pg.evaluate("""() => {
              const on = [];
              document.querySelectorAll(".cfg-ses.on").forEach(
                c => on.push(c.innerText.replace(/\\s+/g, " ").trim()));
              return on;
            }""")
            check("so only one of the two hours is chosen",
                  not any("07:30" in c for c in chosen), str(chosen))
            c9 = card_at("09:00")
            if c9 is not None:
                c9.click()
                pg.wait_for_timeout(800)
                chosen = pg.evaluate("""() => {
                  const on = [];
                  document.querySelectorAll(".cfg-ses.on").forEach(
                    c => on.push(c.innerText.replace(/\\s+/g, " ").trim()));
                  return on;
                }""")
                check("but nine, which only touches, is taken",
                      any("09:00" in c for c in chosen), str(chosen))

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
