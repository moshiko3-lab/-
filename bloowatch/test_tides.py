#!/usr/bin/env python3
"""The tide table decides what hours the school tells people to come at.

A misread clock here is not a cosmetic fault: 7:11PM parsed as 07:11 puts the
evening high in the morning, and the recommended hours follow it. So the
twelve-hour clock, the shape of the parse, and the rule that a merge never
loses a day are pinned here. Nothing touches the network.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tides                                                     # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


PAGE = """<html><body><script> //<![CDATA[
window.FCGON = {"tideDays":[
 {"date":"2026-09-02","tides":[
   {"time":"00:10AM","height":0.49,"type":null},
   {"time":"00:32AM","height":0.46,"type":"low"},
   {"time":" 6:45AM","height":3.6,"type":"high"},
   {"time":" 1:02PM","height":0.41,"type":"low"},
   {"time":" 7:11PM","height":3.28,"type":"high"}]},
 {"date":"2026-09-03","tides":[
   {"time":" 1:14AM","height":0.6,"type":"low"},
   {"time":" 7:29AM","height":3.46,"type":"high"}]},
 {"date":"2026-09-04","tides":[{"time":" 3:00AM","height":1.0,"type":null}]}
],"mode":"x"};
//]]> </script></body></html>"""


def main():
    # --- the twelve-hour clock ----------------------------------------------
    for raw, want in ((" 6:07AM", "06:07"), ("00:32AM", "00:32"),
                      (" 7:11PM", "19:11"), ("12:22PM", "12:22"),
                      ("12:05AM", "00:05"), (" 1:02PM", "13:02"),
                      ("11:59PM", "23:59")):
        check("%r is %s" % (raw, want), tides.clock(raw) == want,
              tides.clock(raw))
    for bad in ("", "6:07", "25:00AM", "nonsense"):
        try:
            tides.clock(bad)
            check("%r is refused" % bad, False, "it was accepted")
        except ValueError:
            check("%r is refused" % bad, True)

    # --- the parse ----------------------------------------------------------
    days = tides.to_days(tides.extract(PAGE))
    check("a day with no turning point is not a day",
          [d["date"] for d in days] == ["2026-09-02", "2026-09-03"],
          str([d["date"] for d in days]))
    d = days[0]
    check("both highs are kept", len(d["highs"]) == 2, str(d["highs"]))
    check("and both lows", len(d["lows"]) == 2, str(d["lows"]))
    check("the evening high is in the evening",
          d["highs"][1]["t"] == "19:11", d["highs"][1]["t"])
    check("heights keep two decimals as text",
          d["highs"][0]["m"] == "3.60", d["highs"][0]["m"])
    check("turning points come out in clock order",
          [p["t"] for p in d["lows"]] == ["00:32", "13:02"],
          str([p["t"] for p in d["lows"]]))
    check("the source is written on every day",
          all(x["source"] == "surf-forecast.com" for x in days))
    check("a page with no tide blob is an error",
          _raises(lambda: tides.extract("<html>nothing</html>")))

    # --- the merge ----------------------------------------------------------
    # A short fetch must not quietly drop the days it did not cover.
    old = {"tides": [
        {"date": "2026-08-30", "spot": "x", "highs": [{"t": "05:00", "m": "3"}],
         "lows": []},
        {"date": "2026-09-02", "spot": "x", "highs": [{"t": "06:56", "m": "3.17"}],
         "lows": []},
        {"date": "2026-12-31", "spot": "x", "highs": [{"t": "09:00", "m": "2"}],
         "lows": []}], "products": [1, 2]}
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(old, f)
    n, r, total = tides.merge(days, path)
    with open(path, encoding="utf-8") as f:
        got = json.load(f)
    os.unlink(path)
    have = {t["date"]: t for t in got["tides"]}
    check("the days we fetched are in", n == 2 and r == 1, "%d/%d" % (n, r))
    check("a day we did not fetch is untouched",
          have["2026-08-30"]["highs"][0]["m"] == "3", str(have["2026-08-30"]))
    check("and so is one months away", "2026-12-31" in have)
    check("the day we did fetch is the new one",
          have["2026-09-02"]["highs"][0]["m"] == "3.60",
          str(have["2026-09-02"]))
    check("no day is duplicated",
          len(have) == len(got["tides"]) == 4, str(len(got["tides"])))
    check("they stay in date order",
          [t["date"] for t in got["tides"]] == sorted(have), "out of order")
    check("nothing else in the catalog is disturbed",
          got["products"] == [1, 2], str(got.get("products")))

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


def _raises(f):
    try:
        f()
        return False
    except Exception:
        return True


if __name__ == "__main__":
    sys.exit(main())
