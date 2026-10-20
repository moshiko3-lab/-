#!/usr/bin/env python3
"""Match the hard-board photos to Bloowatch's SURFBOARDS models.

    python3 photo_match.py <work-dir>

The work directory holds `rentals.json` (from `rentals.py --out`) and the
unpacked photo folder with its `Shokogi-boards.csv`; the matches land in
`match_hard.json` beside them, and `photo_stage.py` turns those into files
named after the model.

Bloowatch writes a board as `F19/TORQ 6'6/SWOLLOW/GO KART` -- an F-number,
a size and a bag of brand, model and colour words in no fixed order, with
the typos of whoever typed it (WIHTE, SWOLLOW, MERICK, FIRWIRE). The photo
set carries the same boards named the other way round, plus a CSV giving
size, brand and model as separate fields.

So the match is scored on what both sides agree about, and nothing is
assigned on a tie: **a photo of the wrong board is worse than none**,
because nothing downstream would ever say it is wrong. On 20/10/2026 that
left 59 of 121 matched and 22 refused, nearly all of them TORQ midlengths
and funboards that Bloowatch tells apart by colour (`TORQ WHITE` against
`TORQ RED RAILS`) while the photographs are named `#1` to `#4`. Those
need an eye on the pictures, not a better scorer.
"""
import csv, json, os, re, sys

SC = sys.argv[1]

# What the two sides spell differently, folded to one spelling.
FIX = [("WIHTE","WHITE"), ("SWOLLOW","SWALLOW"), ("SWALOW","SWALLOW"),
       ("MERICK","MERRICK"), ("FIRWIRE","FIREWIRE"), ("FIRWIR","FIREWIRE"),
       ("GOSOFT","GO SOFT"), ("MIDLEGHT","MIDLENGTH"), ("AL MERRICK","ALMERRICK"),
       ("OCEAN AND EARTH","OCEANEARTH"), ("OCEAN & EARTH","OCEANEARTH")]

# Words that say nothing about which board this is.
STOP = set("""AND THE A OF BOARD SURFBOARD SHORTBOARD FUNBOARD MIDLENGTH
LONGBOARD FISH SHORT MINI FUN JPG HEIC""".split())


def norm(s):
    s = (s or "").upper()
    for a, b in FIX:
        s = s.replace(a, b)
    return s


def size_of(s):
    m = re.search(r"(\d{1,2})\s*'\s*(\d{1,2})", s)
    return "%d'%d" % (int(m.group(1)), int(m.group(2))) if m else None


def tokens(s):
    s = norm(s)
    s = re.sub(r"\d{1,2}\s*'\s*\d{1,2}", " ", s)      # the size is scored apart
    s = re.sub(r"^F[\d.]+", " ", s)                    # Bloowatch's own F-number
    s = re.sub(r"#\d+", " ", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return {w for w in s.split() if w not in STOP and len(w) > 1}


def main():
    d = json.load(open(os.path.join(SC, "rentals.json"), encoding="utf-8"))
    models = [f["model"] for f in d["fleet"]
              if f["family"] == "SHOKOGI SURFBOARDS"]

    base = os.path.join(SC, "pics", "hard", "Shokogi rental boards")
    rows = list(csv.DictReader(open(os.path.join(base, "Shokogi-boards.csv"),
                                    encoding="utf-8-sig")))
    photos = []
    for r in rows:
        fn = r["שם קובץ"]
        if not os.path.exists(os.path.join(base, fn)):
            continue
        text = " ".join([r["שם הגלשן"], r["מותג"], r["דגם"]])
        photos.append({"file": fn, "size": size_of(r["מידה"]) or size_of(fn),
                       "tok": tokens(text), "name": r["שם הגלשן"]})

    # The size alone is never a match. There are a dozen 6'10s in this
    # store and the photo of the wrong one is worse than no photo: nothing
    # downstream would ever say it is wrong. So a pair counts only once the
    # two sides agree on a word that names the board -- a brand, a model, a
    # colour -- and the size is what breaks the ties between those.
    pairs = []
    for m in models:
        ms, mt = size_of(m), tokens(m)
        for p in photos:
            same_size = bool(ms and p["size"] and ms == p["size"])
            if ms and p["size"] and not same_size:
                continue                # a different length is a different board
            shared = mt & p["tok"]
            if not shared:
                continue                # nothing but the tape measure in common
            score = 2 * len(shared) + (4 if same_size else 0)
            pairs.append((score, m, p["file"], sorted(shared)))

    pairs.sort(key=lambda x: (-x[0], x[1]))

    by_model = {}
    for s, m, f, sh in pairs:
        by_model.setdefault(m, []).append((s, f, sh))

    taken, out, unsure = set(), {}, []
    for s, m, f, sh in pairs:
        if m in out or f in taken or m in {u[0] for u in unsure}:
            continue
        rivals = [x for x in by_model[m] if x[0] == s and x[1] not in taken]
        if len(rivals) > 1:
            unsure.append((m, s, [r[1] for r in rivals]))
            continue
        out[m] = {"file": f, "score": s, "on": sh}
        taken.add(f)

    print("matched   %d of %d models" % (len(out), len(models)))
    print("ambiguous %d" % len(unsure))
    print("photos unused: %d of %d" % (len(photos) - len(taken), len(photos)))
    print("\n--- matched ---")
    for m in sorted(out):
        print("  %-34s <- %-46s  s=%d %s"
              % (m, out[m]["file"][:46], out[m]["score"], ",".join(out[m]["on"])))
    print("\n--- ambiguous ---")
    for m, s, fs in unsure:
        print("  %-34s  s=%d" % (m, s))
        for f in fs[:4]:
            print("        %s" % f)
    print("\n--- models with no photo ---")
    for m in sorted(models):
        if m not in out and m not in {u[0] for u in unsure}:
            print("  " + m)
    print("\n--- photos not used ---")
    for p in photos:
        if p["file"] not in taken:
            print("  " + p["file"])

    json.dump({"matched": out}, open(os.path.join(SC, "match_hard.json"), "w"),
              ensure_ascii=False, indent=1)


main()
