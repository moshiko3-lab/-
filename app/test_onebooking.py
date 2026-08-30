#!/usr/bin/env python3
"""One client, one day, one booking.

Somebody who takes a course in the morning and hires a board in the afternoon
has bought two things, not been to the school twice. Two rows for them is two
rows to chase, invoice and reconcile, and the school said so plainly.

So a sale at the till joins whatever that client already has open that day,
and the rows made before it worked that way can still be folded together.
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


def store(pg):
    return pg.evaluate("() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const plain = d.products.find(p => p.ptype !== "rental" && !p.gearId
                  && (p.sessions || 1) === 1);
  if (!plain) return null;
  d.bookings = [];
  d.clients.push({id:"cOne", name:"Moshe Levy", phone:"+507 5", custom:{}});
  // one booking already open for them today
  d.bookings.push({id:"bOne", date: today, clientId:"cOne", ref:"AAAAA",
    payments: [{id:"pay1", date: today, amount: 60, method:"cash", note:""}],
    refunds: [], participants: [], custom:{}, notes:"first",
    lines: [{lid:"lOne", productId: plain.id, qty:1, pax:1, hours:null,
             price: 60, wanted: today, sessionIds: []}]});
  // and a second, the way it used to be made
  d.bookings.push({id:"bTwo", date: today, clientId:"cOne", ref:"BBBBB",
    payments: [], refunds: [], participants: [], custom:{}, notes:"second",
    lines: [{lid:"lTwo", productId: plain.id, qty:1, pax:1, hours:null,
             price: 60, wanted: today, sessionIds: []}]});
  localStorage.setItem(k, JSON.stringify(d));
  return {product: plain.name};
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
        pg.wait_for_timeout(2600)

        seeded = pg.evaluate(SEED, today)
        check("a client with two bookings on one day was seeded", seeded is not None)
        if seeded is None:
            b.close()
            return 1
        pg.reload()
        pg.wait_for_timeout(2200)

        # --- the tidy-up on rows that already exist ---
        pg.click('#tabs button[data-id="bookings"]')
        pg.wait_for_timeout(1400)
        merge = pg.locator('#p-bookings button:has-text("Merge")')
        check("a duplicate row offers to merge", merge.count() == 2,
              str(merge.count()))
        merge.first.click()
        pg.wait_for_timeout(600)
        check("it asks first", "merge" in low(pg, "#modal"), low(pg, "#modal")[:120])
        pg.click('#modal button:has-text("Merge")')
        pg.wait_for_timeout(900)

        st = store(pg)
        mine = [x for x in st["bookings"] if x["clientId"] == "cOne"]
        check("the two become one", len(mine) == 1, str(len(mine)))
        if mine:
            check("carrying both lines", len(mine[0]["lines"]) == 2,
                  str(len(mine[0]["lines"])))
            check("and the money already taken",
                  sum(p["amount"] for p in mine[0]["payments"]) == 60,
                  str(mine[0]["payments"]))
            check("and both notes", "first" in (mine[0]["notes"] or "")
                  and "second" in (mine[0]["notes"] or ""), mine[0].get("notes"))
        check("no offer to merge is left",
              pg.locator('#p-bookings button:has-text("Merge")').count() == 0)

        # --- and the till does not make a second one in the first place ---
        # The app's script runs inside its own closure, so nothing is reachable
        # from evaluate(). This goes through the counter the way a person does.
        def sell(day):
            """One sale at the till for Moshe Levy on a given day."""
            pg.click("#btn-newbooking")
            pg.wait_for_timeout(1200)
            if day:
                # the date lives behind the booking's own menu
                pg.locator(".pos-sh .kebab").last.click()
                pg.wait_for_timeout(500)
                pg.click('.rowmenu button:has-text("Booking date")')
                pg.wait_for_timeout(600)
                pg.fill('#modal input[type=date]', day)
                pg.click('#modal button:has-text("Save")')
                pg.wait_for_timeout(700)
            # a tile that needs no configuring: a hire opens its own pane
            picked = False
            for i in range(pg.locator(".pos-tile").count()):
                pg.locator(".pos-tile").nth(i).click()
                pg.wait_for_timeout(450)
                if pg.locator(".cfg-head").count() == 0:
                    picked = True
                    break
                pg.locator(".cfg-head .kebab").click()   # take it back off
                pg.wait_for_timeout(350)
            if not picked:
                return False
            pg.locator('.pos-foot button:has-text("Confirm")').click()
            pg.wait_for_timeout(700)
            # the customer dialog opens because the sale has nobody on it yet
            pg.fill('#modal input[type=search]', "Moshe")
            pg.wait_for_timeout(600)
            pg.locator('#modal .pick-row').first.click()
            pg.wait_for_timeout(700)
            pg.locator('.pos-foot button:has-text("Confirm")').click()
            pg.wait_for_timeout(1200)
            if pg.locator("#scrim").is_visible():
                pg.keyboard.press("Escape")     # the payment dialog that follows
                pg.wait_for_timeout(500)
            return True

        before = len([x for x in store(pg)["bookings"] if x["clientId"] == "cOne"])
        lines_before = len([x for x in store(pg)["bookings"]
                            if x["clientId"] == "cOne"][0]["lines"])
        check("a sale went through the till", sell(today))
        mine = [x for x in store(pg)["bookings"] if x["clientId"] == "cOne"]
        check("a second sale that day makes no second booking",
              len(mine) == before, f"{before} before, {len(mine)} after")
        if len(mine) == before and mine:
            check("the line joined the one that was open",
                  len(mine[0]["lines"]) == lines_before + 1,
                  f"{lines_before} lines before, {len(mine[0]['lines'])} after")

        # a different day is a different booking, which is the point of the rule
        other = (dt.date.today() + dt.timedelta(days=3)).isoformat()
        check("a sale on another day went through", sell(other))
        mine = [x for x in store(pg)["bookings"] if x["clientId"] == "cOne"]
        check("another day is still its own booking", len(mine) == before + 1,
              str(len(mine)))

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
