#!/usr/bin/env python3
"""The one sentence in the forecast that is written rather than measured.

Everything else in the evening forecast is a number off surf-forecast or
arithmetic on the tide table. This line is the school talking, and it goes to
two hundred customers, so the two ways it can go wrong are pinned here.

It can go stale: at Playa Venao the swell barely moves, and the version this
replaced had twelve possible sentences, so it landed on "ים דומה להיום" most
nights until the line stopped being read. The wording therefore rotates on the
date.

And it can lie by omission: if the rotation were allowed to choose which
facts appear, a fourteen-knot onshore -- the single most important thing about
that day -- could be rotated out in favour of something prettier. So the
wording rotates and the facts do not. That is the invariant worth a test.

Nothing here touches the network.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import forecast_message as F                                      # noqa: E402

fails = []
ran = []


def check(name, cond, detail=""):
    ran.append(name)
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def he(today, tom, **kw):
    return F.compare_line(today, tom, "he", **kw)


def en(today, tom, **kw):
    return F.compare_line(today, tom, "en", **kw)


print("the sentence says nothing it does not know")
check("no line at all when today's height is unknown",
      he("", "0.7", date="2026-09-04", period=17) == "")
check("nor when tomorrow's is",
      he("0.4", "", date="2026-09-04", period=17) == "")

# A wind that is doing something outranks everything else on the page. These
# are the days where being wrong is worst: somebody reads "perfect for
# beginners" and drives an hour into a wall of onshore chop.
print("\nwhat the wind is doing is never rotated out")
for d in ("2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07",
          "2026-09-08", "2026-09-09", "2026-09-10"):
    s = he("0.5-0.7", "0.4-0.5", date=d, period=8, wind_kt="14", wind_deg=200)
    check("a 14kt onshore is mentioned on " + d, "רוח" in s and "מהים" in s, s)

for d in ("2026-09-04", "2026-09-05", "2026-09-06"):
    s = he("0.4", "0.7-0.8", date=d, period=17, wind_kt="4", wind_deg=337)
    check("a light offshore is mentioned on " + d, "מהיבשה" in s, s)

print("\nand the same is true in English")
for d in ("2026-09-04", "2026-09-05", "2026-09-06"):
    s = en("0.5-0.7", "0.4-0.5", date=d, period=8, wind_kt="14", wind_deg=200)
    check("14kt onshore in English on " + d,
          "onshore" in s or "sea breeze" in s, s)

print("\nthe wording moves even when the sea does not")
same = [he("0.4-0.6", "0.4-0.6", date=d, period=16, wind_kt="5", wind_deg=0)
        for d in ("2026-09-04", "2026-09-05", "2026-09-06", "2026-09-07")]
check("four identical days read four different ways",
      len(set(same)) == 4, " | ".join(same))
check("but the same date always rebuilds the same sentence",
      he("0.4-0.6", "0.4-0.6", date="2026-09-04", period=16,
         wind_kt="5", wind_deg=0) == same[0])

print("\nthe direction of the change is the school's, not the rotation's")
up = he("0.4", "1.0", date="2026-09-04", period=12, wind_kt="5", wind_deg=90)
down = he("1.0", "0.4", date="2026-09-04", period=12, wind_kt="5", wind_deg=90)
check("a bigger sea never reads as a calmer one",
      "רגוע" not in up and "מוריד" not in up and "יורדים" not in up, up)
check("and a smaller sea never reads as a bigger one",
      "מתעורר" not in down and "מוסיף כוח" not in down
      and "יותר גובה" not in down, down)

# Checked by meaning rather than by one word: a small day is welcoming
# whether it says "beginners", "a first lesson" or "easy to learn in", and
# pinning a single phrase would only forbid rewording the pool later.
WELCOMING = ("מתחילים", "שיעור ראשון", "ללמוד")
DEMANDING = ("מנוסים", "טריים", "היכרות", "ניסיון")


def says(s, words):
    return any(w in s for w in words)


print("\nwho the day is for follows the height, not the mood")
for d in ("2026-09-04", "2026-09-05", "2026-09-06"):
    s = he("0.5", "0.4", date=d, period=12)
    check("half a metre reads as welcoming on " + d, says(s, WELCOMING), s)
for d in ("2026-09-04", "2026-09-05", "2026-09-06"):
    s = he("1.0", "2.0", date=d, period=12)
    check("two metres never does, on " + d, not says(s, WELCOMING), s)
    check("and asks for experience instead, on " + d, says(s, DEMANDING), s)

# The wind row three lines above already reads "3-5 knots from the north-west
# (offshore) - clean and groomed". Saying that again underneath, mirror emoji
# and all, is how a message starts looking automatic.
print("\nit does not repeat the wind row above it")
s = he("0.4", "0.7-0.8", date="2026-09-04", period=17,
       wind_kt="3-5", wind_deg=337)
check("no second mirror emoji", "🪞" not in s, s)
check("and not the wind row's own words", "חלק ומסודר" not in s, s)

print("\nit still works with the numbers missing")
check("no wind: the period speaks instead",
      "פריוד" in he("0.6", "0.6", date="2026-09-04", period=16), "")
check("no wind and an unremarkable period: two clauses, no filler",
      he("0.6", "0.6", date="2026-09-04", period=12).count(",") == 0,
      he("0.6", "0.6", date="2026-09-04", period=12))
check("no date: still builds",
      he("0.4", "0.8", period=17, wind_kt="4", wind_deg=337) != "")

# BEACH_FACES decides offshore from onshore for every wind in every forecast.
# Confirmed south by the owner on 3/9/2026.
print("\nthe beach still faces south")
check("BEACH_FACES is 180", F.BEACH_FACES == 180, str(F.BEACH_FACES))
check("north wind reads as offshore",
      F._deciding_fact("4", 0, 12) == "off_light",
      str(F._deciding_fact("4", 0, 12)))
check("south wind reads as onshore",
      F._deciding_fact("4", 180, 12) == "on_light",
      str(F._deciding_fact("4", 180, 12)))
check("and an east wind is neither, so the period talks",
      F._deciding_fact("4", 90, 16) == "long",
      str(F._deciding_fact("4", 90, 16)))

# The school opens at six and the last surf is at seven. A window outside that
# is not a near miss -- it is the forecast recommending an hour when nobody is
# on the beach, which is how the owner spots that it does not know his day. The
# mid-tide window was the one that leaked: its centre was checked against the
# day but the ninety minutes either side were not, so a mid-tide at 06:30
# printed "05:00-08:00" on 4/9/2026.
print("\nno window falls outside the hours anybody surfs")


def all_windows(highs, lows):
    t = {"highs": [{"t": x} for x in highs], "lows": [{"t": x} for x in lows]}
    low_w, high_w, mid_w = F.windows(t)
    return low_w + high_w + mid_w


DAYS = [
    (["09:23"], ["15:54"]),          # 5/9/2026 -- the day that printed 05:00
    (["06:40"], ["12:50"]),          # a high just after opening
    (["18:50"], ["12:10"]),          # a high just before the last surf
    (["05:30", "18:00"], ["11:45"]),  # a high before the beach opens at all
    (["07:00", "19:30"], ["01:00", "13:15"]),   # peaks either side of the day
]
for highs, lows in DAYS:
    ws = all_windows(highs, lows)
    label = "highs %s lows %s" % (",".join(highs), ",".join(lows))
    check("every window starts at 06:00 or later — " + label,
          all(w[0] >= "06:00" for w in ws), str(ws))
    check("every window ends by 19:00 — " + label,
          all(w[1] <= "19:00" for w in ws), str(ws))
    check("and none of them is under an hour — " + label,
          all(F.mins(w[1]) - F.mins(w[0]) >= 60 for w in ws), str(ws))

print("\n%d checks, %d failed" % (len(ran), len(fails)))
if fails:
    print("FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
