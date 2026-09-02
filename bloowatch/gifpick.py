#!/usr/bin/env python3
"""Which animation goes to whom on a day off.

    python3 gifpick.py 0                    # the first person off tomorrow
    python3 gifpick.py 1 --date 2026-09-02  # the second
    python3 gifpick.py --list

Prints the id of a WhatsApp message holding the animation. The sender then
asks TimelinesAI for that message, which hands back a signed link to the
file itself.

Two people off on the same day get different ones, and tomorrow everybody
moves along by one -- worked out from the date and the person's place in
today's list rather than remembered, so there is no state to keep and no
file to write at seven in the evening. With two in the library that
alternates; the point of it appears once there are four or five.
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, "gifs.json")
PANAMA = dt.timezone(dt.timedelta(hours=-5))


def library(path=LIBRARY):
    try:
        with open(path, encoding="utf-8") as f:
            return [g for g in (json.load(f).get("gifs") or []) if g.get("uid")]
    except (OSError, ValueError):
        return []


def pick(nth=0, date=None, gifs=None, skip=0):
    """The one for the nth person off on this day, or nothing if none.

    `skip` steps to the next one, for the night a message has been deleted
    at the far end and the link comes back empty.
    """
    gifs = library() if gifs is None else gifs
    if not gifs:
        return None
    d = dt.date.fromisoformat(date) if date else (
        dt.datetime.now(PANAMA).date() + dt.timedelta(days=1))
    return gifs[(d.toordinal() + int(nth) + int(skip)) % len(gifs)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("nth", nargs="?", default="",
                    help="the person's place in today's list of who is off, "
                         "counting from nought")
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--skip", type=int, default=0,
                    help="take the next one instead, for a link that failed")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    gifs = library()
    if a.list:
        for g in gifs:
            print("%s  %s" % (g["uid"], g.get("note") or ""))
        return 0
    if a.nth == "":
        print("error: whose place in the list?", file=sys.stderr)
        return 1
    got = pick(a.nth, a.date, gifs, a.skip)
    if not got:
        print("error: no animations in gifs.json", file=sys.stderr)
        return 1
    print(got["uid"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
