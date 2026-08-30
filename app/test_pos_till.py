#!/usr/bin/env python3
"""Drive the till: press tiles, add a customer, confirm, take the money.

Their new booking is a whole screen laid out like a till, not a dialog, and
this is the flow the school is in all day. The build check only proves the
screen renders; it cannot tell whether pressing a tile twice makes a quantity
of two, or whether confirming actually leaves a booking behind.
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
  // and no socket reaching out of a test: the live connection has its own,
  // in test_cloud, where the test holds the other end of it
  window.WebSocket = function() {
    this.readyState = 0;
    this.send = function() {};
    this.close = function() {};
  };
"""


def build():
    out = os.path.join(tempfile.mkdtemp(), "app.html")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def low(pg, sel):
    """Lowercased text: the stylesheet uppercases buttons and headings, so a
    case-sensitive assertion measures the CSS rather than the app."""
    return (pg.inner_text(sel) or "").lower()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2200)

        before = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}').bookings.length")

        pg.click("#btn-newbooking")
        pg.wait_for_timeout(1400)
        check("the till opens on + Booking", pg.locator(".pos-tile").count() > 0,
              str(pg.locator(".pos-tile").count()) + " tiles")
        check("it starts empty", "select a product" in low(pg, ".pos-lines"))
        check("confirm is refused while empty",
              pg.locator('.pos-foot button:has-text("Confirm")').is_disabled())

        # a tile for something that needs no configuring: a rental opens its
        # own pane, which is a different flow tested further down
        simple = None
        for i in range(pg.locator(".pos-tile").count()):
            pg.locator(".pos-tile").nth(i).click()
            pg.wait_for_timeout(500)
            if pg.locator(".cfg-body").count() == 0:
                simple = i
                break
            # back out of the pane and clear the line it added
            pg.click('.cfg-foot button:has-text("Add another product")')
            pg.wait_for_timeout(400)
            pg.locator(".pos-line .del").first.click()
            pg.wait_for_timeout(300)
        check("the till has a product that needs no configuring", simple is not None)
        pg.locator(".pos-line .del").first.click()
        pg.wait_for_timeout(400)

        # the price a tile shows must be the price pressing it charges
        tile_price = pg.locator(".pos-tile .px").nth(simple).inner_text().strip()
        pg.locator(".pos-tile").nth(simple).click()
        pg.wait_for_timeout(600)
        line_price = pg.locator(".pos-line .amt").first.inner_text().strip()
        check("the tile quotes what it charges",
              tile_price.rstrip("$€£") == line_price.rstrip("$€£"),
              f"tile {tile_price}, line {line_price}")

        # a second press of the same tile is a quantity of two, as a till behaves
        pg.locator(".pos-tile").nth(simple).click()
        pg.wait_for_timeout(600)
        check("pressing the same tile again makes it two",
              pg.locator(".pos-line").count() == 1 and
              pg.locator(".pos-line .qty span").first.inner_text().strip() == "2",
              pg.inner_text(".pos-lines")[:160].replace("\n", " / "))

        # a different tile is a second line
        other = 0 if simple != 0 else 1
        pg.locator(".pos-tile").nth(other).click()
        pg.wait_for_timeout(700)
        check("a different tile is a second line", pg.locator(".pos-line").count() == 2)
        if pg.locator(".cfg-body").count():
            pg.click('.cfg-foot button:has-text("Add another product")')
            pg.wait_for_timeout(500)

        # the stepper and the remove button
        pg.locator('.pos-line .qty button:has-text("−")').first.click()
        pg.wait_for_timeout(500)
        check("the stepper comes back down",
              pg.locator(".pos-line .qty span").first.inner_text().strip() == "1")
        pg.locator(".pos-line .del").nth(1).click()
        pg.wait_for_timeout(500)
        check("a line can be removed", pg.locator(".pos-line").count() == 1)

        totals = low(pg, ".pos-foot")
        check("it totals up", "subtotal" in totals and "tax" in totals and "total" in totals)

        # confirming without a customer asks for one rather than saving a stray
        pg.locator('.pos-foot button:has-text("Confirm")').click()
        pg.wait_for_timeout(700)
        check("a booking with no customer is refused",
              "customer" in (pg.inner_text("#toast") or "").lower(),
              pg.inner_text("#toast"))
        check("and it opens the customer dialog",
              "customer info" in low(pg, "#modal"), low(pg, "#modal")[:120])

        # the search box is type=search, so the text inputs start at the name
        pg.fill('#modal input[type=text] >> nth=0', "Nuria")
        pg.fill('#modal input[type=text] >> nth=1', "Campos")
        pg.fill('#modal input[type=email]', "nuria@example.com")
        pg.click('#modal button:has-text("Confirm")')
        pg.wait_for_timeout(900)
        check("the customer lands on the booking, both names",
              "nuria campos" in low(pg, ".pos-cust"), pg.inner_text(".pos-cust"))

        pg.locator('.pos-foot button:has-text("Confirm")').click()
        pg.wait_for_timeout(1200)
        check("the payment dialog follows the confirm",
              "payment" in low(pg, "#modal"),
              "toast=" + (pg.inner_text("#toast") or ""))
        pg.click('#modal button:has-text("Record payment")')
        pg.wait_for_timeout(900)

        after = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}')")
        check("the booking was saved", len(after.get("bookings", [])) == before + 1,
              f"{before} before, {len(after.get('bookings', []))} after")
        bk = (after.get("bookings") or [{}])[-1]
        check("it carries the line", len(bk.get("lines") or []) == 1,
              str(bk.get("lines")))
        check("it carries the payment", len(bk.get("payments") or []) == 1)
        check("the payment left a ticket", len(after.get("tickets") or []) >= 1)
        check("back on the bookings list",
              "nuria campos" in low(pg, "#p-bookings"),
              pg.inner_text("#p-bookings")[:200])

        # ---- a line that still needs answering blocks the confirm ----
        def tile_with(word):
            n = pg.locator(".pos-tile").count()
            for i in range(n):
                if word in (pg.locator(".pos-tile").nth(i).inner_text() or "").upper():
                    return i
            return None

        pg.click("#btn-newbooking")
        pg.wait_for_timeout(1300)
        i = tile_with("RENTAL")
        check("a rental is on the till", i is not None)
        pg.locator(".pos-tile").nth(i).click()
        pg.wait_for_timeout(900)
        check("a rental opens its own pane", pg.locator(".cfg-body").count() == 1)
        cfg = low(pg, ".cfg-body")
        for want in ("date", "starting hour", "duration", "gear"):
            check(f"the rental pane asks for {want}", want in cfg, cfg[:200])
        durations = pg.eval_on_selector_all(
            ".cfg-body select option", "e => e.map(x => x.textContent)")
        check("duration options carry their price",
              any("$" in (d or "") for d in durations), str(durations[:3]))
        check("the panel says a unit is missing",
              "please select unit" in low(pg, ".pos-lines"), pg.inner_text(".pos-lines")[:160])

        pg.locator('.pos-foot button:has-text("Confirm")').click()
        pg.wait_for_timeout(700)
        check("confirm is refused while a unit is missing",
              "unit" in (pg.inner_text("#toast") or "").lower(), pg.inner_text("#toast"))

        # picking a unit clears it
        sels = pg.locator(".cfg-body select")
        gear = sels.nth(sels.count() - 1)
        vals = gear.locator("option").all_text_contents()
        check("real boards are offered", len(vals) > 1, str(vals[:3]))
        gear.select_option(index=1)
        pg.wait_for_timeout(800)
        check("the missing-unit warning clears",
              "please select unit" not in low(pg, ".pos-lines"),
              pg.inner_text(".pos-lines")[:160])

        # ---- a course asks for its sessions ----
        pg.click('.cfg-foot button:has-text("Add another product")')
        pg.wait_for_timeout(800)
        j = tile_with("COURSE")
        if j is not None:
            pg.locator(".pos-tile").nth(j).click()
            pg.wait_for_timeout(1100)
            cfg = low(pg, ".cfg-body")
            check("the course pane asks for participants", "participants" in cfg, cfg[:200])
            check("the course pane counts its sessions", "sessions (0 of" in cfg, cfg[:250])
            # sessions can wait, so the panel counts them rather than blocking
            check("the panel says sessions are still to schedule",
                  "to schedule" in low(pg, ".pos-lines"),
                  pg.inner_text(".pos-lines")[:200])
            cards = pg.locator(".cfg-ses")
            if cards.count():
                cards.first.click()
                pg.wait_for_timeout(800)
                check("choosing a session counts up",
                      "1 of" in low(pg, ".pos-lines"), pg.inner_text(".pos-lines")[:200])

            # and the booking closes without them, because the school schedules later
            pg.click('.cfg-foot button:has-text("Add another product")')
            pg.wait_for_timeout(600)
            pg.locator('.pos-foot button:has-text("Confirm")').click()
            pg.wait_for_timeout(1200)
            check("a course with sessions unscheduled still confirms",
                  "payment" in low(pg, "#modal") or
                  "booking" in (pg.inner_text("#toast") or "").lower(),
                  "toast=" + (pg.inner_text("#toast") or ""))

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
