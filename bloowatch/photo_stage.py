#!/usr/bin/env python3
"""Resize the matched photos for the page and name them by model.

    python3 photo_stage.py <work-dir>

Reads `match_hard.json` (from `photo_match.py`) and the softboard table
below, writes `staged/` and `staged.json`. The files are then uploaded to
the board-store page as assets and tied to their models in its `photos/map`
document -- see RENTALS.md.


The originals are 20MB across 110 files, shot portrait at full phone
resolution. The page shows them at 46px in a row and full-screen at a tap,
so the width that matters is the second one; everything above about 900px
is bytes the counter waits for on Venao's wifi and never sees.

Each file comes out named after the model it belongs to, so the upload and
the map that follows cannot drift apart.
"""
import json, os, re, shutil, sys
from PIL import Image

SC = sys.argv[1]
OUT = os.path.join(SC, "staged")
WIDE, Q = 900, 82

# Decided by eye off the contact sheet and confirmed by measuring the
# dominant hue of each board: Bloowatch names these by colour and the photo
# set names them by length, so the colour is what joins them.
# "7'0 #2" and "7'6 #1" measure the same tan (hue 27 and 29) -- Bloowatch
# calls that BROWN at 7'0 and CREAM at 7'6.
SOFT = {
    "7'6/YELLOW OCEAN EARTH":   "SOFTBOARD OCEAN EARTH 7'4.jpg",
    "8'0/RED OCEAN & EARTH":    "SOFTBOARD OCEAN EARTH 8'0.jpg",
    "9'0/BLUE OCEAN AND EARTH": "SOFTBOARD OCEAN EARTH 9'0.jpg",
    "6'0/YELLOW/OM":            "SOFTBOARD OCEAN MONKEY 6'0 #1.jpg",
    "6'0/LIGHT BLUE/OM":        "SOFTBOARD OCEAN MONKEY 6'0 #2.jpg",
    "6'6/LIGHT BLUE/OM":        "SOFTBOARD OCEAN MONKEY 6'6.jpg",
    "7'0/BLUE/OM":              "SOFTBOARD OCEAN MONKEY 7'0 #1.jpg",
    "7'0/BROWN/OM":             "SOFTBOARD OCEAN MONKEY 7'0 #2.jpg",
    "7'6/CREAM/OM":             "SOFTBOARD OCEAN MONKEY 7'6 #1.jpg",
    "7'6/BLUE/OM":              "SOFTBOARD OCEAN MONKEY 7'6 #2.jpg",
    "7'6/BLUE WIDE/OM":         "SOFTBOARD OCEAN MONKEY 7'6 WIDE.jpg",
    "8'0/WIDE GREEN/OM":        "SOFTBOARD OCEAN MONKEY 8'0 WIDE.jpg",
    "8'4/PINK/OM":              "SOFTBOARD OCEAN MONKEY 8'4.jpg",
}

SOFT_DIR = os.path.join(SC, "pics", "soft", "Shokogi softboards")
HARD_DIR = os.path.join(SC, "pics", "hard", "Shokogi rental boards")


def slug(family, model):
    s = ("%s %s" % (family, model)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:90]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)

    hard = json.load(open(os.path.join(SC, "match_hard.json"),
                          encoding="utf-8"))["matched"]
    plan = []
    for model, fn in SOFT.items():
        plan.append(("SHOKOGI SOFTBOARDS", model, os.path.join(SOFT_DIR, fn)))
    for model, m in hard.items():
        plan.append(("SHOKOGI SURFBOARDS", model,
                     os.path.join(HARD_DIR, m["file"])))

    made, saved_from, saved_to = [], 0, 0
    for family, model, src in plan:
        if not os.path.exists(src):
            print("MISSING  %s" % src)
            continue
        im = Image.open(src)
        im = im.convert("RGB")
        if im.width > WIDE:
            im = im.resize((WIDE, round(im.height * WIDE / im.width)),
                           Image.LANCZOS)
        name = slug(family, model) + ".jpg"
        dst = os.path.join(OUT, name)
        im.save(dst, "JPEG", quality=Q, optimize=True)
        saved_from += os.path.getsize(src)
        saved_to += os.path.getsize(dst)
        made.append({"family": family, "model": model, "file": name})

    json.dump(made, open(os.path.join(SC, "staged.json"), "w"),
              ensure_ascii=False, indent=1)
    print("staged %d photos: %.1f MB -> %.1f MB"
          % (len(made), saved_from / 1e6, saved_to / 1e6))


main()
