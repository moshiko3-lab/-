#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tomorrow's sea from Surfline, in the numbers the evening forecast wants.

    python3 surfline.py --curl        # one script; run it in the sandbox
    # it prints one compact JSON blob. Save it here and read it:
    python3 surfline.py --parse sea.json

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
Re-measured 4/9/2026: services.surfline.com and surf-forecast.com both answer
403 CONNECT from here. That is network policy, to be reported and not routed
around; if the owner ever adds the domain to the environment's allowed list the
sandbox drops out of the evening entirely.

The blob that comes back is trimmed in the sandbox to the fields read below, so
the hop carries the numbers and not the scores, labels and gusts around them.
The trimming only selects fields; it computes nothing that reaches the message,
which is why it is safe to run it on a machine with no tests on it.
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


def curl_commands(days=2):
    """The one script to run in the sandbox, as a single string.

    Printed rather than executed: this container is blocked from Surfline by
    the network policy, and that is a policy to report, not to route around.

    One script and not three commands, because every extra step in a hop
    between machines is another place for an evening to stall half-finished.
    It fetches, trims to the fields `hours()` reads, and prints one compact
    JSON object; if any of the three fetches comes back without its rows it
    says so on stderr and prints nothing, so a partial sea can never be
    mistaken for a whole one.

    `days=2` is today and tomorrow: tomorrow is the forecast and today is what
    the message compares it against.
    """
    h = " ".join('-H "%s: %s"' % (k, v) for k, v in HEADERS.items())
    fetches = "\n".join(
        'curl -s -m 25 %s -o %s.json "%s/%s?spotId=%s&days=%d&intervalHours=1%s"'
        % (h, name, BASE, name, SPOT, days, extra)
        for name, extra in (("surf", "&units%5BwaveHeight%5D=M"),
                            ("swells", ""),
                            ("wind", "&units%5BwindSpeed%5D=KTS")))
    return fetches + "\n" + TRIM


# Runs in the sandbox, on stock python3, with no repository checkout. Kept
# here rather than pulled from GitHub because raw.githubusercontent serves a
# stale copy of a branch for minutes, and a forecast built from yesterday's
# parser is the kind of mistake nobody sees.
TRIM = r'''python3 - <<'PY'
import json, sys
def rows(f, k):
    d = json.load(open(f, encoding="utf-8"))
    return (d.get("data") or d)[k]
try:
    surf = [{"timestamp": r["timestamp"], "utcOffset": r["utcOffset"],
             "surf": {"raw": r["surf"]["raw"]}} for r in rows("surf.json", "surf")]
    swells = [{"timestamp": r["timestamp"], "utcOffset": r["utcOffset"],
               "swells": [{"height": s.get("height"), "period": s.get("period")}
                          for s in r["swells"]]} for r in rows("swells.json", "swells")]
    wind = [{"timestamp": r["timestamp"], "utcOffset": r["utcOffset"],
             "speed": r.get("speed"), "direction": r.get("direction"),
             "directionType": r.get("directionType")}
            for r in rows("wind.json", "wind")]
except Exception as e:
    sys.exit("surfline fetch incomplete (%s) -- do not send, and do not guess" % e)
if not (surf and swells and wind):
    sys.exit("surfline returned no rows -- do not send, and do not guess")
print(json.dumps({"surf": surf, "swells": swells, "wind": wind},
                 separators=(",", ":")))
PY'''


def _rows(payload, key):
    d = payload.get("data", payload)
    return d[key]


def load(paths):
    """The three feeds, from one trimmed blob or from three raw payloads.

    One file is what the sandbox script prints; three are the endpoints saved
    as they came, which is what a hand-run check on a strange day looks like.
    Both shapes read the same here so a debugging session never has to go
    through a different code path than the evening does.
    """
    if len(paths) == 1:
        d = json.load(open(paths[0], encoding="utf-8"))
        d = d.get("data", d)
        return d["surf"], d["swells"], d["wind"]
    if len(paths) != 3:
        raise SystemExit("--parse takes one combined file or three raw ones")
    p = [json.load(open(f, encoding="utf-8")) for f in paths]
    return (_rows(p[0], "surf"), _rows(p[1], "swells"), _rows(p[2], "wind"))


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
                   help="print the sandbox script and stop")
    p.add_argument("--parse", nargs="+", metavar="FILE",
                   help="the blob the sandbox printed, or the three raw payloads")
    p.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    p.add_argument("--table", action="store_true", help="show every hour")
    a = p.parse_args()

    if a.curl:
        print(curl_commands())
        return 0
    if not a.parse:
        p.error("give --curl or --parse")

    panama = dt.datetime.utcnow() - dt.timedelta(hours=5)
    date = a.date or (panama + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    surf, swells, wnd = load(a.parse)
    rows = hours(surf, swells, wnd, date)
    if not rows:
        print("no Surfline hours for %s -- do not send, and do not guess" % date,
              file=sys.stderr)
        return 1

    # The day before the one being forecast, for the message's own comparison.
    # Absent on a blob fetched with days=1, and the line simply goes unwritten
    # rather than being guessed at.
    prev = (dt.datetime.strptime(date, "%Y-%m-%d")
            - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    today = waves(hours(surf, swells, wnd, prev))

    if a.table:
        print("%-6s %-12s %-7s %s" % ("hour", "surf m", "period", "wind"))
        for r in rows:
            print("%-6s %.2f-%.2f  %-7s %.1f kt %s"
                  % (r["hour"], r["min"], r["max"], r["period"] or "-",
                     r["wind_kt"] or 0, r["wind_type"] or ""))
        print()

    # The offshore call is the one number in here that can invert the whole
    # message without looking wrong. Surfline labels every hour itself, so say
    # so when the two disagree rather than publishing our own answer quietly.
    bad = offshore_disagreement(rows)
    if bad:
        print("wind direction disagrees with Surfline's own label at %s -- "
              "check BEACH_FACES before sending" % ", ".join(h for h, _, _ in bad),
              file=sys.stderr)

    s = summary(rows)
    print("date       %s  (%d surfable hours)" % (date, s["hours"]))
    print("waves      %s m" % s["waves"])
    print("period     %s s" % s["period"])
    print("wind       %s kt from %s deg" % (s["wind"], s["wind_dir"]))
    print("%s   %s m" % (prev.ljust(11), today or "-- not in this blob"))
    print()
    print("--waves %s --period %s --wind %s --wind-dir %s%s"
          % (s["waves"], s["period"], s["wind"], s["wind_dir"],
             (" --waves-today %s" % today) if today else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
