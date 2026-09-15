#!/usr/bin/env python3
"""The Surfline chart for Playa Venao, as a picture for the forecast.

    python3 surfshot.py --out /tmp/surf.png
    python3 surfshot.py --out /tmp/surf.png --date 2026-09-16

The owner asked for the forecast to carry a Surfline screenshot the way
the 19:00 rota carries a photograph of the planner. Same shape as
`shot.py`, and the same rule as the board: **the picture is a bonus and
the message is the point.** Nothing here is allowed to stop a forecast --
`shoot()` returns a reason instead of raising, and the caller sends the
text.

**It needs two hosts on the network allow-list**, both added to the
`Bloowatch` environment on 15/9/2026: `www.surfline.com` for the page and
`wa.cdn-surfline.com` for its stylesheets, scripts and icons. With only
the first the page renders as bare HTML. Everything else the page reaches
for stays blocked and is not needed -- analytics, two ad networks, a
cookie banner, map tiles, cam stills -- and each of those would be a third
party given a way into the environment that holds the school's keys. If
either host is ever dropped the proxy answers 403 to CONNECT, which is
policy, not a fault: `shoot()` says so in as many words and the forecast
goes out as text.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfline                                                 # noqa: E402

PAGE = "https://www.surfline.com/surf-report/playa-venao/%s" % surfline.SPOT

# The phone layout, on the owner's suggestion after seeing the desktop one.
# It is the better picture by some way: one day per screen instead of three
# side by side, bars wide enough to read at a glance, and a tide curve the
# desktop page does not show at all. A forecast is read on a phone, so the
# phone's own layout is the one that suits it.
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
          "Mobile/15E148 Safari/604.1")
WIDTH, HEIGHT, SCALE = 430, 932, 3

# Which day the graphs show is a button, not a crop: the phone layout has a
# day selector and picking tomorrow redraws every graph for tomorrow. That
# is why this reads better than cutting a three-day chart into thirds.
DAY_BUTTON = "button.graph-day"

TOP = "[class*='surfGraphSection']"
BOTTOM = "[class*='tideGraphSection']"

# Above the surf graph sit the conditions bar, the surf height in words and
# the swell components; below the tide graph, first light and sunset. All of
# it is worth having, so the clip is opened out at each end. The top pad is
# the one that matters: at 120 it cut the conditions bar off, and the height
# panel it was widened for is the only place a number appears in writing.
PAD_TOP, PAD_BOTTOM = 210, 70

SETTLE_MS = 11000
SCROLL_MS = 6000
REDRAW_MS = 7000

# The owner asked for waves and tide and nothing else -- "רק את הגלים
# גובהה טייד" -- and three things sit between them: the wind graph, the
# wind reading above it, and the two "View hourly data" upsell rows. All
# four selectors below are that gap. Hiding is what closes it; cropping
# cannot, because the two graphs the picture is for are on either side.
#
# `featurePaywallWrapper` is both upsell rows at once, the one under the
# surf graph included -- it is an advert for a paid account either way.
#
# The reading panels are *not* hidden. They were, while the picture came
# from the desktop layout, where they describe *now* and bled into a crop
# of tomorrow. Here the day is chosen with a button, so the panel follows
# it: with tomorrow selected it reads "SURF HEIGHT 3-4ft, waist to chest",
# which is the number the owner went looking for and did not find when it
# was hidden. It is also the only place the height is written rather than
# drawn.
#
# Hiding goes in a stylesheet, always. An attempt to hide the "View hourly
# data" rows by walking the DOM crashed the page's own components into
# "Something went wrong here" where the graphs had been. Injecting CSS
# leaves React's tree alone; changing it does not.
HIDE = ("[class*='windGraphSection'], [class*='windTooltipContainer'], "
        "[class*='featurePaywallWrapper']")


def _labels(date):
    """How the day selector spells `date`: ("Tomorrow", "9/16").

    Two spellings because the button says "Tomorrow" for the next day and
    "Thu, 9/17" for the ones after, and the forecast is usually -- but not
    always -- about tomorrow.
    """
    import datetime as dt
    d = dt.date.fromisoformat(date)
    today = (dt.datetime.utcnow() - dt.timedelta(hours=5)).date()
    word = {0: "Today", 1: "Tomorrow"}.get((d - today).days, "")
    return [word or "\u0000", "%d/%d" % (d.month, d.day)]


def _blocked(exc):
    """True when the proxy refused, rather than the page failing."""
    text = str(exc)
    return ("ERR_TUNNEL_CONNECTION_FAILED" in text
            or "403" in text and "CONNECT" in text)


def shoot(out, date=None, width=WIDTH, height=HEIGHT, scale=SCALE,
          timeout=90000):
    """Save the chart to `out`. Returns (path, reason).

    `date` is the day the forecast is about, as YYYY-MM-DD. It is used to
    press that day's button in the page's own day selector, so every graph
    redraws for it; without a date the page is left on today. This is not
    a crop -- an earlier version cut a three-day desktop chart into thirds
    and had to throw away the day headings to do it.

    A path and an empty reason on success; "" and a sentence otherwise. It
    never raises, because every caller is a send that must still go.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:                                    # noqa: BLE001
        return "", "playwright is not available here: %s" % exc

    try:
        from shot import chromium
        where = chromium()
    except Exception:                                           # noqa: BLE001
        where = None

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    try:
        with sync_playwright() as pw:
            how = {"args": surfline.BROWSER_ARGS}
            if where:
                how["executable_path"] = where
            if proxy:
                how["proxy"] = {"server": proxy}
            b = pw.chromium.launch(**how)
            try:
                ctx = b.new_context(
                    user_agent=IPHONE,
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale, is_mobile=True,
                    has_touch=True, locale="en-US")
                p = ctx.new_page()
                p.goto(PAGE, wait_until="domcontentloaded", timeout=timeout)
                p.wait_for_timeout(SETTLE_MS)

                # One scroll, then wait. A second one, added to give the
                # wind graph more time, broke both graphs and opened a
                # cam-matches panel over the chart.
                p.mouse.wheel(0, 2500)
                p.wait_for_timeout(SCROLL_MS)

                picked = False
                if date:
                    picked = bool(p.evaluate("""(arg) => {
                        const [sel, want] = arg;
                        const days = [...document.querySelectorAll(sel)];
                        const hit = days.find(b => {
                            const t = (b.innerText || "").trim();
                            return t.startsWith(want[0]) || t.includes(want[1]);
                        });
                        if (!hit) return false;
                        hit.click();
                        return true;
                    }""", [DAY_BUTTON, _labels(date)]))
                    if picked:
                        p.wait_for_timeout(REDRAW_MS)

                if HIDE:
                    try:
                        p.add_style_tag(
                            content="%s { display: none !important; }" % HIDE)
                        p.wait_for_timeout(600)
                    except Exception:                           # noqa: BLE001
                        pass            # a panel left in beats no picture

                box = p.evaluate("""(sel) => {
                    const a = document.querySelector(sel[0]);
                    const b = document.querySelector(sel[1]);
                    if (!a || !b) return null;
                    const top = a.getBoundingClientRect().top + window.scrollY;
                    const bot = b.getBoundingClientRect().bottom
                                + window.scrollY;
                    return {top: top, bottom: bot};
                }""", [TOP, BOTTOM])

                if box and box["bottom"] - box["top"] > 200:
                    y = max(0, box["top"] - PAD_TOP)
                    p.screenshot(path=out, full_page=True,
                                 clip={"x": 0, "y": y, "width": width,
                                       "height": (box["bottom"] - y)
                                       + PAD_BOTTOM})
                else:
                    # The graphs did not appear. The top of the page still
                    # names the spot and today's conditions, which beats
                    # sending nothing.
                    p.screenshot(path=out, clip={"x": 0, "y": 0,
                                                 "width": width,
                                                 "height": height})
            finally:
                b.close()
    except Exception as exc:                                    # noqa: BLE001
        if _blocked(exc):
            return "", ("www.surfline.com is not on this environment's "
                        "network allow-list — the proxy refused the "
                        "connection. That is policy, not a fault: add the "
                        "host to the Bloowatch environment.")
        return "", "surfline could not be photographed: %s" % str(exc)[:200]

    if not (os.path.exists(out) and os.path.getsize(out) > 0):
        return "", "the screenshot came out empty"
    return out, ""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="where to write the PNG")
    ap.add_argument("--date", default="",
                    help="YYYY-MM-DD: cut the picture to this day's column")
    ap.add_argument("--width", type=int, default=WIDTH)
    ap.add_argument("--height", type=int, default=HEIGHT)
    a = ap.parse_args()
    path, why = shoot(a.out, a.date, a.width, a.height)
    if not path:
        print("no picture: " + why, file=sys.stderr)
        return 1
    print("%s (%d bytes)" % (path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
