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
def row(ts, mn, mx):
    return {"timestamp": ts, "utcOffset": -5,
            "surf": {"raw": {"min": mn, "max": mx}}}


BASE = 1788606000          # 2026-09-05 06:00 in Panama (UTC-5)
HRS = 3600
SURF = [row(BASE + i * HRS, mn, mx) for i, (mn, mx) in enumerate([
    (1.14, 1.36), (1.16, 1.39), (1.20, 1.42), (1.22, 1.46), (1.24, 1.49),
    (1.15, 1.52), (1.17, 1.53), (1.19, 1.55), (1.20, 1.56), (1.21, 1.58),
    (1.22, 1.58), (1.23, 1.59), (1.23, 1.59), (1.21, 1.58)])]
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
      holed[0]["hour"] == "06:00" and holed[0]["min"] == 1.14)
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
print("\nheight is the day's average, not its extremes")
w = S.waves(ROWS)
check("5/9 reads 1.2-1.5", w == "1.2-1.5", str(w))
check("the top is below the biggest single hour (1.59)",
      float(w.split("-")[1]) < 1.59, w)
check("and the bottom is above the smallest (1.14)",
      float(w.split("-")[0]) > 1.14, w)
check("a flat day gives one number, not a fake range",
      S.waves([{"min": 1.0, "max": 1.0}] * 5) == "1.0",
      str(S.waves([{"min": 1.0, "max": 1.0}] * 5)))

print("\nperiod is the one the day mostly runs at")
check("16 seconds", S.period(ROWS) == 16, str(S.period(ROWS)))
check("a zero-height swell never sets it",
      S.period([{"period": 16}, {"period": None}]) == 16)

# The whole point of the change: Surfline reads higher than surf-forecast, and
# the school's size language is written in Surfline metres.
print("\nand it is meaningfully bigger than surf-forecast said")
check("Surfline 1.2-1.5 against surf-forecast 0.9-1.1 on the same day",
      float(w.split("-")[0]) - 0.9 >= 0.2, w)

print("\n%d checks, %d failed" % (len(ran), len(fails)))
if fails:
    print("FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
