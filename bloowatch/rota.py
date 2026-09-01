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
import sys

from daily_report import BloowatchError, login
from export_dataset import _get, _rows

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


def _is_placeholder(name):
    up = (name or "").upper()
    return any(up.startswith(p) or p in up for p in NOT_PEOPLE)


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
        out.append({"time": when, "title": title, "category": cat,
                    "students": len(x.get("attendants") or []),
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


def _line(l, lang, sep=" · "):
    bits = [l["title"], _students(l["students"], lang)]
    return sep.join(x for x in bits if x)


def _heading(date, lang):
    d = dt.date.fromisoformat(date)
    if lang == "en":
        return "%s %d/%d" % (EN_DOW[d.weekday()], d.day, d.month)
    return "יום %s %d/%d" % (HEB_DOW[d.weekday()], d.day, d.month)


def personal(name, lessons, date, lang="he"):
    """One instructor's own day. Written so it can be read at a glance in bed.

    Somebody with nothing tomorrow is told so plainly rather than left to
    wonder whether the message failed to arrive.
    """
    first = (name or "").split()[0].title()
    when = _heading(date, lang)
    if not lessons:
        if lang == "en":
            return ("Hey %s 👋\n\nNothing on your schedule for %s.\n\n"
                    "Enjoy the day off 🤙" % (first, when))
        return ("היי %s 👋\n\nאין לך שיעורים ב%s.\n\nתיהנה מהיום החופשי 🤙"
                % (first, when))

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
        L.append("*%s* · %s" % (l["time"], _line(l, lang)))
    L.append("")
    L.append("Have a good one 🤙" if lang == "en" else "בהצלחה 🤙")
    return "\n".join(L)


def group(lessons, date, lang="he"):
    """The whole day for the staff group, in the order it happens."""
    when = _heading(date, lang)
    if not lessons:
        return ("*Schedule %s*\n\nNothing booked yet." % when if lang == "en"
                else "*לו״ז %s*\n\nאין עדיין שיעורים." % when)
    L = ["*Schedule %s*" % when if lang == "en" else "*לו״ז %s*" % when, ""]
    last = None
    for l in lessons:
        if last and l["time"] != last:
            L.append("")
        last = l["time"]
        who = ", ".join(n.split()[0].title() for n in l["staff"])
        n = _students(l["students"], lang)
        L.append("*%s* %s%s — %s" % (l["time"], l["title"],
                                     (" (%s)" % n) if n else "", who))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--lang", choices=("he", "en"), default="he")
    ap.add_argument("--who", default="", help="only this person's message")
    ap.add_argument("--group", action="store_true",
                    help="only the staff group's message")
    a = ap.parse_args()
    date = a.date or tomorrow()
    try:
        s, base = login()
        lessons = lessons_for(s, base, date)
    except BloowatchError as e:
        print("error: " + str(e), file=sys.stderr)
        return 1

    if a.who:
        want = a.who.strip().upper()
        mine = [l for l in lessons if any(n.upper().startswith(want)
                                          for n in l["staff"])]
        print(personal(a.who, mine, date, a.lang))
        return 0
    if a.group:
        print(group(lessons, date, a.lang))
        return 0

    print("======== staff group ========")
    print(group(lessons, date, a.lang))
    for name, mine in sorted(by_person(lessons).items()):
        print("\n======== %s ========" % name)
        print(personal(name, mine, date, a.lang))
    return 0


if __name__ == "__main__":
    sys.exit(main())
