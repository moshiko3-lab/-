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

# What the hold still covers. On 27/11/2026 the owner took the whole rota
# side back -- *"אני רוצה להחזיר את עניין הלו״ז למדריכים בקבוצת הצוות
# והודעות לכל מדריך בסוף יום"*, and then the 20:00 changes pass with it --
# so only the forecast to the two surfer groups is still stopped, with the
# 18:00 preview that feeds it.
#
# `changes` belongs with the rota rather than apart from it: it is what
# tells the group and the instructors that tomorrow's board moved after
# the 19:00 rota went out. Held, a change made at eight in the evening
# reached nobody until the next day's rota.
HELD = ("forecast", "preview")

# The reminders were never in here: stopping those would mean instructors
# stop being told about lessons they are teaching, which is a different
# decision and not one the owner has made.

# What the safety nets call each thing, against what this file calls it.
# Without this the nets would go on treating a lifted send as held and
# never notice it failing to go out.
WATCHED = {"forecast_he": "forecast", "forecast_en": "forecast",
           "forecast_preview": "preview",
           "staff_rota": "rota", "personal_rotas": "personal"}


def held(what):
    """Is this evening job on hold? Returns a reason, or ''."""
    if not HOLD or what not in HELD:
        return ""
    return ("on hold since %s at the owner's request (\"%s\"). "
            "Nothing was deleted: remove it from HELD in hold.py to resume."
            % (SINCE, WORDS))


def watching(item):
    """Is this thing the safety nets watch for on hold? A reason, or ''."""
    return held(WATCHED.get(item, item))


def main():
    if not HOLD:
        print("the evening is running")
        return 0
    print("ON HOLD since %s — %s" % (SINCE, ", ".join(HELD)))
    print(WORDS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
