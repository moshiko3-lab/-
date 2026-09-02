#!/usr/bin/env python3
"""A photograph of the board itself, taken from Bloowatch.

    python3 shot.py                        # tomorrow, to board.png
    python3 shot.py --date 2026-09-02 --out /tmp/wed.png
    python3 shot.py --keep-open            # leave the full page shot too

We draw our own version of this board in board.py, and it is a good likeness.
This is the thing itself: the same planner the office reads all day, in the
STAFF - 7D HORIZONTAL view, cropped to the one day.

It needs a real browser, because the agenda is an Ember app that builds the
grid in JavaScript. Two things about that browser are not obvious and both
cost an hour to find:

  * Chromium has to be launched with --ssl-version-max=tls1.2. Through this
    container's egress proxy a TLS 1.3 handshake is dropped mid-exchange and
    every page load comes back ERR_CONNECTION_RESET, while curl to the same
    host succeeds -- which sends you looking for a login problem that is not
    there.
  * The browser is the one already on the box; Playwright's own download is
    not available, so the binary is named explicitly.

Nothing here writes to Bloowatch. It signs in, changes the view, and reads.
"""
import argparse
import datetime as dt
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PANAMA = dt.timezone(dt.timedelta(hours=-5))
BASE = "https://shokogi.bloowatch.com"
VIEW = "STAFF - 7D HORIZONTAL"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def chromium():
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/usr/bin/chromium", "/usr/bin/google-chrome"):
        found = sorted(glob.glob(pat))
        if found:
            return found[-1]
    raise SystemExit("no chromium on this machine")


def label(date):
    """How the board writes a day at the head of its own block: WED 2 SEP."""
    d = dt.date.fromisoformat(date)
    return "%s %d %s" % (DOW[d.weekday()], d.day, MONTHS[d.month - 1])


def shoot(date, out, email, password, full=None, width=2200, scale=2):
    from playwright.sync_api import sync_playwright

    day = label(date)
    with sync_playwright() as pw:
        b = pw.chromium.launch(
            executable_path=chromium(),
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  # see the note at the top: without this every load resets
                  "--ssl-version-max=tls1.2"],
            proxy={"server": os.environ.get("HTTPS_PROXY")}
            if os.environ.get("HTTPS_PROXY") else None)
        p = b.new_page(viewport={"width": width, "height": 1300},
                       device_scale_factor=scale)
        p.goto(BASE + "/signin", wait_until="networkidle", timeout=90000)
        p.fill("input[type=text]", email)
        p.fill("input[type=password]", password)
        p.click("button")
        p.wait_for_timeout(8000)

        p.goto(BASE + "/agenda/activities", wait_until="networkidle",
               timeout=60000)
        p.wait_for_timeout(6000)
        p.locator("a.dropdown-toggle", has_text="ACTIVITIES").first.click()
        p.wait_for_timeout(1500)
        # Ember listens for a real mouse event, not element.click(), so the
        # menu item is found by its own text and then actually clicked on.
        at = p.evaluate("""(want) => {
          for (const e of document.querySelectorAll('.dropdown-menu a, .dropdown-menu li, .dropdown-menu span')) {
            if ((e.innerText || '').trim() === want) {
              const r = e.getBoundingClientRect();
              if (r.width > 0) return {x: r.x + r.width / 2, y: r.y + r.height / 2};
            }
          }
          return null;
        }""", VIEW)
        if not at:
            b.close()
            raise SystemExit("could not find the %r view" % VIEW)
        p.mouse.click(at["x"], at["y"])
        p.wait_for_timeout(10000)
        # the staff view is the one with people down the side
        if "NAFTUL" not in p.inner_text("body").upper():
            b.close()
            raise SystemExit("the board did not switch to %r" % VIEW)

        if full:
            p.screenshot(path=full, full_page=True)

        box = p.evaluate("""(day) => {
          // the board renders one .cp-Panel per day, each headed "WED 2 SEP"
          for (const e of document.querySelectorAll('.cp-Panel')) {
            if ((e.innerText || '').trim().startsWith(day)) {
              const r = e.getBoundingClientRect();
              // the panel's own box is exact; a couple of pixels either way
              // either clip the last name or let the next day's tide curve
              // creep into the picture
              const pad = 1;
              return {x: Math.max(0, r.x + window.scrollX),
                      y: Math.max(0, r.y + window.scrollY - 2),
                      width: Math.min(r.width,
                                      document.documentElement.scrollWidth - r.x),
                      height: r.height + pad};
            }
          }
          return null;
        }""", day)
        if not box:
            b.close()
            raise SystemExit("no block headed %r on the board" % day)
        p.screenshot(path=out, clip=box)
        b.close()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--out", default=os.path.join(HERE, "board.png"))
    ap.add_argument("--full", default="", help="also keep the whole page")
    ap.add_argument("--width", type=int, default=2200,
                    help="the wider the viewport, the more of the "
                         "day the board fits across")
    a = ap.parse_args()
    date = a.date or (dt.datetime.now(PANAMA).date()
                      + dt.timedelta(days=1)).isoformat()
    email = os.environ.get("BLOOWATCH_EMAIL")
    password = os.environ.get("BLOOWATCH_PASSWORD")
    if not email or not password:
        print("error: BLOOWATCH_EMAIL and BLOOWATCH_PASSWORD are not set",
              file=sys.stderr)
        return 1
    print(shoot(date, a.out, email, password, a.full or None, a.width))
    return 0


if __name__ == "__main__":
    sys.exit(main())
