#!/usr/bin/env python3
"""The check that notices a reminder nobody sent.

This exists because of one day. On 11/09/2026 eight reminder slots in a row
did not run, four instructors were never told about six lessons and shifts,
and every routine involved reported a clean silent run -- because a slot with
nobody to write to and a slot that never happened produce the same output.

Two things are pinned here, and they are the two that were got wrong.

The slot arithmetic, because the whole guarantee of the reminder system is
that the (35, 65] window stepped every half hour covers every minute once: a
gap in it skips a lesson silently, and an overlap sends the same one twice.

And what counts as evidence that a reminder arrived. The first version of the
check looked for the lesson's hour in any message to that instructor and so
passed the very day it was written to catch: the evening rota names tomorrow's
hours to the same people, every night, whether or not the morning's reminder
ever left. A check that cannot fail is worse than no check, because it is
believed. So the reminder's own wording is required, and the wording is
compared against rota.remind() itself rather than copied -- if somebody
rewords the reminder, this fails loudly instead of quietly passing forever.

Nothing here touches the network.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_reminders as A                                       # noqa: E402
import rota                                                       # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def L(time, title, staff, cat="SURF PACK"):
    return {"time": time, "title": title, "category": cat,
            "students": 1, "capacity": 12, "staff": staff}


def main():
    date = dt.date(2026, 9, 11)
    end = dt.datetime(2026, 9, 11, 23, 0, tzinfo=A.PANAMA)

    # --- the slots themselves ----------------------------------------------
    day = A.slots(date, end)
    check("a full day is 28 slots", len(day) == 28, "got %d" % len(day))
    check("the first is 05:10", day[0].strftime("%H:%M") == "05:10")
    check("the last is 18:40", day[-1].strftime("%H:%M") == "18:40")
    check("they step by exactly thirty minutes",
          all((b - a).total_seconds() == 1800 for a, b in zip(day, day[1:])))
    check("a slot that has not come round yet is not counted",
          len(A.slots(date, dt.datetime(2026, 9, 11, 9, 0, tzinfo=A.PANAMA)))
          == 8)

    # --- every lesson is owed a reminder by exactly one slot ----------------
    # The property that matters: not "most lessons get one", but each one
    # gets one and only one, whatever minute of the day it starts at.
    for minute in range(0, 60, 5):
        for hour in range(7, 19):
            at = "%02d:%02d" % (hour, minute)
            one = [L(at, "SURF PACK", ["NAFTUL"])]
            hits = [s for s in day if rota.starting_between(one, 35, 65, now=s)]
            check("a %s lesson is claimed by exactly one slot" % at,
                  len(hits) == 1, "claimed by %d" % len(hits))

    owed = A.due_today([L("12:00", "SURF PACK", ["VLADI", "SHAKED"])],
                       date, end)
    check("both instructors on one lesson are owed a reminder",
          sorted(o["name"] for o in owed) == ["SHAKED", "VLADI"])
    check("and it is the 11:10 slot that owed it",
          owed and owed[0]["slot"].strftime("%H:%M") == "11:10")

    # --- what counts as proof a reminder went out --------------------------
    # Compared against the real message, so a reworded reminder fails here
    # rather than silently making the check pass everything forever.
    for lang in ("he", "en"):
        real = rota.remind("NAFTUL", [L("13:30", "SURF PACK", ["NAFTUL"])],
                           lang)
        check("a real %s reminder is recognised as one" % lang,
              A.is_reminder(real))
        check("and it carries the hour it is for (%s)" % lang, "13:30" in real)

    shift = rota.remind("YONATAN", [L("10:30", "SHOP PLAYA", ["YONATAN"],
                                      "SHOP PLAYA")], "he")
    check("a shift reminder is recognised too", A.is_reminder(shift))

    # The exact miss that started this: the evening rota names tomorrow's
    # hours to the same instructor and must never be mistaken for a reminder.
    rotas = rota.personal("NAOR", [L("12:30", "SURF PACK", ["NAOR"])],
                          "2026-09-12", "he")
    check("tomorrow's rota is not evidence of today's reminder",
          not A.is_reminder(rotas),
          "the rota would have counted as a reminder")
    check("even though it names the same hour", "12:30" in rotas)

    for other in ("היי נאור 👋", "*ערב טוב חברים🌞*", ""):
        check("%r is not a reminder" % other[:20], not A.is_reminder(other))

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
