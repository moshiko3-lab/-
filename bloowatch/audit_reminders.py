#!/usr/bin/env python3
"""Which reminders should have gone out today, and which actually did.

    python3 audit_reminders.py
    python3 audit_reminders.py --date 2026-09-11 --json

The reminder routines are silent by design: most runs have nobody to write
to, so a run that sends nothing looks exactly like a run that never happened.
That is the hole this closes. On 11/09/2026 eight slots in a row did not run
and four instructors went unreminded, and nothing anywhere said so -- the
gap was only found by reading the day backwards afterwards.

**The check does not trust this side of the wire.** Whether a reminder was
sent is not read from a local log, a state file, or anything the same process
that failed could also have failed to write. It is read from Green-API's own
outgoing journal, which is the record of what actually reached WhatsApp and
survives this container dying mid-morning. A local log would have recorded
"nothing to send" on 11/09 just as confidently as the routine reported it.

**Matching is on the reminder's own opening line plus the lesson's hour**,
not on the message text as a whole. Rebuilding the exact reminder and
comparing it byte for byte is the obvious thing and it is wrong: the board
moves during the day, and a lesson added at noon changes the text of a
reminder that correctly went out at nine.

The hour alone is not enough either, and the first version of this check
passed a day it should have failed because of it. The evening rota names
tomorrow's hours to the same instructor, so "a message to Naor mentioning
12:30" is true every night whether or not this morning's reminder ever left.
Only the reminder says "תזכורת לשיעור שלך" / "A reminder for your shift", so
the evidence is that line and the hour together.

Exit status is 1 when a reminder is missing, so a routine can act on the
status alone and say nothing on a clean day.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

import daily_report
import rota

PANAMA = rota.PANAMA

# The two reminder routines fire at ten and forty past, 05:10 through 18:40
# Panama. Reconstructing the slots here rather than reading them from the
# scheduler is deliberate: the point of the check is to notice when the
# scheduler did not do what it was supposed to, so it cannot ask the
# scheduler what it was supposed to do.
FIRST_SLOT = (5, 10)
LAST_SLOT = (18, 40)

# What makes an outgoing message a reminder rather than a rota. Taken from
# rota.remind() in both languages; if that wording is ever reworded, this has
# to move with it, and the test pins the two together so it cannot quietly
# drift into passing everything.
REMINDER_MARKS = ("תזכורת לשיעור שלך", "תזכורת למשמרת שלך",
                  "A reminder for your lesson", "A reminder for your shift")


def is_reminder(text):
    return any(m in text for m in REMINDER_MARKS)


def slots(date, now):
    """Every reminder slot on `date` that has already come round."""
    out = []
    day = dt.datetime.combine(date, dt.time(0, 0), tzinfo=PANAMA)
    for hour in range(FIRST_SLOT[0], LAST_SLOT[0] + 1):
        for minute in (10, 40):
            if (hour, minute) < FIRST_SLOT or (hour, minute) > LAST_SLOT:
                continue
            at = day.replace(hour=hour, minute=minute)
            if at <= now:
                out.append(at)
    return out


def outgoing(ident, token, minutes=1440):
    """Today's outgoing messages, as {chatId: [text, ...]}.

    An unreachable journal is not "nothing was sent" -- that would turn every
    network blip into a false alarm naming instructors who were reminded
    perfectly well. It raises instead, and the caller stays quiet.
    """
    url = "%s/waInstance%s/lastOutgoingMessages/%s?minutes=%d" % (
        os.environ.get("GREENAPI_URL", "").rstrip("/"), ident, token, minutes)
    with urllib.request.urlopen(url, timeout=60) as r:
        said = json.loads(r.read().decode("utf-8", "replace"))
    by_chat = {}
    for m in said if isinstance(said, list) else []:
        text = m.get("textMessage") or m.get("extendedTextMessage") or ""
        if isinstance(text, dict):
            text = text.get("text") or ""
        by_chat.setdefault(m.get("chatId"), []).append(str(text))
    return by_chat


def due_today(lessons, date, now):
    """Every (slot, person, lesson) a reminder was owed for.

    Built by stepping the real window over the real slots, so it stays right
    by construction if the window or the cadence ever changes: there is one
    definition of "whose turn is it", in rota.starting_between, and this
    reads it rather than restating it.
    """
    owed = []
    for at in slots(date, now):
        for lesson in rota.starting_between(lessons, 35, 65, now=at):
            for name in rota.by_person([lesson]):
                owed.append({"slot": at, "name": name, "lesson": lesson})
    return owed


def audit(date=None, now=None):
    date = date or dt.datetime.now(PANAMA).date()
    now = now or dt.datetime.now(PANAMA)

    ident = os.environ.get("GREENAPI_ID", "")
    token = os.environ.get("GREENAPI_TOKEN", "")
    if not (ident and token and os.environ.get("GREENAPI_URL")):
        raise SystemExit("error: GREENAPI_ID, GREENAPI_TOKEN and "
                         "GREENAPI_URL must be set. Never guess a token.")

    session, base = daily_report.login()
    lessons = rota.lessons_for(session, base, date.isoformat())
    owed = due_today(lessons, date, now)
    if not owed:
        return []

    book = rota._book()
    from export_catalog import crew_numbers
    numbers = crew_numbers()
    phone = {c["name"].strip().upper(): c["phone"] for c in numbers}
    said = outgoing(ident, token)

    missing = []
    for item in owed:
        # plan() owns every rule about who may be written to. Asking it about
        # one person at a time keeps the quiet list, the sending number and
        # the missing-number rule in exactly one place.
        sends, _ = rota.plan(lambda n, lang: "x", [item["name"]],
                             numbers=numbers, book=book)
        if not sends:
            continue                      # deliberately not messaged
        where = __import__("send").target(sends[0]["phone"], {})
        hour = item["lesson"]["time"]
        if any(is_reminder(t) and hour in t
               for t in said.get(where["jid"], [])):
            continue
        missing.append({
            "slot": item["slot"].strftime("%H:%M"),
            "name": item["name"],
            "at": hour,
            "what": rota.short(item["lesson"].get("title") or ""),
        })
    return missing


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD, default today in Panama")
    ap.add_argument("--json", action="store_true",
                    help="machine-readable, for a routine to act on")
    a = ap.parse_args()

    date = (dt.date.fromisoformat(a.date) if a.date else None)
    missing = audit(date)

    if a.json:
        print(json.dumps(missing, ensure_ascii=False))
    elif not missing:
        print("every reminder due today was sent")
    else:
        for m in missing:
            print("MISSED  slot %s  %-18s %s  %s"
                  % (m["slot"], m["name"], m["at"], m["what"]))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
