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
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import report                                                  # noqa: E402
import rota                                                    # noqa: E402
import send                                                    # noqa: E402

PANAMA = rota.PANAMA

# How hard to press the journal before giving up on it, and how long to wait
# between asks. Green-API takes a few seconds to show a message that has just
# gone out; these are here as names so a test can set the wait to nothing.
JOURNAL_TRIES, JOURNAL_WAIT = 3, 8


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


def sent_ids(lines):
    """What the gateway accepted, each with the id it handed back.

    The id is the point. Matching a reminder to "some message in that chat
    since the run began" is loose enough that the evening rota to the same
    instructor would satisfy it; the id Green-API returns identifies this
    message and nothing else.
    """
    accepted = []
    for line in lines:
        try:
            one = json.loads(line)
        except ValueError:
            continue
        if not isinstance(one, dict) or "chatId" not in one:
            continue
        if one.get("skipped") or one.get("code") != 200:
            continue
        try:
            one["idMessage"] = json.loads(one.get("said") or "{}").get("idMessage")
        except ValueError:
            one["idMessage"] = None
        accepted.append(one)
    return accepted


def landed(accepted, tries=None, wait=None):
    """Which of those the journal has caught up with. Returns (seen, missing).

    **The journal lags by a few seconds.** SENDING.md has said so since
    `--once-today` was written -- "a double send inside a minute does get
    through; a minute later the same call skips" -- and the first version of
    this file read the journal the instant after sending and called
    everything it could not yet see lost. On 15/09/2026 at 09:40 it reported
    Yonatan's reminder as not sent. It had been sent, at 09:40:51, under the
    exact id the gateway had just returned. The run was correct and the
    check was wrong.

    So it asks again, a few times, before concluding anything. And an id
    the journal still has not shown is reported as *unconfirmed*, not as
    lost: the gateway handed back an id for it, which is positive evidence,
    and Green-API holds a message for a day when the phone is offline.
    Whether it truly arrived is `audit_reminders`'s question, asked hours
    later against the same journal when no lag can colour the answer.
    """
    import audit_reminders as A
    tries = JOURNAL_TRIES if tries is None else tries
    wait = JOURNAL_WAIT if wait is None else wait
    want = {o["idMessage"] for o in accepted if o.get("idMessage")}
    if not want:
        return [], accepted
    seen = set()
    for attempt in range(tries):
        if attempt:
            time.sleep(wait)
        try:
            rows = A.journal(os.environ.get("GREENAPI_ID", ""),
                             os.environ.get("GREENAPI_TOKEN", ""))
        except Exception:                                      # noqa: BLE001
            continue            # an unreadable journal proves nothing
        seen |= {r.get("idMessage") for r in rows if r.get("idMessage")}
        if want <= seen:
            break
    ok = [o for o in accepted if o.get("idMessage") in seen]
    return ok, [o for o in accepted if o.get("idMessage") not in seen]


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

    # run_batch reports one JSON line per person. They are kept as well as
    # printed, because the ids the gateway hands back are what the journal
    # is then asked about.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = deliver(sends, a.dry_run)
    lines = buffer.getvalue().splitlines()
    for line in lines:
        print(line)

    if a.dry_run:
        _r("RESULT planned=%d dry-run" % len(sends))
        return 0

    # Two witnesses, and they answer different questions. The gateway says
    # whether it took the message; the journal says whether it has appeared
    # yet, and it runs a few seconds behind, so it is asked more than once
    # and its silence is never read as a denial.
    accepted = sent_ids(lines)
    ok, unconfirmed = landed(accepted)
    _r("RESULT planned=%d accepted=%d gateway=%s journal=%d/%d"
       % (len(sends), len(accepted), "ok" if status == 0 else "FAILED",
          len(ok), len(accepted)))

    if unconfirmed:
        # Not a failure, and deliberately not exit 1. The gateway returned an
        # id for each of these, Green-API holds a message for a day when a
        # phone is offline, and the run that shouted "not sent" at a message
        # that had gone out thirty seconds earlier taught its own lesson: an
        # alert that cries wolf is one nobody reads by Friday. Whether these
        # truly arrived is audit_reminders' question, asked at 11:45 and
        # 19:45 against the same journal, when no lag can colour it.
        print("the journal has not caught up with these yet — the gateway "
              "took them and audit_reminders will confirm later. Do not "
              "resend: " + ", ".join(o.get("name", "?") for o in unconfirmed),
              file=sys.stderr)

    if status != 0:
        print("some reminders did not reach WhatsApp — see FAILED above",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
