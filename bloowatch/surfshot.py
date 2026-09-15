#!/usr/bin/env python3
"""The Surfline chart for Playa Venao, as a picture for the forecast.

    python3 surfshot.py --out /tmp/surf.png
    python3 surfshot.py --out /tmp/surf.png --full /tmp/whole-page.png

The owner asked for the forecast to carry a Surfline screenshot the way
the 19:00 rota carries a photograph of the planner. Same shape as
`shot.py`, and the same rule as the board: **the picture is a bonus and
the message is the point.** Nothing here is allowed to stop a forecast.

**It needs the site on the network allow-list.** This container reaches
`services.surfline.com` -- that is how the numbers arrive -- but
`www.surfline.com` answers 403 at the proxy's CONNECT, which is the
environment's policy and not a fault to route around. Until the owner adds
the host to the `Bloowatch` environment the way he added Green-API's on
3/9/2026, `shoot()` returns no path and the reason, and the forecast goes
out as text exactly as it does today.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfline                                                 # noqa: E402

PAGE = "https://www.surfline.com/surf-report/playa-venao/%s" % surfline.SPOT

# Wide enough that the chart is not squeezed into a phone layout, and
# doubled so the numbers on it survive WhatsApp's preview. shot.py learned
# the same thing about the planner: a picture read on a phone is read at
# arm's length.
WIDTH, HEIGHT, SCALE = 1400, 1100, 2

# The chart sits well down the page and is built after load, so the page is
# scrolled to it and then given time. Nothing is clipped until it is there:
# an empty frame is worse than no picture, because it reads as a day with
# no surf.
#
# The clip runs from the top of the forecast section -- which carries the
# ten-day strip and the day headings -- to the bottom of the wind graph.
# Surf and wind are what the school's own message talks about; the swell
# and energy graphs below them are for somebody reading a forecast, not
# somebody deciding whether to come down.
# The graph shows three days side by side and the owner wants one: the day
# the forecast is about. The day headings ("Tomorrow, 9/16") sit above each
# column and give its left edge and width, so the clip is cut to that
# column and starts at the headings rather than at the ten-day strip --
# a strip that spans all three days is meaningless sliced to one.
BOTTOM = "[class*='windGraphSection']"

# The reading panels above each graph describe *now* -- current surf height,
# current wind -- which is today, and this picture is about tomorrow. They
# also sit across the full width, so cropping to one day cuts them in half
# and leaves the rest of their box as white space. Hidden rather than
# cropped around: they take up layout, so removing them closes the gap too.
HIDE = ("[class*='TooltipContainer'], [class*='SurfTooltip'], "
        "[class*='WindTooltip'], [class*='surfGraphTooltip'], "
        "[class*='windGraphTooltip']")
SETTLE_MS = 10000
SCROLL_MS = 5000


def _blocked(exc):
    """True when the proxy refused, rather than the page failing."""
    text = str(exc)
    return ("ERR_TUNNEL_CONNECTION_FAILED" in text
            or "403" in text and "CONNECT" in text)


def shoot(out, date=None, width=WIDTH, height=HEIGHT, scale=SCALE,
          timeout=90000):
    """Save the chart to `out`. Returns (path, reason).

    `date` is the day the forecast is about, as YYYY-MM-DD; the picture is
    cut to that day's column alone. Without it the whole three-day graph is
    kept, which is what the first version sent and what the owner asked to
    narrow.

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
                    user_agent=surfline.HEADERS["User-Agent"],
                    viewport={"width": width, "height": height},
                    device_scale_factor=scale, locale="en-US")
                p = ctx.new_page()
                p.goto(PAGE, wait_until="domcontentloaded", timeout=timeout)
                p.wait_for_timeout(SETTLE_MS)
                p.mouse.wheel(0, 3000)
                p.wait_for_timeout(SCROLL_MS)

                # The graphs follow the pointer: leaving it anywhere over
                # them freezes a reading panel open across the chart, and
                # the first shot taken this way had two of them covering
                # the surf it was meant to show. Park it in the corner.
                try:
                    p.mouse.move(2, 2)
                    p.wait_for_timeout(700)
                except Exception:                               # noqa: BLE001
                    pass

                try:
                    p.add_style_tag(content="%s { display: none !important; }"
                                    % HIDE)
                    p.wait_for_timeout(600)
                except Exception:                               # noqa: BLE001
                    pass                # a panel left in beats no picture

                want = ""
                if date:
                    d = date.split("-")
                    want = "%d/%d" % (int(d[1]), int(d[2]))      # 9/16

                box = p.evaluate("""(arg) => {
                    const [sel, want] = arg;
                    const end = document.querySelector(sel);
                    if (!end) return null;
                    const bottom = end.getBoundingClientRect().bottom
                                   + window.scrollY;

                    // The day headings above each column, widest first so
                    // the column's own width is used and not the label's.
                    const heads = [...document.querySelectorAll("*")]
                      .filter(e => e.children.length === 0
                              && /^[A-Z][a-z]+(day)?, \\d+\\/\\d+/
                                 .test((e.innerText || "").trim()))
                      .map(e => {
                        const r = e.getBoundingClientRect();
                        return {t: (e.innerText || "").trim(),
                                x: r.left + window.scrollX,
                                w: r.width,
                                y: r.top + window.scrollY};
                      })
                      .filter(h => h.w > 200)
                      .sort((a, b) => a.x - b.x);
                    if (!heads.length) return null;

                    let i = want
                      ? heads.findIndex(h => h.t.endsWith(" " + want))
                      : -1;
                    const top = heads[0].y - 24;
                    if (i < 0) {
                        // Whole graph: the day was not found, and a picture
                        // of three days beats no picture at all.
                        const last = heads[heads.length - 1];
                        return {x: heads[0].x, y: top,
                                width: (last.x + last.w) - heads[0].x,
                                height: bottom - top, whole: true};
                    }
                    // Cut at the midpoints of the gaps either side, so the
                    // divider lines are not clipped through.
                    const me = heads[i];
                    const prev = heads[i - 1];
                    const next = heads[i + 1];
                    const left = prev ? (prev.x + prev.w + me.x) / 2 : me.x;
                    const right = next ? (me.x + me.w + next.x) / 2
                                       : me.x + me.w;
                    return {x: left, y: top, width: right - left,
                            height: bottom - top};
                }""", [BOTTOM, want])

                if box and box["width"] > 200 and box["height"] > 200:
                    # full_page because the clip is far below the fold.
                    p.screenshot(path=out, clip=box, full_page=True)
                else:
                    # The graphs did not appear. The top of the page still
                    # names the spot and the day's conditions, which beats
                    # sending nothing -- and the caller reports which it got.
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
