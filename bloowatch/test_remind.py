#!/usr/bin/env python3
"""The check that a reminder slot can no longer fail quietly.

On 14/09/2026 four reminder slots fired, were recorded as SUCCEEDED, and sent
nothing. Six instructors went unreminded and two of their lessons had already
started by the time anybody noticed. The slot was two commands then -- build
the plan, then send it -- and a run that stopped between them was
indistinguishable from a slot with nobody to remind: both silent, both clean,
both reported as success.

`remind.py` is one command so that gap cannot exist, and its exit status is
the claim. What is pinned here is exactly that claim, in the three shapes it
has to hold:

  * nobody due            -> 0, and nothing is sent
  * everybody due sent    -> 0
  * the gateway refused   -> **1**

What the journal has not shown *yet* is not a failure and does not flip the
status. It lags a few seconds behind a send, and on 15/09/2026 at 09:40 the
first version of this reported Yonatan's reminder as not sent while it sat
in the journal under the very id the gateway had just returned. An alert
that cries wolf is one nobody reads by Friday.

What the journal is still good for is the count, and for refusing to accept
the wrong evidence: matching is on the message id Green-API handed back, so
another message to the same instructor can never stand in for the reminder.
Whether a reminder truly arrived is audit_reminders' question, asked hours
later when no lag can colour the answer.

Touches no network: the board, the gateway and the journal are all stubbed.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import remind as R                                             # noqa: E402
import rota                                                    # noqa: E402

TESTER = "TEST INSTRUCTOR"
fails = []


SENT_ID = "3EB0TESTID"


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


class Stub:
    """One run of remind.main() with the world replaced."""

    def __init__(self, lessons, batch_status=0, journal=None):
        self.lessons = lessons
        self.batch_status = batch_status
        # The journal Green-API would return: a list of entries, or None for
        # a journal that will not answer at all.
        self.journal = journal
        self.sent = []

    def __enter__(self):
        import export_catalog
        import audit_reminders
        self.real = (rota.login, rota.lessons_for, R.send.run_batch,
                     audit_reminders.journal, R.send.pick_gateway,
                     export_catalog.crew_numbers)
        rota.login = lambda: ("s", "b")
        rota.lessons_for = lambda s, b, d: self.lessons
        R.send.pick_gateway = lambda: ("green", "1", "t")
        # The catalog holds real phone numbers. The check is about what the
        # exit status claims, not about who is in the crew, so it supplies
        # its own one-person crew rather than reading the real one.
        export_catalog.crew_numbers = lambda: [
            {"name": TESTER, "phone": "+972500000000"}]

        def run_batch(path, gateway, ident, token, dry_run, once_today):
            import json
            with open(path, encoding="utf-8") as f:
                self.sent = json.load(f)
            # run_batch's real contract: one JSON line per person, on stdout.
            for one in self.sent:
                where = R.send.target(one["phone"], {})
                # Green-API answers with an idMessage, and that id is what
                # the journal is matched on. A stub that omits it would let
                # the match pass on something looser than the real one.
                print(json.dumps(
                    {"name": one["name"], "chatId": where["jid"],
                     "code": 200 if not self.batch_status else 500,
                     "said": json.dumps({"idMessage": SENT_ID})},
                    ensure_ascii=False))
            return self.batch_status
        R.send.run_batch = run_batch

        def fake_journal(ident, token, minutes=1440):
            if self.journal is None:
                raise RuntimeError("journal unreadable")
            return self.journal
        audit_reminders.journal = fake_journal
        return self

    def __exit__(self, *a):
        import export_catalog, audit_reminders
        (rota.login, rota.lessons_for, R.send.run_batch,
         audit_reminders.journal, R.send.pick_gateway,
         export_catalog.crew_numbers) = self.real
        return False


def lesson(minutes_ahead, who=None):
    who = who or TESTER
    at = dt.datetime.now(rota.PANAMA) + dt.timedelta(minutes=minutes_ahead)
    return {"time": at.strftime("%H:%M"), "staff": [who], "students": [],
            "title": "SURF LESSON", "attendants": [], "duration": 60}


# The journal is asked more than once, seconds apart, because it lags. The
# wait is a name so the tests need not sit through it.
R.JOURNAL_WAIT = 0


def run(stub_args, argv=()):
    """One run, with everything it printed captured on the stub as `.out`."""
    import contextlib
    import io
    old = sys.argv
    sys.argv = ["remind.py"] + list(argv)
    buf = io.StringIO()
    try:
        with Stub(*stub_args) as s:
            with contextlib.redirect_stdout(buf), \
                 contextlib.redirect_stderr(buf):
                code = R.main()
            s.out = buf.getvalue()
            print(s.out, end="")
            return code, s
    finally:
        sys.argv = old


def main():
    # --- an empty slot is a clean, silent zero ------------------------
    code, s = run(([lesson(200)],))
    check("a slot with nobody due exits 0", code == 0, "exit %s" % code)
    check("and sends nothing", s.sent == [], repr(s.sent))

    # The journal entries Green-API would return. `ours` carries the id the
    # gateway handed back; `somebody_else` is the 19:00 rota going out to the
    # staff group at the same moment, and `wrong_id` is another message to
    # the very same instructor -- their evening rota, say.
    mine = R.send.target("+972500000000", {})["jid"]
    now = int(dt.datetime.now(rota.PANAMA).timestamp())
    ours = [{"chatId": mine, "idMessage": SENT_ID,
             "textMessage": "reminder", "timestamp": now}]
    somebody_else = [{"chatId": "staff-group@g.us", "idMessage": "3EB0OTHER",
                      "caption": "*לו״ז יום ג׳*", "timestamp": now}]
    wrong_id = [{"chatId": mine, "idMessage": "3EB0SOMETHINGELSE",
                 "textMessage": "your rota for tomorrow", "timestamp": now}]

    # --- the ordinary good slot ---------------------------------------
    code, s = run(([lesson(50)], 0, ours))
    check("a slot with somebody due sends them", len(s.sent) == 1,
          repr([x.get("name") for x in s.sent]))
    check("and exits 0 when the journal shows that very message", code == 0,
          "exit %s" % code)

    # --- the failure that must still be loud --------------------------
    # The gateway itself refused. run_batch already knows, and the status
    # must survive all the way out rather than being swallowed.
    code, _ = run(([lesson(50)], 1, ours))
    check("a gateway failure exits 1", code == 1, "exit %s" % code)

    # --- and the one that must not be ---------------------------------
    # Every call returned 200 and the journal has not caught up. It lags a
    # few seconds, and on 15/09/2026 at 09:40 this was reported as "not
    # sent" about a message already sitting in the journal under the id the
    # gateway had just returned. The count still says 0/1; the status does
    # not lie about it.
    code, st = run(([lesson(50)], 0, []))
    check("a journal that has not caught up does not fail the run",
          code == 0, "exit %s" % code)
    check("but it is not counted as confirmed either",
          "journal=0/1" in st.out, st.out[-200:])
    check("and the run says not to resend",
          "Do not resend" in st.out, st.out[-200:])

    # **Somebody else's message is not proof, and neither is another of
    # theirs.** The first version counted every outgoing message in the
    # window, so a rota to the staff group satisfied it while the reminders
    # were lost. Matching on the id closes the looser case too: the same
    # instructor's evening rota is a message in the right chat and still not
    # this one.
    for label, rows in (("to a different chat", somebody_else),
                        ("to the same person, but a different message",
                         wrong_id)):
        _, st = run(([lesson(50)], 0, rows))
        check("a message %s is not counted as the reminder" % label,
              "journal=0/1" in st.out, st.out[-200:])

    # An unreachable journal must not invent a failure: a network blip at
    # 05:10 would otherwise page somebody about reminders that went out fine.
    code, _ = run(([lesson(50)], 0, None))
    check("an unreadable journal does not fail a good send", code == 0,
          "exit %s" % code)

    # --- a board that cannot be read is not an empty board -------------
    class Boom:
        def __enter__(self):
            self.real = rota.login
            def bang():
                raise RuntimeError("login refused")
            rota.login = bang
            return self

        def __exit__(self, *a):
            rota.login = self.real
            return False

    old = sys.argv
    sys.argv = ["remind.py"]
    try:
        with Boom():
            code = R.main()
    finally:
        sys.argv = old
    check("an unreadable board exits 1, not 0", code == 1, "exit %s" % code)

    # --- the window is still the one the two slots step through --------
    # remind.py must not quietly widen it: a window wider than 30 minutes
    # reminds the same lesson from both slots, and people stop reading.
    import export_catalog
    real = export_catalog.crew_numbers
    export_catalog.crew_numbers = lambda: [
        {"name": TESTER, "phone": "+972500000000"}]
    try:
        inside, _ = R.due([lesson(50)], 35, 65)
        early, _ = R.due([lesson(20)], 35, 65)
        late, _ = R.due([lesson(80)], 35, 65)
    finally:
        export_catalog.crew_numbers = real
    check("a lesson 50 minutes out is this slot's", len(inside) == 1)
    check("one 20 minutes out belongs to the slot before", not early,
          repr(early))
    check("one 80 minutes out belongs to the slot after", not late,
          repr(late))

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
