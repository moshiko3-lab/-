#!/usr/bin/env python3
"""The check that notices an evening send nobody made.

Written after 13/09/2026, when the 18:00 forecast routine fired on time,
stopped on a permission prompt, and sat there until the owner asked at
19:00 why the group was empty. A run that hangs reports nothing, so the
only honest source is Green-API's own outgoing journal.

Two things are pinned, and they are the two that were got wrong.

**The shape of a journal entry.** The 19:00 rota is not a text message. It
is one imageMessage whose `caption` carries the whole rota, and the first
version of the reader knew only about `textMessage` -- so it read the
biggest send of the evening as an empty string and called it missing. It
did that against real data on the first run. A nightly false alarm is
worse than no check, because by the end of the week it is the thing people
scroll past.

**What counts as evidence.** The heading has to be tomorrow's and the chat
has to be the right one. Yesterday's rota is still sitting in the same
group; if the marker matched it, the check would pass forever. And the
same heading goes to every instructor privately, so a message to one of
them is not evidence that the group was written to.

Nothing here touches the network.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audit_reminders as A                                     # noqa: E402
import rota                                                     # noqa: E402
import watch_sends as W                                         # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main():
    # --- the journal entry shapes that actually occur -------------------
    journal = [
        {"chatId": "g1@g.us", "typeMessage": "imageMessage",
         "caption": "*לו״ז יום ב׳ 15/9*", "fileName": "board.png"},
        {"chatId": "g2@g.us", "typeMessage": "textMessage",
         "textMessage": "*ערב טוב חברים🌞*"},
        {"chatId": "p1@c.us", "typeMessage": "extendedTextMessage",
         "extendedTextMessage": {"text": "היי נאור 👋"}},
    ]
    seen = A.by_chat(journal)
    check("an image caption is read as the message text",
          "*לו״ז יום ב׳ 15/9*" in seen.get("g1@g.us", []),
          repr(seen.get("g1@g.us")))
    check("a plain text message is read", "*ערב טוב חברים🌞*"
          in seen.get("g2@g.us", []))
    check("an extended text message is read",
          "היי נאור 👋" in seen.get("p1@c.us", []))
    check("a message is filed under its own chat only",
          set(seen) == {"g1@g.us", "g2@g.us", "p1@c.us"}, repr(sorted(seen)))

    # --- a rate-limited journal is not an answer ------------------------
    # Green-API rate-limits the journal, and the two safety-net runs land
    # minutes apart on a busy evening. A 429 took the whole check down with
    # a traceback the first time it happened, which would have meant no
    # recovery on exactly the night recovery was needed.
    import urllib.error
    import urllib.request
    calls = {"n": 0}

    def responder(code, body=b'[{"chatId":"x@c.us","textMessage":"hi"}]'):
        def opener(url, timeout=0):
            calls["n"] += 1
            if calls["n"] <= 2 and code:
                raise urllib.error.HTTPError(url, code, "nope", None, None)

            class R:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return body
            return R()
        return opener

    real_open, real_sleep = urllib.request.urlopen, A.time.sleep
    A.time.sleep = lambda s: None
    try:
        urllib.request.urlopen = responder(429)
        calls["n"] = 0
        got = A.outgoing("1", "t")
        check("a 429 is retried rather than raised",
              got == {"x@c.us": ["hi"]}, repr(got))
        check("and it took the retries to get there", calls["n"] == 3,
              "attempts: %d" % calls["n"])

        # A bad token is an answer, not a blip: retrying it wastes the
        # window and tells nobody anything.
        urllib.request.urlopen = responder(401)
        calls["n"] = 0
        raised = False
        try:
            A.outgoing("1", "t")
        except urllib.error.HTTPError:
            raised = True
        check("a 401 raises straight away", raised and calls["n"] == 1,
              "raised=%s attempts=%d" % (raised, calls["n"]))
    finally:
        urllib.request.urlopen, A.time.sleep = real_open, real_sleep

    # --- yesterday's message must not answer today's question -----------
    # This is the one that got through. The forecast opens with the same
    # greeting every night, and the check asked "is that greeting anywhere
    # in the last day". On 14/09/2026 the 18:00 forecast never went out and
    # this check said everything was fine, because last night's forecast was
    # still inside the window. It could never have caught a missing
    # forecast; it would have passed for ever.
    now = dt.datetime.now(W.PANAMA).replace(microsecond=0)
    last_night = now - dt.timedelta(hours=24)
    journal = [
        {"chatId": "g2@g.us", "typeMessage": "textMessage",
         "textMessage": W.FORECAST_HE, "timestamp": int(last_night.timestamp())},
    ]
    due_tonight = now.replace(hour=18, minute=0, second=0)
    seen = A.by_chat(journal, since=due_tonight - dt.timedelta(minutes=10))
    check("last night's forecast does not count as tonight's",
          not seen.get("g2@g.us"), repr(seen))

    tonight = dict(journal[0])
    tonight["timestamp"] = int(due_tonight.timestamp()) + 120
    seen = A.by_chat([tonight], since=due_tonight - dt.timedelta(minutes=10))
    check("but one sent tonight does", seen.get("g2@g.us") == [W.FORECAST_HE],
          repr(seen))

    # A routine that starts a minute early must still count. The cutoff is
    # deliberately a few minutes before the deadline, not the deadline.
    early = dict(journal[0])
    early["timestamp"] = int(due_tonight.timestamp()) - 120
    seen = A.by_chat([early], since=due_tonight - dt.timedelta(minutes=10))
    check("and so does one sent a couple of minutes early",
          seen.get("g2@g.us") == [W.FORECAST_HE], repr(seen))

    check("no cutoff still means everything, for callers that want that",
          A.by_chat(journal).get("g2@g.us") == [W.FORECAST_HE])

    # --- the forecast markers must match the real message ---------------
    # Compared against the source of forecast_message rather than copied
    # into it, so rewording the greeting fails here instead of quietly
    # making every evening look fine forever.
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "forecast_message.py"), encoding="utf-8") as f:
        source = f.read()
    check("the Hebrew forecast marker still appears in forecast_message",
          W.FORECAST_HE in source, W.FORECAST_HE)
    check("the English forecast marker still appears in forecast_message",
          W.FORECAST_EN in source, W.FORECAST_EN)

    # --- the rota marker is tomorrow's, and only tomorrow's -------------
    tom = dt.date(2026, 9, 15)
    head = rota._heading(tom.isoformat(), "he")
    yesterday = rota._heading((tom - dt.timedelta(days=1)).isoformat(), "he")
    check("the rota marker names tomorrow", head in "*לו״ז %s*" % head)
    check("and it differs from the day before", head != yesterday,
          "%r == %r" % (head, yesterday))
    real = rota.group([], tom.isoformat(), "he")
    check("the marker appears in a rota the code actually builds",
          head in real, real[:60])

    # --- nothing is late before its time --------------------------------
    day = dt.date(2026, 9, 14)
    items = W.due_times(day)
    check("four things are due each evening", len(items) == 4,
          "got %d" % len(items))
    check("the forecast is due at 18:00",
          items[0]["due"].strftime("%H:%M") == "18:00")
    check("the staff rota at 19:00",
          items[2]["due"].strftime("%H:%M") == "19:00")
    check("the personal rotas at 19:15",
          items[3]["due"].strftime("%H:%M") == "19:15")

    at_1810 = dt.datetime.combine(day, dt.time(18, 10), tzinfo=W.PANAMA)
    late = [i for i in items
            if at_1810 >= i["due"] + dt.timedelta(minutes=W.GRACE_MINUTES)]
    check("ten minutes past due is not yet late", not late,
          "flagged %r" % [i["what"] for i in late])

    at_1830 = dt.datetime.combine(day, dt.time(18, 30), tzinfo=W.PANAMA)
    late = [i["what"] for i in items
            if at_1830 >= i["due"] + dt.timedelta(minutes=W.GRACE_MINUTES)]
    check("half past six, both forecasts are late and nothing else is",
          late == ["forecast_he", "forecast_en"], repr(late))

    # --- a forecast the office stopped is not a forecast that went astray -
    # Without this the 18:25 net finds it missing, the recovery routine
    # sends it, and the veto the owner asked for on 24/9/2026 is undone
    # half an hour later by the safety net built to protect that same
    # message. The staff rota, which nobody vetoed, must still be checked.
    import approval as Ap
    os.environ.setdefault("GREENAPI_ID", "1")
    os.environ.setdefault("GREENAPI_TOKEN", "t")
    os.environ.setdefault("GREENAPI_URL", "https://x")
    real_journal, real_state, real_personal = A.journal, Ap.state, W._personal
    try:
        A.journal = lambda i, t, minutes=1440: []
        W._personal = lambda said, tom, book: []
        at_1930 = dt.datetime.combine(day, dt.time(19, 30), tzinfo=W.PANAMA)

        Ap.state = lambda *a, **k: {"decision": "silent", "said": "",
                                    "when": 0, "preview": 0}
        missing = [m["what"] for m in W.audit(now=at_1930)]
        check("with nothing sent and nobody objecting, everything is missing",
              missing == ["forecast_he", "forecast_en", "staff_rota"],
              repr(missing))

        Ap.state = lambda *a, **k: {"decision": "stop", "said": "עצור",
                                    "when": 1, "preview": 1}
        missing = [m["what"] for m in W.audit(now=at_1930)]
        check("a forecast the office held is not reported as missing",
              "forecast_he" not in missing and "forecast_en" not in missing,
              repr(missing))
        check("and the rota, which nobody held, still is",
              missing == ["staff_rota"], repr(missing))
    finally:
        A.journal, Ap.state, W._personal = real_journal, real_state, real_personal

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
