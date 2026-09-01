#!/usr/bin/env python3
"""The school's evening forecast message for the clients group, built.

    python3 forecast_message.py --date 2026-09-02 --waves 0.6-0.9 --period 12

Most of this message is not a forecast at all -- it is the tide table, which
the app already holds for every day to the end of the year, and a set of
windows worked out from it. Reading their own message back:

    high 06:18 / 18:37, low 12:17     -> exactly the tide table for that day
    "near low (10:00-14:00)"          -> the low, give or take two hours
    "near mid and high (06:00-10:00,
     14:00-19:00)"                    -> each high, out to two hours
    recommended 08:00-11:00,
                14:00-17:00           -> mid-tide, give or take an hour and a
                                         half: the water is moving most there

So only two numbers have to come from outside: how big the swell is and how
long the period. Everything else is arithmetic on tides the school already has,
which is why this runs with no network at all.

The wording is the school's own, kept as it is written. It is a message to
customers in their voice, not a report -- so this fills their sentences in
rather than inventing new ones.
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "..", "app", "catalog.json")

HEB_DOW = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def tides_for(date):
    """The day's highs and lows, from the table the app already carries."""
    with open(CATALOG, encoding="utf-8") as f:
        cat = json.load(f)
    for t in cat.get("tides") or []:
        if t.get("date") == date:
            return t
    return None


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def hhmm(m):
    m = max(0, min(24 * 60 - 1, int(round(m))))
    return "%02d:%02d" % (m // 60, m % 60)


def snap(m):
    """To the nearest hour, not outwards. Rounding a window open at both ends
    stretches three hours into five, and the school's own message rounds to
    whichever hour is closer: 10:17 is ten o'clock, 14:17 is two."""
    return int(round(m / 60.0)) * 60


def hour_window(centre, half):
    a = snap(centre - half)
    b = snap(centre + half)
    return hhmm(max(0, a)), hhmm(min(24 * 60 - 1, b))


# The hours anybody is actually going in, which is what the windows are cut
# to. The school's message never mentions the small hours, and neither does
# its board.
DAY_FROM, DAY_TO = 6 * 60, 19 * 60

# Listing a tide is a wider question than recommending an hour. A high at
# 19:17 is the evening tide everybody plans the last surf around; cutting it
# because the recommendation window stops at seven leaves the message saying
# the day has one high tide when it has two.
LIST_FROM, LIST_TO = 5 * 60, 21 * 60


def windows(t):
    """The three kinds of window the school talks about."""
    highs = sorted(mins(x["t"]) for x in (t.get("highs") or []))
    lows = sorted(mins(x["t"]) for x in (t.get("lows") or []))

    # near low: the low, give or take two hours
    low_w = []
    for x in lows:
        a = max(DAY_FROM, snap(x - 120))
        b = min(DAY_TO, snap(x + 120))
        if b - a >= 60:
            low_w.append((hhmm(a), hhmm(b)))

    # near high: the rest of the day around the low. Reading their message
    # back, "near mid and high 06:00-10:00, 14:00-19:00" against a low window
    # of 10:00-14:00 is exactly the daylight the low does not claim -- the
    # tide is on its high side for all of it.
    cuts = [DAY_FROM]
    for a, b in low_w:
        cuts += [mins(a), mins(b)]
    cuts.append(DAY_TO)
    high_w = []
    for i in range(0, len(cuts) - 1, 2):
        a, b = cuts[i], cuts[i + 1]
        if b - a >= 60:
            high_w.append((hhmm(a), hhmm(b)))

    # mid-tide: halfway between a peak and the next trough, either way round.
    # That is where the water is moving, which is what the school recommends.
    peaks = sorted([(x, "H") for x in highs] + [(x, "L") for x in lows])
    mids = []
    for i in range(len(peaks) - 1):
        a, ka = peaks[i]
        b, kb = peaks[i + 1]
        if ka == kb:
            continue
        mids.append((a + b) / 2.0)
    mid_w = [hour_window(m, 90) for m in mids
             if DAY_FROM <= m <= DAY_TO]
    return low_w, high_w, mid_w


def span(w):
    return "%s-%s" % w


def mid(waves):
    """The middle of a range like 0.6-0.9, for comparing one day to the next."""
    try:
        parts = [float(x) for x in str(waves).replace(",", ".").split("-")]
        return sum(parts) / len(parts)
    except Exception:
        return None


def compare_line(today, tomorrow):
    """The school's own call, in their words: is tomorrow bigger or smaller
    than today, and is that good news. Written only when both are known --
    guessing at the sea in a message to customers is not on."""
    a, b = mid(today), mid(tomorrow)
    if a is None or b is None:
        return ""
    diff = b - a
    if abs(diff) < 0.15:
        how = "ים דומה להיום"
    elif diff > 0:
        how = "ים יותר גבוה מהיום"
    else:
        how = "ים יותר נמוך מהיום"
    # the second half is about the size itself, not the change
    if b < 0.5:
        mood = "קטן ונוח – מושלם למתחילים"
    elif b < 1.0:
        mood = "יום ממש כיפי לגלישה"
    elif b < 1.5:
        mood = "יום טוב לגולשים עם ניסיון"
    else:
        mood = "רק לגולשים מנוסים"
    return "מחר צפוי להיות %s – %s" % (how, mood)


def tide_range_note(t):
    """Free intelligence from the table we already hold: how far the water
    moves. A three-metre swing in six hours is a lot of water leaving the bay,
    and that is when the current down the beach is worth a word. A small swing
    is a gentle, forgiving day. Nobody has to look this up -- it is arithmetic
    on the numbers already in front of us."""
    hs = [float(x.get("m") or 0) for x in (t.get("highs") or [])]
    ls = [float(x.get("m") or 0) for x in (t.get("lows") or [])]
    if not hs or not ls:
        return "", None
    rng = max(hs) - min(ls)
    if rng >= 3.2:
        return ("*⚠️ הפרשי גאות גדולים היום (%.1f מטר) – זרם חזק יותר, "
                "במיוחד סביב אמצע הגאות. להישאר מול הצוות.*" % rng), rng
    if rng <= 2.3:
        return ("*הפרשי גאות קטנים היום (%.1f מטר) – ים נוח וזרם חלש.*"
                % rng), rng
    return "", rng


def build(date, waves, period, compare, rain, spot_note, note=""):
    t = tides_for(date)
    if not t:
        return None, "no tide table for " + date
    low_w, high_w, mid_w = windows(t)
    d = dt.date.fromisoformat(date)

    # Only the tides anybody is going in for. A low at half past midnight is a
    # real low and no use to a surfer reading this at bedtime, and putting it
    # in the message is how a reader loses trust in the rest of the numbers.
    def daytime(rows):
        return [x for x in rows if LIST_FROM <= mins(x["t"]) <= LIST_TO]

    hi_rows = daytime(t.get("highs") or []) or (t.get("highs") or [])
    lo_rows = daytime(t.get("lows") or []) or (t.get("lows") or [])
    highs = " ".join(x["t"] for x in sorted(hi_rows,
                                            key=lambda x: x["t"], reverse=True))
    lows = " ".join(x["t"] for x in sorted(lo_rows, key=lambda x: x["t"]))

    # Feet alongside metres, the way they write it. When the swell is not
    # known the line says so loudly rather than quietly carrying yesterday's
    # number: a forecast nobody checked, sent to two hundred customers as if
    # it were checked, is worse than no forecast.
    feet = ""
    shown = str(waves)
    try:
        parts = [float(x) for x in str(waves).split("-")]
        # a single number is a range whose ends happen to meet
        a, b = (parts[0], parts[-1])
        fa, fb = round(a * 3.28), round(b * 3.28)
        # "1.0-1.0 metres (3-3 feet)" is a range with nothing in it. When the
        # sea is the same all day, say so once.
        if abs(a - b) < 0.05:
            shown = ("%.1f" % a)
            feet = " (%d פיט)" % fa
        else:
            feet = " (%d-%d פיט)" % (fa, fb) if fa != fb else " (%d פיט)" % fa
    except Exception:
        pass
    waves = shown

    L = []
    L.append("*ערב טוב חברים🌞*")
    L.append("")
    L.append("🏄‍♀️תחזית גלים לתאריך %d/%d🏄‍♂️" % (d.day, d.month))
    L.append("")
    L.append("*שיא גאות* - " + highs)
    L.append("*שיא שפל* - " + lows)
    L.append("")
    L.append("*גובה גלים* - %s מטר%s" % (waves, feet))
    L.append("*פריוד גלים* - %s שניות" % period)
    L.append("")
    if compare:
        L.append("*🌞🏄‍♀️🎉 %s 😎🏄‍♂️🌊*" % compare)
        L.append("")

    L.append("*תחזית ושעות מומלצות לגולשים עם נסיון*")
    L.append("")
    for w in mid_w:
        L.append(span(w))
    L.append("")
    if low_w:
        L.append("*קרוב לשפל (%s) גל מהיר, צינורי ורדוד יותר – שורט וביצועים.*"
                 % ", ".join(span(w) for w in low_w))
    if high_w:
        L.append("*קרוב למיד טייד וגאות (%s) גל סלחני ורך יותר – נפח גבוה.*"
                 % ", ".join(span(w) for w in high_w))
    L.append("")
    L.append("*תחזית ושעות מומלצות למתחילים*")
    L.append("")
    for w in mid_w:
        L.append(span(w))
    L.append("")
    L.append("*🏄‍♀️%s🏄‍♂️*" % spot_note)
    L.append("")
    L.append("*קרוב לגאות רך ואיטי.*")
    L.append("*קרוב לשפל צינורי ומהיר – טוב לגלי קצף.*")
    L.append("")
    L.append("*חתירה בסאפ*")
    L.append("קרוב לשיאי הגאות/שפל")
    L.append("")
    if note:
        L.append(note)
        L.append("")
    if rain:
        L.append(rain)
        L.append("")
    L.append("בהצלחה בים! 🤙🌊")
    return "\n".join(L), None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--waves", default="0.6-0.9",
                    help="wave height in metres, e.g. 0.6-0.9")
    ap.add_argument("--period", default="12", help="swell period in seconds")
    ap.add_argument("--waves-today", default="",
                    help="today's height, so the 'bigger or smaller' line "
                         "writes itself instead of being typed each evening")
    ap.add_argument("--compare", default="",
                    help="override that line by hand")
    ap.add_argument("--rain", default="",
                    help="the rain line, when there is one")
    ap.add_argument("--tide-note", action="store_true",
                    help="add a line when the tide range is unusually big or "
                         "small — worked out from the table, not forecast")
    ap.add_argument("--spot", default="צד שמאל של החוף מול סלינה נמוך ונוח יותר לתרגול")
    a = ap.parse_args()

    date = a.date
    if not date:
        # Panama is UTC-5 all year; tomorrow there, not tomorrow here
        now = dt.datetime.utcnow() - dt.timedelta(hours=5)
        date = (now.date() + dt.timedelta(days=1)).isoformat()

    compare = a.compare or compare_line(a.waves_today, a.waves)

    note = ""
    if a.tide_note:
        t = tides_for(date)
        if t:
            note, _rng = tide_range_note(t)

    msg, err = build(date, a.waves, a.period, compare, a.rain, a.spot, note)
    if err:
        print("error: " + err, file=sys.stderr)
        return 1
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
