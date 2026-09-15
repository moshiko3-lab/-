#!/usr/bin/env python3
"""The 19:00 rota, kept somewhere the 20:00 check can still read it.

    python3 snapshot.py --save            # after the rota has gone out
    python3 snapshot.py --load /tmp/x.json

The 20:00 change check exists to catch the bookings that land after the
staff group has already been told what tomorrow looks like. On 3/9/2026
four of them landed in that hour and two were for somebody who had been
wished a good day off at 19:15. To notice a change you need the board as
it was when the rota went out, so `evening.py rota` wrote a snapshot to
`~/.shokogi/rota.json` and the 20:00 run compared against it.

**That stopped working the moment the routines began firing in fresh
containers.** 19:00 and 20:00 are two different machines now. The 19:00
container writes the file and is then thrown away; the 20:00 container
comes up empty, finds no file, prints "no snapshot -- nothing to compare
against" and stops. It fails quietly and in the safe direction, which is
why it went unnoticed: every night it reported a clean run, and every
night it was blind.

The repository cannot hold the file either -- a fired routine can clone it
but cannot push to it.

So the snapshot goes where the two containers already both have
credentials and already both read: WhatsApp's own journal, as a message
from the school's number to itself. It is a chat nobody else is in, it
carries exactly the data the staff group was just sent, and Green-API
keeps it long enough for an hour-later run to read it back.

The message is prefixed with a marker line so it is unmistakably machine
state rather than something a person wrote, and so that neither the
reminder audit nor the safety nets can mistake it for a rota that went to
real people.
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audit_reminders as A                                     # noqa: E402
import rota                                                     # noqa: E402
import send                                                     # noqa: E402

MARKER = "#SHOKOGI-SNAPSHOT"

# An hour is the gap the 20:00 check has to cross. Asking for a good deal
# more costs nothing and covers a run that fires late or is re-run by hand.
LOOK_BACK_MINUTES = 360


def self_chat():
    """The school's own number, as a chat id.

    Read from whatsapp.json rather than typed, so there is one place where
    the school's number is written down. `rota.plan` already refuses to
    send anything to this number as if it were an instructor, so a
    snapshot sitting in this chat can never be mistaken for a rota that
    reached a person.
    """
    phone = str(send.book()["account"]["phone"]).lstrip("+").strip()
    return phone + "@c.us"


def encode(date, lessons):
    return "%s %s\n%s" % (MARKER, date,
                          json.dumps({"date": date, "lessons": lessons},
                                     ensure_ascii=False))


def decode(text):
    """The snapshot inside one journal message, or None if it is not one.

    Anything unparseable is not a snapshot. Returning None rather than
    raising matters: the journal holds every message the school sends, and
    most of them are rotas and reminders that happen to be long.
    """
    if not text or not text.startswith(MARKER):
        return None
    _, _, body = text.partition("\n")
    try:
        one = json.loads(body)
    except ValueError:
        return None
    if not isinstance(one, dict) or "lessons" not in one:
        return None
    return one


def save(date=None, lessons=None):
    """Publish today's reference point. Returns the date it saved."""
    if lessons is None:
        session, base = rota.login()
        date = date or rota.tomorrow()
        lessons = rota.lessons_for(session, base, date)
    gateway, ident, token = send.pick_gateway()
    if gateway != "green":
        # The journal is a Green-API feature. Without it there is nowhere to
        # put the snapshot, and saying so beats writing it where no later
        # run can find it.
        raise RuntimeError("the snapshot needs Green-API; the credentials in "
                           "the environment say %r" % (gateway or "none"))
    where = send.target(self_chat(), {})
    code, body = send.via_green(where, encode(date, lessons), "", ident, token)
    if code != 200:
        raise RuntimeError("the snapshot was not accepted by the gateway: "
                           "%s %s" % (code, body))
    return date, len(lessons)


def load(date, ident=None, token=None):
    """The most recent snapshot for `date`, or None.

    The newest wins: a rota re-sent by hand after a fix is the one the
    20:00 check should be comparing against, not the broken first attempt.
    """
    ident = ident or os.environ.get("GREENAPI_ID", "")
    token = token or os.environ.get("GREENAPI_TOKEN", "")
    mine = self_chat()
    best, best_at = None, -1
    for m in A.journal(ident, token, minutes=LOOK_BACK_MINUTES):
        if m.get("chatId") != mine:
            continue
        text = (m.get("textMessage") or m.get("caption")
                or (m.get("extendedTextMessage") or {}).get("text") or "")
        one = decode(text)
        if one is None or one.get("date") != date:
            continue
        at = m.get("timestamp") or 0
        if at > best_at:
            best, best_at = one, at
    return best


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--save", action="store_true",
                   help="read the board and publish it as the reference point")
    g.add_argument("--load", metavar="PATH",
                   help="write the stored snapshot to this file, for "
                        "`rota.py --diff`. Exits 1 if there is none.")
    a = ap.parse_args()

    if a.save:
        date, n = save(a.date)
        print("snapshot saved: %d lessons for %s" % (n, date))
        return 0

    date = a.date or rota.tomorrow()
    one = load(date)
    if one is None:
        # Not an error to shout about: on the first night after a change,
        # and on any night the rota did not go out, there is genuinely
        # nothing to compare against. The caller decides what that means.
        print("no snapshot for %s in the journal" % date)
        return 1
    with open(a.load, "w", encoding="utf-8") as f:
        json.dump(one, f, ensure_ascii=False)
    print("snapshot for %s restored: %d lessons"
          % (date, len(one.get("lessons") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
