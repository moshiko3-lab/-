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
  * due but not delivered -> **1**, whether the gateway said so or the
                             journal shows nothing arrived

The last one is the whole file. A version that returns 0 when the gateway
accepts a message that never reaches WhatsApp puts the system straight back
where it was, and it would pass every other check in this directory.

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
                print(json.dumps({"name": one["name"], "chatId": where["jid"],
                                  "code": 200 if not self.batch_status else 500},
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


def run(stub_args, argv=()):
    old = sys.argv
    sys.argv = ["remind.py"] + list(argv)
    try:
        with Stub(*stub_args) as s:
            return R.main(), s
    finally:
        sys.argv = old


def main():
    # --- an empty slot is a clean, silent zero ------------------------
    code, s = run(([lesson(200)],))
    check("a slot with nobody due exits 0", code == 0, "exit %s" % code)
    check("and sends nothing", s.sent == [], repr(s.sent))

    # The journal entries Green-API would return. `ours` is a message to the
    # person we actually wrote to; `somebody_else` is the 19:00 rota going
    # out to the staff group at the same moment.
    mine = R.send.target("+972500000000", {})["jid"]
    now = int(dt.datetime.now(rota.PANAMA).timestamp())
    ours = [{"chatId": mine, "textMessage": "reminder", "timestamp": now}]
    somebody_else = [{"chatId": "staff-group@g.us",
                      "caption": "*לו״ז יום ג׳*", "timestamp": now}]

    # --- the ordinary good slot ---------------------------------------
    code, s = run(([lesson(50)], 0, ours))
    check("a slot with somebody due sends them", len(s.sent) == 1,
          repr([x.get("name") for x in s.sent]))
    check("and exits 0 when that person's own chat shows it", code == 0,
          "exit %s" % code)

    # --- the failure that hid, in both its shapes ---------------------
    # The gateway itself refused: run_batch already knows, and the status
    # must survive all the way out rather than being swallowed.
    code, _ = run(([lesson(50)], 1, ours))
    check("a gateway failure exits 1", code == 1, "exit %s" % code)

    # And the quieter one: every call returned 200 and the journal shows
    # nothing left the building. This is the case a status-only check calls
    # a success, and it is the case that cost six reminders.
    code, _ = run(([lesson(50)], 0, []))
    check("a 200 that left no trace in the journal exits 1", code == 1,
          "exit %s" % code)

    # **Somebody else's message is not proof.** The first version of this
    # counted every outgoing message in the window, so a rota to the staff
    # group satisfied it while the reminders themselves were lost. That is
    # the same mistake that let a missing forecast pass for a whole day:
    # evidence something else could have produced is not evidence.
    code, _ = run(([lesson(50)], 0, somebody_else))
    check("a message to a different chat is not proof the reminder arrived",
          code == 1, "exit %s" % code)

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
