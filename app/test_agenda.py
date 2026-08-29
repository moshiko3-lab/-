#!/usr/bin/env python3
"""Drive the planning screen's four views and its fortnight range.

Seeds a day through the UI, then checks each view actually changes what is on
screen -- a switch that renders the same table four times would pass a build
check and fail the person using it.
"""
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))

fails = []


def build():
    out = os.path.join(tempfile.mkdtemp(), "app.html")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def tab(pg, name):
    pg.click(f'#tabs button[data-id="{name}"]')
    pg.wait_for_timeout(400)


def modal_button(pg, text):
    pg.click(f'#modal button:has-text("{text}")')
    pg.wait_for_timeout(500)


def view(pg, label):
    pg.click(f'#p-schedule .range button:has-text("{label}")')
    pg.wait_for_timeout(500)


def plan_text(pg):
    return (pg.inner_text("#p-schedule") or "").lower()


def add_session(pg, title, time_):
    pg.click('#p-schedule button:has-text("New session")')
    pg.wait_for_timeout(600)
    # the title is picked from the activities and the products; a name of your
    # own is the last option, and it is what these sessions are given
    pg.select_option("#modal select >> nth=0", label="Something else…")
    pg.wait_for_timeout(250)
    pg.fill('#modal input[type=text]:visible >> nth=0', title)
    pg.fill('#modal input[type=time]:visible >> nth=0', time_)
    modal_button(pg, "Save")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1500, "height": 1000}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(1500)

        tab(pg, "schedule")
        add_session(pg, "Dawn patrol", "07:30")
        add_session(pg, "Sunset session", "16:00")
        txt = plan_text(pg)
        check("both sessions listed", "dawn patrol" in txt and "sunset session" in txt, txt[:300])
        check("morning band", "morning (before 13:00)" in txt, txt[:400])
        check("afternoon band", "afternoon (after 13:00)" in txt, txt[:400])

        # the four views must actually differ
        seen = {}
        for v in ("Compact", "Simple", "Details", "Accommodation"):
            view(pg, v)
            seen[v] = plan_text(pg)
        check("compact drops the extra columns",
              "note" not in seen["Compact"].split("morning")[-1], seen["Compact"][:300])
        check("simple keeps the chosen columns", "dawn patrol" in seen["Simple"])
        check("details still lists sessions", "dawn patrol" in seen["Details"])
        check("compact differs from details", seen["Compact"] != seen["Details"])
        check("accommodation is a different screen",
              "dawn patrol" not in seen["Accommodation"], seen["Accommodation"][:250])
        check("accommodation explains itself when empty",
              "no accommodation is set up" in seen["Accommodation"], seen["Accommodation"][:250])

        # fortnight
        view(pg, "Details")
        pg.click('#p-schedule .range button:has-text("14 days")')
        pg.wait_for_timeout(600)
        txt = plan_text(pg)
        check("fortnight shows the seeded day", "dawn patrol" in txt, txt[:300])
        # the bundled catalog fills most days, so count date headers rather than
        # expecting the fortnight to have gaps
        check("fortnight spans several days", txt.count("open day") > 1,
              str(txt.count("open day")) + " day headers")
        check("fortnight offers a way back into a day", "open day" in txt)
        pg.click('#p-schedule .range button:has-text("Daily")')
        pg.wait_for_timeout(500)
        check("back to a single day", "of the 14 days" not in plan_text(pg))

        check("no uncaught errors", not errs, "; ".join(errs[:3]))
        b.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
