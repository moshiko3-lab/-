#!/usr/bin/env python3
"""Today's reminders, built and sent by one command.

    python3 remind.py
    python3 remind.py --dry-run
    python3 remind.py --from 10 --to 25      # recovering a slot that was missed

Until 14/09/2026 a reminder slot was two commands -- `rota.py --remind --plan`
to build the plan, then `send.py --batch` to send it -- and the routine ran
them one after the other. That split is what this file exists to close.

**Two commands means a run can stop between them, and a run that stops
between them looks exactly like a slot with nobody to remind.** Both are
silent, both finish cleanly, both report success. On 14/09/2026 four slots did
precisely that: they fired, they were recorded as SUCCEEDED, and six
instructors were not reminded. Nothing anywhere said so; it was found by
reading Green-API's journal by hand, hours later, and by then two of the
lessons had already started.

So the two halves are one call now, and the exit status carries the one fact
that matters:

    0   nobody was due, or everybody due was written to
    1   somebody was due and was not written to

There is no third outcome and no silent one. `RESULT planned=N sent=N ...` is
printed on the last line either way, so a routine reports from the numbers
rather than from an impression of how the run went.

**The count of what was planned is taken before anything is sent**, and the
count of what arrived is taken from what the gateway actually returned. A run
that dies halfway through therefore fails loudly: planned is already 2 and
sent never reaches it. That is the whole point -- the failure that hid was the
one where the planning half succeeded and the sending half never happened.

Nothing about who gets a message or in which language is decided here:
`rota.plan` owns that, as it does for every other message the school sends.
"""

import argparse
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rota                                                    # noqa: E402
import send                                                    # noqa: E402

PANAMA = rota.PANAMA


def due(lessons, lo, hi, now=None):
    """The reminders owed right now, as rota.plan would build them.

    `starting_between` decides whose turn it is and `plan` decides who may be
    written to; neither rule is restated here. A name that plan deliberately
    skips -- the sending number, somebody on the quiet list, somebody with no
    number in Bloowatch -- is not owed a reminder and must not count as one,
    or every run would fail on a person nobody ever intended to message.
    """
    soon = rota.starting_between(lessons, lo, hi, now=now)
    if not soon:
        return [], []
    mine = rota.by_person(soon)
    return rota.plan(lambda n, lang: rota.remind(n, mine[n], lang), mine)


def deliver(sends, dry_run=False):
    """Hand the plan to send.py's batch path, and report what it returned.

    It goes through a file because that is the path `send.run_batch` is
    written and tested against, and a reminder is not the place to introduce
    a second way of sending. The file holds crew phone numbers, so it is
    written to a private temporary file and removed in `finally` -- including
    when the send raises.
    """
    fd, path = tempfile.mkstemp(prefix="remind-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(sends, f, ensure_ascii=False)
        gateway, ident, token = send.pick_gateway()
        return send.run_batch(path, gateway, ident, token, dry_run, True)
    finally:
        os.remove(path)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="lo", type=int, default=35,
                    help="window starts this many minutes ahead (default 35)")
    ap.add_argument("--to", dest="hi", type=int, default=65,
                    help="and ends this many (default 65). The two reminder "
                         "slots step this window by its own width, so every "
                         "lesson falls inside exactly one of them.")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print the plan; send nothing")
    a = ap.parse_args()

    today = dt.datetime.now(PANAMA).date().isoformat()
    try:
        session, base = rota.login()
        lessons = rota.lessons_for(session, base, today)
    except Exception as exc:                                   # noqa: BLE001
        # A board that cannot be read is not an empty board. Saying "nothing
        # due" here would be the same lie the split commands told.
        print("error: could not read today's board: %s" % exc, file=sys.stderr)
        print("RESULT planned=? sent=0 skipped=0 failed=? board=unreadable")
        return 1

    sends, not_sent = due(lessons, a.lo, a.hi)
    for s in not_sent:
        print("not messaged  %-18s %s" % (s["name"], s["why"]), file=sys.stderr)

    if not sends:
        print("nothing starting between %d and %d minutes from now"
              % (a.lo, a.hi))
        print("RESULT planned=0 sent=0 skipped=0 failed=0")
        return 0

    for s in sends:
        print("%-18s %-4s %d chars" % (s["name"], s["lang"], len(s["text"])))

    before = _journal_count()
    status = deliver(sends, a.dry_run)
    if a.dry_run:
        print("RESULT planned=%d sent=0 skipped=0 failed=0 dry-run"
              % len(sends))
        return 0

    # What the gateway said is one witness; Green-API's journal is the other,
    # and it is the one that survives this process dying. They should agree.
    # When they do not, the journal wins and the run fails: a 200 that left no
    # trace in the journal has not reached anybody's phone.
    after = _journal_count()
    arrived = None if (before is None or after is None) else after - before
    line = ("RESULT planned=%d gateway=%s journal=%s"
            % (len(sends), "ok" if status == 0 else "FAILED",
               "unreadable" if arrived is None else "+%d" % arrived))
    print(line)

    if status != 0:
        print("some reminders did not reach WhatsApp — see FAILED above",
              file=sys.stderr)
        return 1
    if arrived is not None and arrived <= 0:
        print("the gateway accepted %d reminders and the journal shows none — "
              "treat this as not sent" % len(sends), file=sys.stderr)
        return 1
    return 0


def _journal_count(minutes=15):
    """How many messages Green-API has recorded going out just now.

    Deliberately a count and not a comparison of texts: this is a witness that
    something left the building, not a second implementation of `already_said`.
    Unreadable is reported as unreadable, never as zero -- a journal that will
    not answer must not turn a good run into a failure.
    """
    import urllib.request
    ident = os.environ.get("GREENAPI_ID", "")
    token = os.environ.get("GREENAPI_TOKEN", "")
    base = os.environ.get("GREENAPI_URL", "").rstrip("/")
    if not (ident and token and base):
        return None
    url = "%s/waInstance%s/lastOutgoingMessages/%s?minutes=%d" % (
        base, ident, token, minutes)
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            said = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:                                          # noqa: BLE001
        return None
    return len(said) if isinstance(said, list) else None


if __name__ == "__main__":
    sys.exit(main())
