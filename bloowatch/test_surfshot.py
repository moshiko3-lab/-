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
