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
import time
import urllib.error
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


def outgoing(ident, token, minutes=1440, since=None):
    """Today's outgoing messages, as {chatId: [text, ...]}.

    An unreachable journal is not "nothing was sent" -- that would turn every
    network blip into a false alarm naming instructors who were reminded
    perfectly well. It retries, and if the journal still will not answer it
    raises, so the caller stays quiet rather than reporting a day it could
    not see.
    """
    # Green-API rate-limits this endpoint, and the two safety-net runs land
    # within minutes of each other on a busy evening. A 429 is the server
    # saying "ask again shortly", not an answer -- and treating it as a
    # crash takes the recovery routine down with it, which is the one run
    # whose whole purpose is to still work when something else failed.
    # Same for a 5xx or a dropped connection. After three tries it raises,
    # and the caller stays quiet rather than naming people as unreminded on
    # the strength of a journal it never actually read.
    return by_chat(_fetch(ident, token, minutes), since=since)


def _fetch(ident, token, minutes):
    """The journal itself, with the retries. Raises rather than guessing."""
    url = "%s/waInstance%s/lastOutgoingMessages/%s?minutes=%d" % (
        os.environ.get("GREENAPI_URL", "").rstrip("/"), ident, token, minutes)
    wait = 2
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise                       # 401 is a real answer: stop.
        except urllib.error.URLError:
            pass
        if attempt < 2:
            time.sleep(wait)
            wait *= 3
    raise RuntimeError("Green-API's outgoing journal did not answer after "
                       "three tries -- reporting nothing rather than "
                       "guessing what went out")


def journal(ident, token, minutes=1440):
    """The raw journal, for a caller that needs its own cutoff per question.

    `outgoing` answers "what went out" in one window, which suits the
    reminder audit. The evening check asks a different question of the same
    fetch -- was *this* message sent after *this* deadline -- and asking it
    four times would be four calls to an endpoint that rate-limits. So the
    fetch and the filtering are separable.
    """
    return _fetch(ident, token, minutes)


def by_chat(said, since=None):
    """Green-API's journal, reduced to {chatId: [text, ...]}.

    Split out from the fetch so the shape of a journal entry can be tested
    without a network call -- which is how the caption case below was got
    wrong in the first place.

    `since` (a datetime) drops everything sent before it, and it is not
    optional in spirit. The journal covers a whole day, and the evening
    messages repeat: the forecast opens with the same greeting every single
    night. On 14/09/2026 the 18:00 forecast did not go out, and the check
    that exists to notice that reported "everything due by now went out" --
    because **last night's** forecast was still inside the window and its
    opening line matched. A check that yesterday's message can satisfy is
    not a check. Whoever asks "did this go out?" must also say "since
    when?", and the answer is the moment it was due.
    """
    cut = since.timestamp() if since is not None else None
    by_chat = {}
    for m in said if isinstance(said, list) else []:
        if cut is not None and (m.get("timestamp") or 0) < cut:
            continue
        # `caption` is not an afterthought here: the 19:00 rota goes out as
        # one imageMessage whose caption *is* the rota, so a reader that
        # only knows about textMessage sees the biggest send of the evening
        # as an empty string and calls it missing every single night. A
        # check that cries wolf nightly is a check nobody reads by Friday.
        text = (m.get("textMessage") or m.get("extendedTextMessage")
                or m.get("caption") or "")
        if isinstance(text, dict):
            text = text.get("text") or text.get("caption") or ""
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
    # Since midnight, not "the last day": the journal window reaches back
    # into yesterday evening, where the same instructor was told about the
    # same hour. Without the cutoff, yesterday's message answers today's
    # question -- the same flaw that let a missing forecast pass unnoticed.
    said = outgoing(ident, token, since=dt.datetime.combine(
        date, dt.time(0, 0), tzinfo=PANAMA))

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

    # Filed on a clean run too. A check that is silent when it is happy
    # looks exactly like a check that never ran, and telling those two
    # apart is the whole reason these reports exist.
    import report
    report.result("reminder audit", "RESULT missed=%d" % len(missing),
                  echo=not a.json)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
