#!/bin/sh
# What a routine's container needs before any of this will run.
#
#     sh bloowatch/routine_setup.sh
#
# **Why this file exists.** On 15/9/2026 the 18:00 forecast routine fired on
# time, cloned the repo, ran `evening.py forecast`, and died on
#
#     ModuleNotFoundError: No module named 'playwright'   (surfline.py:151)
#
# It sent nothing. Checking the journal afterwards showed the real shape of
# it: **no automatic container has ever sent the forecast or the rota.**
# Every one of those lines was filed by `vm` or by `hand`. Only the
# reminders had ever gone out from a routine, and they are the one job that
# needs no browser.
#
# So the container-boots-empty fix of 14/9 was half a fix. It got the code
# into the container. Nothing got the code's dependencies in after it, and
# the two jobs that need a browser had been failing silently ever since --
# silently because a routine that stops before it sends has nothing to
# report, and because the safety nets watch the *gateway*, which correctly
# reported that nothing was sent.
#
# **The dependency list lives here and not in the routines' own text.** That
# is the point of the file. Ten routines carry a copy of the preparation
# step; editing ten prompts by hand every time a dependency moves is how one
# of them ends up different from the others. They call this instead, and
# this is in the repository where it can be changed once and tested.
#
# **It never downloads a browser.** Chromium is already in the image at
# /opt/pw-browsers and PLAYWRIGHT_BROWSERS_PATH points at it; `shot.chromium()`
# finds it there. `playwright install` would pull ~150 MB into a container
# that is thrown away an hour later, and would fail anyway on an environment
# whose network policy does not reach the CDN.
set -e

need=""
for mod in playwright requests; do
    python3 -c "import $mod" 2>/dev/null || need="$need $mod"
done

if [ -n "$need" ]; then
    echo "installing:$need"
    # No browser download: the image already carries Chromium.
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
        python3 -m pip install --quiet --disable-pip-version-check $need
fi

# Say so out loud rather than leaving it to the first import at six in the
# evening. A routine that stops here has sent nothing and can be re-run; one
# that stops half way through a forecast cannot.
missing=""
for mod in playwright requests; do
    python3 -c "import $mod" 2>/dev/null || missing="$missing $mod"
done
if [ -n "$missing" ]; then
    echo "SETUP FAILED — still missing:$missing" >&2
    exit 1
fi

python3 - <<'PY'
import sys
sys.path.insert(0, "bloowatch")
import shot
where = shot.chromium()
print("SETUP OK  playwright yes  requests yes  chromium %s"
      % (where or "playwright's own"))
PY
