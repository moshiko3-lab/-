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

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
