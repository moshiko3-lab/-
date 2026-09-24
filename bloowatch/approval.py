#!/usr/bin/env python3
"""The office sees tomorrow's forecast before two hundred customers do.

    python3 approval.py --state
    python3 approval.py --state --json

The owner asked for this on 24/9/2026: *"בוא נעשה את התחזיות לשתי הקבוצות
בהודעה לווצאפ של העסק לאישור לפני שליחה"*. It was built first as a veto --
shown at 17:30, sent at 18:00 unless he objected -- and he read that and
asked for the other thing, in his own words: *"במקום לשלוח אוטומטי ב-18:00,
לשלוח ב-18:00 לווצאפ העסק את שניהם לאישור"*.

**So nothing reaches a customer until he types a word.** That is his call,
made after being told what it costs, and what it costs is this: on an
evening he is busy -- a lesson running late, a phone in a dry bag, a flat
battery -- the two surfer groups get nothing, and by his own older rule a
forecast that does not arrive is a failure. This file cannot make that
trade-off go away. What the rest of the system does about it:

  * 18:00  `evening.py preview` puts both messages in the school's own
           chat. Nothing else happens.
  * 18:05  onwards, every ten minutes until 21:00, `evening.py forecast`
           asks this file. Silence means it sends nothing and says
           nothing. The evening he answers, the next tick sends -- so
           "approved" costs him a wait of minutes, not a second command.
  * 21:00  the last tick. After that the forecast does not go out at all.
           A tomorrow-forecast arriving at midnight helps nobody, and a
           deadline is the difference between a decision he made and a
           message that leaked out while he was asleep.
  * 19:50  the safety net names the state on its own line, so a night
           nobody approved is visible in the journal the next morning
           instead of looking like a night the routines never fired.

REQUIRE_YES is the switch between the two bargains, and both halves of
this file are live either way. Setting it back to False restores the veto:
the preview still goes out, and silence sends.

**Where the reply is read from.** Both journals, because the school's own
chat is the one place where the distinction between them is not obvious.
A message typed into it on the linked phone is *sent by* the account, so
it lands in the outgoing journal beside our own reports; a message that
arrives from elsewhere lands in the incoming one. Asking only one of them
would work right up until the evening it mattered.

Nothing here sends anything to a customer. It reads, it decides, and the
caller does the rest.
"""

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audit_reminders as A                                     # noqa: E402
import send                                                     # noqa: E402
import snapshot                                                 # noqa: E402

PANAMA = dt.timezone(dt.timedelta(hours=-5))    # Panama, all year round

# True: the preview is a gate and nothing goes out without a typed yes --
# the owner's own choice on 24/9/2026, made after reading what it costs.
# False restores the veto, where silence sends. Read the docstring first.
REQUIRE_YES = True

# The last moment a typed approval still puts the forecast out, in Panama
# time. Not enforced here -- the poller simply stops firing -- but written
# down here because it is part of the bargain and belongs beside it.
DEADLINE_HOUR = 21

# The line the preview's own report starts with, and the hour to fall back
# to when that report never made it into the journal. Tying the window to
# the preview keeps a "stop" from yesterday out of tonight's answer.
PREVIEW_REPORT = "18:00 preview"
PREVIEW_HOUR = 17           # 17:00, not 18:00: a routine that fires a few
                            # minutes early must still open its own window

# Both lists are matched on the whole reply, or on its first word, so a
# forecast that happens to contain "no" somewhere cannot be read as an
# answer. STOP is checked first on purpose: "לא, שלח" is a person changing
# their mind mid-sentence, and the safer reading of it is to hold.
STOP = ("עצור", "עצרי", "עצרו", "לא", "בטל", "בטלי", "אל תשלח", "אל תשלחי",
        "רגע", "חכה", "stop", "no", "cancel", "hold", "wait",
        "don't send", "dont send")
GO = ("כן", "אישור", "מאושר", "אשר", "שלח", "שלחי", "אוקיי", "אוקי", "סבבה",
        "ok", "okay", "yes", "go", "send", "approved", "👍", "✅", "👌")

# Punctuation somebody types after a one-word answer. Stripped before the
# comparison so "עצור!" and "ok." are answers and not near-misses.
EDGE = " \t\r\n.!?,;:\"'״׳`*_-–—()[]…"


def normalise(text):
    """One line, lower case, no decoration -- ready to compare."""
    return " ".join(str(text or "").split()).strip(EDGE).lower()


def verdict(text):
    """"stop", "go", or "" when the reply is neither."""
    said = normalise(text)
    if not said:
        return ""
    for words, answer in ((STOP, "stop"), (GO, "go")):
        for word in words:
            if said == word or said.startswith(word + " ") \
                    or said.startswith(word + ","):
                return answer
    return ""


def _text(message):
    """Whatever a journal row is carrying, as a string.

    Green-API spells the body four different ways depending on how the
    message was typed -- plain, with a link preview, quoting something, or
    as a caption -- and a reply to the preview is very likely to be a quote
    of it. Missing one of those spellings would mean a "stop" that was
    typed, sent, and then ignored.
    """
    for key in ("textMessage", "caption"):
        value = message.get(key)
        if value:
            return str(value)
    extended = message.get("extendedTextMessage")
    if isinstance(extended, dict):
        return str(extended.get("text") or "")
    return str(extended or "")


def incoming(ident, token, minutes=1440):
    """The other journal. Mirrors audit_reminders._fetch, retries and all."""
    base = (os.environ.get("GREENAPI_URL") or "").rstrip("/")
    url = "%s/waInstance%s/lastIncomingMessages/%s?minutes=%d" % (
        base, ident, token, minutes)
    wait = 2
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
        except urllib.error.URLError:
            pass
        if attempt < 2:
            time.sleep(wait)
            wait *= 3
    raise RuntimeError("Green-API's incoming journal did not answer after "
                       "three tries")


def preview_at(rows, mine, now=None):
    """When tonight's preview was filed, as a unix time, or None.

    The report line is used as the anchor rather than the preview messages
    themselves because it is the one thing in the chat that says *which
    run* this was, and report.py already puts it there for every routine.

    **Only today's counts.** The journal reaches back a full day, so last
    evening's preview is still in it at six o'clock tonight -- and taking
    that as the anchor would open the window wide enough for a reply about
    last night's forecast to hold tonight's.
    """
    now = now or dt.datetime.now(PANAMA)
    today = now.astimezone(PANAMA).date()
    when = None
    for m in rows:
        if m.get("chatId") != mine:
            continue
        text = _text(m)
        if not text.startswith("#SHOKOGI-RUN"):
            continue
        if PREVIEW_REPORT not in text.split("|")[0]:
            continue
        stamp = m.get("timestamp") or 0
        if dt.datetime.fromtimestamp(stamp, PANAMA).date() != today:
            continue
        if stamp > (when or 0):
            when = stamp
    return when


def replies(rows, mine, floor):
    """Messages a person put in the school's own chat after `floor`.

    Everything this system writes there carries a marker -- report.py's
    #SHOKOGI-RUN and snapshot.py's own -- so anything without one was
    typed by somebody. That is the whole test, and it holds because the
    chat has no other use: 39 messages in it over the last day, every one
    of them ours.
    """
    out = []
    for m in rows:
        if m.get("chatId") != mine:
            continue
        stamp = m.get("timestamp") or 0
        if stamp < floor:
            continue
        text = _text(m)
        if not text.strip() or text.lstrip().startswith("#SHOKOGI"):
            continue
        out.append((stamp, text))
    return sorted(out)


def _floor(preview, now):
    """The moment after which a reply is about tonight's forecast."""
    if preview:
        return preview
    start = now.astimezone(PANAMA).replace(hour=PREVIEW_HOUR, minute=0,
                                           second=0, microsecond=0)
    if now < start:
        start = now - dt.timedelta(hours=2)
    return start.timestamp()


def fetch(ident="", token="", minutes=1440):
    """Both journals, each best-effort: (outgoing, incoming, reached_either).

    Separate from state() so one caller can ask two questions of one pair
    of fetches. That matters now: from 24/9/2026 the forecast is driven by
    a tick that fires every ten minutes all evening, and each tick needs
    both "did the office answer" and "has it already gone out" -- which is
    two journal reads a tick, or one, depending on nothing but this split.
    """
    ident = ident or os.environ.get("GREENAPI_ID", "")
    token = token or os.environ.get("GREENAPI_TOKEN", "")
    out, inc, reached = [], [], False
    try:
        out = A.journal(ident, token, minutes=minutes)
        reached = True
    except Exception:                                           # noqa: BLE001
        pass
    try:
        inc = incoming(ident, token, minutes=minutes)
        reached = True
    except Exception:                                           # noqa: BLE001
        pass
    return out, inc, reached


def state(ident="", token="", now=None, minutes=1440, journals=None):
    """What the office said about tonight's forecast, if anything.

        {"decision": "stop" | "go" | "silent" | "unknown",
         "said": the reply verbatim, "when": unix time or 0,
         "preview": unix time of tonight's preview, or 0}

    "unknown" means neither journal could be read. It is kept distinct from
    "silent" because the two deserve opposite treatment under REQUIRE_YES,
    and because a caller that cannot tell them apart will eventually decide
    that an unreachable gateway is consent.

    `journals` takes a (outgoing, incoming, reached) triple from fetch(),
    for a caller that has already paid for it.
    """
    now = now or dt.datetime.now(PANAMA)
    mine = snapshot.self_chat()

    out, inc, reached = (journals if journals is not None
                         else fetch(ident, token, minutes))

    if not reached:
        return {"decision": "unknown", "said": "", "when": 0, "preview": 0}

    preview = preview_at(out, mine, now) or 0
    floor = _floor(preview, now)
    said = replies(out, mine, floor) + replies(inc, mine, floor)
    said.sort()

    # The last answer wins. He is allowed to change his mind between 17:30
    # and 18:00, and a "stop" typed at 17:35 and withdrawn at 17:50 must
    # not still be holding the send.
    answer, when, words = "", 0, ""
    for stamp, text in said:
        got = verdict(text)
        if got:
            answer, when, words = got, stamp, text
    return {"decision": answer or "silent", "said": words,
            "when": when, "preview": preview}


def held(st=None, require_yes=None):
    """True when the 18:00 forecast must not go out. Reason as the second value."""
    st = st if st is not None else state()
    strict = REQUIRE_YES if require_yes is None else require_yes
    if st["decision"] == "stop":
        return True, "the office said: %s" % normalise(st["said"])[:60]
    if not strict:
        return False, ""
    if st["decision"] == "go":
        return False, ""
    if st["decision"] == "unknown":
        return True, "no answer could be read from WhatsApp, and nothing " \
                     "goes out unapproved"
    return True, "nobody approved tonight's forecast"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", action="store_true",
                    help="what the office said about tonight's forecast")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.state:
        ap.error("--state is the only thing to ask for")

    st = state()
    stop, why = held(st)
    st["held"] = stop
    st["why"] = why
    if a.json:
        print(json.dumps(st, ensure_ascii=False))
        return 0
    print("  preview   %s" % (dt.datetime.fromtimestamp(st["preview"], PANAMA)
                              .strftime("%m-%d %H:%M") if st["preview"]
                              else "not filed tonight"))
    print("  decision  %s" % st["decision"])
    if st["said"]:
        print("  said      %s" % normalise(st["said"])[:80])
    print("  the 18:00 forecast %s%s"
          % ("is HELD" if stop else "will go out", (" — " + why) if why else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
