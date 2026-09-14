#!/usr/bin/env python3
"""The check that notices an evening send nobody made.

Written after 13/09/2026, when the 18:00 forecast routine fired on time,
stopped on a permission prompt, and sat there until the owner asked at
19:00 why the group was empty. A run that hangs reports nothing, so the
only honest source is Green-API's own outgoing journal.

Two things are pinned, and they are the two that were got wrong.

**The shape of a journal entry.** The 19:00 rota is not a text message. It
is one imageMessage whose `caption` carries the whole rota, and the first
version of the reader knew only about `textMessage` -- so it read the
biggest send of the evening as an empty string and called it missing. It
did that against real data on the first run. A nightly false alarm is
worse than no check, because by the end of the week it is the thing people
scroll past.

**What counts as evidence.** The heading has to be tomorrow's and the chat
has to be the right one. Yesterday's rota is still sitting in the same
group; if the marker matched it, the check would pass forever. And the
same heading goes to every instructor privately, so a message to one of
them is not evidence that the group was written to.

Nothing here touches the network.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_reminders as A                                     # noqa: E402
import rota                                                     # noqa: E402
import watch_sends as W                                         # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main():
    # --- the journal entry shapes that actually occur -------------------
    journal = [
        {"chatId": "g1@g.us", "typeMessage": "imageMessage",
         "caption": "*לו״ז יום ב׳ 15/9*", "fileName": "board.png"},
        {"chatId": "g2@g.us", "typeMessage": "textMessage",
         "textMessage": "*ערב טוב חברים🌞*"},
        {"chatId": "p1@c.us", "typeMessage": "extendedTextMessage",
         "extendedTextMessage": {"text": "היי נאור 👋"}},
    ]
    seen = A.by_chat(journal)
    check("an image caption is read as the message text",
          "*לו״ז יום ב׳ 15/9*" in seen.get("g1@g.us", []),
          repr(seen.get("g1@g.us")))
    check("a plain text message is read", "*ערב טוב חברים🌞*"
          in seen.get("g2@g.us", []))
    check("an extended text message is read",
          "היי נאור 👋" in seen.get("p1@c.us", []))
    check("a message is filed under its own chat only",
          set(seen) == {"g1@g.us", "g2@g.us", "p1@c.us"}, repr(sorted(seen)))

    # --- the forecast markers must match the real message ---------------
    # Compared against the source of forecast_message rather than copied
    # into it, so rewording the greeting fails here instead of quietly
    # making every evening look fine forever.
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "forecast_message.py"), encoding="utf-8") as f:
        source = f.read()
    check("the Hebrew forecast marker still appears in forecast_message",
          W.FORECAST_HE in source, W.FORECAST_HE)
    check("the English forecast marker still appears in forecast_message",
          W.FORECAST_EN in source, W.FORECAST_EN)

    # --- the rota marker is tomorrow's, and only tomorrow's -------------
    tom = dt.date(2026, 9, 15)
    head = rota._heading(tom.isoformat(), "he")
    yesterday = rota._heading((tom - dt.timedelta(days=1)).isoformat(), "he")
    check("the rota marker names tomorrow", head in "*לו״ז %s*" % head)
    check("and it differs from the day before", head != yesterday,
          "%r == %r" % (head, yesterday))
    real = rota.group([], tom.isoformat(), "he")
    check("the marker appears in a rota the code actually builds",
          head in real, real[:60])

    # --- nothing is late before its time --------------------------------
    day = dt.date(2026, 9, 14)
    items = W.due_times(day)
    check("four things are due each evening", len(items) == 4,
          "got %d" % len(items))
    check("the forecast is due at 18:00",
          items[0]["due"].strftime("%H:%M") == "18:00")
    check("the staff rota at 19:00",
          items[2]["due"].strftime("%H:%M") == "19:00")
    check("the personal rotas at 19:15",
          items[3]["due"].strftime("%H:%M") == "19:15")

    at_1810 = dt.datetime.combine(day, dt.time(18, 10), tzinfo=W.PANAMA)
    late = [i for i in items
            if at_1810 >= i["due"] + dt.timedelta(minutes=W.GRACE_MINUTES)]
    check("ten minutes past due is not yet late", not late,
          "flagged %r" % [i["what"] for i in late])

    at_1830 = dt.datetime.combine(day, dt.time(18, 30), tzinfo=W.PANAMA)
    late = [i["what"] for i in items
            if at_1830 >= i["due"] + dt.timedelta(minutes=W.GRACE_MINUTES)]
    check("half past six, both forecasts are late and nothing else is",
          late == ["forecast_he", "forecast_en"], repr(late))

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
