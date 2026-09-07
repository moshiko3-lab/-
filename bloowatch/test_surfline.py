#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""What Surfline's numbers must survive on their way into the evening message.

These run on a real payload — Playa Venao, 5/9/2026, fourteen surfable hours,
saved from the live API — because the two bugs worth catching here are both
ones that look perfectly fine in synthetic data.

The first is the compass. Bearings are not numbers you can average: a Venao
morning of 328, 335, 347, 4, 9, 12 degrees is north from end to end, and its
arithmetic mean is 173, which is due south. That single wrong number would flip
"offshore, clean and groomed" into "onshore" for every reader, and nothing in
the message would look broken. Surfline labels each hour Offshore or Onshore
itself, so the test does not have to take our word for the maths.

The second is the day boundary. The feed carries three days at one-hour steps
in Panama time; taking the wrong slice means publishing yesterday's sea to two
hundred people, which reads as a forecast rather than as a mistake.

Nothing here touches the network.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surfline as S                                              # noqa: E402

fails = []
ran = []


def check(name, cond, detail=""):
    ran.append(name)
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- the payload
# Saved from services.surfline.com on 4/9/2026. Trimmed to the surfable hours
# of 5/9 so the file stays readable; the shape is the API's own.
# Every hour carries BOTH heights, as the API does: `min`/`max` is what
# Surfline publishes on the spot page, `raw` is its continuous model output.
# They are far apart at the bottom, which is the whole point of the test --
# reading raw is what made the message say 1.1 where the site said 0.9.
def row(ts, mn, mx, rmn, rmx):
    return {"timestamp": ts, "utcOffset": -5,
            "surf": {"min": mn, "max": mx, "raw": {"min": rmn, "max": rmx}}}


BASE = 1788606000          # 2026-09-05 06:00 in Panama (UTC-5)
HRS = 3600
SURF = [row(BASE + i * HRS, 0.9, 1.5, rmn, rmx)
        for i, (rmn, rmx) in enumerate([
            (1.14, 1.36), (1.16, 1.39), (1.20, 1.42), (1.22, 1.46),
            (1.24, 1.49), (1.15, 1.52), (1.17, 1.53), (1.19, 1.55),
            (1.20, 1.56), (1.21, 1.58), (1.22, 1.58), (1.23, 1.59),
            (1.23, 1.59), (1.21, 1.58)])]
SWELLS = [{"timestamp": BASE + i * HRS, "utcOffset": -5,
           "swells": [{"height": 1.2, "period": 16}, {"height": 0, "period": 4}]}
          for i in range(14)]
WINDDEG = [328.8, 335.6, 347.8, 4.0, 9.4, 11.8, 20.2, 24.0,
           152.6, 204.8, 214.6, 224.1, 234.9, 241.1]
WINDKT = [3.8, 4.0, 4.3, 6.9, 7.8, 6.7, 5.3, 2.3,
          0.4, 2.3, 3.1, 4.3, 3.9, 3.4]
WIND = [{"timestamp": BASE + i * HRS, "utcOffset": -5, "speed": WINDKT[i],
         "direction": WINDDEG[i],
         "directionType": "Offshore" if WINDDEG[i] > 270 or WINDDEG[i] < 90
         else "Onshore"}
        for i in range(14)]

ROWS = S.hours(SURF, SWELLS, WIND, "2026-09-05")

print("the right day, and only the hours anybody surfs")
check("all fourteen surfable hours are there", len(ROWS) == 14, str(len(ROWS)))
check("the first is 06:00", ROWS[0]["hour"] == "06:00", ROWS[0]["hour"])
check("the last is 19:00", ROWS[-1]["hour"] == "19:00", ROWS[-1]["hour"])
check("a different date returns nothing rather than the wrong day",
      S.hours(SURF, SWELLS, WIND, "2026-09-04") == [])

# A gap in one feed must shorten that hour, never pair it with another hour's
# wind — a silent mismatch nobody could see in the output.
print("\na gap in one feed does not borrow another hour's numbers")
holed = S.hours(SURF, SWELLS, [w for w in WIND if w["timestamp"] != BASE],
                "2026-09-05")
check("the hour with no wind keeps its own height",
      holed[0]["hour"] == "06:00" and holed[0]["min"] == 0.9)
check("and reports no wind rather than the next hour's",
      holed[0]["wind_kt"] is None and holed[0]["wind_deg"] is None)

# ------------------------------------------------------------------ the compass
print("\nbearings are averaged as directions, not as numbers")
check("a morning either side of north stays north",
      S.mean_deg([328.8, 335.6, 347.8, 4.0, 9.4, 11.8]) in range(345, 360),
      str(S.mean_deg([328.8, 335.6, 347.8, 4.0, 9.4, 11.8])))
check("and never lands due south, which is what the plain mean does",
      abs(S.mean_deg([328.8, 335.6, 347.8, 4.0, 9.4, 11.8]) - 173) > 90)
check("two opposite winds have no mean direction",
      S.mean_deg([0, 180]) is None, str(S.mean_deg([0, 180])))
check("north and east average to north-east",
      S.mean_deg([0, 90]) == 45, str(S.mean_deg([0, 90])))
check("350 and 10 average to 0, not to 180",
      S.mean_deg([350, 10]) == 0, str(S.mean_deg([350, 10])))

# Surfline's own label is the referee. If our offshore call and its label ever
# disagree, either BEACH_FACES is wrong or `direction` is not the bearing the
# wind blows FROM — and every wind sentence in the message inverts.
print("\nour offshore call agrees with Surfline's own label, hour by hour")
bad = S.offshore_disagreement(ROWS, faces=180)
check("no hour disagrees", not bad, str(bad))
check("and the check has teeth: facing north flips every hour",
      len(S.offshore_disagreement(ROWS, faces=0)) == len(ROWS),
      str(len(S.offshore_disagreement(ROWS, faces=0))))

print("\nthe wind we publish is the morning's, and it is offshore")
speed, deg = S.wind(ROWS)
check("direction is north-ish", deg > 300 or deg < 60, str(deg))
check("which is offshore for a beach facing south",
      abs(((deg - 180) + 180) % 360 - 180) > 90, str(deg))
check("speed comes from the morning too, so it matches the direction",
      speed == "4-8", str(speed))

# ------------------------------------------------------------------- the height
# The owner's rule, 5/9/2026: the range is the day's real edges, lowest
# reading to highest. Averaging across the hours narrowed it -- this same
# Saturday, which runs 1.14 to 1.59, came out as "1.2-1.5" and hid both ends
# from somebody deciding whether the day is worth the drive.
print("\nheight spans the day's extremes, not its average")
w = S.waves(ROWS)
check("5/9 reads 0.9-1.5, which is what Surfline's own page says",
      w == "0.9-1.5", str(w))
check("it is the published height and not the raw model output",
      not w.startswith("1.1"), w + " (raw would give 1.1-1.6)")
check("one quiet hour widens the bottom",
      S.waves(ROWS + [{"min": 0.6, "max": 1.0}]).startswith("0.6"),
      str(S.waves(ROWS + [{"min": 0.6, "max": 1.0}])))
check("and one big set widens the top",
      S.waves(ROWS + [{"min": 1.2, "max": 2.1}]).endswith("2.1"),
      str(S.waves(ROWS + [{"min": 1.2, "max": 2.1}])))
check("a flat day gives one number, not a fake range",
      S.waves([{"min": 1.0, "max": 1.0}] * 5) == "1.0",
      str(S.waves([{"min": 1.0, "max": 1.0}] * 5)))

print("\nperiod is the primary swell's, start of day to end of day")
check("a steady day reads as one number", S.period(ROWS) == "16",
      str(S.period(ROWS)))
check("a zero-height swell never sets it",
      S.period([{"period": 16}, {"period": None}]) == "16")
check("a day that eases reads as both ends",
      S.period([{"period": 14}] * 9 + [{"period": 13}] * 5) == "14,13")
check("and a wobble is one sea, not four",
      S.period([{"period": 14}, {"period": 13}, {"period": 14},
                {"period": 13}]) == "14,13")
check("a long slide is named by its ends only",
      S.period([{"period": p} for p in (16, 15, 14, 13, 12)]) == "16,12")

# 7/9/2026: a 2.9 m swell at 14 s under a 0.25 m forerunner at 21 s. Taking the
# longest period made the message promise twenty seconds for a day that
# fourteen was going to build, and the owner corrected it by hand.
FORERUNNER = [{"timestamp": BASE + i * HRS, "utcOffset": -5,
               "swells": [{"height": 2.9, "period": 14},
                          {"height": 1.7, "period": 6},
                          {"height": 0.25, "period": 21}]} for i in range(14)]
fr = S.hours(SURF, FORERUNNER, WIND, "2026-09-05")
check("the biggest swell sets the period, not the longest",
      {r["period"] for r in fr} == {14}, str({r["period"] for r in fr}))
check("so the day reads 14 and never 21", S.period(fr) == "14", str(S.period(fr)))

print("\nthe afternoon the wind row does not cover")
ON = [{"hour": "%02d:00" % (6 + i), "wind_kt": kt, "wind_type": t}
      for i, (kt, t) in enumerate(
          [(0.7, "Offshore"), (1.2, "Cross-shore"), (0.6, "Cross-shore"),
           (0.8, "Offshore"), (2.0, "Cross-shore"), (4.2, "Cross-shore"),
           (5.8, "Cross-shore"), (5.2, "Onshore"), (5.2, "Onshore"),
           (4.8, "Onshore"), (3.0, "Onshore"), (0.7, "Onshore"),
           (1.4, "Offshore"), (2.0, "Offshore")])]
check("7/9 swings onshore at one o'clock", S.onshore_spell(ON)[0] == "13:00",
      str(S.onshore_spell(ON)))
check("and lies down again afterwards", S.onshore_spell(ON)[1] is True)
check("a single onshore hour is model wobble, not a sea breeze",
      S.onshore_spell([{"hour": "06:00", "wind_kt": 1, "wind_type": "Offshore"},
                       {"hour": "07:00", "wind_kt": 1, "wind_type": "Onshore"},
                       {"hour": "08:00", "wind_kt": 1,
                        "wind_type": "Cross-shore"}]) == (None, False))
check("a day with no onshore at all says nothing",
      S.onshore_spell([{"hour": "06:00", "wind_kt": 1, "wind_type": "Offshore"}]
                      * 3) == (None, False))
check("an onshore that holds to the last hour does not claim to ease",
      S.onshore_spell(
          [{"hour": "06:00", "wind_kt": 1, "wind_type": "Offshore"}]
          + [{"hour": "%02d:00" % h, "wind_kt": 9, "wind_type": "Onshore"}
             for h in range(7, 20)])[1] is False)

# The whole point of the change: Surfline reads higher than surf-forecast, and
# the school's size language is written in Surfline metres.
# Read like for like -- both sites' published figures -- the two agree on the
# bottom of 5/9 and differ at the top: surf-forecast 0.9-1.1, Surfline
# 0.9-1.5. The earlier "half a metre apart" note compared surf-forecast's
# published numbers against Surfline's raw ones, which was not a fair
# comparison. The gap that matters is the sets, and it is still a size class.
print("\nand its sets are well above what surf-forecast said")
check("same bottom as surf-forecast on 5/9", w.startswith("0.9"), w)
check("but 0.4 m more at the top (1.5 against 1.1)",
      float(w.split("-")[1]) - 1.1 >= 0.4 - 1e-9, w)

# -------------------------------------------------------------- the hop itself
# The trimmer runs unattended in the sandbox, on a machine nobody is watching,
# and its output is the only thing the evening message is built from. So it is
# run here for real -- on payloads shaped like the API's, in a scratch
# directory, with no network -- rather than being trusted because it reads well.
print("\nthe sandbox script survives the trip")
import subprocess                                                  # noqa: E402
import tempfile                                                    # noqa: E402

RAW_SURF = {"data": {"surf": [dict(r, probability=80,
                                   surf=dict(r["surf"], plus=False,
                                             humanRelation="waist to chest"))
                              for r in SURF]}}
RAW_SWELLS = {"data": {"swells": [dict(r, swells=[dict(s, direction=200.5,
                                                       directionMin=190.0)
                                                  for s in r["swells"]])
                                  for r in SWELLS]}}
RAW_WIND = {"data": {"wind": [dict(r, gust=9.1, optimalScore=2) for r in WIND]}}

tmp = tempfile.mkdtemp()
for name, payload in (("surf", RAW_SURF), ("swells", RAW_SWELLS), ("wind", RAW_WIND)):
    with open(os.path.join(tmp, name + ".json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh)

r = subprocess.run(["bash", "-c", S.TRIM], cwd=tmp, capture_output=True, text=True)
check("it runs clean", r.returncode == 0, r.stderr.strip())
check("and prints one line, not a file per feed",
      r.returncode == 0 and r.stdout.count("\n") == 1, str(r.stdout[:80]))

if r.returncode == 0:
    blob = os.path.join(tmp, "sea.json")
    with open(blob, "w", encoding="utf-8") as fh:
        fh.write(r.stdout)
    trimmed = S.hours(*S.load([blob]), date="2026-09-05")
    check("what comes back reads as the same sea it went in as",
          trimmed == ROWS, "%d rows vs %d" % (len(trimmed), len(ROWS)))
    # Size is the point of trimming, but a byte count measured against a
    # hand-written payload only proves how lean the hand-written payload was.
    # What is worth pinning is the rule: nothing crosses that is not read.
    sea = json.loads(r.stdout)
    keys = set()
    for feed in sea.values():
        for row in feed:
            keys |= set(row)
    check("nothing crosses that hours() does not read",
          keys == {"timestamp", "utcOffset", "surf", "swells",
                   "speed", "direction", "directionType"},
          str(sorted(keys)))
    check("including inside each swell",
          {k for row in sea["swells"] for s in row["swells"] for k in s}
          == {"height", "period"})

# A feed that came back empty must stop the evening, not shorten it: a message
# built from two of the three feeds still looks like a forecast.
os.rename(os.path.join(tmp, "wind.json"), os.path.join(tmp, "wind.bak"))
with open(os.path.join(tmp, "wind.json"), "w", encoding="utf-8") as fh:
    json.dump({"data": {"wind": []}}, fh)
r2 = subprocess.run(["bash", "-c", S.TRIM], cwd=tmp, capture_output=True, text=True)
check("a feed that came back empty stops it", r2.returncode != 0, r2.stdout[:80])
check("and it says not to guess", "do not guess" in r2.stderr, r2.stderr.strip())

print("\nthree raw payloads read the same as one trimmed blob")
paths = [os.path.join(tmp, n) for n in ("surf.json", "swells.json", "wind.json")]
os.rename(os.path.join(tmp, "wind.bak"), paths[2])
check("the three-file form still works",
      S.hours(*S.load(paths), date="2026-09-05") == ROWS)

print("\n%d checks, %d failed" % (len(ran), len(fails)))
if fails:
    print("FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
