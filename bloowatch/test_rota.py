#!/usr/bin/env python3
"""The rota that goes out to twelve people at once.

A forecast that is wrong is embarrassing. A rota that is wrong sends an
instructor to the beach at the wrong hour, or leaves a lesson with nobody on
it, and it reaches everybody at the same moment with no way to call it back.
So the parts that decide what each person is told are pinned here.

Three of them matter most. The board's section headings are staff records
with no person behind them, and an "INSTRUCTORS - FREELANCE" who teaches
"SHOKOGI - STAFF" every day at six in the morning would make the whole
message ignorable within a week. Somebody with a free day has to be told
that in words, because silence is indistinguishable from a message that
never arrived. And a shop shift has no students by design, so writing "0
students" on it reads as a fault rather than as a fact.

Nothing here touches the network, and nothing anywhere in rota.py sends.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import rota                                                       # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def L(time, title, students, staff, cat="SURF PACK"):
    return {"time": time, "title": title, "category": cat,
            "students": students, "capacity": 12, "staff": staff}


DAY = [
    L("08:00", "SURF PACK", 1, ["NAFTUL"]),
    L("09:00", "SURF PACK", 1, ["NAFTUL"]),
    L("09:00", "CLASS 2024 - mica mizrahi", 1, ["VLADI"]),
    L("13:00", "SHOP PLAYA", 0, ["ELLA"], "SHOP PLAYA"),
    L("15:00", "SURF PACK", 12, ["NAFTUL", "VLADI", "ELLA"]),
]


def main():
    # --- what is not a lesson ----------------------------------------------
    for junk in ("INSTRUCTORS - FULL", "INSTRUCTORS - FREELANCE",
                 "INSTRUCTORS - ASSISTANTS", "PHOTOGRAPHERS",
                 "SHOKOGI - STAFF"):
        check("%r is furniture, not a person" % junk, rota._is_placeholder(junk))
    check("a real instructor is not", not rota._is_placeholder("NAFTUL"))
    check("nor is a full name", not rota._is_placeholder("MOSHIKO LEVY"))
    check("it does not depend on how the record was typed",
          rota._is_placeholder("instructors - full"))
    # a nameless assignment is a gap in the record, not a section heading;
    # lessons_for drops those on the name being empty, before asking this
    check("an empty name is not called a heading", not rota._is_placeholder(""))

    # --- who teaches what ---------------------------------------------------
    who = rota.by_person(DAY)
    check("everybody teaching appears once",
          sorted(who) == ["ELLA", "NAFTUL", "VLADI"], str(sorted(who)))
    check("a lesson with three on it is in all three lists",
          all(any(l["time"] == "15:00" for l in who[n]) for n in who),
          str({k: [l["time"] for l in v] for k, v in who.items()}))
    check("and somebody's own hours are only their own",
          [l["time"] for l in who["NAFTUL"]] == ["08:00", "09:00", "15:00"],
          str([l["time"] for l in who["NAFTUL"]]))

    # --- one person's message -----------------------------------------------
    m = rota.personal("NAFTUL", who["NAFTUL"], "2026-09-01")
    check("it opens with their first name, not their file name",
          m.startswith("היי Naftul"), m.split("\n")[0])
    check("it names the day", "יום שלישי 1/9" in m, m[:80])
    check("every hour they teach is in it",
          all(t in m for t in ("08:00", "09:00", "15:00")), m)
    check("and no hour they do not",
          "13:00" not in m, m)
    check("a full session says how many are coming", "12 תלמידים" in m, m)
    check("and a single student is not '1 students'",
          "תלמיד אחד" in m and "1 תלמידים" not in m, m)

    # --- a day off is said out loud -----------------------------------------
    off = rota.personal("SHAKED", [], "2026-09-01")
    check("somebody with nothing on is told so",
          "אין לך שיעורים" in off, off)
    check("rather than being sent an empty list",
          "*" not in off.replace("*הלו״ז", ""), off)
    off_en = rota.personal("VICTOR", [], "2026-09-01", "en")
    check("in English too", "Nothing on your schedule" in off_en, off_en)

    # --- a shift with nobody booked -----------------------------------------
    shop = rota.personal("ELLA", who["ELLA"], "2026-09-01")
    check("a shop shift carries no student count",
          "0 תלמידים" not in shop and "13:00" in shop, shop)
    check("but the shift itself is still listed",
          "SHOP PLAYA" in shop, shop)

    # --- the group's copy ---------------------------------------------------
    g = rota.group(DAY, "2026-09-01")
    check("the group message is the whole day", g.count("*0") + g.count("*1") >= 5, g)
    check("in the order it happens",
          g.index("08:00") < g.index("09:00") < g.index("15:00"), g)
    check("it names who is on each one",
          "Naftul" in g and "Vladi" in g and "Ella" in g, g)
    check("a shared lesson names all of them",
          "Naftul, Vladi, Ella" in g, g)
    check("and the empty shift has no zero on it", "(0" not in g, g)

    empty = rota.group([], "2026-09-01")
    check("a day with nothing booked says so", "אין עדיין" in empty, empty)

    # --- English ------------------------------------------------------------
    en = rota.personal("VLADI", who["VLADI"], "2026-09-01", "en")
    check("the English day is the English weekday",
          "Tuesday 1/9" in en, en[:90])
    check("and its counts read as English",
          "1 student" in en and "12 students" in en, en)

    # --- who is actually coming ---------------------------------------------
    # Bloowatch numbers the people on an order, and a group booked under one
    # name arrives as twelve copies of it. Both have to be dealt with before
    # a name is worth putting in a message.
    check("the participant number is stripped off the name",
          rota.student_names([{"first_name": "P1 yedidia  k", "last_name": ""}])
          == ["Yedidia K"],
          str(rota.student_names([{"first_name": "P1 yedidia  k", "last_name": ""}])))
    check("a name without one is left alone",
          rota.student_names([{"first_name": "noa", "last_name": ""}]) == ["Noa"])
    check("a double-digit index too",
          rota.student_names([{"first_name": "P14 young guns", "last_name": ""}])
          == ["Young Guns"])
    twelve = [{"first_name": "P%d young guns sep 26" % i} for i in range(1, 13)]
    check("twelve of the same booking collapse to one name",
          rota.student_names(twelve) == ["Young Guns Sep 26"],
          str(rota.student_names(twelve)))
    check("two different people stay two",
          len(rota.student_names([{"first_name": "P1 ibai a"},
                                  {"first_name": "P2 dana b"}])) == 2)
    check("nobody booked is an empty list", rota.student_names([]) == [])
    check("and a missing attendants field does not explode",
          rota.student_names(None) == [])

    # a name is worth saying while it tells you something, and not past that
    named = L("09:00", "SURF PACK", 1, ["NAFTUL"])
    named["names"] = ["Itay A"]
    check("one student is named", "Itay A" in rota._line(named, "he"),
          rota._line(named, "he"))
    crowd = L("15:00", "SURF PACK", 12, ["NAFTUL"])
    crowd["names"] = ["A One", "B Two", "C Three", "D Four", "E Five"]
    check("five names are a list, so the count carries it alone",
          "A One" not in rota._line(crowd, "he") and
          "12 תלמידים" in rota._line(crowd, "he"), rota._line(crowd, "he"))
    check("a lesson with no names recorded still reads cleanly",
          rota._line(L("09:00", "SURF PACK", 1, ["N"]), "he")
          == "SURF PACK · תלמיד אחד")

    # --- the reminder window ------------------------------------------------
    # An hourly run steps a 60-minute window by 60 minutes. Every lesson in
    # the day has to fall in exactly one of those steps: land in two and the
    # instructor is reminded twice, land in none and nobody turns up.
    import datetime as _dt
    day = [L("%02d:%02d" % (h, m), "SURF PACK", 1, ["NAFTUL"])
           for h in range(6, 20) for m in (0, 30)]
    seen = {}
    for hour in range(0, 24):
        now = _dt.datetime(2026, 9, 1, hour, 0, tzinfo=rota.PANAMA)
        for l in rota.starting_between(day, 45, 105, now):
            seen[l["time"]] = seen.get(l["time"], 0) + 1
    twice = sorted(t for t, n in seen.items() if n > 1)
    never = sorted(l["time"] for l in day if l["time"] not in seen)
    check("no lesson is reminded twice in a day", not twice, str(twice))
    check("and none is missed", not never, str(never))

    now = _dt.datetime(2026, 9, 1, 8, 0, tzinfo=rota.PANAMA)
    soon = rota.starting_between(day, 45, 105, now)
    check("at eight, the nine and the half nine are what is coming",
          [l["time"] for l in soon] == ["09:00", "09:30"],
          str([l["time"] for l in soon]))
    check("the one already under way is not 'coming up'",
          "08:00" not in [l["time"] for l in soon], str([l["time"] for l in soon]))

    r = rota.remind("NAFTUL", soon)
    check("the reminder names the hour, never 'in an hour'",
          "09:00" in r and "בעוד שעה" not in r, r)
    check("and it is addressed to them", r.startswith("היי Naftul"), r[:30])
    check("nobody coming up gets no message", rota.remind("NAFTUL", []) == "")

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
