#!/usr/bin/env python3
"""The hold has to hold, and it has to be visible while it does.

Two failures this guards against, and the second is the subtle one.

**It must stop every path to WhatsApp, not the six routines we turned off.**
The owner declined to disable the two safety nets, and a net exists to
notice a message that did not go out and send it. If the hold lived only in
the routine list, the 19:50 net would have undone it the same evening.

**And it must never read like a quiet night.** `missing=0 all sent` is true
of an evening nobody stopped and of an evening the owner stopped, and
telling them apart in the morning is the whole job of the journal line. On
24/9 and 25/9/2026 two evenings were lost to exactly that sentence.

Nothing here touches the network, and nothing here can send.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hold                                                     # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main():
    # --- the hold list names real commands, and nothing else ---------------
    # A name in HELD that no longer matches a subcommand holds nothing at
    # all, and the only sign would be the message going out as usual.
    src = open(os.path.join(HERE, "evening.py"), encoding="utf-8").read()
    subs = sorted(set(
        line.split('sub.add_parser("')[1].split('"')[0]
        for line in src.splitlines() if 'sub.add_parser("' in line))
    check("every name on the hold list is a real evening.py subcommand",
          all(h in subs for h in hold.HELD),
          "held=%s commands=%s" % (list(hold.HELD), subs))

    # And what the safety nets look for maps onto those same names, or a
    # lifted send would go on being treated as stopped and never watched.
    check("and what the nets watch maps onto them too",
          all(v in subs for v in hold.WATCHED.values()),
          str(hold.WATCHED))

    # The reminders are deliberately outside it: stopping those means
    # instructors stop being told about lessons they are teaching, which is
    # a different decision and not one the owner has made.
    check("and the reminders are not swept up in it",
          "remind" not in hold.HELD and "reminders" not in hold.HELD)

    check("a job that is held says why, in words a person can act on",
          "hold.py" in hold.held("forecast")
          and hold.SINCE in hold.held("forecast"), hold.held("forecast"))
    check("and a job nobody held says nothing at all",
          hold.held("audit") == "", hold.held("audit"))

    # --- the switch is one line, and it is the only thing holding ----------
    # Coming back from the hold must not mean reconstructing an evening from
    # memory. If anything else had to be undone, this is where it would show.
    check("turning it back on is a single flag",
          "HOLD = True" in open(os.path.join(HERE, "hold.py"),
                                encoding="utf-8").read())
    for what in hold.HELD:
        hold.HOLD = False
        try:
            off = hold.held(what)
        finally:
            hold.HOLD = True
        check("'%s' runs again the moment the flag is off" % what, off == "")

    # --- and the real command refuses, rather than merely intending to ----
    # The check sits in main(), before the subcommand runs, so this is worth
    # running for real: with the hold on it cannot get past the first few
    # lines of main(), so it builds nothing and sends nothing.
    #
    # **Only the held ones are ever run bare.** On 27/11/2026 the owner
    # lifted the rota and the personal messages, this loop still named them,
    # and running the test sent five instructors tomorrow's rota at two in
    # the afternoon. A test that sends is not a test. The list is taken from
    # HELD itself now, so lifting something removes it from here by the same
    # edit -- and anything not held is only ever run with --dry-run below.
    env = dict(os.environ, SHOKOGI_NO_REPORT="1")
    for what in hold.HELD:
        p = subprocess.run([sys.executable, "evening.py", what],
                           cwd=HERE, env=env, capture_output=True, text=True,
                           timeout=120)
        out = p.stdout + p.stderr
        check("evening.py %s refuses while it is held" % what,
              p.returncode == 0 and "held" in out,
              "exit=%d %r" % (p.returncode, out[-300:]))
        # It must not have reached the sea, the board or the browser: those
        # cost 40 seconds and a third-party page, and a held run that still
        # does all the work would be held in name only.
        check("  and stops before it builds anything",
              "RESULT: %s held" % what in out, out[-300:])

    # The guard above is only as good as the rule behind it, so the rule is
    # the check: this file must never run a sending subcommand bare.
    tsrc = open(os.path.join(HERE, "test_hold.py"), encoding="utf-8").read()
    # A command named as a literal, with no --dry-run: the loop above passes
    # `what` and so never matches, and neither does reading the file.
    bare = [ln.strip() for ln in tsrc.splitlines()
            if '"evening.py", "' in ln and "--dry-run" not in ln]
    check("the test never runs an unheld evening.py command for real",
          not bare, str(bare))

    # A dry run still has to work. A week of hold with no way to look at the
    # system is how we come back to something nobody can check.
    p = subprocess.run([sys.executable, "evening.py", "rota", "--dry-run"],
                       cwd=HERE, env=env, capture_output=True, text=True,
                       timeout=180)
    check("but a dry run is not held", "RESULT: rota held" not in p.stdout,
          p.stdout[-200:] + p.stderr[-200:])

    # --- the net skips what is held, and watches what is not --------------
    # A blanket skip was right while everything was stopped. With the rota
    # live and the forecast held it would leave the live half with no net
    # under it, which is the failure the nets exist for.
    wsrc = open(os.path.join(HERE, "watch_sends.py"), encoding="utf-8").read()
    check("the net asks per item, not for the evening as a whole",
          "hold.watching(item[" in wsrc and "if hold.HOLD:\n        return []" not in wsrc)
    check("and says what is still held rather than 'all sent' alone",
          "held=%s" in wsrc and "still on hold" in wsrc)

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
