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

**The count of what was planned is taken before anything is sent**, so a run
that dies halfway through fails loudly: planned is already 2 and the rest
never follows. That is the whole point -- the failure that hid was the one
where the planning half succeeded and the sending half never happened.

**And the proof that a reminder arrived is asked per person, of that person's
own chat, since this run began.** Anything looser is not proof: the first
version of this file counted every outgoing message in the window, which a
rota to the staff group would have satisfied just as well as the reminders
it was supposed to be checking.

Nothing about who gets a message or in which language is decided here:
`rota.plan` owns that, as it does for every other message the school sends.
"""

import argparse
import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import report                                                  # noqa: E402
import rota                                                    # noqa: E402
import send                                                    # noqa: E402

PANAMA = rota.PANAMA


def _r(text):
    """Print the RESULT line and file it where it can be read back."""
    report.result("reminders", text)


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


def landed(lines, since):
    """Of the reminders the gateway accepted, which ones the journal shows.

    Returns (accepted, arrived, lost) -- names, not counts, so the report can
    say who.

    The first version of this counted **every** outgoing message in the
    window and called a rise in that number proof. It is the same mistake
    that let a missing forecast pass for a day: evidence something else could
    have produced is not evidence. The 19:00 rota going out while an 18:40
    slot ran would have satisfied it, and a slot whose reminders all failed
    would have reported success.

    So the question is asked per person: this chat, since this run started.
    Messages the gateway skipped as already-sent are not expected to appear
    again and are not counted against the run.
    """
    accepted, skipped = [], []
    for line in lines:
        try:
            one = json.loads(line)
        except ValueError:
            continue
        if not isinstance(one, dict) or "chatId" not in one:
            continue
        (skipped if one.get("skipped") else accepted).append(one)
    accepted = [o for o in accepted if o.get("code") == 200]

    import audit_reminders as A
    try:
        seen = A.by_chat(A.journal(os.environ.get("GREENAPI_ID", ""),
                                   os.environ.get("GREENAPI_TOKEN", "")),
                         since=since)
    except Exception:                                          # noqa: BLE001
        # An unreadable journal must not turn a good run into a failure: a
        # reminder that never arrives is the worse of the two mistakes.
        return accepted, None, []
    lost = [o for o in accepted if not seen.get(o["chatId"])]
    return accepted, len(accepted) - len(lost), lost


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
        _r("RESULT planned=? sent=0 skipped=0 failed=? board=unreadable")
        return 1

    sends, not_sent = due(lessons, a.lo, a.hi)
    for s in not_sent:
        print("not messaged  %-18s %s" % (s["name"], s["why"]), file=sys.stderr)

    if not sends:
        print("nothing starting between %d and %d minutes from now"
              % (a.lo, a.hi))
        _r("RESULT planned=0 sent=0 skipped=0 failed=0")
        return 0

    for s in sends:
        print("%-18s %-4s %d chars" % (s["name"], s["lang"], len(s["text"])))

    started = dt.datetime.now(PANAMA) - dt.timedelta(minutes=2)

    # run_batch reports one JSON line per person. They are kept as well as
    # printed, because who the gateway accepted is what the journal is then
    # asked about, one chat at a time.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = deliver(sends, a.dry_run)
    lines = buffer.getvalue().splitlines()
    for line in lines:
        print(line)

    if a.dry_run:
        _r("RESULT planned=%d dry-run" % len(sends))
        return 0

    # What the gateway said is one witness; Green-API's journal is the other,
    # and it is the one that survives this process dying. They are asked
    # about the same people, since the same moment.
    accepted, arrived, lost = landed(lines, started)
    _r("RESULT planned=%d accepted=%d gateway=%s journal=%s"
          % (len(sends), len(accepted), "ok" if status == 0 else "FAILED",
             "unreadable" if arrived is None else "%d/%d"
             % (arrived, len(accepted))))

    if status != 0:
        print("some reminders did not reach WhatsApp — see FAILED above",
              file=sys.stderr)
        return 1
    if lost:
        print("the gateway accepted these and the journal has no trace of "
              "them — treat them as not sent: "
              + ", ".join(o.get("name", "?") for o in lost), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
