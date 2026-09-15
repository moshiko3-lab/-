#!/usr/bin/env python3
"""The day's sea as one card, drawn from our own numbers.

    python3 card.py --date 2026-09-16 --out /tmp/card.png

**Why this exists rather than a screenshot.** The forecast carried a
screenshot of Surfline's page for a day, and the owner kept saying it did
not look like what he sees. He was right, and it took several rounds to
find out why: what he reads is Surfline's *app*, and the app's day view --
a tide card with every peak labelled, an energy card beside it -- has no
equivalent on the website. The website also reports in feet while the
message reports in metres, because units live in a signed-in account
setting we do not have.

Every number on that card is already in this repository: the tide table
with times and heights, the energy feed in kilojoules, first light and
sunset, the surf, the wind. So it is drawn here instead, in Hebrew, in
metres, with no clutter to crop around and nothing to break when Surfline
next changes its markup.

It is rendered as HTML through the Chromium already on this machine --
the same browser `shot.py` and `surfshot.py` use -- because laying Hebrew
out right to left in an image library is a source of silent, unreadable
bugs, and a browser already does it correctly.

**The card is a bonus and the message is the point.** `draw()` returns a
reason instead of raising, exactly as `surfshot.shoot()` does, and the
forecast goes out as text when anything here fails.
"""

import argparse
import datetime as dt
import html
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import forecast_message as F                                    # noqa: E402

WIDTH, SCALE = 440, 3

HEB_DAY = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")


def _mins(t):
    h, _, m = t.partition(":")
    return int(h) * 60 + int(m)


def tide_points(t):
    """Every tide peak of the day as (minutes, metres, "HH:MM", is_high).

    Sorted by time, which is what a curve needs and is not how the table
    stores them -- highs and lows come in two separate lists.
    """
    out = []
    for key, high in (("highs", True), ("lows", False)):
        for x in (t.get(key) or []):
            try:
                out.append((_mins(x["t"]), float(x.get("m") or 0), x["t"], high))
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(out)


def _curve(points, w, h, pad):
    """A smooth path through the peaks, and where each label goes.

    The tide is a sine between one peak and the next, so the curve is
    drawn as a cosine segment per pair rather than straight lines: a tide
    chart with corners in it reads as wrong to anyone who surfs.
    """
    import math
    if len(points) < 2:
        return "", [], ""
    lo = min(p[1] for p in points)
    hi = max(p[1] for p in points)
    span = (hi - lo) or 1.0

    def x_of(m):
        return pad + (m / 1440.0) * (w - 2 * pad)

    def y_of(v):
        return pad + (1 - (v - lo) / span) * (h - 2 * pad)

    d = []
    for i in range(len(points) - 1):
        a_m, a_v = points[i][0], points[i][1]
        b_m, b_v = points[i + 1][0], points[i + 1][1]
        steps = 24
        for s in range(steps + 1):
            f = s / float(steps)
            # cosine ease: flat at each peak, steepest halfway between
            v = a_v + (b_v - a_v) * (1 - math.cos(f * math.pi)) / 2.0
            m = a_m + (b_m - a_m) * f
            d.append("%s %.1f %.1f" % ("M" if not d else "L", x_of(m), y_of(v)))
    close = ""
    if d:
        x0 = x_of(points[0][0])
        x1 = x_of(points[-1][0])
        close = "L %.1f %.1f L %.1f %.1f Z" % (x1, h - pad + 12,
                                               x0, h - pad + 12)
    return " ".join(d), [(x_of(p[0]), y_of(p[1]), p[2], p[1], p[3])
                         for p in points], close


def html_for(date, tides, light, energy, waves, period, wind, windows):
    """The card, as a page. Every value is already decided by the caller."""
    pts = tide_points(tides)
    # Tall enough that a peak label has somewhere to go. The first version
    # was 118 and the 19:10 label was clipped by the top edge.
    w, h, pad = 400, 150, 34
    path, labels, close = _curve(pts, w, h, pad)

    # A high is labelled above the curve and a low below it, so the text is
    # never over the line and never over the hour axis underneath.
    marks = []
    for x, y, when, metres, high in labels:
        x = min(max(x, 26), w - 26)         # keep the text inside the box
        first, second = (-19, -7) if high else (17, 29)
        marks.append(
            '<circle cx="%.1f" cy="%.1f" r="3.5" class="dot"/>'
            '<text x="%.1f" y="%.1f" class="pk mid">%s</text>'
            '<text x="%.1f" y="%.1f" class="pk2 mid">%s מ׳</text>'
            % (x, y, x, y + first, when, x, y + second,
               ("%.1f" % metres).rstrip("0").rstrip(".")))

    hours = "".join(
        '<text x="%.1f" y="%d" class="ax mid">%02d</text>'
        % (pad + (hh * 60 / 1440.0) * (w - 2 * pad), h + 15, hh)
        for hh in (3, 6, 9, 12, 15, 18, 21))

    d = dt.date.fromisoformat(date)
    day = HEB_DAY[d.weekday()]
    rows = "".join(
        '<div class="row"><span>%s</span><b>%s</b></div>' % (k, v)
        for k, v in (("אור ראשון", light.get("dawn", "")),
                     ("זריחה", light.get("sunrise", "")),
                     ("שקיעה", light.get("sunset", "")),
                     ("אור אחרון", light.get("dusk", ""))) if v)

    # \u2066 ... \u2069 isolates each range left-to-right. Without it the
    # RTL paragraph lays the two times out backwards and 14:00-18:30 is
    # printed as 18:30-14:00, which is what the first card did.
    hrs = "".join('<span class="win" dir="ltr">\u2066%s–%s\u2069</span>'
                  % (a, b) for a, b in windows)

    return """<!doctype html><html dir="rtl" lang="he"><head>
<meta charset="utf-8">
<style>
 *{box-sizing:border-box;margin:0;padding:0}
 body{width:%(W)dpx;background:#eef2f7;font-family:-apple-system,
   "Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;padding:14px;
   color:#0f172a}
 .card{background:#fff;border-radius:18px;padding:16px 16px 12px;
   margin-bottom:12px;box-shadow:0 1px 3px rgba(15,23,42,.07)}
 .cap{font-size:12px;letter-spacing:.06em;color:#7c8aa0;font-weight:700}
 .big{font-size:34px;font-weight:800;line-height:1.1;margin-top:2px}
 .big small{font-size:15px;font-weight:700;color:#64748b;margin-right:3px}
 .sub{font-size:13px;color:#64748b;margin-top:2px}
 .two{display:flex;gap:26px}
 svg{display:block;margin:14px auto 2px}
 .ln{fill:none;stroke:#3b82f6;stroke-width:2.5}
 .fill{fill:#dbeafe;opacity:.75}
 .dot{fill:#fff;stroke:#3b82f6;stroke-width:2.5}
 .pk{font-size:11px;font-weight:800;fill:#0f172a}
 .pk2{font-size:11px;font-weight:600;fill:#64748b}
 .ax{font-size:10px;fill:#94a3b8;font-weight:600}
 .mid{text-anchor:middle}
 .row{display:flex;justify-content:space-between;font-size:13px;
   padding:5px 0;border-bottom:1px solid #f1f5f9}
 .row:last-child{border:0}
 .row span{color:#64748b}
 .row b{font-variant-numeric:tabular-nums}
 .hd{display:flex;justify-content:space-between;align-items:baseline;
   margin-bottom:10px}
 .hd h1{font-size:19px;font-weight:800}
 .hd em{font-style:normal;font-size:13px;color:#64748b}
 .win{display:inline-block;background:#eff6ff;color:#1d4ed8;font-weight:700;
   font-size:13px;border-radius:9px;padding:5px 10px;margin:4px 4px 0 0;
   font-variant-numeric:tabular-nums}
</style></head><body>
 <div class="hd"><h1>%(DAY)s %(DM)s</h1><em>פלאיה ונאו</em></div>

 <div class="card">
  <div class="two">
   <div><div class="cap">גובה גלים</div>
        <div class="big">%(WAVES)s<small>מ׳</small></div></div>
   <div><div class="cap">פריוד</div>
        <div class="big">%(PERIOD)s<small>שנ׳</small></div></div>
  </div>
  <div class="sub">%(WIND)s</div>
  <div style="margin-top:8px">%(HRS)s</div>
 </div>

 <div class="card">
  <div class="cap">גאות</div>
  <svg width="%(w)d" height="%(hh)d" viewBox="0 0 %(w)d %(hh)d">
   <path class="fill" d="%(PATH)s %(CLOSE)s"/>
   <path class="ln" d="%(PATH)s"/>%(MARKS)s%(HOURS)s
  </svg>
  <div style="margin-top:12px">%(ROWS)s</div>
 </div>

 <div class="card">
  <div class="two">
   <div><div class="cap">אנרגיה סמוכה לחוף</div>
        <div class="big">%(NEAR)s<small>kJ</small></div></div>
   <div><div class="cap">בים הפתוח</div>
        <div class="big">%(OFF)s<small>kJ</small></div></div>
  </div>
 </div>
</body></html>""" % {
        "W": WIDTH, "w": w, "h": h, "hh": h + 22,
        "DAY": html.escape("יום " + day), "DM": "%d/%d" % (d.day, d.month),
        "WAVES": html.escape(waves), "PERIOD": html.escape(str(period)),
        "WIND": html.escape(wind), "HRS": hrs,
        "PATH": path, "CLOSE": close, "MARKS": "".join(marks), "HOURS": hours, "ROWS": rows,
        "NEAR": energy.get("near", "—"), "OFF": energy.get("off", "—"),
    }


def draw(out, date, tides, light, energy, waves, period, wind, windows,
         width=WIDTH, scale=SCALE, timeout=60000):
    """Render the card to `out`. Returns (path, reason), never raises."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:                                    # noqa: BLE001
        return "", "playwright is not available here: %s" % exc
    try:
        from shot import chromium
        where = chromium()
    except Exception:                                           # noqa: BLE001
        where = None

    fd, page = tempfile.mkstemp(suffix="-card.html", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html_for(date, tides, light, energy, waves, period, wind,
                         windows))
    try:
        with sync_playwright() as pw:
            how = {}
            if where:
                how["executable_path"] = where
            b = pw.chromium.launch(**how)
            try:
                ctx = b.new_context(viewport={"width": width, "height": 200},
                                    device_scale_factor=scale)
                p = ctx.new_page()
                p.goto("file://" + page, wait_until="load", timeout=timeout)
                p.wait_for_timeout(400)
                p.screenshot(path=out, full_page=True)
            finally:
                b.close()
    except Exception as exc:                                    # noqa: BLE001
        return "", "the card could not be drawn: %s" % str(exc)[:200]
    finally:
        os.remove(page)

    if not (os.path.exists(out) and os.path.getsize(out) > 0):
        return "", "the card came out empty"
    return out, ""


def for_day(date, out):
    """Everything the card needs, gathered the way the forecast gathers it."""
    import surfline
    blob = surfline.fetch(days=2)
    rows = surfline.hours(blob["surf"], blob["swells"], blob["wind"], date)
    s = surfline.summary(rows)
    t = F.tides_for(date)
    if not t:
        return "", "no tide table for " + date

    near = surfline.day_energy(blob.get("energy"), date)
    off = None
    vals = [r.get("offshore") for r in (blob.get("energy") or [])
            if r.get("offshore") is not None
            and surfline._local(r["timestamp"], r.get("utcOffset") or 0)
            .date().isoformat() == date]
    if vals:
        off = sum(vals) / len(vals)

    wind = ""
    if s.get("wind") and s.get("wind_dir"):
        wind = F.wind_line(s["wind"], s["wind_dir"], F.BEACH_FACES, "he")
        # The message's own wind line, minus its label and its verdict: the
        # card has a heading of its own and no room for "ים חלק ומסודר".
        wind = wind.replace("*", "").split(" – ")[0]
        wind = wind.split(" - ", 1)[-1].strip()

    weak = near is not None and near < F.WEAK_ENERGY
    _, _, mid, _beg = F.windows(t, weak=weak)

    return draw(out, date, t, surfline.light(blob.get("sunlight"), date),
                {"near": "%d" % near if near else "—",
                 "off": "%d" % off if off else "—"},
                s.get("waves", ""), s.get("period", ""), wind, mid)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    a = ap.parse_args()
    path, why = for_day(a.date, a.out)
    if not path:
        print("no card: " + why, file=sys.stderr)
        return 1
    print("%s (%d bytes)" % (path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
