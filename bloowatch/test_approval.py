#!/usr/bin/env python3
"""The word that holds a send, and the silence that does not.

approval.py sits between the 17:30 preview and two hundred customers, and
it has exactly two ways to be wrong. It can read "נראה מעולה" as an
objection and leave both groups with nothing; or it can miss a typed
"עצור" and send anyway, which is the first time in three weeks the owner
asked for a say and the one time it would not have been honoured.

Everything below is offline. Both journals are handed in as lists, which
is the shape Green-API returns, so the parsing is exercised without a
gateway and without the risk of a test putting a message on WhatsApp.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import datetime as dt
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import approval as Ap                                           # noqa: E402
import audit_reminders as A                                     # noqa: E402
import snapshot                                                 # noqa: E402

MINE = snapshot.self_chat()
ELSEWHERE = "120363000000000000@g.us"

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + str(detail)) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def msg(text, at, chat=MINE, key="textMessage"):
    return {"chatId": chat, "timestamp": at, key: text}


def run(out, inc, now, require_yes=False):
    """state() and held(), with both journals faked.

    `require_yes` defaults to False rather than to the module's own setting
    so that the veto half of this file keeps testing veto semantics after
    the owner switched the shipped default to the gate on 24/9/2026. Both
    bargains have to keep working: he can switch back, and the checks that
    prove the reading of a reply -- which word, whose chat, when -- are the
    same either way.
    """
    real_out, real_inc = A.journal, Ap.incoming
    try:
        A.journal = lambda i, t, minutes=1440: list(out)
        Ap.incoming = lambda i, t, minutes=1440: list(inc)
        st = Ap.state("id", "tok", now=now)
    finally:
        A.journal, Ap.incoming = real_out, real_inc
    stop, why = Ap.held(st, require_yes=require_yes)
    return st, stop, why


def main():
    # ---- the words themselves -------------------------------------------
    for text in ("עצור", "עצור!", "  עצור  ", "*עצור*", "לא", "No.",
                 "stop", "אל תשלח", "לא, תוריד את הגרף", "רגע"):
        check("%r holds the send" % text, Ap.verdict(text) == "stop",
              Ap.verdict(text))
    for text in ("כן", "אישור", "ok", "OK!", "👍", "שלח", "yes, go"):
        check("%r lets it go" % text, Ap.verdict(text) == "go",
              Ap.verdict(text))

    # The dangerous middle. A remark is not an answer, and reading one as a
    # "stop" costs the whole evening's send.
    for text in ("נראה מעולה", "יפה מאוד", "the chart is nice",
                 "מחר יש לי שיעור ב-7", ""):
        check("%r is not an answer at all" % text, Ap.verdict(text) == "",
              Ap.verdict(text))

    # A forecast quoted back at us contains every word in both lists. Only
    # the start of a reply counts, which is what keeps that from mattering.
    long = ("ערב טוב חברים, מחר גלים של 0.5 מטר, כן אפשר לשלוח, "
            "אין סיבה לא")
    check("a long message that merely contains the words is not an answer",
          Ap.verdict(long) == "", Ap.verdict(long))

    # "לא, שלח" is somebody changing their mind mid-sentence. Holding is the
    # recoverable reading of it; sending is not.
    check("stop is read before go when a reply has both",
          Ap.verdict("לא, שלח") == "stop", Ap.verdict("לא, שלח"))

    # ---- how a reply is spelled -----------------------------------------
    check("a plain message is read", Ap._text({"textMessage": "עצור"}) == "עצור")
    check("a reply that quotes the preview is read",
          Ap._text({"extendedTextMessage": {"text": "עצור"}}) == "עצור")
    check("a caption is read", Ap._text({"caption": "עצור"}) == "עצור")
    check("and a row carrying nothing is empty, not an exception",
          Ap._text({}) == "")

    # ---- the window -----------------------------------------------------
    now = dt.datetime(2026, 9, 24, 18, 0, tzinfo=Ap.PANAMA)
    at = lambda h, m: dt.datetime(2026, 9, 24, h, m,
                                  tzinfo=Ap.PANAMA).timestamp()
    yesterday = dt.datetime(2026, 9, 23, 17, 35,
                            tzinfo=Ap.PANAMA).timestamp()
    preview = {"chatId": MINE, "timestamp": at(17, 30),
               "textMessage": "#SHOKOGI-RUN 18:00 preview | auto 01x | "
                              "09-24 22:30Z | RESULT built=he,en"}
    other = {"chatId": MINE, "timestamp": at(17, 45),
             "textMessage": "#SHOKOGI-RUN 19:00 rota | auto 01y | "
                            "09-24 00:12Z | RESULT rota=sent"}

    st, stop, _ = run([preview, msg("עצור", at(17, 40))], [], now)
    check("a stop typed after the preview holds the send", stop, st)
    check("and the report can say what was said", st["said"] == "עצור", st)

    st, stop, _ = run([preview, msg("עצור", at(17, 20))], [], now)
    check("a message from before the preview is not an answer to it",
          not stop, st)

    st, stop, _ = run([preview, msg("עצור", yesterday)], [], now)
    check("and last night's stop does not hold tonight's forecast",
          not stop, st)

    # Last night's preview is still inside the journal's day-long window at
    # six o'clock tonight. Anchoring on it would reopen a window wide enough
    # for a reply about yesterday's forecast to hold today's.
    stale = {"chatId": MINE, "timestamp": yesterday,
             "textMessage": "#SHOKOGI-RUN 18:00 preview | auto 01z | "
                            "09-23 22:30Z | RESULT built=he,en"}
    check("last night's preview is not tonight's anchor",
          Ap.preview_at([stale], MINE, now) is None,
          Ap.preview_at([stale], MINE, now))
    st, stop, _ = run([stale, msg("עצור", yesterday + 300)], [], now)
    check("so a reply typed right after it does not hold tonight's send",
          not stop, st)

    # ---- the last word wins ---------------------------------------------
    st, stop, _ = run([preview, msg("עצור", at(17, 35)),
                       msg("כן שלח", at(17, 50))], [], now)
    check("a stop withdrawn before 18:00 does not hold the send",
          not stop, st)
    st, stop, _ = run([preview, msg("אישור", at(17, 35)),
                       msg("רגע", at(17, 55))], [], now)
    check("and a stop after an approval does hold it", stop, st)

    # ---- our own lines are not replies ----------------------------------
    st, stop, _ = run([preview, other], [], now)
    check("the routines' own reports are never read as answers",
          st["decision"] == "silent" and not stop, st)
    snap = {"chatId": MINE, "timestamp": at(19, 5),
            "textMessage": snapshot.MARKER + " 2026-09-25\n{}"}
    st, stop, _ = run([preview, snap], [], now)
    check("nor is the board snapshot", st["decision"] == "silent", st)

    # ---- which journal it arrives in ------------------------------------
    # A message typed on the linked phone is sent *by* the account and lands
    # in the outgoing journal; one from anywhere else lands in the incoming
    # one. Reading a single feed works until the evening it does not.
    st, stop, _ = run([preview], [msg("עצור", at(17, 40))], now)
    check("a stop in the incoming journal holds the send too", stop, st)

    # ---- the wrong chat --------------------------------------------------
    st, stop, _ = run([preview, msg("עצור", at(17, 40), chat=ELSEWHERE)],
                      [], now)
    check("a stop in some other chat is not an answer", not stop, st)

    # ---- silence ---------------------------------------------------------
    st, stop, why = run([preview], [], now)
    check("under the veto, silence sends", st["decision"] == "silent"
          and not stop, (st, why))

    st, stop, _ = run([preview], [], now, require_yes=True)
    check("and under the gate, silence holds instead", stop, st)
    st, stop, _ = run([preview, msg("אישור", at(17, 40))], [], now,
                      require_yes=True)
    check("under the gate an approval releases it", not stop, st)

    # A stop is still a stop after an approval, under the gate too: he is
    # allowed to approve and then change his mind before the next tick.
    st, stop, _ = run([preview, msg("אישור", at(17, 35)),
                       msg("עצור", at(17, 55))], [], now, require_yes=True)
    check("and a stop after an approval still holds it", stop, st)

    # ---- no preview at all ------------------------------------------------
    # The 18:00 run died, or never ran. Under the veto nothing was objected
    # to, so the send that has been going out every night since long before
    # any of this still goes.
    st, stop, _ = run([], [], now)
    check("under the veto, a preview that never went out holds nothing",
          st["preview"] == 0 and not stop, st)
    st, stop, _ = run([msg("עצור", at(17, 40))], [], now)
    check("but a stop typed this evening still counts without one",
          stop, st)

    # Under the gate it is the opposite, and this is the sharp edge of the
    # bargain the owner chose: a preview that never went out is nothing for
    # him to approve, so the groups get nothing. It is why the preview's own
    # failure is loud and why 19:50 writes the state into the journal.
    st, stop, why = run([], [], now, require_yes=True)
    check("under the gate, no preview means no send", stop, (st, why))

    # ---- an unreachable gateway -------------------------------------------
    def boom(*a, **k):
        raise RuntimeError("Green-API did not answer")

    real_out, real_inc = A.journal, Ap.incoming
    try:
        A.journal, Ap.incoming = boom, boom
        st = Ap.state("id", "tok", now=now)
    finally:
        A.journal, Ap.incoming = real_out, real_inc
    check("neither journal readable is 'unknown', not 'silent'",
          st["decision"] == "unknown", st)
    check("under the veto an unreadable journal does not hold the send",
          not Ap.held(st, require_yes=False)[0], st)
    check("under the gate it does, because nothing was approved",
          Ap.held(st, require_yes=True)[0], st)

    # One journal answering is enough: a 429 on one endpoint must not turn
    # into "we could not tell", which under the gate would mean no send.
    real_out, real_inc = A.journal, Ap.incoming
    try:
        A.journal = boom
        Ap.incoming = lambda i, t, minutes=1440: [msg("עצור", at(17, 40))]
        st = Ap.state("id", "tok", now=now)
    finally:
        A.journal, Ap.incoming = real_out, real_inc
    check("one journal is enough to hear an answer",
          st["decision"] == "stop", st)

    # ---- the default is the one the owner is living with ------------------
    # He asked for the veto on 24/9/2026, read what it did, and asked for
    # the gate instead: "במקום לשלוח אוטומטי ב-18:00, לשלוח ב-18:00 לווצאפ
    # העסק את שניהם לאישור". Pinned so that a later edit here is a decision
    # somebody makes rather than a line that drifts.
    check("the shipped default is the gate: nothing goes out unapproved",
          Ap.REQUIRE_YES is True)
    check("and the deadline is written down beside it",
          Ap.DEADLINE_HOUR == 21, Ap.DEADLINE_HOUR)
    st, stop, why = run([preview], [], now, require_yes=None)
    check("held() with no argument follows that default",
          stop and "approved" in why, (st, why))

    # ---- what stops the tick from repeating itself ------------------------
    # Two guards, and they are not the same guard. already_out reads the
    # groups' own chats and stops the browser; send.py --once-today reads
    # the text and stops the message. The journal lags a few seconds, so a
    # tick firing while the last one is still sending sees nothing in the
    # first -- and the second is all that is left.
    import evening as E
    import send as S
    import watch_sends as W

    groups = S.book()["groups"]
    he = S.target("surfers_he", groups)["jid"]
    en = S.target("surfers_en", groups)["jid"]
    tonight = int(at(18, 7))

    rows = [{"chatId": he, "timestamp": tonight,
             "textMessage": W.FORECAST_HE + " ..."}]
    check("a group that has tonight's forecast is reported as served",
          E.already_out(rows, ["he", "en"], now=now) == ["he"],
          E.already_out(rows, ["he", "en"], now=now))

    # The forecast travels as a caption on the chart most nights, and a
    # caption is a different field. Reading only textMessage would make
    # every tick think nothing had gone out.
    rows = [{"chatId": en, "timestamp": tonight,
             "caption": W.FORECAST_EN + " ..."}]
    check("a forecast sent as a chart caption counts too",
          E.already_out(rows, ["he", "en"], now=now) == ["en"],
          E.already_out(rows, ["he", "en"], now=now))

    rows = [{"chatId": he, "timestamp": int(yesterday),
             "textMessage": W.FORECAST_HE + " ..."}]
    check("last night's does not",
          E.already_out(rows, ["he", "en"], now=now) == [],
          E.already_out(rows, ["he", "en"], now=now))

    # The same blind spot, one layer down. already_said is what actually
    # refuses the duplicate, and until 24/9/2026 it never looked at a
    # caption either -- which is the field the forecast uses.
    real_open = urllib.request.urlopen

    def answer(rows):
        def fake(url, timeout=None):
            body = json.dumps(rows).encode("utf-8")
            r = io.BytesIO(body)
            r.__enter__ = lambda: r
            r.__exit__ = lambda *a: False
            return r
        return fake

    where = {"jid": he}
    text = "ערב טוב חברים — גלים 0.5"
    try:
        urllib.request.urlopen = answer([{"chatId": he, "caption": text}])
        check("already_said sees a message that went as a caption",
              S.already_said(where, text, "1", "t"))
        urllib.request.urlopen = answer([{"chatId": en, "caption": text}])
        check("but only in the chat it is asked about",
              not S.already_said(where, text, "1", "t"))
    finally:
        urllib.request.urlopen = real_open

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
