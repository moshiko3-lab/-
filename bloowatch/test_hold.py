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
    # --- every evening send is covered, and named the way the CLI names it -
    # A command missing from HELD is a command that still goes out, and the
    # only sign would be a message arriving during the hold.
    src = open(os.path.join(HERE, "evening.py"), encoding="utf-8").read()
    subs = sorted(set(
        line.split('sub.add_parser("')[1].split('"')[0]
        for line in src.splitlines() if 'sub.add_parser("' in line))
    check("every evening.py subcommand is on the hold list",
          subs and all(s in hold.HELD for s in subs),
          "commands=%s held=%s" % (subs, list(hold.HELD)))

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
    # The check sits in main(), before the subcommand runs, so this is the
    # one thing worth running for real. It builds nothing and sends nothing:
    # with the hold on it cannot get past the first few lines of main().
    env = dict(os.environ, SHOKOGI_NO_REPORT="1")
    for what in ("forecast", "rota", "personal", "changes", "preview"):
        p = subprocess.run([sys.executable, "evening.py", what],
                           cwd=HERE, env=env, capture_output=True, text=True,
                           timeout=120)
        out = p.stdout + p.stderr
        check("evening.py %s refuses while the hold is on" % what,
              p.returncode == 0 and "held" in out,
              "exit=%d %r" % (p.returncode, out[-300:]))
        # It must not have reached the sea, the board or the browser: those
        # cost 40 seconds and a third-party page, and a held run that still
        # does all the work would be held in name only.
        check("  and stops before it builds anything",
              "RESULT: %s held" % what in out, out[-300:])

    # A dry run still has to work. A week of hold with no way to look at the
    # system is how we come back to something nobody can check.
    p = subprocess.run([sys.executable, "evening.py", "rota", "--dry-run"],
                       cwd=HERE, env=env, capture_output=True, text=True,
                       timeout=180)
    check("but a dry run is not held", "RESULT: rota held" not in p.stdout,
          p.stdout[-200:] + p.stderr[-200:])

    # --- the net does not call a stopped evening a quiet one --------------
    import watch_sends
    check("nothing is missing from an evening that was stopped",
          watch_sends.audit() == [])
    wsrc = open(os.path.join(HERE, "watch_sends.py"), encoding="utf-8").read()
    check("and the journal line says held, not 'all sent'",
          "RESULT held since" in wsrc
          and wsrc.index("if hold.HOLD:") < wsrc.index('"RESULT missing=%d'),
          "the hold must be checked before the all-sent line")
    check("the printed line does not claim everything went out either",
          "elif hold.HOLD:" in wsrc
          and wsrc.index("elif hold.HOLD:")
          < wsrc.index('"everything due by now went out"'))

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
