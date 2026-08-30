#!/usr/bin/env python3
"""Real clients, and the bookings they actually made.

A hundred names on their own are not worth loading. What makes the app worth
clicking is that each one arrives with what they bought: the product priced
the way the counter priced it, the board that went out by its own name, and
what was paid and by what method.

Skips itself when no clients.json has been exported -- that file holds real
people and is not in the repository, so a clean checkout has no clients and
the app is right to have none.
"""
import json
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


def main():
    src = os.path.join(HERE, "clients.json")
    if not os.path.exists(src):
        print("  --   no clients.json in this checkout, nothing to check")
        return 0
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    # Two of their customer records can be the same person: "yoga morning"
    # with no phone number is a walk-in label typed twice. The import merges
    # them onto one client and hangs both bookings off it, so what should
    # arrive is the number of distinct people, not the number of rows.
    want = len({(c["name"], c.get("phone", "")) for c in data["clients"]})
    named = [c for c in data["clients"] if c.get("phone")]
    check("the export has clients to load", want > 0)
    check("and bookings behind them", len(data["bookings"]) > 0)

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(3200)

        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}')")
        got = stored.get("clients") or []
        bks = stored.get("bookings") or []
        check("every client loaded on the first run", len(got) == want,
              f"{len(got)} of {want}")
        check("and the same person is not on file twice",
              len({(c.get("name"), c.get("phone", "")) for c in got}) == len(got),
              f"{len(got)} rows")
        check("their bookings came with them", len(bks) >= len(data["bookings"]) * 0.9,
              f"{len(bks)} of {len(data['bookings'])}")

        # a booking is only useful if its lines point at real products
        lines = [l for bk in bks for l in (bk.get("lines") or [])]
        check("the bookings carry lines", len(lines) > 50, str(len(lines)))
        pids = {p["id"] for p in (stored.get("products") or [])}
        check("every line points at a product in the catalogue",
              all(l.get("productId") in pids for l in lines),
              str([l.get("productId") for l in lines[:3]]))
        check("the lines carry a price", all(
            isinstance(l.get("price"), (int, float)) for l in lines))

        # the board that actually went out
        units = {u["id"] for g in (stored.get("gear") or [])
                 for u in (g.get("units") or [])}
        hired = [l for l in lines if l.get("unitId")]
        check("a hire names the board that went out", len(hired) > 0,
              "no line carries a unit")
        check("and that board is one of theirs",
              all(l["unitId"] in units for l in hired),
              str([l.get("unitId") for l in hired[:3]]))

        # money
        paid = [p for bk in bks for p in (bk.get("payments") or [])]
        check("payments came across", len(paid) > 0)
        check("each has an amount and a method",
              all(p.get("amount") is not None and p.get("method") in ("cash", "card")
                  for p in paid),
              str(paid[:2]))

        # and the screens show them
        pg.click('#tabs button[data-id="clients"]')
        pg.wait_for_timeout(1400)
        txt = low(pg, "#p-clients")
        check("the clients screen counts them", str(want) in txt, txt[:160])
        if named:
            who = named[0]["name"].lower()
            check("a client is listed by name", who in txt, who)

        pg.click('#tabs button[data-id="bookings"]')
        pg.wait_for_timeout(1400)
        bt = low(pg, "#p-bookings")
        check("the bookings screen lists them", "$" in bt, bt[:200])

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
