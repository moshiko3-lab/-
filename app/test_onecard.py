#!/usr/bin/env python3
"""One card per client on the board's client list.

Theirs had moshe levy three times down the rail, once per booking. A person is
a person: one card with his name on it, everything he bought inside it under
its own product heading, and the day each product came from beside it so two of
the same product do not read as one purchase.

A booking with nobody on it keeps a card of its own -- there is no name to
gather it under.
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


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const a = d.products.find(p => !p.gearId && p.ptype !== "rental");
  const b = d.products.find(p => !p.gearId && p.ptype !== "rental" && p !== a);
  if (!a || !b) return null;

  const yesterday = new Date(new Date(today + "T12:00:00").getTime() - 864e5)
                      .toISOString().slice(0, 10);

  d.clients = [{id:"cOne", name:"Moshe Levy", phone:"+507 3", custom:{}}];
  d.bookings = [];
  d.sessions = [];

  // three bookings for one person: two today, one yesterday
  [["b1", today, a.id], ["b2", today, b.id], ["b3", yesterday, a.id]]
    .forEach(([id, date, pid]) => {
      d.bookings.push({id: id, date: date, clientId:"cOne", ref: id.toUpperCase(),
        payments: [], refunds: [], custom:{}, notes:"", participants: [],
        lines: [{lid:"l" + id, productId: pid, qty:1, pax:1, hours:null,
                 price: 80, wanted: date, sessionIds: []}]});
    });

  // and one with nobody on it, which has no name to be gathered under
  d.bookings.push({id:"bNone", date: today, clientId:"", ref:"BNONE",
    payments: [], refunds: [], custom:{}, notes:"", participants: [],
    lines: [{lid:"lNone", productId: a.id, qty:1, pax:1, hours:null,
             price: 80, wanted: today, sessionIds: []}]});

  localStorage.setItem(k, JSON.stringify(d));
  return {a: a.name, b: b.name};
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
        check("three bookings for one person were seeded", seeded is not None)
        if seeded is None:
            br.close()
            return 1
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)

        named = pg.locator(".cl-row").filter(has_text="Moshe Levy")
        check("his name is on the rail once, not three times",
              named.count() == 1, str(named.count()) + " cards")
        check("the ownerless booking still has its own card",
              pg.locator(".cl-row").count() == 2,
              str(pg.locator(".cl-row").count()) + " cards in all")
        if named.count() != 1:
            br.close()
            return 1

        card = named.first
        card.locator(".cl-caret").click()
        pg.wait_for_timeout(800)

        prods = card.locator(".cl-prod")
        check("all three purchases are inside his card", prods.count() == 3,
              str(prods.count()) + " products")
        names = " ".join((prods.nth(i).inner_text() or "")
                         for i in range(prods.count())).lower()
        check("each product is named", seeded["a"].lower() in names
              and seeded["b"].lower() in names, names[:180])
        yest = (dt.date.today() - dt.timedelta(days=1)).strftime("%d/%m")
        check("and says which day it came from",
              yest in names and dt.date.today().strftime("%d/%m") in names,
              names[:180])
        check("every slot is under it", card.locator(".cl-slot").count() >= 3,
              str(card.locator(".cl-slot").count()) + " slots")

        # the menu can no longer mean "delete booking" with three of them
        card.locator(".kebab").first.click()
        pg.wait_for_timeout(500)
        menu = (pg.inner_text(".rowmenu") or "").lower()
        check("the menu names each booking", menu.count("open booking") == 3,
              menu[:200])
        check("and offers to merge the two on one day", "merge" in menu,
              menu[:200])
        check("without a blanket delete", "delete booking" not in menu,
              menu[:200])

        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
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
