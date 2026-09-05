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


def hour_window(centre, half, lo=None, hi=None):
    """A window of `half` minutes either side of `centre`, kept inside the day.

    The bounds are not decoration. A mid-tide at 06:30 opens a window at 05:00
    unless something stops it, and the message then recommends an hour nobody
    surfs -- the owner reads that as the forecast not knowing what time the
    school opens. Clamping here rather than at the call site keeps every window
    in the message inside the same hours.
    """
    a = snap(centre - half)
    b = snap(centre + half)
    a = max(0 if lo is None else lo, a)
    b = min(24 * 60 - 1 if hi is None else hi, b)
    return hhmm(a), hhmm(b)


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
    # Clamped to the surfable day, and dropped when the clamp leaves less than
    # an hour -- the same rule the low and high windows above already apply.
    # A forty-minute slot is not a recommendation anybody acts on.
    mid_w = [w for w in (hour_window(m, 90, DAY_FROM, DAY_TO) for m in mids
                         if DAY_FROM <= m <= DAY_TO)
             if mins(w[1]) - mins(w[0]) >= 60]
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


# Which way the beach looks out to sea, in compass degrees. Playa Venao sits
# on the Pacific side of the Azuero peninsula and faces roughly south, so a
# wind out of the north blows off the land and into the face of the wave --
# offshore, which grooms it. Get this number wrong and every offshore/onshore
# call below inverts, so it is a setting and not a buried constant. Confirmed
# by the owner on 3/9/2026.
BEACH_FACES = 180


# The school's own call, in their words, in three parts: how tomorrow sits
# against today, what the sea actually is, and the one thing that decides how
# it will surf. The wording of each part rotates on the date so that the same
# conditions never read identically two days running -- at Venao the swell
# barely moves, and the old single-sentence version landed on "ים דומה להיום"
# most nights until people stopped reading past it.
#
# But only the WORDING rotates. Which facts get said is decided by the
# conditions every time: a real onshore is the headline of that day and must
# never be rotated out in favour of something prettier.
#
# The owner's direction, 4/9/2026: simpler, less about the wind, more of an
# invitation to come and surf, always optimistic, always human. So these are
# short spoken sentences rather than forecast prose -- what somebody at the
# school would actually say to you across the counter. The wind still gets its
# clause whenever it decides the day, because leaving it out on the wrong day
# is a message that got somebody's morning wrong; it just says it in a word
# now rather than in a paragraph.
OPEN_LINES = {
    "he": {
        "same": ["מחר ממשיך באותו קו",
                 "עוד יום באותו אופי",
                 "הים נשאר איפה שהוא",
                 "מחר דומה להיום"],
        "up":   ["מחר הים מתעורר",
                 "עולים מדרגה",
                 "מחר נכנס עוד קצת גובה",
                 "מחר יש יותר במים"],
        "down": ["מחר הים מתיישב",
                 "מחר יותר עדין",
                 "מחר הים נח",
                 "יורדים מדרגה"],
    },
    "en": {
        "same": ["Tomorrow carries on the same",
                 "Another day of much the same",
                 "The sea stays where it is",
                 "Tomorrow looks like today"],
        "up":   ["The sea wakes up tomorrow",
                 "Stepping up a notch",
                 "A bit more size tomorrow",
                 "More in the water tomorrow"],
        "down": ["The sea settles tomorrow",
                 "Softer tomorrow",
                 "Tomorrow the sea rests",
                 "A step down"],
    },
}

# Size talks about height and who the day suits -- never about how the sea
# looks. Texture is the wind's to describe, and a "calm sea" glued to a
# fourteen-knot onshore is a sentence that contradicts itself.
SIZE_LINES = {
    "he": {
        "tiny":  ["בדיוק הגובה לשיעור ראשון",
                  "ים קטן וסלחני למתחילים",
                  "גובה נוח ללמוד בו"],
        "small": ["גובה נעים שמתאים לכולם",
                  "ים קטן וכיפי למתחילים ולמתקדמים",
                  "גובה שכיף ללמוד ולהשתפר בו"],
        "mid":   ["גובה יפה למי שכבר עם קצת ניסיון",
                  "ים עם נפח לגולשים מנוסים",
                  "יום טוב למי שיודע לקרוא גל – ניסיון בבקשה"],
        "big":   ["ים גדול ויפה לגולשים מנוסים",
                  "יום עם כוח שלא לגולשים טריים",
                  "גובה רציני שדורש היכרות עם המקום"],
    },
    "en": {
        "tiny":  ["exactly the size for a first lesson",
                  "small and forgiving for beginners",
                  "an easy size to learn in"],
        "small": ["a friendly size that suits everyone",
                  "small and fun for beginners and improvers alike",
                  "a lovely size to learn and improve in"],
        "mid":   ["a nice size once you have a little experience",
                  "a sea with volume for experienced surfers",
                  "a good day if you read the wave — experience helps"],
        "big":   ["big and beautiful for experienced surfers",
                  "a powerful day not made for fresh legs",
                  "serious size that wants local knowledge"],
    },
}

# The last clause: the single fact that decides the day. Wind gets first
# refusal whenever it is doing something, because clean offshore and a real
# onshore each change a session more than anything else on the page. Only a
# wind that barely touches the wave lets the period speak instead.
#
# These must not echo the *רוח* row three lines above them. That row already
# states what the wind IS ("3-5 knots from the north-west, offshore, clean
# and groomed"); saying "the land breeze tidies the sea up" straight after is
# the same sentence twice, mirror emoji and all, and reads like a machine that
# never looked at its own message. So this clause says what the wind MEANS for
# the session instead -- what it does to the wave, or when to be on it.
FACT_LINES = {
    "he": {
        "off_light":  ["והרוח מהיבשה תשמור על גלים נקיים",
                       "ורוח נעימה מהיבשה שעושה לגל טוב"],
        "off_strong": ["ורוח חזקה מהיבשה – שווה להיכנס לגל מוקדם",
                       "ורוח חזקה מהיבשה שמעמידה גלים תלולים ויפים"],
        "on_light":   ["ורוח קלה מהים שמשאירה קצף נחמד לתרגול",
                       "ומעט רוח מהים שמרככת את הגלים"],
        "on_strong":  ["ורוח מהים אחר הצהריים – הבוקר הוא הזמן",
                       "ורוח מהים שמתחזקת במהלך היום – כדאי להקדים"],
        "long":       ["ופריוד ארוך עם סטים חזקים ורוגע ביניהם",
                       "ופריוד ארוך שנותן זמן להתארגן בין הסטים"],
        "short":      ["ופריוד קצר עם גלים צפופים",
                       "ופריוד קצר וים קצת עצבני"],
    },
    "en": {
        "off_light":  ["and the land breeze will keep the waves clean",
                       "with a lovely breeze off the land doing the wave good"],
        "off_strong": ["and a strong offshore — worth taking off early",
                       "with a strong offshore standing the waves up beautifully"],
        "on_light":   ["with just enough sea breeze to leave foam to practise on",
                       "and a light sea breeze softening the waves"],
        "on_strong":  ["with the onshore sea breeze in the afternoon — mornings are the one",
                       "and a sea breeze building through the day — come early"],
        "long":       ["and a long period with strong sets and calm in between",
                       "with a long period leaving time to set up between sets"],
        "short":      ["and a short period with the waves stacked close",
                       "and a short period making for a fidgety sea"],
    },
}


# What counts as a wind worth calling strong, in knots, read at the MIDDLE of
# the range rather than its top edge. Eight at the top edge made "4-8 knots"
# -- a pleasant Venao morning that Surfline itself labels light -- come out as
# "strong offshore", twice in one message. Twelve on the middle is the wind
# that actually changes how a session goes.
STRONG_KT = 12


def _speed(wind_kt):
    """The middle of a wind range, or None. A range is two readings of the
    same morning, not a worst case to plan around."""
    try:
        parts = [float(x) for x in str(wind_kt).split("-")]
    except (TypeError, ValueError):
        return None
    return sum(parts) / len(parts)


def _deciding_fact(wind_kt, wind_deg, period, faces=BEACH_FACES):
    """Which single fact earns the last clause, or None when nothing does."""
    try:
        p = float(period)
    except (TypeError, ValueError):
        p = None
    side = None
    fast = _speed(wind_kt)
    try:
        off = abs(((float(wind_deg) - faces) + 180) % 360 - 180)
        side = None if fast is None else (
            "off" if off > 120 else ("on" if off < 60 else "cross"))
    except (TypeError, ValueError):
        pass
    if side == "off":
        return "off_strong" if fast >= STRONG_KT else "off_light"
    if side == "on":
        return "on_strong" if fast >= STRONG_KT else "on_light"
    # cross-shore barely touches the wave, and so does a missing wind: let the
    # period talk, but only when it is long or short enough to be worth a word
    if p is None:
        return None
    if p >= 14:
        return "long"
    if p < 10:
        return "short"
    return None


def compare_line(today, tomorrow, lang="he", date="", period=None,
                 wind_kt=None, wind_deg=None, faces=BEACH_FACES):
    """How tomorrow reads against today, what it is, and what decides it.

    Written only when both heights are known -- guessing at the sea in a
    message to two hundred customers is not on. Everything past the first
    clause is optional: with no wind and no period it still says how big
    tomorrow is and who it suits.
    """
    a, b = mid(today), mid(tomorrow)
    if a is None or b is None:
        return ""
    diff = b - a
    change = "same" if abs(diff) < 0.15 else ("up" if diff > 0 else "down")
    size = ("tiny" if b < 0.5 else "small" if b < 1.0
            else "mid" if b < 1.5 else "big")

    # The same day always rebuilds the same sentence -- a message resent after
    # a container restart must not come back reworded, or the group reads it
    # as two different forecasts.
    try:
        n = int(str(date).replace("-", "")) % 97
    except (TypeError, ValueError):
        n = 0

    op = OPEN_LINES[lang][change]
    sz = SIZE_LINES[lang][size]
    out = "%s%s%s" % (op[n % len(op)],
                      " – " if lang == "he" else " — ",
                      sz[n % len(sz)])
    key = _deciding_fact(wind_kt, wind_deg, period, faces)
    if key:
        fact = FACT_LINES[lang][key]
        out += ", " + fact[n % len(fact)]
    return out


HEB_COMPASS = ["צפון", "צפון-מזרח", "מזרח", "דרום-מזרח",
               "דרום", "דרום-מערב", "מערב", "צפון-מערב"]
EN_COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def compass(deg, lang="he"):
    i = int((float(deg) + 22.5) % 360 // 45)
    return (EN_COMPASS if lang == "en" else HEB_COMPASS)[i]


def wind_line(speed, direction, faces=BEACH_FACES, lang="he"):
    """Wind is the half of a surf forecast the school was not sending, and
    the half that decides whether a metre of swell is a clean wall or a mess.
    Offshore holds the wave up; onshore knocks it over. Speed alone says
    nothing -- fifteen knots offshore is a good day and fifteen onshore is a
    write-off -- so the two are always said together."""
    if speed in (None, "", "?"):
        return ""
    try:
        parts = [float(x) for x in str(speed).split("-")]
        lo, hi = parts[0], parts[-1]
        d = float(direction)
    except (TypeError, ValueError):
        return ""

    # the angle between where the wind comes from and where the beach looks
    off = abs(((d - faces) + 180) % 360 - 180)
    fast = (lo + hi) / 2          # the middle of the range, as in _speed above
    rng_ = ("%g" % lo) if abs(hi - lo) < 0.6 else ("%g-%g" % (lo, hi))
    if lang == "en":
        if off < 60:
            side = "onshore"
            mood = ("plenty of whitewater — great for beginners"
                    if fast < STRONG_KT
                    else "lively sea — the inside will be working")
        elif off > 120:
            side = "offshore"
            mood = ("clean and groomed 🪞" if fast < STRONG_KT
                    else "strong offshore — steep, fast faces")
        else:
            side = "cross-shore"
            mood = "barely touches the wave"
        return "*Wind* - %s kt from %s (%s) — %s" % (
            rng_, compass(d, "en"), side, mood)

    if off < 60:
        side, how = "אונשור", "מהים"
    elif off > 120:
        side, how = "אופשור", "מהיבשה"
    else:
        side, how = "רוח צד", ""

    if side == "אופשור":
        mood = ("ים חלק ומסודר 🪞" if fast < STRONG_KT
                else "אופשור חזקה – גלים תלולים ומהירים")
    elif side == "אונשור":
        mood = ("הרבה גלי קצף – מעולה למתחילים" if fast < STRONG_KT
                else "ים תוסס – הפנים יעבוד יפה")
    else:
        mood = "כמעט לא נוגעת בגל"

    rng = ("%g" % lo) if abs(hi - lo) < 0.6 else ("%g-%g" % (lo, hi))
    return "*רוח* - %s קשר מ%s (%s%s) – %s" % (
        rng, compass(d), side, (" " + how) if how else "", mood)


def tide_range_note(t, lang="he"):
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
    if lang == "en":
        if rng >= 3.2:
            return ("*⚠️ Big tidal range today (%.1f m) — stronger current, "
                    "especially around mid tide. Stay in front of the crew.*"
                    % rng), rng
        if rng <= 2.3:
            return ("*Small tidal range today (%.1f m) — easy sea, weak "
                    "current.*" % rng), rng
        return "", rng
    if rng >= 3.2:
        return ("*⚠️ הפרשי גאות גדולים היום (%.1f מטר) – זרם חזק יותר, "
                "במיוחד סביב אמצע הגאות. להישאר מול הצוות.*" % rng), rng
    if rng <= 2.3:
        return ("*הפרשי גאות קטנים היום (%.1f מטר) – ים נוח וזרם חלש.*"
                % rng), rng
    return "", rng


def _build_en(d, highs, lows, waves, feet, period, compare, spot_note,
              note, wind, low_w, high_w, mid_w):
    """The same message for the English-speaking group.

    Same numbers, same windows, same order -- translated, not re-invented, so
    that two groups reading side by side never see two different forecasts.
    """
    L = []
    L.append("*Good evening everyone🌞*")
    L.append("")
    L.append("🏄‍♀️Surf forecast for %d/%d🏄‍♂️" % (d.day, d.month))
    L.append("")
    L.append("*High tide* - " + highs)
    L.append("*Low tide* - " + lows)
    L.append("")
    L.append("*Wave height* - %s m%s" % (waves, feet))
    L.append("*Period* - %s seconds" % period)
    if wind:
        L.append(wind)
    L.append("")
    if compare:
        L.append("*🌞🏄‍♀️🎉 %s 😎🏄‍♂️🌊*" % compare)
        L.append("")

    L.append("*Best hours for experienced surfers*")
    L.append("")
    for w in mid_w:
        L.append(span(w))
    L.append("")
    if low_w:
        L.append("*Around low tide (%s) the wave is faster, hollower and "
                 "shallower – shortboards and performance.*"
                 % ", ".join(span(w) for w in low_w))
    if high_w:
        L.append("*Around mid and high tide (%s) the wave is softer and more "
                 "forgiving – more volume.*"
                 % ", ".join(span(w) for w in high_w))
    L.append("")
    L.append("*Best hours for beginners*")
    L.append("")
    for w in mid_w:
        L.append(span(w))
    L.append("")
    L.append("*🏄‍♀️%s🏄‍♂️*" % spot_note)
    L.append("")
    L.append("*Near high tide: soft and slow.*")
    L.append("*Near low tide: hollow and fast – good for whitewater.*")
    L.append("")
    L.append("*SUP paddling*")
    L.append("Around the tide peaks")
    L.append("")
    if note:
        L.append(note)
        L.append("")
    L.append("Have a good one out there! 🤙🌊")
    return "\n".join(L)


def build(date, waves, period, compare, spot_note, note="", wind="",
          lang="he"):
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
        unit = "ft" if lang == "en" else "פיט"
        if abs(a - b) < 0.05:
            shown = ("%.1f" % a)
            feet = " (%d %s)" % (fa, unit)
        else:
            feet = (" (%d-%d %s)" % (fa, fb, unit) if fa != fb
                    else " (%d %s)" % (fa, unit))
    except Exception:
        pass
    waves = shown

    if lang == "en":
        return _build_en(d, highs, lows, waves, feet, period, compare,
                         spot_note, note, wind, low_w, high_w, mid_w), None

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
    if wind:
        L.append(wind)
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
    ap.add_argument("--wind", default="",
                    help="wind speed in knots over the surfable hours, e.g. 2-5")
    ap.add_argument("--wind-dir", default="",
                    help="the direction it blows FROM, in degrees")
    ap.add_argument("--faces", type=int, default=BEACH_FACES,
                    help="which way the beach looks out to sea, in degrees "
                         "(180 = south). Getting this wrong inverts every "
                         "offshore/onshore call.")
    ap.add_argument("--tide-note", action="store_true",
                    help="add a line when the tide range is unusually big or "
                         "small — worked out from the table, not forecast")
    ap.add_argument("--lang", choices=("he", "en"), default="he",
                    help="he for the Hebrew group, en for the English one — "
                         "same numbers, same windows, translated")
    ap.add_argument("--spot", default="")
    a = ap.parse_args()
    if not a.spot:
        a.spot = ("The left side of the beach in front of Selina is lower "
                  "and easier to practise on" if a.lang == "en" else
                  "צד שמאל של החוף מול סלינה נמוך ונוח יותר לתרגול")

    date = a.date
    if not date:
        # Panama is UTC-5 all year; tomorrow there, not tomorrow here
        now = dt.datetime.utcnow() - dt.timedelta(hours=5)
        date = (now.date() + dt.timedelta(days=1)).isoformat()

    # The wind and the period go in too: they decide how a given height will
    # actually surf, and the line used to be written without ever seeing them.
    compare = a.compare or compare_line(
        a.waves_today, a.waves, a.lang, date=date, period=a.period,
        wind_kt=a.wind or None, wind_deg=a.wind_dir or None, faces=a.faces)

    note = ""
    if a.tide_note:
        t = tides_for(date)
        if t:
            note, _rng = tide_range_note(t, a.lang)

    wind = (wind_line(a.wind, a.wind_dir, a.faces, a.lang)
            if a.wind and a.wind_dir else "")
    msg, err = build(date, a.waves, a.period, compare, a.spot, note,
                     wind, a.lang)
    if err:
        print("error: " + err, file=sys.stderr)
        return 1
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
