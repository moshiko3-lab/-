#!/usr/bin/env python3
"""The snapshot has to survive a container it did not start in.

That is the whole reason this file exists rather than an open() and a
json.dump(). The 19:00 rota and the 20:00 change check run on two
different machines, so the reference point travels through WhatsApp's own
journal, and every way that can go wrong is quiet:

  - a rota message mistaken for a snapshot, and the day compared against
    a formatted Hebrew rota;
  - yesterday's snapshot answering for today's, so a board that changed
    overnight reads as unchanged;
  - a snapshot re-sent after a correction losing to the broken first one;
  - a message in some other chat counting as ours.

None of those raise. Each of them makes the 20:00 check report a clean
run while seeing the wrong thing, which is the failure this whole
mechanism was built to stop. So they are pinned here.

Nothing here touches the network.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import snapshot as S                                            # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


LESSONS = [{"start": "08:30", "title": "Bar S", "staff": ["Dylan"]},
           {"start": "09:30", "title": "Tim I", "staff": ["Shaked"]}]

MINE = "5076661234@c.us"


def msg(text, at, chat=MINE):
    return {"chatId": chat, "textMessage": text, "timestamp": at}


def with_journal(items, fn):
    real = S.A.journal
    S.A.journal = lambda ident, token, minutes=1440: items
    try:
        return fn()
    finally:
        S.A.journal = real


def with_self(fn):
    real = S.self_chat
    S.self_chat = lambda: MINE
    try:
        return fn()
    finally:
        S.self_chat = real


def main():
    # --- what goes in comes back out ------------------------------------
    one = S.decode(S.encode("2026-09-15", LESSONS))
    check("a snapshot survives the round trip",
          one == {"date": "2026-09-15", "lessons": LESSONS}, repr(one))

    # --- and nothing else is ever read as one ---------------------------
    # The journal holds every message the school sends. Most of them are
    # long, and one of them is the rota this snapshot describes.
    rota_text = ("‎*לו״ז יום "
                 "שלישי 15/9*\n\n*08:30* Bar S "
                 "— Dylan")
    for name, text in (("a rota", rota_text),
                       ("a reminder", "היי Dylan, בעוד 50 דקות"),
                       ("an empty message", ""),
                       ("the marker with nothing after it", S.MARKER),
                       ("the marker with junk after it",
                        S.MARKER + " 2026-09-15\nnot json"),
                       ("the marker over a list rather than a snapshot",
                        S.MARKER + " 2026-09-15\n[1, 2, 3]"),
                       ("the marker over an object with no lessons",
                        S.MARKER + ' 2026-09-15\n{"date": "2026-09-15"}')):
        check("%s is not read as a snapshot" % name, S.decode(text) is None,
              repr(S.decode(text)))

    # --- the right day, and no other ------------------------------------
    j = [msg(S.encode("2026-09-14", LESSONS), 100),
         msg(S.encode("2026-09-15", LESSONS), 200)]
    got = with_self(lambda: with_journal(j, lambda: S.load("2026-09-15")))
    check("the snapshot for the day asked about is the one returned",
          got is not None and got["date"] == "2026-09-15", repr(got))

    got = with_self(lambda: with_journal(j, lambda: S.load("2026-09-16")))
    check("a day with no snapshot returns None, not the nearest one",
          got is None, repr(got))

    # --- the newest wins ------------------------------------------------
    # A rota re-sent by hand after a fix saves a second snapshot. The 20:00
    # check must compare against what the group last received, not against
    # the attempt that was wrong.
    fixed = LESSONS + [{"start": "14:30", "title": "Ofek M",
                        "staff": ["Naor"]}]
    j = [msg(S.encode("2026-09-15", LESSONS), 100),
         msg(S.encode("2026-09-15", fixed), 300),
         msg(S.encode("2026-09-15", []), 50)]
    got = with_self(lambda: with_journal(j, lambda: S.load("2026-09-15")))
    check("the most recent snapshot of the day is the one used",
          got is not None and len(got["lessons"]) == 3, repr(got))

    # --- and only our own chat counts -----------------------------------
    # Anything arriving from elsewhere is somebody else's text, and the
    # board the school works from must never come from outside it.
    j = [msg(S.encode("2026-09-15", fixed), 400, chat="1234@g.us")]
    got = with_self(lambda: with_journal(j, lambda: S.load("2026-09-15")))
    check("a snapshot-shaped message in another chat is ignored",
          got is None, repr(got))

    # --- an empty journal is no snapshot, not an empty day --------------
    got = with_self(lambda: with_journal([], lambda: S.load("2026-09-15")))
    check("an empty journal means no snapshot", got is None, repr(got))

    # --- a caption carries text too -------------------------------------
    # The rota goes out as a picture with a caption, so the journal's text
    # lives under two different keys depending on the message.
    j = [{"chatId": MINE, "caption": S.encode("2026-09-15", LESSONS),
          "timestamp": 500}]
    got = with_self(lambda: with_journal(j, lambda: S.load("2026-09-15")))
    check("a snapshot sent as a caption is still found", got is not None,
          repr(got))

    # --- and it can never answer for a message that did not go out ------
    # The safety nets prove a send by looking for its opening line in the
    # chat it was due in. A snapshot lands in the journal every night, so
    # if it carried one of those lines it would stand in for a forecast or
    # a rota that never left -- the exact failure watch_sends.py was
    # rewritten to stop.
    import audit_reminders as A
    import rota as R
    import watch_sends as W
    text = S.encode("2026-09-15", LESSONS)
    check("a snapshot is not mistaken for a reminder",
          not A.is_reminder(text))
    check("nor for either forecast",
          W.FORECAST_HE not in text and W.FORECAST_EN not in text)
    check("nor for a rota",
          R._heading("2026-09-15", "he") not in text
          and R._heading("2026-09-15", "en") not in text)

    # --- no journal, no snapshot ----------------------------------------
    # Without Green-API there is nowhere to put it. Saying so beats writing
    # it where the 20:00 run can never look.
    real = S.send.pick_gateway
    S.send.pick_gateway = lambda: ("timelines", None, None)
    try:
        S.save("2026-09-15", LESSONS)
        check("saving without Green-API refuses", False, "it did not raise")
    except RuntimeError:
        check("saving without Green-API refuses", True)
    finally:
        S.send.pick_gateway = real

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
