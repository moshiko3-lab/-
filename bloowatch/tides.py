#!/usr/bin/env python3
"""The tide table, taken from the same forecast the school reads.

    python3 tides.py --parse page.html      # print our shape, from the page
    python3 tides.py --merge days.json      # fold it into app/catalog.json

Bloowatch carries a tide table of its own and we used it for a while, but it
is published against a different chart datum: its highs run about 0.4 m below
surf-forecast's and about 0.6 m below Surfline's, and its lows go negative,
which no water does. That is not an error in anybody's data -- every table
measures from its own zero -- but it matters here, because the school's own
rule for whether a day is a big one or a small one is written in metres. A
rule in Surfline's metres applied to Bloowatch's numbers calls a big day an
average one and sends people down at the wrong hour.

So the numbers come from surf-forecast, which is the closest source that can
actually be reached from here; Surfline itself is behind Cloudflare from all
three routes this machine has. The page carries the whole month at ten-minute
resolution with each turning point marked, which is more than the old table
ever had.

The fetch has to happen somewhere with a route to the site -- the Composio
sandbox -- so this file only ever parses; it never downloads. See
`bloowatch/whatsapp.json` for the same split on the picture.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "..", "app", "catalog.json")
SOURCE = "surf-forecast.com"


def extract(html):
    """The blob the page hands its own chart, which is the whole month."""
    i = html.find("window.FCGON")
    if i < 0:
        raise ValueError("no tide data on this page")
    i = html.index("{", i)
    depth = 0
    for j in range(i, len(html)):
        if html[j] == "{":
            depth += 1
        elif html[j] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[i:j + 1])
    raise ValueError("tide data is truncated")


def clock(s):
    """"  6:07AM" and "00:32AM" and " 7:11PM" all mean what they look like."""
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*([AP])M\s*$", s, re.I)
    if not m:
        raise ValueError("unreadable time %r" % s)
    h, mi, half = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    # a twelve-hour clock has twelve hours on it, and the page writes the
    # midnight hour as 00. Anything else is a page we are not reading right,
    # and a wrong hour here moves the recommended surf window.
    if h > 12 or mi > 59:
        raise ValueError("impossible time %r" % s)
    if half == "A":
        h = 0 if h == 12 else h
    else:
        h = 12 if h == 12 else h + 12
    return "%02d:%02d" % (h % 24, mi)


def to_days(blob, spot="Playa Venao"):
    """Our shape: the turning points, which is all anybody quotes."""
    out = []
    for day in blob.get("tideDays") or []:
        highs, lows = [], []
        for t in day.get("tides") or []:
            kind = (t.get("type") or "").lower()
            if kind not in ("high", "low"):
                continue
            (highs if kind == "high" else lows).append(
                {"t": clock(t["time"]), "m": "%.2f" % float(t["height"])})
        if not highs and not lows:
            continue
        out.append({"date": day["date"], "spot": spot, "source": SOURCE,
                    "highs": sorted(highs, key=lambda p: p["t"]),
                    "lows": sorted(lows, key=lambda p: p["t"])})
    return out


def merge(days, path=CATALOG):
    """Replace the days we now have, keep the ones we do not.

    Nothing is thrown away on a short fetch: a page that only reaches the end
    of the month leaves next month's rows exactly as they were.
    """
    with open(path, encoding="utf-8") as f:
        cat = json.load(f)
    have = {t["date"]: t for t in cat.get("tides") or []}
    replaced = [d for d in days if d["date"] in have]
    for d in days:
        have[d["date"]] = d
    cat["tides"] = [have[k] for k in sorted(have)]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    return len(days), len(replaced), len(cat["tides"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parse", help="a saved surf-forecast tides page")
    ap.add_argument("--merge", help="days.json from --parse, into the catalog")
    ap.add_argument("--catalog", default=CATALOG)
    a = ap.parse_args()

    if a.parse:
        with open(a.parse, encoding="utf-8", errors="replace") as f:
            days = to_days(extract(f.read()))
        json.dump(days, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        print()
        return 0

    if a.merge:
        with open(a.merge, encoding="utf-8") as f:
            days = json.load(f)
        if not isinstance(days, list) or not days:
            print("error: nothing to merge", file=sys.stderr)
            return 1
        for d in days:                      # never write a half-read day
            if not d.get("date") or not (d.get("highs") or d.get("lows")):
                print("error: %r has no tide on it" % d.get("date"),
                      file=sys.stderr)
                return 1
        n, r, total = merge(days, a.catalog)
        print("merged %d days (%d replaced), %d in the catalog, %s to %s"
              % (n, r, total, days[0]["date"], days[-1]["date"]))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
