#!/usr/bin/env python3
"""One switch that stops every evening send, whoever calls it.

    python3 hold.py            # says whether the evening is on hold

The owner asked for this on 19/10/2026: *"בוא נעצור כרגע את התחזיות והלו״ז,
נשים הכל בהולד עד שאני אומר להחזיר"*.

**Why a switch in the code and not just six disabled routines.** The six
that build and send were turned off that evening, and that would have been
enough if they were the only way a message gets out. They are not. Two
safety nets stay on by the owner's own choice -- he declined to disable
them -- and a net's whole job is to notice that something did not go out
and send it. At 19:50 the rota is due, nothing went out, and the net would
have filed `staff_rota MISSING` and sent it: the hold undone by the
machinery built to protect the same message, forty minutes after it began.

So the hold lives where the sending does. `evening.py` refuses every
subcommand that reaches WhatsApp, and `watch_sends.py` stops calling
tonight's silence a fault, because tonight the silence is the instruction.

**Turning it back on is one line: `HOLD = False`.** Nothing else was
changed to make the hold -- no deleted routine, no rewritten prompt, no
edited group list -- so flipping it back restores exactly the evening that
was running on 19/10, and the six routines are re-enabled from their own
screen. The gate in `approval.py` is untouched and still applies after
that: the forecast still waits for a typed word.

`--dry-run`, `--print` and the tests are deliberately *not* held. They
send nothing, and a hold that also blindfolds us would mean coming back in
a week to a system nobody could check in the meantime.
"""

import sys

# The owner's word, and only the owner's word, moves this line.
HOLD = True

SINCE = "19/10/2026"
WORDS = "נעצור כרגע את התחזיות והלו״ז, נשים הכל בהולד עד שאני אומר להחזיר"

# What the hold covers: everything that puts a message in front of a
# customer, an instructor or the staff group. The reminders are not here --
# they are a separate question the owner has not answered, and stopping
# them would mean instructors stop being told about lessons they teach.
HELD = ("forecast", "preview", "rota", "personal", "changes")


def held(what):
    """Is this evening job on hold? Returns a reason, or ''."""
    if not HOLD or what not in HELD:
        return ""
    return ("on hold since %s at the owner's request (\"%s\"). "
            "Nothing was deleted: set HOLD = False in hold.py to resume."
            % (SINCE, WORDS))


def main():
    if not HOLD:
        print("the evening is running")
        return 0
    print("ON HOLD since %s — %s" % (SINCE, ", ".join(HELD)))
    print(WORDS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
