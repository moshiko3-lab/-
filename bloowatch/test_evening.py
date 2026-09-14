#!/usr/bin/env python3
"""The check that evening.py says exactly what the old six commands said.

Collapsing the forecast routine into one command is only safe if the
message it produces is byte for byte the message the documented path
produced. Otherwise the routine stops drifting and the *text* starts --
which is worse, because nobody is watching the wording once the command
looks tidy.

So this builds the same forecast twice: once through evening.message, and
once by running forecast_message.py exactly as ROUTINES.md section 2 spells
it out, and requires the two to be identical. Change either side alone and
this fails.

The refusals are pinned too. No Surfline hours, or a wind direction
Surfline itself labels the other way, must stop the send -- a forecast
invented for two hundred customers is far worse than one that never
arrived.

Nothing here touches the network or sends anything.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evening                                                  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


SUMMARY = {"waves": "0.4-0.8", "period": "13", "wind": "3-7",
           "wind_dir": "200", "onshore_from": "", "onshore_eases": False,
           "hours": 13}
TODAY = "0.3-0.9"
DATE = "2026-09-15"


def via_cli(lang, s=SUMMARY, today=TODAY, date=DATE):
    cmd = [sys.executable, os.path.join(HERE, "forecast_message.py"),
           "--lang", lang, "--date", date,
           "--waves", s["waves"], "--period", s["period"],
           "--wind", s["wind"], "--wind-dir", s["wind_dir"],
           "--waves-today", today, "--tide-note"]
    if s.get("onshore_from"):
        cmd += ["--onshore-from", s["onshore_from"]]
    if s.get("onshore_eases"):
        cmd += ["--onshore-eases"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit("the documented path itself failed: " + out.stderr)
    return out.stdout.rstrip("\n")


def main():
    # --- the two paths must agree, in both languages --------------------
    for lang in ("he", "en"):
        mine, err = evening.message(DATE, SUMMARY, TODAY, lang)
        check("evening builds a %s forecast without error" % lang, not err,
              str(err))
        theirs = via_cli(lang)
        check("the %s forecast is identical to the documented path" % lang,
              mine == theirs,
              "first difference at %d" % next(
                  (i for i, (a, b) in enumerate(zip(mine, theirs)) if a != b),
                  min(len(mine), len(theirs))))

    # An onshore afternoon changes the wind line; the two paths have to
    # agree about that too, since it is assembled from three arguments.
    windy = dict(SUMMARY, onshore_from="13:00", onshore_eases=True)
    mine, err = evening.message(DATE, windy, TODAY, "he")
    check("an onshore afternoon builds", not err, str(err))
    check("and still matches the documented path",
          mine == via_cli("he", s=windy))

    # --- both groups read the same sea ----------------------------------
    he, _ = evening.message(DATE, SUMMARY, TODAY, "he")
    en, _ = evening.message(DATE, SUMMARY, TODAY, "en")
    for number in (SUMMARY["waves"], SUMMARY["period"]):
        check("both languages carry %s" % number,
              number in he and number in en)
    check("and they are not the same message", he != en)

    # --- refusing beats guessing ----------------------------------------
    import surfline
    keep = (surfline.fetch, surfline.hours, surfline.offshore_disagreement)
    try:
        surfline.fetch = lambda days=2: {"surf": [], "swells": [], "wind": []}
        surfline.hours = lambda *a, **k: []
        s, today, problem = evening.sea(DATE)
        check("no Surfline hours is a refusal", problem and s is None,
              repr(problem))
        check("and it says not to guess", "do not guess" in (problem or ""))

        surfline.hours = lambda *a, **k: [{"hour": "09:00"}]
        surfline.offshore_disagreement = lambda rows: [("09:00", 1, 2)]
        s, today, problem = evening.sea(DATE)
        check("a disputed wind direction is a refusal",
              problem and s is None, repr(problem))
        check("and it names the hour", "09:00" in (problem or ""))
    finally:
        surfline.fetch, surfline.hours, surfline.offshore_disagreement = keep

    # --- the group names cannot be swapped ------------------------------
    check("Hebrew goes to the Hebrew group",
          evening.GROUP["he"] == "surfers_he")
    check("English goes to the English group",
          evening.GROUP["en"] == "surfers_en")

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
