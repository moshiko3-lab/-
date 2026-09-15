#!/usr/bin/env python3
"""The card has to be readable in Hebrew and never stop the forecast.

Two bug classes, both of which bit the first draft.

**Direction.** The card is an RTL page full of times, and a pair of times
separated by a dash lays itself out backwards unless it is isolated: the
first card printed the recommended hours as 18:30-14:00. This is the same
bug that reversed the tide line in the message, and it is invisible to
anybody reading the source -- the characters are in the right order and
the screen is not.

**The peaks.** The tide table keeps highs and lows in two separate lists,
so a curve drawn in the order they arrive zig-zags across the day. And a
label placed without regard to which kind of peak it is lands on the line
or on the hour axis.

Nothing here opens a browser or touches the network.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import card as C                                                # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


TIDES = {"highs": [{"t": "06:44", "m": "3.43"}, {"t": "19:10", "m": "3.15"}],
         "lows": [{"t": "00:33", "m": "0.56"}, {"t": "12:59", "m": "0.51"}]}
LIGHT = {"dawn": "05:51", "sunrise": "06:12",
         "sunset": "18:21", "dusk": "18:42"}
WINDOWS = [("08:00", "11:30"), ("14:00", "18:30")]


def page():
    return C.html_for("2026-09-16", TIDES, LIGHT,
                      {"near": "208", "off": "225"},
                      "0.6-1.2", "8,10", "5-11 קשר מצפון", WINDOWS)


def main():
    # --- the peaks are one series, in time order ------------------------
    pts = C.tide_points(TIDES)
    check("every peak is on the curve", len(pts) == 4, str(len(pts)))
    check("and they are in time order, not highs then lows",
          [p[2] for p in pts] == ["00:33", "06:44", "12:59", "19:10"],
          repr([p[2] for p in pts]))
    check("each one knows whether it is a high",
          [p[3] for p in pts] == [False, True, False, True],
          repr([p[3] for p in pts]))

    # --- a high is labelled above the line, a low below it --------------
    # Otherwise the text sits on the curve or on the hour axis, which is
    # what the first draft did to 00:33 and 12:59.
    html = page()
    rows = re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)"[^>]*/>'
                      r'<text x="[\d.]+" y="([\d.]+)"', html)
    check("every peak is drawn and labelled", len(rows) == 4, str(len(rows)))
    for (cx, cy, ty), p in zip(rows, pts):
        above = float(ty) < float(cy)
        check("%s is labelled %s the line" % (p[2], "above" if p[3] else "below"),
              above == p[3], "circle %s, text %s" % (cy, ty))

    # --- the hour ranges must not flip -----------------------------------
    # The whole card is dir="rtl". Without an isolate, "08:00–11:30" is laid
    # out as "11:30–08:00" and nothing in the source looks wrong.
    for a, b in WINDOWS:
        want = "⁦%s–%s⁩" % (a, b)
        check("%s–%s is isolated left-to-right" % (a, b), want in html,
              "looked for %r" % want)
    check("and the ranges carry dir=ltr as well",
          html.count('class="win" dir="ltr"') == len(WINDOWS))

    # --- everything the caller passed is actually on the card ------------
    for what, value in (("the surf height", "0.6-1.2"),
                        ("the period", "8,10"),
                        ("the wind", "5-11"),
                        ("the nearshore energy", "208"),
                        ("the offshore energy", "225"),
                        ("first light", "05:51"),
                        ("sunset", "18:21")):
        check("%s is on the card" % what, value in html, value)
    check("the day is named in Hebrew, and it is a Wednesday",
          "רביעי" in html and "16/9" in html)

    # --- and the tide heights are in metres, as the message is ----------
    check("the peaks are labelled in metres",
          "3.4 מ׳" in html and "0.5 מ׳" in html,
          [m for m in re.findall(r'>([\d.]+ מ׳)<', html)])

    # --- a day with no tide table is a reason, not a crash --------------
    thin = C.html_for("2026-09-16", {"highs": [], "lows": []}, {},
                      {"near": "—", "off": "—"}, "", "", "", [])
    check("a card with nothing in it still builds", "<body>" in thin)

    # --- and nothing here can stop a forecast ---------------------------
    import builtins
    real = builtins.__import__

    def no_pw(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError("no playwright here")
        return real(name, *a, **k)

    builtins.__import__ = no_pw
    try:
        path, why = C.draw("/tmp/never-drawn.png", "2026-09-16", TIDES, LIGHT,
                           {"near": "1", "off": "2"}, "1", "1", "", WINDOWS)
    finally:
        builtins.__import__ = real
    check("no playwright is a reason, not a crash",
          path == "" and "playwright" in why, "%r %r" % (path, why))
    check("and it leaves no file behind",
          not os.path.exists("/tmp/never-drawn.png"))

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
