#!/usr/bin/env python3
"""The chart must never be able to stop the forecast.

That is the whole risk this file guards. surfshot opens a browser, loads a
third-party page, waits on JavaScript and presses a button in it — five
ways to hang or throw, at six in the evening, in front of the one send
that reaches two hundred customers. Every one of them has to come back as
"no picture, here is why" and let the text go.

The other half is the day. The picture is only right if it shows the day
the message is about, and which day the page draws is decided by the label
this file computes for the selector button. Get that wrong and the message
says tomorrow while the chart shows today, which is worse than no chart:
nothing about the picture would look wrong.

Nothing here touches the network or opens a browser.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfshot as S                                            # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def panama_today():
    return (dt.datetime.utcnow() - dt.timedelta(hours=5)).date()


def main():
    # --- the day the button is looking for ------------------------------
    today = panama_today()
    word, num = S._labels(today.isoformat())
    check("today is spelled the way the selector spells it", word == "Today",
          repr(word))

    tom = today + dt.timedelta(days=1)
    word, num = S._labels(tom.isoformat())
    check("and tomorrow is 'Tomorrow', not a date", word == "Tomorrow",
          repr(word))
    check("with the date as a fallback in the page's own format",
          num == "%d/%d" % (tom.month, tom.day), repr(num))

    # Further out the button says "Thu, 9/17" and there is no word for it.
    far = today + dt.timedelta(days=3)
    word, num = S._labels(far.isoformat())
    check("a day further out has no word and is matched on its date",
          word == chr(0) and num == "%d/%d" % (far.month, far.day),
          "%r %r" % (word, num))
    # chr(0) and not "": startsWith("") is true of every button, so an empty
    # word would match the first day in the list — today — and the chart
    # would quietly show the wrong day under tomorrow's forecast.
    check("and that word can never match a button by accident",
          not "Today".startswith(word) and not "Tomorrow".startswith(word),
          repr(word))

    # --- a proxy refusal is named as policy, not as a fault -------------
    check("a blocked tunnel is recognised",
          S._blocked(Exception("net::ERR_TUNNEL_CONNECTION_FAILED at ...")))
    check("and so is a 403 on CONNECT",
          S._blocked(Exception("403 to CONNECT (policy denial)")))
    check("an ordinary timeout is not mistaken for one",
          not S._blocked(Exception("Timeout 90000ms exceeded")))

    # --- and every failure comes back as a sentence, never a raise ------
    # Each of these is a real way the evening can go wrong: playwright gone,
    # the browser refusing to start, the page throwing, the host blocked.
    import builtins
    real_import = builtins.__import__

    def no_playwright(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError("no playwright here")
        return real_import(name, *a, **k)

    builtins.__import__ = no_playwright
    try:
        path, why = S.shoot("/tmp/never-written.png")
    finally:
        builtins.__import__ = real_import
    check("no playwright is a reason, not a crash",
          path == "" and "playwright" in why, "%r %r" % (path, why))
    check("and it writes no file", not os.path.exists("/tmp/never-written.png"))

    class Boom(object):
        def __init__(self, exc):
            self.exc = exc

        def __call__(self):
            return self

        def __enter__(self):
            raise self.exc

        def __exit__(self, *a):
            return False

    import playwright.sync_api as PW
    real_pw = PW.sync_playwright
    for name, exc, want in (
            ("a blocked host", Exception("net::ERR_TUNNEL_CONNECTION_FAILED"),
             "allow-list"),
            ("a page that throws", Exception("Timeout 90000ms exceeded"),
             "could not be photographed")):
        PW.sync_playwright = Boom(exc)
        try:
            path, why = S.shoot("/tmp/never-written.png")
        finally:
            PW.sync_playwright = real_pw
        check("%s is a reason, not a crash" % name,
              path == "" and want in why, "%r" % why)

    # --- the crop keeps the two graphs and drops everything between -----
    # The owner asked for waves and tide only. The page puts the wind graph,
    # a wind reading and two "View hourly data" adverts in between, so the
    # picture is made by hiding those rather than by cropping -- the two
    # things it is for are on either side of them.
    #
    # The danger in a `[class*=...]` selector is that it is a substring
    # match: one written a little wider would take the surf or tide graph
    # with it, the clip would collapse, and `shoot()` would still hand back
    # a perfectly valid picture of the top of the page.
    fragments = [f.split("'")[1] for f in S.HIDE.split(",") if "'" in f]
    check("the crop is made by hiding, and the hiding is CSS",
          len(fragments) == 3 and "[class*=" in S.HIDE, repr(S.HIDE))

    # Real class names off the page, on 16/9/2026.
    GONE = ("GraphContainer_windGraphSection__xyz",
            "GraphContainer_windTooltipContainer__nducO",
            "GraphContainer_featurePaywallWrapper__p0Frv")
    KEPT = ("GraphContainer_surfGraphSection__tkfKf",
            "GraphContainer_tideGraphSection__Ml8cp",
            "GraphContainer_surfTooltipContainer__abc",
            "GraphContainer_tideGraphHeader__73UVN",
            "ForecastGraphSurf_forecastGraphContainer__1kdxq")

    def hidden(cls):
        return any(f in cls for f in fragments)

    for cls in GONE:
        check("%s is hidden" % cls.split("_")[1], hidden(cls))
    for cls in KEPT:
        check("%s survives the stylesheet" % cls.split("_")[1], not hidden(cls))

    # And the clip still runs from the one to the other, so whatever is
    # hidden between them simply closes up.
    check("the clip is still surf graph to tide graph",
          hidden(S.TOP) is False and hidden(S.BOTTOM) is False
          and "surfGraph" in S.TOP and "tideGraph" in S.BOTTOM,
          "%s -> %s" % (S.TOP, S.BOTTOM))

    # The top pad is what reaches up to "SURF HEIGHT 3-4ft, waist to chest".
    # It is the only place the height is written as a number, and it is the
    # thing the owner went looking for and did not find. At 120 it was cut.
    check("and the clip still opens out far enough to take the height panel",
          S.PAD_TOP >= 200, str(S.PAD_TOP))

    # --- the picture is of the school's spot, and nowhere else ----------
    # A page URL built from the wrong id would produce a perfectly good
    # chart of somebody else's beach, and nothing in the message would say.
    import surfline
    check("the page is Playa Venao's own", surfline.SPOT in S.PAGE, S.PAGE)

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
