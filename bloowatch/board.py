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

Rendered by pointing headless Chromium at a page this builds. Nothing here
sends anything; it writes a PNG and prints its path.
"""
import argparse
import datetime as dt
import glob
import html
import json
import os
import re
import subprocess
import sys
import tempfile

from daily_report import BloowatchError, login
from forecast_message import tides_for
from rota import PANAMA, lessons_for, short, tomorrow

HERE = os.path.dirname(os.path.abspath(__file__))

# The grid never shrinks below the working day, however quiet it is: a board
# that redraws its own axis every morning cannot be compared with yesterday's
# at a glance.
FIRST_HOUR, LAST_HOUR = 6, 20

# One colour per kind of thing, so the shape of the day is legible before a
# single word is read: teaching in the sea, shifts on the land.
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


def page(date, lessons, lang="he"):
    d = dt.date.fromisoformat(date)
    lo, hi = FIRST_HOUR * 60, LAST_HOUR * 60
    for l in lessons:                      # never clip a real booking
        a, b = _span(l)
        lo, hi = min(lo, a - 60), max(hi, b + 60)
    lo, hi = max(0, (lo // 60) * 60), min(1440, -(-hi // 60) * 60)
    width = hi - lo

    def pct(x):
        return 100.0 * (x - lo) / width

    if lang == "en":
        title = "%s %d/%d" % (EN_DOW[d.weekday()], d.day, d.month)
        who_hd, tide_hd = "Crew", "Tide"
        high_w, low_w = "high", "low"
    else:
        title = "יום %s %d/%d" % (HEB_DOW[d.weekday()], d.day, d.month)
        who_hd, tide_hd = "צוות", "גאות ושפל"
        high_w, low_w = "גאות", "שפל"

    hours = list(range(lo // 60, hi // 60 + 1))
    head = "".join(
        '<div class="h" style="left:%.4f%%">%02d</div>' % (pct(h * 60), h)
        for h in hours)
    grid = "".join('<div class="v" style="left:%.4f%%"></div>' % pct(h * 60)
                   for h in hours)

    body = []
    for name, mine in rows(lessons):
        bars = []
        for l in sorted(mine, key=lambda x: x["time"]):
            a, b = _span(l)
            names = ", ".join(l.get("names") or [])
            if len(l.get("names") or []) > 4:
                names = ""
            # a plain surf lesson has no name worth printing, so the person
            # coming to it takes the top line instead of sitting under a
            # word that is on every other bar too
            head_, sub = short(l["title"]), names
            if not head_:
                head_, sub = names or l["title"], ""
            bars.append(
                '<div class="bar %s" style="left:%.4f%%;width:%.4f%%">'
                '<b>%s</b>%s</div>'
                % (kind(l["title"]), pct(a), 100.0 * (b - a) / width,
                   html.escape(head_),
                   ('<i>%s</i>' % html.escape(sub)) if sub else ""))
        body.append('<div class="row"><div class="who">%s</div>'
                    '<div class="track">%s%s</div></div>'
                    % (html.escape(name), grid, "".join(bars)))

    pts = curve(date, lo, hi)
    tide = ""
    if pts:
        top = max(p[1] for p in pts)
        bot = min(p[1] for p in pts)
        rng = (top - bot) or 1.0
        xy = " ".join("%.3f,%.3f" % (pct(x), 100 - 100 * (m - bot) / rng)
                      for x, m in pts)
        marks = "".join(
            '<div class="peak %s%s" style="left:%.4f%%">'
            '<span>%s</span><b>%s</b><i>%.1f</i></div>'
            % (p["what"],
               " first" if pct(p["x"]) < 6 else
               (" last" if pct(p["x"]) > 94 else ""), pct(p["x"]),
               high_w if p["what"] == "high" else low_w, p["t"], p["m"])
            for p in peaks_in(date, lo, hi))
        tide = ('<div class="tide"><div class="who">%s</div>'
                '<div class="track">%s'
                '<svg viewBox="0 0 100 100" preserveAspectRatio="none">'
                '<polyline points="%s"/></svg>%s</div></div>'
                % (tide_hd, grid, xy, marks))

    # the key describes this board, not every board: a day with no rentals
    # on it should not carry a colour nobody can find
    words = ({"lesson": "Lesson", "shift": "Shop shift", "rental": "Rental"}
             if lang == "en" else
             {"lesson": "שיעור", "shift": "משמרת חנות", "rental": "השכרה"})
    here = {kind(l["title"]) for l in lessons}
    key = [(k, words[k]) for k in ("lesson", "shift", "rental") if k in here]
    return TEMPLATE % {
        "lang": "en" if lang == "en" else "he",
        "title": html.escape(title),
        "sub": "SHOKOGI · Playa Venao",
        "who": html.escape(who_hd),
        "head": head,
        "rows": "".join(body),
        "tide": tide,
        "key": "".join('<span><i class="dot %s"></i>%s</span>'
                       % (cls, html.escape(word)) for cls, word in key),
    }


TEMPLATE = """<!doctype html><html dir="ltr"><head><meta charset="utf-8">
<style>
:root{
  --ink:#0c2430; --muted:#5d7684; --line:#e3ded4; --sand:#f7f2e9;
  --sea:#0f7d8f; --sea-soft:#daeef1; --shift:#e0932c; --shift-soft:#fbeed6;
  --rental:#7a6bb5; --rental-soft:#e8e4f5;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#fff;font:14px/1.35 "DejaVu Sans","FreeSans",sans-serif;
     color:var(--ink);width:1400px;padding:26px 30px 30px}
h1{font-size:26px;letter-spacing:.2px}
.sub{color:var(--muted);font-size:13px;letter-spacing:.4px}
.head{display:flex;align-items:baseline;justify-content:space-between;
      border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:4px}
.axis{position:relative;height:22px;margin-left:130px}
.h{position:absolute;top:5px;transform:translateX(-50%%);font-size:12px;
   color:var(--muted);font-variant-numeric:tabular-nums}
.row{display:flex;align-items:stretch;border-bottom:1px solid var(--line)}
.row:first-of-type{border-top:1px solid var(--line)}
.who{width:130px;flex:0 0 130px;padding-right:12px;font-weight:bold;
     font-size:15px;display:flex;align-items:center}
.track{position:relative;flex:1;min-height:54px;background:var(--sand)}
.v{position:absolute;top:0;bottom:0;width:1px;background:#fff}
.bar{position:absolute;top:6px;bottom:6px;border-radius:5px;padding:6px 6px;
     overflow:hidden;border-left:3px solid var(--sea);background:var(--sea-soft)}
.bar b{display:block;font-size:10.5px;line-height:1.2;white-space:nowrap;
       overflow:hidden;text-overflow:ellipsis}
.bar i{display:block;font-style:normal;font-size:10.5px;color:var(--muted);
       white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:3px}
.bar.shift{border-left-color:var(--shift);background:var(--shift-soft)}
.bar.rental{border-left-color:var(--rental);background:var(--rental-soft)}
.tide{display:flex;margin-top:16px}
.tide .who{align-items:flex-start;padding-top:6px;font-size:13px}
.tide .track{min-height:110px;background:#f1f7f9;border-radius:6px}
.tide svg{position:absolute;inset:0;width:100%%;height:100%%}
.tide polyline{fill:none;stroke:var(--sea);stroke-width:1.8;
               vector-effect:non-scaling-stroke;stroke-linejoin:round}
.peak{position:absolute;bottom:9px;transform:translateX(-50%%);
      text-align:center;font-size:11px;line-height:1.3}
.peak.high{top:9px;bottom:auto}
.peak span{display:block;color:var(--muted);font-size:10px}
.peak b{display:block;font-variant-numeric:tabular-nums;font-size:12px}
.peak i{display:block;font-style:normal;color:var(--sea);font-weight:bold;
        font-variant-numeric:tabular-nums}
.key{display:flex;gap:20px;margin:14px 0 0 130px;font-size:12px;
     color:var(--muted)}
.key span{display:flex;align-items:center;gap:7px}
.dot{width:12px;height:12px;border-radius:3px;background:var(--sea-soft);
     border-left:3px solid var(--sea)}
.dot.shift{background:var(--shift-soft);border-left-color:var(--shift)}
.peak.first{transform:none;text-align:left}
.peak.last{transform:translateX(-100%%);text-align:right}
body.he h1,body.he .tide .who,body.he .peak span{direction:rtl}
</style></head><body class="%(lang)s">
<div class="head"><h1>%(title)s</h1><div class="sub">%(sub)s</div></div>
<div class="axis">%(head)s</div>
%(rows)s
%(tide)s
<div class="key">%(key)s</div>
</body></html>"""


def chromium():
    """Whichever headless Chromium this machine happens to carry."""
    for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser",
              "/usr/bin/google-chrome"):
        if os.path.exists(p):
            return p
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/opt/pw-browsers/chromium_headless_shell-*/"
                "chrome-linux/headless_shell"):
        found = sorted(glob.glob(pat))
        if found:
            return found[-1]
    raise SystemExit("no chromium on this machine")


def render(source, out, width=1400, scale=2, tall=2400):
    """Shoot the page into a window taller than it needs, then cut it down.

    Headless Chromium screenshots the viewport, not the document, and asking
    it for the document's height means running it twice. Shooting into a
    window nobody will ever fill and trimming the white off the bottom costs
    one run and always fits.
    """
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "board.html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(source)
        cmd = [chromium(), "--headless", "--disable-gpu", "--no-sandbox",
               "--hide-scrollbars", "--default-background-color=ffffffff",
               "--force-device-scale-factor=%d" % scale,
               "--window-size=%d,%d" % (width, tall),
               "--screenshot=" + out, "--virtual-time-budget=3000",
               "file://" + src]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           cwd=tmp, timeout=120)
        if not os.path.exists(out):
            raise SystemExit("chromium wrote nothing:\n" + r.stderr[-2000:])
    trim(out, pad=26 * scale)
    return out


def trim(path, pad=52):
    """Cut the empty page off the bottom, leaving the margin the design has."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return
    im = Image.open(path).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255)))
    bbox = box.getbbox()
    if bbox:
        im.crop((0, 0, im.width, min(im.height, bbox[3] + pad))).save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--lang", choices=("he", "en"), default="he")
    ap.add_argument("--out", default=os.path.join(HERE, "board.png"))
    ap.add_argument("--html", default="", help="also keep the page itself")
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
    src = page(date, lessons, a.lang)
    if a.html:
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(src)
    print(render(src, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
