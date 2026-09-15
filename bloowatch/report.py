#!/usr/bin/env python3
"""What a routine did, written somewhere it can be read back.

    python3 report.py "19:00 rota" "RESULT rota=sent board=photograph"
    python3 report.py --read            # the last day of reports
    python3 report.py --read --minutes 90

Every routine already prints a RESULT line, and until now that line went
into the fired session's own output and from there into a push
notification on the owner's phone. Nowhere else. The container is thrown
away minutes later, and a routine cannot push to the repository, so by
morning the only record of what happened at three a.m. was a notification
somebody had to remember to read.

That is not a small inconvenience, it is the reason a whole day was spent
guessing. On 14/09/2026 ten routines failed in exactly the same way for
twelve hours -- each one reported it clearly, each report went to the
phone, and the sessions trying to diagnose it could see none of them. The
fix took five minutes once somebody read one aloud.

So a routine writes its RESULT line to the same place the 19:00 snapshot
goes: WhatsApp's own journal, in the school's own chat, from the school's
own number. It is durable, both a fired container and a working session
can read it, and it costs one short message per run.

**It never fails the routine.** A report that cannot be sent is written to
stderr and the exit status stays 0. The report exists to explain a run,
and a run that did its job must not be recorded as broken because the
note about it did not go out.
"""

import argparse
import datetime as dt
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audit_reminders as A                                     # noqa: E402
import send                                                     # noqa: E402
import snapshot                                                 # noqa: E402

MARKER = "#SHOKOGI-RUN"

# WhatsApp will take far more than this. The limit is here so that a
# routine which decides to paste a traceback, a plan or somebody's phone
# number into its report cannot: a report is one line about one run.
MAX = 900


def line(what, result, when=None, host=None):
    when = when or dt.datetime.now(dt.timezone.utc)
    host = host or socket.gethostname()
    return "%s %s | %s | %sZ | %s" % (MARKER, what, host,
                                      when.strftime("%m-%d %H:%M"),
                                      " ".join(str(result).split())[:MAX])


def write(what, result):
    """Send one report. Returns True if the journal has it, False otherwise."""
    gateway, ident, token = send.pick_gateway()
    if gateway != "green":
        print("report not sent: no Green-API credentials", file=sys.stderr)
        return False
    where = send.target(snapshot.self_chat(), {})
    try:
        code, body = send.via_green(where, line(what, result), "", ident, token)
    except Exception as exc:                                    # noqa: BLE001
        print("report not sent: %s" % exc, file=sys.stderr)
        return False
    if code != 200:
        print("report not sent: %s %s" % (code, body), file=sys.stderr)
        return False
    return True


def read(minutes=1440):
    """Every report in the journal, oldest first, as (when, text) pairs."""
    ident = os.environ.get("GREENAPI_ID", "")
    token = os.environ.get("GREENAPI_TOKEN", "")
    mine = snapshot.self_chat()
    out = []
    for m in A.journal(ident, token, minutes=minutes):
        if m.get("chatId") != mine:
            continue
        text = (m.get("textMessage") or m.get("caption")
                or (m.get("extendedTextMessage") or {}).get("text") or "")
        if not text.startswith(MARKER):
            continue
        out.append((m.get("timestamp") or 0, text[len(MARKER):].strip()))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="?", help="which routine, e.g. '19:00 rota'")
    ap.add_argument("result", nargs="?", help="its RESULT line, verbatim")
    ap.add_argument("--read", action="store_true",
                    help="print the reports already in the journal")
    ap.add_argument("--minutes", type=int, default=1440,
                    help="how far back --read looks (default a day)")
    a = ap.parse_args()

    if a.read:
        rows = read(a.minutes)
        if not rows:
            print("no reports in the last %d minutes" % a.minutes)
            return 0
        tz = dt.timezone(dt.timedelta(hours=-5))                # Panama
        for at, text in rows:
            print("%s  %s" % (dt.datetime.fromtimestamp(at, tz)
                              .strftime("%m-%d %H:%M"), text))
        return 0

    if not (a.what and a.result):
        ap.error("give both a name and a result, or --read")
    ok = write(a.what, a.result)
    print("report sent" if ok else "report NOT sent (the run itself is "
                                   "unaffected)")
    return 0                                                    # never fails


if __name__ == "__main__":
    sys.exit(main())
