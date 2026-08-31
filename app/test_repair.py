#!/usr/bin/env python3
"""Putting old lessons back on the course they came from.

This is the school's real state, reproduced: a client on a ten-lesson course
with three lessons already taught. The sessions hold them, so the card lists
all three under Sessions -- and the course row still reads 0 of 10, because
those sessions never recorded which course the lesson came out of. A card that
says nothing has been taught invites the school to teach it again.

The repair only claims what it can prove: the person is in the session, exactly
one course still owes them a place, and the activity matches. Two possible
answers means it leaves the lesson alone and says so, because guessing here
spends somebody's course. And it never touches the book until the list has been
shown and confirmed -- pressing Cancel has to leave everything exactly as it
was, which is the check that matters most.
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

# Yuval's shape: one ten-lesson course, three lessons already sat in with the
# link never written -- exactly what the old code left behind.
SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const base = d.products.find(p => !p.gearId && p.ptype !== "rental");
  if (!base) return null;

  const course = JSON.parse(JSON.stringify(base));
  course.id = "prR"; course.name = "10X REPAIR COURSE";
  course.category = "REPAIR TEST"; course.sessions = 10;
  course.sessionsAtBooking = false;
  d.products.push(course);
  d.settings.kinds.push({k: "repair_test", l: "REPAIR TEST", color: "#7b61ff"});

  d.clients = [{id: "cR", name: "Repair Client", phone: "+507 9", custom: {}}];
  d.bookings = [{id: "bkR", date: today, clientId: "cR",
    payments: [], refunds: [], custom: {}, notes: "", participants: [],
    lines: [{lid: "lR", productId: "prR", qty: 1, pax: 1, hours: null,
             price: 600, wanted: today, sessionIds: []}]}];

  // three lessons taught: the person is in them, the link was never written
  d.sessions = ["08:00", "09:00", "09:30"].map(function(t, i) {
    return {id: "seR" + i, date: today, time: t, duration: 60,
      title: "REPAIR TEST", capacity: 12, minCapacity: 0,
      category: "REPAIR TEST", note: "", staffIds: [],
      participants: ["c:cR"], spot: "", level: "", ageFrom: "", ageTo: "",
      allDay: false, isPublic: true};
  });
  localStorage.setItem(k, JSON.stringify(d));
  return true;
}"""

STORE = "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))"


def links(pg):
    return pg.evaluate("""() => {
      const d = JSON.parse(localStorage.getItem("shokogi.manager.v1"));
      let n = 0;
      d.sessions.forEach(s => { if ((s.fromLines || []).indexOf("lR") >= 0) n++; });
      return n;
    }""")


def open_repair(pg):
    pg.click('#tabs button[data-id="settings"]')
    pg.wait_for_timeout(1200)
    pg.locator('#p-settings button:has-text("Check course links")').first.click()
    pg.wait_for_timeout(1100)


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

        check("the school's state was reproduced",
              pg.evaluate(SEED, today) is True)
        pg.reload()
        pg.wait_for_timeout(2400)

        check("three lessons hold the person, none knows the course",
              links(pg) == 0, str(links(pg)))

        # --- the card is wrong in exactly the way the school saw -------------
        pg.click('#tabs button[data-id="clients"]')
        pg.wait_for_timeout(1200)
        row = pg.locator("#p-clients tbody tr").filter(has_text="Repair Client").first
        row.locator('button:has-text("Card")').first.click()
        pg.wait_for_timeout(1100)
        card = pg.inner_text("#modal") or ""
        check("the card lists the three lessons", card.count("REPAIR TEST") >= 3,
              str(card.count("REPAIR TEST")))
        check("but the course reads none of ten", "0 / 10" in card or "0/10" in card,
              [l for l in card.split("\n") if "/" in l][:4])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(600)

        # --- cancelling must change nothing ---------------------------------
        open_repair(pg)
        body = pg.inner_text("#modal") or ""
        check("the repair offers exactly the three", "3 lesson" in body, body[:160])
        check("and shows who and which course",
              "Repair Client" in body and "10X REPAIR COURSE" in body, body[:220])
        pg.locator('.modal-f button:has-text("Cancel")').first.click()
        pg.wait_for_timeout(800)
        check("cancelling leaves the book exactly as it was", links(pg) == 0,
              str(links(pg)))

        # --- repairing ------------------------------------------------------
        open_repair(pg)
        pg.locator('.modal-f button:has-text("Repair")').first.click()
        pg.wait_for_timeout(1200)
        check("all three lessons are put back", links(pg) == 3, str(links(pg)))

        pg.click('#tabs button[data-id="clients"]')
        pg.wait_for_timeout(1200)
        row = pg.locator("#p-clients tbody tr").filter(has_text="Repair Client").first
        row.locator('button:has-text("Card")').first.click()
        pg.wait_for_timeout(1100)
        card = pg.inner_text("#modal") or ""
        check("and the course now reads three of ten",
              "3 / 10" in card or "3/10" in card,
              [l for l in card.split("\n") if "/" in l][:4])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(600)

        # --- running it again finds nothing left -----------------------------
        open_repair(pg)
        body = pg.inner_text("#modal") or ""
        check("running it again has nothing to do",
              "nothing to repair" in body.lower(), body[:160])
        pg.locator('.modal-f button:has-text("Close")').first.click()
        pg.wait_for_timeout(600)
        check("and it did not invent an eleventh lesson", links(pg) == 3,
              str(links(pg)))

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
