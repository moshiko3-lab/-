#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tomorrow's sea from Surfline, in the numbers the evening forecast wants.

    # in the sandbox, which can reach services.surfline.com:
    python3 surfline.py --curl              # prints the three commands to run
    # then, here, with the three files it wrote:
    python3 surfline.py --parse surf.json swells.json wind.json --date 2026-09-05

Why Surfline and not surf-forecast: the owner asked for it, and he was right
about the reason. Measured on 4/9/2026 for the same day and the same hours,
surf-forecast said 0.9-1.1 m and Surfline said 1.14-1.59 m -- a third to a half
a metre apart, which is a whole size class in a message that tells people
whether the day suits a first lesson. The school's own "high / average / low"
call is written in Surfline metres, so the forecast has to speak them too.

Getting in is a matter of headers, not permission. services.surfline.com sits
behind Cloudflare and returns 403 to a bare curl; with an Origin and Referer of
surfline.com it answers 200. The spot is Playa Venao, 584204204e65fad6a7709681
-- confirmed against the endpoint's own name and its 7.42N 80.20W.

Three endpoints carry what we need, and a fourth does not: `surf` has the wave
heights, `swells` the periods, `wind` the speed and direction. `conditions`
returns empty heights without a subscription, and `forecasts/wave` 404s; do not
go looking for them again.

**This container cannot reach Surfline** -- the egress policy answers 403 CONNECT
-- so the fetch happens in the sandbox and the JSON comes back here. That is
data and not Hebrew text, so nothing can lose its direction marks on the way.
If services.surfline.com is ever added to the environment's allowed domains,
--fetch does the whole thing here and the sandbox drops out.
"""
import argparse
import datetime as dt
import json
import math
import sys

SPOT = "584204204e65fad6a7709681"          # Playa Venao
BASE = "https://services.surfline.com/kbyg/spots/forecasts"

# Cloudflare lets these through and refuses a bare curl. Keep them together:
# dropping Origin or Referer is what turns a 200 back into a 403.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/128.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.surfline.com",
    "Referer": "https://www.surfline.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

# The hours anybody is actually going in. Same window the message's own
# recommendations are cut to, so the height and the hours agree.
DAY_FROM, DAY_TO = 6, 19


def curl_commands(days=3):
    """What to run in the sandbox. Printed rather than executed: this
    container is blocked from Surfline by the network policy, and that is a
    policy to report, not to route around."""
    h = " ".join('-H "%s: %s"' % (k, v) for k, v in HEADERS.items())
    out = []
    for name, extra in (("surf", "&units%5BwaveHeight%5D=M"),
                        ("swells", ""),
                        ("wind", "&units%5BwindSpeed%5D=KTS")):
        out.append('curl -s -m 25 %s -o %s.json '
                   '"%s/%s?spotId=%s&days=%d&intervalHours=1%s"'
                   % (h, name, BASE, name, SPOT, days, extra))
    return out


def _rows(payload, key):
    d = payload.get("data", payload)
    return d[key]


def _local(ts, off):
    return dt.datetime.utcfromtimestamp(ts) + dt.timedelta(hours=off)


def hours(surf, swells, wind, date):
    """One row per surfable hour of `date`: heights, period, wind.

    Everything is keyed by Surfline's own timestamp, so a gap in one feed
    leaves that hour short rather than silently pairing it with another hour's
    wind -- which is the kind of mistake nobody would ever see in the output.
    """
    sw = {x["timestamp"]: x for x in swells}
    wd = {x["timestamp"]: x for x in wind}
    out = []
    for s in surf:
        t = _local(s["timestamp"], s["utcOffset"])
        if t.strftime("%Y-%m-%d") != date or not (DAY_FROM <= t.hour <= DAY_TO):
            continue
        raw = s["surf"]["raw"]
        periods = [x["period"] for x in sw.get(s["timestamp"], {}).get("swells", [])
                   if x.get("height", 0) > 0]
        w = wd.get(s["timestamp"], {})
        out.append({
            "hour": t.strftime("%H:%M"),
            "min": raw["min"],
            "max": raw["max"],
            "period": max(periods) if periods else None,
            "wind_kt": w.get("speed"),
            # Surfline's `direction` is the direction the wind blows FROM,
            # which is what the message wants. Its own `directionType` says
            # Offshore/Onshore, and cross-checking the two is how a flipped
            # convention would be caught rather than quietly inverting every
            # offshore call in the message.
            "wind_deg": w.get("direction"),
            "wind_type": w.get("directionType"),
        })
    return out


def _r1(x):
    """To one decimal. Surf heights are read at a glance, not to the centimetre."""
    return round(x + 1e-9, 1)


def waves(rows):
    """The day's height as a range, in the school's own terms.

    Averaged across the surfable hours and not taken from the extremes: one
    freak hour must not set what two hundred people read as the day. Surfline
    gives a min and a max per hour -- the smaller waves and the bigger sets --
    so the range runs from the mean of the mins to the mean of the maxes, which
    keeps that character without letting a single hour widen it.
    """
    if not rows:
        return None
    lo = sum(r["min"] for r in rows) / len(rows)
    hi = sum(r["max"] for r in rows) / len(rows)
    a, b = _r1(lo), _r1(hi)
    return "%.1f" % a if a == b else "%.1f-%.1f" % (a, b)


def period(rows):
    """The period the day mostly runs at, not the one lucky hour."""
    vals = [r["period"] for r in rows if r["period"]]
    if not vals:
        return None
    vals.sort()
    return int(round(vals[len(vals) // 2]))


def mean_deg(degs):
    """The average of compass bearings, which is not their arithmetic mean.

    A Venao morning runs 328, 335, 347, 4, 9, 12 -- all of it north, all of it
    offshore. Averaging those as numbers gives 173, which is due south, which
    is onshore, which would invert every call the message makes about the wind.
    Bearings have to be averaged as directions: unit vectors, then the angle of
    their sum.
    """
    if not degs:
        return None
    x = sum(math.cos(math.radians(d)) for d in degs)
    y = sum(math.sin(math.radians(d)) for d in degs)
    if abs(x) < 1e-9 and abs(y) < 1e-9:      # opposing winds, no mean direction
        return None
    return int(round(math.degrees(math.atan2(y, x)))) % 360


def wind(rows):
    """The morning's wind: a speed range in knots and one bearing.

    The morning and not the whole day, and the two together rather than a
    speed from one window and a direction from another. At Venao the wind
    almost always starts offshore and swings onshore after lunch, so a single
    figure spanning both describes neither -- and the hours the school teaches
    are the morning ones. Saying "3-8 from the north, offshore" is true of the
    lessons; saying "0-8" across a day that reverses is true of nothing.
    """
    morning = [r for r in rows if r["hour"] < "12:00"]
    src = morning or rows
    kts = [r["wind_kt"] for r in src if r["wind_kt"] is not None]
    speed = None
    if kts:
        a, b = int(round(min(kts))), int(round(max(kts)))
        speed = str(a) if a == b else "%d-%d" % (a, b)
    deg = mean_deg([r["wind_deg"] for r in src if r["wind_deg"] is not None])
    return speed, deg


def offshore_disagreement(rows, faces=180):
    """Hours where our offshore/onshore call differs from Surfline's own.

    Surfline labels every hour Offshore or Onshore itself, so the message never
    has to take our word for it. If this returns anything, something is wrong
    that no reader would ever spot in the output: the beach's facing, or the
    assumption that Surfline's `direction` is the bearing the wind blows FROM.
    It is the cheapest check we have on the one number that inverts the whole
    message, so it runs on real data in the tests.
    """
    bad = []
    for r in rows:
        d, t = r.get("wind_deg"), (r.get("wind_type") or "")
        if d is None or t not in ("Offshore", "Onshore"):
            continue
        off = abs(((d - faces) + 180) % 360 - 180) > 90
        if off != (t == "Offshore"):
            bad.append((r["hour"], d, t))
    return bad


def summary(rows):
    return {"waves": waves(rows), "period": period(rows), "wind": wind(rows)[0],
            "wind_dir": wind(rows)[1], "hours": len(rows)}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--curl", action="store_true",
                   help="print the three sandbox commands and stop")
    p.add_argument("--parse", nargs=3, metavar=("SURF", "SWELLS", "WIND"),
                   help="the three JSON files the sandbox wrote")
    p.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    p.add_argument("--table", action="store_true", help="show every hour")
    a = p.parse_args()

    if a.curl:
        for c in curl_commands():
            print(c)
            print()
        return 0
    if not a.parse:
        p.error("give --curl or --parse")

    date = a.date or (dt.datetime.utcnow() - dt.timedelta(hours=5)
                      + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    payloads = [json.load(open(f, encoding="utf-8")) for f in a.parse]
    rows = hours(_rows(payloads[0], "surf"), _rows(payloads[1], "swells"),
                 _rows(payloads[2], "wind"), date)
    if not rows:
        print("no Surfline hours for %s -- do not send, and do not guess" % date,
              file=sys.stderr)
        return 1

    if a.table:
        print("%-6s %-12s %-7s %s" % ("hour", "surf m", "period", "wind"))
        for r in rows:
            print("%-6s %.2f-%.2f  %-7s %.1f kt %s"
                  % (r["hour"], r["min"], r["max"], r["period"] or "-",
                     r["wind_kt"] or 0, r["wind_type"] or ""))
        print()

    s = summary(rows)
    print("date       %s  (%d surfable hours)" % (date, s["hours"]))
    print("waves      %s m" % s["waves"])
    print("period     %s s" % s["period"])
    print("wind       %s kt from %s deg" % (s["wind"], s["wind_dir"]))
    print()
    print("--waves %s --period %s --wind %s --wind-dir %s"
          % (s["waves"], s["period"], s["wind"], s["wind_dir"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
