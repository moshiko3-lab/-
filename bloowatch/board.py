#!/usr/bin/env python3
"""Tomorrow's board as a picture: who is on, when, and what the tide is doing.

    python3 board.py                          # tomorrow, to board.png
    python3 board.py --date 2026-09-02 --out /tmp/wed.png
    python3 board.py --lang en

A fifty-lesson day is unreadable as a list. The office already reads its day
off a grid -- staff down the side, hours across the top, a bar for every
booking -- so this draws the same grid, and puts the tide underneath it on
the same hour axis, because at Playa Venao the tide decides what a lesson at
noon is actually going to be like.

The drawing itself is in draw_board.py, which needs nothing but Pillow.
`--spec` prints the picture as data instead: two kilobytes that will go
where a rendered PNG will not -- into the sandbox that can actually reach
WhatsApp. Nothing here sends anything; it writes a PNG and prints its path.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

from daily_report import BloowatchError, login
from forecast_message import tides_for
from rota import MANY as MANY_NAMES, lessons_for, short, tomorrow

HERE = os.path.dirname(os.path.abspath(__file__))

# The grid never shrinks below the working day, however quiet it is: a board
# that redraws its own axis every morning cannot be compared with yesterday's
# at a glance.
FIRST_HOUR, LAST_HOUR = 6, 20

# One colour per kind of thing, so the shape of the day is legible before a
# single word is read: teaching in the sea, shifts on the land. The colours
# themselves live in draw_board.py; this only decides which is which.
COLOURS = [
    (("SHOP", "TIENDA", "STORE"), "shift"),
    (("RENTAL", "ALQUILER"), "rental"),
]


def kind(title):
    up = (title or "").upper()
    for words, name in COLOURS:
        if any(w in up for w in words):
            return name
    return "lesson"


def minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def curve(date, lo, hi, step=10):
    """The tide between two hours, as the points of a line to draw.

    Tide runs as a smooth swing from each peak to the next, so the height
    between two of them is the cosine that joins them -- the same shape the
    water actually makes. The peaks either side of midnight come from the
    neighbouring days, or the curve would flatten out at both ends of the
    picture exactly where the early and late sessions are.
    """
    pts = []
    d = dt.date.fromisoformat(date)
    for off in (-1, 0, 1):
        day = (d + dt.timedelta(days=off)).isoformat()
        t = tides_for(day)
        if not t:
            continue
        for key in ("highs", "lows"):
            for p in t.get(key) or []:
                pts.append((off * 1440 + minutes(p["t"]), float(p["m"])))
    pts.sort()
    if len(pts) < 2:
        return []

    import math
    out = []
    for x in range(lo, hi + 1, step):
        prev = [p for p in pts if p[0] <= x]
        nxt = [p for p in pts if p[0] >= x]
        if not prev or not nxt:
            continue
        (t0, h0), (t1, h1) = prev[-1], nxt[0]
        if t1 == t0:
            out.append((x, h0))
            continue
        f = (1 - math.cos(math.pi * (x - t0) / (t1 - t0))) / 2
        out.append((x, h0 + (h1 - h0) * f))
    return out


def peaks_in(date, lo, hi):
    """The highs and lows that fall inside the drawn hours, to label them."""
    t = tides_for(date) or {}
    out = []
    for key, what in (("highs", "high"), ("lows", "low")):
        for p in t.get(key) or []:
            x = minutes(p["t"])
            if lo <= x <= hi:
                out.append({"x": x, "m": float(p["m"]), "what": what,
                            "t": p["t"]})
    return sorted(out, key=lambda p: p["x"])


def rows(lessons):
    """One row per person, in the order the day hands them their first job."""
    by = {}
    for l in lessons:
        for name in l["staff"]:
            by.setdefault(name.split()[0].title(), []).append(l)
    return sorted(by.items(), key=lambda kv: (min(x["time"] for x in kv[1]),
                                              kv[0]))


def _span(l):
    a = minutes(l["time"])
    b = minutes(l["until"]) if l.get("until") else a + 60
    return a, max(b, a + 60)


HEB_DOW = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
EN_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
          "Sunday"]


def spec(date, lessons, lang="he"):
    """Everything the picture needs, and nothing that is only in the picture.

    Kept as plain data so the drawing can happen somewhere else -- the only
    machine that can put a picture into WhatsApp has no browser on it, and
    two kilobytes of this travels where forty of PNG will not.
    """
    d = dt.date.fromisoformat(date)
    lo, hi = FIRST_HOUR * 60, LAST_HOUR * 60
    for l in lessons:                      # never clip a real booking
        a, b = _span(l)
        lo, hi = min(lo, a - 60), max(hi, b + 60)
    lo, hi = max(0, (lo // 60) * 60), min(1440, -(-hi // 60) * 60)

    if lang == "en":
        title = "%s %d/%d" % (EN_DOW[d.weekday()], d.day, d.month)
        tide_hd, high_w, low_w = "Tide", "high", "low"
        words = {"lesson": "Lesson", "shift": "Shop shift", "rental": "Rental"}
    else:
        title = "יום %s %d/%d" % (HEB_DOW[d.weekday()], d.day, d.month)
        tide_hd, high_w, low_w = "גאות ושפל", "גאות", "שפל"
        words = {"lesson": "שיעור", "shift": "משמרת חנות", "rental": "השכרה"}

    out_rows = []
    for name, mine in rows(lessons):
        bars = []
        for l in sorted(mine, key=lambda x: x["time"]):
            a, b = _span(l)
            names = ", ".join(l.get("names") or [])
            if len(l.get("names") or []) > MANY_NAMES:
                names = ""
            # a plain surf lesson has no name worth printing, so the person
            # coming to it takes the top line instead of sitting under a word
            # that is on every other bar too
            label, sub = short(l["title"]), names
            if not label:
                label, sub = names or l["title"], ""
            bars.append({"x0": a, "x1": b, "kind": kind(l["title"]),
                         "label": label, "sub": sub,
                         "when": ("%s–%s" % (l["time"], l["until"]))
                                 if l.get("until") else l["time"]})
        out_rows.append({"who": name, "bars": bars})

    tide = None
    pts = curve(date, lo, hi)
    if pts:
        tide = {"label": tide_hd,
                "points": [[x, round(m, 3)] for x, m in pts],
                "peaks": [dict(p, word=high_w if p["what"] == "high" else low_w)
                          for p in peaks_in(date, lo, hi)]}

    # the key describes this board, not every board: a day with no rentals on
    # it should not carry a colour nobody can find
    here = {kind(l["title"]) for l in lessons}
    key = [{"kind": k, "word": words[k]}
           for k in ("lesson", "shift", "rental") if k in here]

    n, crew = len(lessons), len(out_rows)
    if lang == "en":
        stat = "%d booking%s · %d on" % (n, "" if n == 1 else "s", crew)
        foot = "Built from Bloowatch"
    else:
        stat = "%d שיבוצים · %d מדריכים" % (n, crew)
        foot = "נבנה מהבלו"

    return {"date": date, "lang": lang, "title": title,
            "sub": "SHOKOGI · PLAYA VENAO",
            "stat": stat, "foot": foot, "band": title,
            "lo": lo, "hi": hi,
            "hours": list(range(lo // 60, hi // 60 + 1)),
            "rows": out_rows, "tide": tide, "key": key}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--lang", choices=("he", "en"), default="he")
    ap.add_argument("--out", default=os.path.join(HERE, "board.png"))
    ap.add_argument("--spec", action="store_true",
                    help="print the spec instead of drawing it, for a machine "
                         "that has Pillow but cannot reach Bloowatch")
    ap.add_argument("--scale", type=float, default=2)
    a = ap.parse_args()
    date = a.date or tomorrow()
    try:
        s, base = login()
        lessons = lessons_for(s, base, date)
    except BloowatchError as e:
        print("error: " + str(e), file=sys.stderr)
        return 1
    if not lessons:
        print("nothing booked for " + date)
        return 0
    sp = spec(date, lessons, a.lang)
    if a.spec:
        json.dump(sp, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        print()
        return 0
    import draw_board
    im = draw_board.draw(sp, a.scale)
    im.quantize(colors=48, method=draw_board.Image.MEDIANCUT).save(
        a.out, optimize=True)
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
