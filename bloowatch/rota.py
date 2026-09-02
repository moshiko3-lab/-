#!/usr/bin/env python3
"""Tomorrow's teaching, per instructor and for the staff group.

    python3 rota.py                     # tomorrow, everything, printed
    python3 rota.py --date 2026-09-02
    python3 rota.py --who NAFTUL        # just one person's message
    python3 rota.py --group             # just the staff group's message

**This never sends anything.** It prints. Sending is a separate, deliberate
act through TimelinesAI, because a rota that goes out wrong reaches twelve
people at once and cannot be taken back.

Two things in the day are not lessons and are dropped: the all-day
"SHOKOGI - STAFF" placeholders, and anything assigned to one of the divider
records the board uses as section headings (INSTRUCTORS - FULL, - FREELANCE,
- ASSISTANTS, PHOTOGRAPHERS). They are furniture, not work, and a message
telling somebody they teach "SHOKOGI - STAFF at 06:00" would be read once and
then ignored for ever after.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

from daily_report import BloowatchError, login
from export_dataset import _get, _rows
from forecast_message import tides_for

SCHOOL = 127
PANAMA = dt.timezone(dt.timedelta(hours=-5))

# the board's section headings, which are staff records with no person behind
# them. Anything assigned to one of these is a placeholder.
NOT_PEOPLE = ("INSTRUCTORS -", "PHOTOGRAPHERS", "SHOKOGI - STAFF")

HEB_DOW = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
EN_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
          "Saturday", "Sunday"]


def tomorrow():
    return (dt.datetime.now(PANAMA).date() + dt.timedelta(days=1)).isoformat()


def student_names(attendants):
    """Who is actually coming, in words an instructor can use on the beach.

    Bloowatch numbers the people on an order -- "P1 mica m", "P2 ibai a" --
    so the prefix is stripped: the instructor needs the name, not its index.

    A group booked under one name arrives as twelve of it ("P1 young guns sep
    26" through "P14"), so identical names collapse to one. Twelve repeats of
    the same words is not twelve pieces of information, and a message that
    long stops being read.
    """
    out = []
    for a in attendants or []:
        nm = " ".join(((a.get("first_name") or "") + " " +
                       (a.get("last_name") or "")).split())
        nm = re.sub(r"^P\d+\s+", "", nm).strip().title()
        if nm and nm not in out:
            out.append(nm)
    return out


def _is_placeholder(name):
    up = (name or "").upper()
    return any(up.startswith(p) or p in up for p in NOT_PEOPLE)


def _end(raw, duration):
    """When it finishes, worked out from Bloowatch's duration field.

    A lesson is an hour and everyone knows it, so its start time says
    everything. A shop shift is not: on the board it is a bar running from
    nine to seven, and a rota that prints only "09:00" for it tells the
    person on it almost nothing. So the end time is kept only for the
    things that last longer than an hour.
    """
    try:
        start = dt.datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S")
        h, m, s = (int(p) for p in str(duration).split(":"))
    except (ValueError, TypeError, AttributeError):
        return ""
    if (h, m) <= (1, 0):
        return ""
    return (start + dt.timedelta(hours=h, minutes=m,
                                 seconds=s)).strftime("%H:%M")


def lessons_for(session, base, date, sid=SCHOOL):
    """The day's actual teaching, earliest first."""
    rows = _rows(_get(session, base, f"/schools/{sid}/sessions/", date=date,
                      offset=0, limit=200, ordering="starting_time"))
    cats = {c["id"]: c.get("name") for c in
            _rows(_get(session, base, f"/schools/{sid}/categories/",
                       show_archived="false"))}
    out = []
    for x in rows:
        if x.get("all_day_event"):
            continue
        cat = cats.get(x.get("category")) or ""
        title = (x.get("name") or cat or "").strip()
        if _is_placeholder(cat) or _is_placeholder(title):
            continue
        crew = []
        for a in (x.get("assigned") or []):
            nm = " ".join(y for y in (a.get("first_name"), a.get("last_name"))
                          if y).strip()
            if nm and not _is_placeholder(nm):
                crew.append(nm)
        if not crew:
            continue
        raw = (x.get("starting_time") or "")[:25].strip()
        try:
            when = dt.datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S").strftime("%H:%M")
        except ValueError:
            continue
        out.append({"id": x.get("id"),
                    "time": when, "until": _end(raw, x.get("duration")),
                    "title": title, "category": cat,
                    "students": len(x.get("attendants") or []),
                    "names": student_names(x.get("attendants")),
                    "capacity": x.get("max_attendants") or 0,
                    "staff": crew})
    out.sort(key=lambda r: (r["time"], r["title"]))
    return out


def by_person(lessons):
    who = {}
    for l in lessons:
        for name in l["staff"]:
            who.setdefault(name, []).append(l)
    return who


def _students(n, lang):
    """Nobody booked is said by saying nothing.

    A shop shift has no students by design, and "0 students" on it reads like
    a fault. An empty lesson is better shown by the absence of a number than
    by a zero somebody has to interpret at eleven at night.
    """
    if not n:
        return ""
    if lang == "en":
        return "1 student" if n == 1 else "%d students" % n
    if n == 1:
        return "תלמיד אחד"
    return "%d תלמידים" % n


MANY = 4


def _who(l, lang):
    """The students by name, while naming them still tells you something.

    One name is the whole point of the message: an instructor walking down to
    the beach wants to know who they are meeting. Four is still a class you
    can picture. Past that it is a list, and a list of strangers' names is
    worse than the number -- so above four the count carries it alone.
    """
    names = l.get("names") or []
    if not names or len(names) > MANY:
        return ""
    return ", ".join(names)


def _when(l):
    """The hours the thing occupies: a span when it has one, else the start."""
    return "%s-%s" % (l["time"], l["until"]) if l.get("until") else l["time"]


# What the school calls an ordinary surf lesson on its own price list. It is
# the right name for a product and no information at all on a rota: almost
# everything on the board is one, so printing it on every line is a word
# everybody has to read past to reach the part that differs.
GENERIC = ("SURF PACK", "SURF LESSON")


def short(title):
    """A booking's name with the filing and the boilerplate left off it.

    Bloowatch names a private course after the year and the customer --
    "CLASS 2024 - jim van weperen" -- which is the right name for a record
    and nothing anybody needs on a rota: the people turning up are named
    beside it, and their names are what the instructor is looking for. The
    plain surf lesson is named after the product, which says even less. Both
    drop out, and the booking is known by who is coming to it.
    """
    t = " ".join((title or "").split())
    if t.upper() in GENERIC:
        return ""
    if re.match(r"^(CLASS|COURSE)\b[\s\-–]*\d{2,4}\b", t, re.I):
        return ""
    return t


def _line(l, lang, sep=" · "):
    """Naming the students already says how many there are.

    "SURF PACK · תלמיד אחד · Mica M" spends three words to say what "Mica M"
    says in one, and the Hebrew island in the middle of a Latin line is what
    makes the message wrap badly on a phone. The count is what is left when
    the names are too many to print, and the product name is what is left
    when there is nobody to name.
    """
    bits = [short(l["title"]), _who(l, lang) or _students(l["students"], lang)]
    out = sep.join(x for x in bits if x)
    return out or l["title"]


DAY_START, DAY_END = 5 * 60, 20 * 60


def tide_lines(date, lang="he"):
    """The day's tide, for the people who have to teach in it.

    Only the peaks somebody could actually be standing in the water for: a
    low at half past midnight is a real low and no use to anybody reading a
    rota, and printing it just makes the two that matter harder to find.
    """
    t = tides_for(date)
    if not t:
        return []

    def peaks(key):
        out = []
        for p in t.get(key) or []:
            h, m = p["t"].split(":")
            if DAY_START <= int(h) * 60 + int(m) <= DAY_END:
                out.append("%s (%.1f %s)" % (p["t"], float(p["m"]),
                                             "m" if lang == "en" else "מ׳"))
        return out

    high, low = peaks("highs"), peaks("lows")
    if not high and not low:
        return []
    words = (("High tide", "Low tide") if lang == "en"
             else ("גאות", "שפל"))
    out = []
    if high:
        out.append("🌊 *%s* %s" % (words[0], " · ".join(high)))
    if low:
        out.append("🏖 *%s* %s" % (words[1], " · ".join(low)))
    return out


# WhatsApp picks a line's direction from its first strong letter. Ours start
# with a digit, which is neither, so the whole bubble inherits the Hebrew of
# the heading and every line flips: "09:00-19:00 SHOP PLAYA — Moshiko" comes
# out with the hour stranded on the far side of the name. A left-to-right
# mark at the head of each line pins the line the way it is written, and the
# Hebrew words inside it still lay themselves out right-to-left.
LTR = "\u200e"


def ltr(lines):
    return "\n".join((LTR + x) if x else x for x in lines)


def _heading(date, lang):
    d = dt.date.fromisoformat(date)
    if lang == "en":
        return "%s %d/%d" % (EN_DOW[d.weekday()], d.day, d.month)
    return "יום %s %d/%d" % (HEB_DOW[d.weekday()], d.day, d.month)


def _enjoy(first, lang, who=None):
    """Enjoy it -- addressed properly, or not addressed at all.

    Hebrew has to choose, and half this crew have names that do not say.
    Somebody not on file is wished a good day off, which is right either way.
    """
    if lang == "en":
        return "Enjoy it 🤙"
    who = genders() if who is None else who
    return {"m": "תהנה 🤙", "f": "תהני 🤙"}.get(who.get(first), "חופש נעים 🤙")


def personal(name, lessons, date, lang="he", off=False, who=None):
    """One instructor's own day. Written so it can be read at a glance in bed.

    Somebody with nothing tomorrow is told so plainly rather than left to
    wonder whether the message failed to arrive -- and a day the planner
    has actually marked off is said as such, because "no lessons" and "your
    day off" are not the same news.
    """
    first = (name or "").split()[0].title()
    when = _heading(date, lang)
    if not lessons:
        if off:
            if lang == "en":
                return ltr(["Hey %s 👋" % first, "",
                            "*Your day off: %s* 🌴" % when, "",
                            _enjoy(first, lang, who)])
            return ltr(["היי %s 👋" % first, "",
                        "*יום החופש שלך: %s* 🌴" % when, "",
                        _enjoy(first, lang, who)])
        if lang == "en":
            return ltr(["Hey %s 👋" % first, "",
                        "Nothing on your schedule for %s." % when, "",
                        _enjoy(first, lang, who)])
        return ltr(["היי %s 👋" % first, "",
                    "אין לך שיעורים ב%s." % when, "",
                    _enjoy(first, lang, who)])

    L = []
    if lang == "en":
        L.append("Hey %s 👋" % first)
        L.append("")
        L.append("*Your schedule for %s:*" % when)
    else:
        L.append("היי %s 👋" % first)
        L.append("")
        L.append("*הלו״ז שלך ל%s:*" % when)
    L.append("")
    for l in lessons:
        L.append("*%s* · %s" % (_when(l), _line(l, lang)))
    tide = tide_lines(date, lang)
    if tide:
        L.append("")
        L.extend(tide)
    L.append("")
    L.append("Have a good one 🤙" if lang == "en" else "בהצלחה 🤙")
    return ltr(L)


def starting_between(lessons, lo, hi, now=None):
    """Lessons starting between lo and hi minutes from now.

    The window matters more than it looks. A reminder that fires on an
    overlapping window sends the same lesson twice, and one that fires on a
    window with a gap in it silently skips a lesson nobody then turns up to.
    So the caller steps the window by exactly its own width: (45, 105] every
    hour covers every minute of the day once and only once.
    """
    now = now or dt.datetime.now(PANAMA)
    out = []
    for l in lessons:
        h, m = l["time"].split(":")
        start = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        ahead = (start - now).total_seconds() / 60.0
        if lo < ahead <= hi:
            out.append(l)
    return out


def remind(name, lessons, lang="he"):
    """The nudge an hour or so before. Says the hour, never "in an hour".

    The window it fires in is wider than the words "in an hour" would be, and
    an instructor who reads "in an hour" at 08:15 for a nine o'clock lesson
    stops trusting the next one. The time itself is always true.
    """
    if not lessons:
        return ""
    first = (name or "").split()[0].title()
    L = []
    if lang == "en":
        L.append("Hey %s 👋" % first)
        L.append("")
        L.append("*A reminder for your lesson, please be there on time* 🤙")
    else:
        L.append("היי %s 👋" % first)
        L.append("")
        L.append("*תזכורת לשיעור שלך, להגיע בזמן ולא לאחר* 🤙")
    L.append("")
    for l in lessons:
        L.append("*%s* · %s" % (l["time"], _line(l, lang)))
    return ltr(L)


def changes(before, after):
    """What moved between the rota that was sent and the rota as it stands.

    Keyed on the session's own id, so a lesson that shifts an hour is one
    change and not a cancellation plus a new booking -- an instructor reading
    "cancelled 09:00, added 10:00" has to work out for themselves that it is
    the same lesson, and at eleven at night they will get it wrong.

    Only what somebody would act on: a lesson appearing or disappearing from
    their day, moving, or being taken off them. A student joining a group of
    twelve is not worth waking anybody for.
    """
    was = {l["id"]: l for l in before if l.get("id") is not None}
    now = {l["id"]: l for l in after if l.get("id") is not None}
    out = []
    for sid, l in now.items():
        old = was.get(sid)
        if not old:
            out.append({"kind": "added", "lesson": l, "staff": set(l["staff"])})
            continue
        # A shift that now finishes at a different hour has moved as surely as
        # one that starts at a different hour. Older snapshots were written
        # before end times were kept, and comparing against a key they never
        # had would report the whole day as changed.
        moved = old["time"] != l["time"] or (
            "until" in old and old["until"] != l.get("until"))
        gained = set(l["staff"]) - set(old["staff"])
        lost = set(old["staff"]) - set(l["staff"])
        if moved:
            out.append({"kind": "moved", "lesson": l, "from": _when(old),
                        "staff": set(l["staff"]) | set(old["staff"])})
        if gained:
            out.append({"kind": "added", "lesson": l, "staff": gained})
        if lost:
            out.append({"kind": "off", "lesson": l, "staff": lost})
    for sid, old in was.items():
        if sid not in now:
            out.append({"kind": "cancelled", "lesson": old,
                        "staff": set(old["staff"])})
    return out


def change_lines(chg, lang="he", named=False):
    """Each change as one line somebody can act on.

    `named` is for the staff group, where "no longer yours" means nothing
    without a name attached -- the group needs to see the handover, while the
    person themselves already knows who they are.

    A move is written as the new time with the old one after it. An arrow
    between two times reads backwards in a right-to-left message, and a
    reader who takes it the wrong way turns up at the wrong hour.
    """
    out = []
    for c in chg:
        l = c["lesson"]
        what = _line(l, lang)
        who = ", ".join(sorted(n.split()[0].title() for n in c["staff"]))
        tail = (" — %s" % who) if named and who else ""
        if lang == "en":
            if c["kind"] == "added":
                out.append("➕ *%s* · %s%s" % (_when(l), what, tail))
            elif c["kind"] == "cancelled":
                out.append("❌ *%s* · %s — cancelled%s"
                           % (_when(l), what, (" (%s)" % who) if named else ""))
            elif c["kind"] == "moved":
                out.append("🕒 *%s* (was %s) · %s%s"
                           % (_when(l), c["from"], what, tail))
            else:
                out.append("➖ *%s* · %s — %s" % (
                    _when(l), what, ("off %s" % who) if named
                    else "no longer yours"))
        else:
            if c["kind"] == "added":
                out.append("➕ *%s* · %s%s" % (_when(l), what, tail))
            elif c["kind"] == "cancelled":
                out.append("❌ *%s* · %s — בוטל%s"
                           % (_when(l), what, (" (%s)" % who) if named else ""))
            elif c["kind"] == "moved":
                out.append("🕒 *%s* (היה %s) · %s%s"
                           % (_when(l), c["from"], what, tail))
            else:
                # the crew's names are in Latin letters, so the Hebrew prefix
                # needs the hyphen it would take before any foreign word
                out.append("➖ *%s* · %s — %s" % (
                    _when(l), what, ("ירד מ-%s" % who) if named
                    else "כבר לא אצלך"))
    return out


def update_group(chg, date, lang="he"):
    if not chg:
        return ""
    when = _heading(date, lang)
    head = ("*Schedule update for %s*" % when if lang == "en"
            else "*עדכון בלו״ז ל%s*" % when)
    return "\n".join([head, ""] + change_lines(chg, lang, named=True))


def update_personal(name, chg, date, lang="he"):
    """Only the changes that touch this person."""
    mine = [c for c in chg if name in c["staff"]]
    if not mine:
        return ""
    first = (name or "").split()[0].title()
    when = _heading(date, lang)
    if lang == "en":
        head = ["Hey %s 👋" % first, "",
                "*Your schedule for %s has changed:*" % when, ""]
        tail = ["", "Sorry for the late change 🤙"]
    else:
        head = ["היי %s 👋" % first, "",
                "*חל שינוי בלו״ז שלך ל%s:*" % when, ""]
        tail = ["", "מצטערים על השינוי המאוחר 🤙"]
    return "\n".join(head + change_lines(mine, lang) + tail)


def first_names_off(crew):
    """The first names the planner has marked away, as a set to test against."""
    return set(off_today(crew))


def off_today(crew):
    """Whoever the planner has marked away, first names only."""
    out = []
    for r in crew or []:
        if not r.get("off"):
            continue
        name = " ".join((r.get("name") or "").split())
        if name and not name.upper().startswith(("INSTRUCTORS", "PHOTOGRAPH",
                                                 "GUIDES", "UNASSIGN")):
            out.append(name.split()[0].title())
    return out


CREW_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "app", "crew.json")


def genders(path=CREW_FILE):
    """Who is a he and who is a she, by first name, from the crew file.

    Hebrew cannot address somebody without knowing, and half the crew have
    names that do not say -- Eden, Yuval, Shaked, Paz all go either way. So
    it is written down rather than guessed, and anyone missing from the file
    gets a form of words that needs no answer.
    """
    try:
        rows = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for r in rows if isinstance(rows, list) else []:
        g = str(r.get("gender") or "").strip().lower()[:1]
        name = " ".join(str(r.get("name") or "").split())
        if g in ("m", "f") and name:
            out[name.split()[0].title()] = g
    return out


def off_lines(names, lang="he", who=None):
    """A word for the people who are off, by name.

    Worth the two lines: the rota is read by the whole crew, and being
    named in it on your day off is the difference between a list and a
    message from the school.

    Someone whose gender is not on file is wished a good day off rather than
    told to enjoy it, which is the one phrasing that fits either way. That is
    deliberate: getting it wrong in front of the whole crew is worse than
    saying something slightly plainer.
    """
    if not names:
        return []
    if lang == "en":
        return ["🌴 *%s* — enjoy your day off 🤙" % n for n in names]
    who = genders() if who is None else who
    out = []
    for n in names:
        g = who.get(n)
        word = {"m": "תהנה ביום חופש",
                "f": "תהני ביום חופש"}.get(g, "חופש נעים")
        out.append("🌴 *%s* — %s 🤙" % (n, word))
    return out


def group(lessons, date, lang="he", crew=None):
    """The whole day for the staff group, in the order it happens."""
    when = _heading(date, lang)
    if not lessons:
        return ltr(["*Schedule %s*" % when, "", "Nothing booked yet."]
                   if lang == "en" else
                   ["*לו״ז %s*" % when, "", "אין עדיין שיעורים."])
    L = ["*Schedule %s*" % when if lang == "en" else "*לו״ז %s*" % when, ""]
    last = None
    for l in lessons:
        if last and l["time"] != last:
            L.append("")
        last = l["time"]
        who = ", ".join(n.split()[0].title() for n in l["staff"])
        inner = _who(l, lang) or _students(l["students"], lang)
        what = short(l["title"])
        if not what:
            what, inner = inner or l["title"], ""
        L.append("*%s* %s%s — %s" % (_when(l), what,
                                     (" (%s)" % inner) if inner else "", who))
    # the sign-off comes before the day-off lines and after the work: the
    # message is sent at seven in the evening, so it is closing today as
    # much as it is opening tomorrow
    L.append("")
    L.append("Thank you all for today, see you tomorrow 🫶" if lang == "en"
             else "תודה רבה לכולם על היום, נפגש מחר 🫶")

    off = off_lines(off_today(crew), lang)
    if off:
        L.append("")
        L.extend(off)
    tide = tide_lines(date, lang)
    if tide:
        L.append("")
        L.extend(tide)
    return ltr(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--lang", choices=("he", "en"), default="he")
    ap.add_argument("--who", default="", help="only this person's message")
    ap.add_argument("--group", action="store_true",
                    help="only the staff group's message")
    ap.add_argument("--crew", default="",
                    help="JSON from `shot.py --crew`. Only the planner knows "
                         "who is away, so without this the rota cannot name "
                         "them and simply leaves the line out.")
    ap.add_argument("--snapshot", default="",
                    help="write tomorrow's rota to this file, so a later run "
                         "can tell what changed since it was sent")
    ap.add_argument("--diff", default="",
                    help="compare against a snapshot and print only what "
                         "changed, for the group and per instructor")
    ap.add_argument("--remind", action="store_true",
                    help="today's reminders: whoever has a lesson starting "
                         "inside the window. Prints nothing when nobody does.")
    ap.add_argument("--from", dest="lo", type=int, default=45,
                    help="window starts this many minutes ahead (default 45)")
    ap.add_argument("--to", dest="hi", type=int, default=105,
                    help="and ends this many (default 105). Step the window "
                         "by its own width or a lesson is reminded twice, or "
                         "not at all.")
    a = ap.parse_args()
    date = a.date or (dt.datetime.now(PANAMA).date().isoformat() if a.remind
                      else tomorrow())
    try:
        s, base = login()
        lessons = lessons_for(s, base, date)
    except BloowatchError as e:
        print("error: " + str(e), file=sys.stderr)
        return 1

    if a.snapshot:
        with open(a.snapshot, "w", encoding="utf-8") as f:
            json.dump({"date": date, "lessons": lessons}, f, ensure_ascii=False)
        print("saved %d lessons for %s to %s" % (len(lessons), date, a.snapshot))
        return 0

    if a.diff:
        if not os.path.exists(a.diff):
            # No baseline means no way to know what changed. Saying nothing is
            # right: a "here is the whole rota again" message at eight at night
            # reads as a fault, and guessing at changes is worse.
            print("no snapshot at %s — nothing to compare against" % a.diff)
            return 0
        with open(a.diff, encoding="utf-8") as f:
            snap = json.load(f)
        if snap.get("date") != date:
            print("snapshot is for %s, not %s — nothing to compare"
                  % (snap.get("date"), date))
            return 0
        chg = changes(snap.get("lessons") or [], lessons)
        if not chg:
            print("nothing changed since the rota was sent")
            return 0
        print("======== GROUP ========")
        print(update_group(chg, date, a.lang))
        for name in sorted({n for c in chg for n in c["staff"]}):
            msg = update_personal(name, chg, date, a.lang)
            if msg:
                print("\n======== %s ========" % name)
                print(msg)
        return 0

    if a.remind:
        soon = starting_between(lessons, a.lo, a.hi)
        if not soon:
            print("nothing starting between %d and %d minutes from now"
                  % (a.lo, a.hi))
            return 0
        for name, mine in sorted(by_person(soon).items()):
            print("======== %s ========" % name)
            print(remind(name, mine, a.lang))
            print()
        return 0

    crew = json.load(open(a.crew, encoding="utf-8")) if a.crew else None

    if a.who:
        want = a.who.strip().upper()
        mine = [l for l in lessons if any(n.upper().startswith(want)
                                          for n in l["staff"])]
        off = first_names_off(crew)
        print(personal(a.who, mine, date, a.lang,
                       off=a.who.split()[0].title() in off))
        return 0
    if a.group:
        print(group(lessons, date, a.lang, crew))
        return 0

    print("======== staff group ========")
    print(group(lessons, date, a.lang, crew))
    for name, mine in sorted(by_person(lessons).items()):
        print("\n======== %s ========" % name)
        print(personal(name, mine, date, a.lang))
    return 0


if __name__ == "__main__":
    sys.exit(main())
