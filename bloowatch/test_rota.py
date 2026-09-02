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
          m.lstrip(rota.LTR).startswith("היי Naftul"), m.split("\n")[0])
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
    # "(0" alone would also match the tide's own "(0.2 m)" at the foot
    check("and the empty shift has no zero on it",
          "(0)" not in g and "(0 " not in g, g)
    check("the day's tide is at the foot of it", "גאות" in g and "שפל" in g, g)
    # WhatsApp reads a line's direction off its first strong letter, and ours
    # start with a digit. Without the mark the whole bubble inherits Hebrew
    # and every line reads back to front.
    check("every line is pinned left-to-right",
          all(x.startswith(rota.LTR) for x in g.split("\n") if x), g)
    check("and so is a personal one",
          all(x.startswith(rota.LTR) for x in m.split("\n") if x), m)

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
    # the product name says nothing -- almost every booking is a SURF PACK --
    # so the line carries whoever is coming, and falls back to the count when
    # nobody was recorded, and to the product name only when there is neither
    check("a plain surf lesson is named by who is coming to it",
          rota._line(named, "he") == "Itay A", rota._line(named, "he"))
    check("a lesson with no names recorded falls back to the count",
          rota._line(L("09:00", "SURF PACK", 1, ["N"]), "he") == "תלמיד אחד",
          rota._line(L("09:00", "SURF PACK", 1, ["N"]), "he"))
    check("and with neither, to the name it was booked under",
          rota._line(L("09:00", "SURF PACK", 0, ["N"]), "he") == "SURF PACK",
          rota._line(L("09:00", "SURF PACK", 0, ["N"]), "he"))
    check("a shop shift keeps its own name",
          rota._line(L("13:00", "SHOP PLAYA", 0, ["N"], "SHOP PLAYA"), "he")
          == "SHOP PLAYA")
    check("a private course is known by who is coming to it, not its filing",
          rota.short("CLASS 2024 - jim van weperen") == "",
          rota.short("CLASS 2024 - jim van weperen"))

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
    check("and it is addressed to them",
          r.lstrip(rota.LTR).startswith("היי Naftul"), r[:30])
    check("nobody coming up gets no message", rota.remind("NAFTUL", []) == "")

    # --- what changed since the rota went out ------------------------------
    # The eight o'clock check exists so somebody who was told one thing at
    # seven is not left with it. Everything here is about reaching exactly
    # the people a change touches, and nobody else.
    def S(sid, time, staff, title="SURF PACK", students=1):
        return {"id": sid, "time": time, "title": title, "category": title,
                "students": students, "names": [], "capacity": 12,
                "staff": list(staff)}

    base = [S(1, "09:00", ["NAFTUL"]), S(2, "10:00", ["VLADI"]),
            S(3, "15:00", ["ELLA", "DYLAN"])]

    check("an unchanged rota produces nothing at all",
          rota.changes(base, [S(1, "09:00", ["NAFTUL"]), S(2, "10:00", ["VLADI"]),
                              S(3, "15:00", ["ELLA", "DYLAN"])]) == [])

    # a lesson that moves is one change, not a cancellation plus a booking
    moved = rota.changes(base, [S(1, "11:00", ["NAFTUL"]), S(2, "10:00", ["VLADI"]),
                                S(3, "15:00", ["ELLA", "DYLAN"])])
    check("a lesson that moves is a single change", len(moved) == 1, str(moved))
    check("and it is described as a move, not a cancellation",
          moved[0]["kind"] == "moved" and moved[0]["from"] == "09:00",
          str(moved[0]))
    check("the person who has it is the one told",
          moved[0]["staff"] == {"NAFTUL"}, str(moved[0]["staff"]))

    gone = rota.changes(base, [S(2, "10:00", ["VLADI"]), S(3, "15:00", ["ELLA", "DYLAN"])])
    check("a cancelled lesson is reported", len(gone) == 1 and
          gone[0]["kind"] == "cancelled", str(gone))

    new = rota.changes(base, base + [S(4, "16:00", ["SHAKED"])])
    check("a new lesson reaches whoever got it",
          len(new) == 1 and new[0]["kind"] == "added" and
          new[0]["staff"] == {"SHAKED"}, str(new))

    # a handover has to reach both ends, and only those two
    swap = rota.changes(base, [S(1, "09:00", ["NAFTUL"]), S(2, "10:00", ["SHAKED"]),
                               S(3, "15:00", ["ELLA", "DYLAN"])])
    kinds = {c["kind"]: c["staff"] for c in swap}
    check("a handover is told to the one who gained it",
          kinds.get("added") == {"SHAKED"}, str(kinds))
    check("and to the one who lost it", kinds.get("off") == {"VLADI"}, str(kinds))
    check("and to nobody else", len(swap) == 2, str(swap))

    # the messages themselves
    g = rota.update_group(swap, "2026-09-02")
    check("the group message names who gained and who lost",
          "Shaked" in g and "Vladi" in g, g)
    mine = rota.update_personal("VLADI", swap, "2026-09-02")
    check("the person who lost it is told in their own message",
          "כבר לא אצלך" in mine, mine)
    check("and is not told about the other person's gain",
          "Shaked" not in mine, mine)
    check("somebody untouched by the change gets no message at all",
          rota.update_personal("ELLA", swap, "2026-09-02") == "")
    check("no changes means no group message",
          rota.update_group([], "2026-09-02") == "")

    # the hours a shift occupies, which is the whole difference between a
    # lesson and a day behind the counter
    start = "Wed, 02 Sep 2026 09:00:00"
    check("an hour-long lesson is just its start time",
          rota._end(start, "01:00:00") == "", rota._end(start, "01:00:00"))
    check("a ten-hour shop shift ends when it ends",
          rota._end(start, "10:00:00") == "19:00", rota._end(start, "10:00:00"))
    check("half past counts as longer than an hour",
          rota._end(start, "01:30:00") == "10:30", rota._end(start, "01:30:00"))
    check("a duration Bloowatch did not send is not guessed at",
          rota._end(start, None) == "")
    check("a span is printed as a span",
          rota._when({"time": "09:00", "until": "19:00"}) == "09:00-19:00")
    check("and a lesson stays a single time",
          rota._when({"time": "09:00", "until": ""}) == "09:00")

    # a shift that now finishes at a different hour has moved
    was = [{"id": 1, "time": "09:00", "until": "15:00", "title": "SHOP PLAYA",
            "students": 0, "names": [], "staff": ["IDAN"]}]
    now = [dict(was[0], until="19:00")]
    ext = rota.changes(was, now)
    check("a shift that runs later is reported as a move",
          len(ext) == 1 and ext[0]["kind"] == "moved", ext)
    check("and it says what the hours were before",
          ext[0]["from"] == "09:00-15:00", ext[0]["from"])
    check("a snapshot written before end times were kept reports nothing",
          rota.changes([{k: v for k, v in was[0].items() if k != "until"}],
                       now) == [])

    # a move is written so it cannot be read backwards in a Hebrew message
    line = rota.change_lines(moved)[0]
    check("a move states the new hour and puts the old one behind it",
          line.index("11:00") < line.index("09:00") and "היה" in line, line)

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
