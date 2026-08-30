#!/usr/bin/env python3
"""How long a session is, and where that number comes from.

Bloowatch keeps the length on the activity calendar: SURF PACK an hour, FOIL
FREE TOW an hour and a half, and every session opened on that calendar starts
there. We were dropping that field on import and opening every session on a
hardcoded 90 minutes, whatever it was for.

So: choosing a calendar takes its length. Choosing a product takes the length
its own name states -- a 2 HOUR FOIL TOW is two hours, not the calendar's hour
and a half, which is the one place ours is deliberately better than theirs --
and falls back to the calendar when the name says nothing. Typing a length
keeps it, whatever is picked afterwards.
"""
import json
import os
import re
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


def mins(hhmmss):
    p = str(hhmmss or "").split(":")
    return (int(p[0]) * 60 + int(p[1])) if len(p) > 1 else 0


def named_mins(name):
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:-|\s)?\s*HOURS?\b", name.upper())
    if m:
        return round(float(m.group(1).replace(",", ".")) * 60)
    m = re.search(r"(\d+)\s*(?:MIN|MINUTES?)\b", name.upper())
    return int(m.group(1)) if m else 0


def main():
    cat = json.load(open(os.path.join(HERE, "catalog.json")))
    cats = {c["name"]: mins(c.get("duration")) for c in cat["categories"]}
    check("their calendars carry a length", any(cats.values()), str(cats))

    # a product whose name states hours that differ from its calendar's, which
    # is the case the school hit: a two-hour tow on an hour-and-a-half calendar
    picks = [p for p in cat["products"]
             if named_mins(p["name"]) and p.get("category")
             and cats.get(p["category"]) and named_mins(p["name"]) != cats[p["category"]]]
    check("a product states hours its calendar does not",
          bool(picks), "none in the catalogue")
    if not picks:
        return 1
    prod = picks[0]
    want_prod = named_mins(prod["name"])
    want_cat = cats[prod["category"]]

    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2600)

        stored = pg.evaluate("() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        kinds = {k["l"]: k.get("mins") for k in stored["settings"]["kinds"]}
        check("the import keeps each calendar's length",
              kinds.get(prod["category"]) == want_cat,
              "%s: %r, theirs %r" % (prod["category"], kinds.get(prod["category"]),
                                     want_cat))

        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1400)

        def open_form():
            pg.click('#p-board button:has-text("+ Session")')
            pg.wait_for_timeout(700)

        def duration():
            return pg.locator('#modal input[type=number]').first.input_value()

        # the calendar's own length
        open_form()
        pg.locator("#modal select").first.select_option(label=prod["category"])
        pg.wait_for_timeout(400)
        check("choosing a calendar takes its length", duration() == str(want_cat),
              duration() + " wanted " + str(want_cat))

        # the product's stated hours win over the calendar
        label = prod["name"] + (" · " + prod["category"] if prod["category"] else "")
        pg.locator("#modal select").first.select_option(label=label)
        pg.wait_for_timeout(400)
        check("a product's own hours win over the calendar's",
              duration() == str(want_prod), duration() + " wanted " + str(want_prod))
        check("and it says where the number came from",
              "from what" in (pg.inner_text("#modal") or "").lower(),
              (pg.inner_text("#modal") or "")[:200])

        # a length typed by hand is not overwritten
        pg.locator('#modal input[type=number]').first.fill("45")
        pg.wait_for_timeout(200)
        pg.locator("#modal select").first.select_option(label=prod["category"])
        pg.wait_for_timeout(400)
        check("a length typed by hand stays", duration() == "45", duration())
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)

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
