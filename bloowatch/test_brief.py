#!/usr/bin/env python3
"""The evening brief, against a real day of the school's own board.

No network and no fixture invented for the occasion: `app/catalog.json` is a
real export, and 24 August 2026 is a real Monday with 23 rows on it. Everything
checked here is something that day does and a made-up day would not have --
one lesson written down once per instructor, five all-day staff blocks that are
not sessions at all, and the customer's name living in the title behind a
prefix.

    python3 test_brief.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tomorrow_brief as tb

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "..", "app", "catalog.json")
DAY = "2026-08-24"

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + str(detail)) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def rows_for(cat, day, extra=()):
    """The catalog's exported shape, in the shape the composer works in."""
    out = [{"time": s["time"], "title": s["title"], "category": s["category"],
            "allDay": s.get("allDay"), "crew": s.get("staff") or [], "people": [],
            "seats": s.get("capacity") or 0, "spot": s.get("spot") or "", "note": ""}
           for s in cat["sessions"] if s["date"] == day]
    return out + list(extra)


def main():
    if not os.path.exists(CATALOG):
        print("app/catalog.json is not here, so there is no real day to read")
        return 0
    with open(CATALOG, encoding="utf-8") as f:
        cat = json.load(f)

    raw = rows_for(cat, DAY)
    if not raw:
        print(f"{DAY} is not in this catalog any more; refresh the day")
        return 0
    tidy = tb.tidy(raw)
    text = tb.compose(DAY, tidy)

    print("the board, folded")
    check("the day has rows to fold", len(raw) >= 20, len(raw))
    check("folding it removes more than it keeps of the noise",
          len(tidy) < len(raw), f"{len(raw)} -> {len(tidy)}")
    check("the all-day staff blocks are gone",
          not any("SHOKOGI - STAFF" in r["title"].upper() for r in tidy),
          [r["title"] for r in tidy])
    check("no session is listed twice at the same hour",
          len({(r["time"], r["title"]) for r in tidy}) == len(tidy))

    print("\none lesson, several instructors")
    both = [r for r in tidy if r["time"] == "08:30" and "Galia" in r["title"]]
    check("the 08:30 class survived as one row", len(both) == 1, both)
    if both:
        check("with both of its instructors on it",
              {"Victor", "Yochai"} <= set(both[0]["crew"]), both[0]["crew"])

    print("\nhow it reads")
    check("the customer's name is there, without the CLASS 2024 in front of it",
          "Galia Frenkel" in text and "CLASS 2024" not in text, text[:160])
    check("nobody is shouted at", "VICTOR" not in text and "YOCHAI" not in text)
    check("a name typed in lower case is not left that way",
          "Koren Shem Tov" in text, text)
    check("the day's hours are in the first line",
          "08:30–17:00" in text.split("\n")[0], text.split("\n")[0])
    check("a capacity nobody is counted against is left off",
          "/12" not in text, text)

    print("\nthe spot, only where it is news")
    check("one beach all day is not repeated on every line",
          "Playa Venao1" not in text, text)
    elsewhere = [{"time": "07:00", "title": "Foil tow", "category": "FOIL FREE TOW",
                  "allDay": False, "crew": ["GUR YOSEF"], "people": ["Stephen Walker"],
                  "seats": 4, "spot": "Portio", "note": ""}]
    mixed = tb.compose(DAY, tb.tidy(rows_for(cat, DAY, elsewhere)))
    check("the one session somewhere else says so", "Portio" in mixed,
          mixed.split("\n")[1] if "\n" in mixed else mixed)
    check("and the usual beach is said once, at the top",
          mixed.split("\n")[0].count("Playa Venao1") == 1,
          mixed.split("\n")[0])
    check("the people read off a session are named under it",
          "Stephen Walker" in mixed)

    print("\nan empty day")
    check("says so rather than sending a heading with nothing under it",
          tb.compose("2026-01-01", []).endswith("nothing on the board."))

    print(("\nFAILED: " + ", ".join(fails)) if fails else "\nall good")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
