#!/usr/bin/env python3
"""The tide, which is the column a surf school actually reads.

Their agenda draws a curve; the times and heights behind it come from
Bloowatch's own spot endpoint and travel with the catalogue. This checks the
table shows them, and that "rising" and "dropping" are the right way round --
getting that backwards would send a lesson out on the wrong water.
"""
import datetime as dt
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
    cat = os.path.join(HERE, "catalog.json")
    tides = json.load(open(cat)).get("tides", []) if os.path.exists(cat) else []
    check("the catalogue carries a tide table", len(tides) > 30,
          f"{len(tides)} days")
    if not tides:
        return 1
    with_heights = [t for t in tides if any(h.get("m") for h in t.get("highs", []))]
    check("with heights, not just times", len(with_heights) > 30,
          f"{len(with_heights)} days have heights")

    today = dt.date.today().isoformat()
    row = [t for t in tides if t["date"] == today]
    check("today is in it", bool(row), f"range {tides[0]['date']}..{tides[-1]['date']}")

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2500)

        stored = pg.evaluate(
            "() => (JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}')"
            ".tides || []).length")
        check("the table lands in the store", stored > 30, f"{stored} days")

        pg.click('#tabs button[data-id="schedule"]')
        pg.wait_for_timeout(1200)
        txt = low(pg, "#p-schedule")
        check("the day's tide is on the planning", "high" in txt and "low" in txt,
              txt[:200])
        check("with the height beside the time", " m" in txt, txt[:250])
        check("no longer says it is unset", "not set for this day" not in txt)

        # rising and dropping have to match the day's own high and low times
        if row:
            t = row[0]
            highs = [h["t"] for h in t.get("highs", [])]
            lows = [l["t"] for l in t.get("lows", [])]
            check("the day has both a high and a low", bool(highs and lows),
                  json.dumps(t)[:160])
            verdicts = pg.evaluate(
                """([hs, ls]) => {
                  const rows = [...document.querySelectorAll('#p-schedule tbody tr')];
                  return rows.map(r => {
                    const c = [...r.querySelectorAll('td')];
                    if (c.length < 3) return null;
                    const hour = (c[1].textContent||'').trim();
                    const tide = (r.textContent||'').toLowerCase();
                    return {hour, rising: tide.includes('rising'),
                            dropping: tide.includes('dropping')};
                  }).filter(Boolean);
                }""", [highs, lows])
            checked = 0
            wrong = []
            for v in verdicts:
                if not re_hhmm(v["hour"]):
                    continue
                m = mins(v["hour"])
                nxt = nearest_after(m, [(mins(x), True) for x in highs] +
                                    [(mins(x), False) for x in lows])
                if nxt is None:
                    continue
                checked += 1
                want_rising = nxt[1]
                if v["rising"] != want_rising or v["dropping"] == want_rising:
                    wrong.append(f"{v['hour']} said "
                                 f"{'rising' if v['rising'] else 'dropping'}")
            check("every row read the tide the right way round",
                  checked > 0 and not wrong, f"{checked} rows, wrong: {wrong[:3]}")

        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)
        curves = pg.locator("#p-board svg path").count()
        check("the board draws the curve", curves > 0, f"{curves} paths")

        check("no uncaught errors", not errs, "; ".join(errs[:3]))
        b.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


def re_hhmm(s):
    return len(s) == 5 and s[2] == ":" and s[:2].isdigit()


def mins(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def nearest_after(m, events):
    later = sorted([e for e in events if e[0] >= m])
    return later[0] if later else None


if __name__ == "__main__":
    sys.exit(main())
