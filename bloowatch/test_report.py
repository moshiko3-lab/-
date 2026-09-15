#!/usr/bin/env python3
"""A report must never be able to break the run it is reporting on.

That is the whole risk of this file. Every routine will call it, at the
end of work that has already succeeded -- the rota is sent, the reminders
are out -- and a note about that work must not be able to turn it into a
failure. A gateway that is down, a token that has expired, a journal that
refuses: each of those is a reason to lose the note, never a reason to
report the evening as broken.

The other half is that a report is a report and nothing else: it must not
be readable as a rota, a reminder or a snapshot, or the safety nets that
read the same journal would count it as a message that went to somebody.

Nothing here touches the network.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import report as R                                              # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def run(main_args, gateway=("green", "id", "tok"), send_result=(200, "{}"),
        raises=None):
    """report.main() with the gateway replaced by an answer."""
    real_pick, real_via, real_self = (R.send.pick_gateway, R.send.via_green,
                                      R.snapshot.self_chat)
    seen = []

    def via(where, text, path, ident, token):
        seen.append((where["jid"], text))
        if raises:
            raise raises
        return send_result

    R.send.pick_gateway = lambda: gateway
    R.send.via_green = via
    R.snapshot.self_chat = lambda: "50700000000@c.us"
    argv = sys.argv
    sys.argv = ["report.py"] + main_args
    try:
        return R.main(), seen
    finally:
        (R.send.pick_gateway, R.send.via_green,
         R.snapshot.self_chat) = real_pick, real_via, real_self
        sys.argv = argv


def main():
    # --- a good report goes out, and says so -----------------------------
    code, seen = run(["19:00 rota", "RESULT rota=sent board=photograph"])
    check("a report exits 0", code == 0, str(code))
    check("and one message is sent", len(seen) == 1, repr(seen))
    check("to the school's own chat", seen and seen[0][0].endswith("@c.us")
          and seen[0][0].startswith("507"), repr(seen))
    check("carrying the result verbatim",
          seen and "RESULT rota=sent board=photograph" in seen[0][1],
          repr(seen))

    # --- and every way it can fail leaves the run alone -------------------
    # This is the point of the file. A routine that did its work and then
    # could not file the paperwork did its work.
    code, seen = run(["19:00 rota", "RESULT rota=sent"],
                     gateway=("", None, None))
    check("no gateway still exits 0", code == 0, str(code))
    check("and nothing is sent", not seen, repr(seen))

    code, _ = run(["19:00 rota", "RESULT rota=sent"],
                  send_result=(401, "unauthorized"))
    check("a rejected report still exits 0", code == 0, str(code))

    code, _ = run(["19:00 rota", "RESULT rota=sent"],
                  raises=OSError("connection reset"))
    check("a report that raises still exits 0", code == 0, str(code))

    # --- a report is never mistaken for a message to a person ------------
    import audit_reminders as A
    import rota as RO
    import snapshot as S
    import watch_sends as W
    text = R.line("19:00 rota", "RESULT rota=sent", host="h")
    check("a report is not read as a reminder", not A.is_reminder(text))
    check("nor as either forecast",
          W.FORECAST_HE not in text and W.FORECAST_EN not in text)
    check("nor as a rota",
          RO._heading("2026-09-15", "he") not in text
          and RO._heading("2026-09-15", "en") not in text)
    check("nor as a snapshot", S.decode(text) is None)

    # --- and a snapshot is not read as a report --------------------------
    check("a snapshot is not read as a report",
          not S.encode("2026-09-15", []).startswith(R.MARKER))

    # --- a report cannot grow into a data dump ---------------------------
    # Without a cap the first routine to paste a traceback, a plan or a
    # crew list into its result publishes it. The journal is the school's
    # own chat, but a phone number belongs in neither.
    long = "x" * 5000
    check("an over-long result is cut down",
          len(R.line("x", long)) < R.MAX + 200, str(len(R.line("x", long))))
    check("and newlines cannot smuggle a second line in",
          "\n" not in R.line("x", "a\nb\nc"), repr(R.line("x", "a\nb\nc")))

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
