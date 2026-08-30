"""The board figures in the brochure, read off the school's own inventory.

A surf brand's catalogue earns its credibility with specifications -- a wetsuit
page is a diagram with numbers on it -- and the equivalent here is the rack.
`app/catalog.json` already carries every board the school owns, each one named
by whoever labelled it, most of them with a length and a good number with a
shaper. So the counts and the range on page five are not written down anywhere
in `content.py`; they are counted at build time, and a rebuild after the next
export prints whatever is true then.

The names are free text typed by staff over years -- `EL MERICK`, `EL MERRICK`
and `FIRWIRE` all appear -- so the shaper list is a table of patterns rather
than a parse, and it is deliberately short: a name goes in only when the model
beside it confirms it. Anything unrecognised is simply not claimed.
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "app", "catalog.json")

# Gear groups that are boards a person could be handed, and which kind each is.
HARD = ("SHOKOGI SURFBOARDS", "SHORTBOARD - CONTAINER")
SOFT = ("SHOKOGI SOFTBOARDS",)
OTHER = {"SUP": "SUP", "BODY-BOARD": "BODYBOARD"}

# Shaper -> the strings that mean it. Only names whose models corroborate them:
# SCI FI, SAMPLER and TWO HAPPY are Channel Islands boards, so `EL MERICK` in a
# label is Al Merrick and not a coincidence. FRK and CYMATIC are Slater Designs,
# which Firewire builds, so both are listed and neither is invented.
SHAPERS = [
    ("TORQ", ("TORQ",)),
    ("JS INDUSTRIES", ("JS ", "JS/", "BLACK BOX", "SUB ZERO", "ZERO GRAVITY")),
    ("…LOST", ("LOST", "MAYHEM", "MINI DRIVER", "QUEIT FLIGHT")),
    ("FIREWIRE", ("FIREWIRE", "FIRWIRE", "TWINZER", "THE GEM", "DOMINATOR")),
    ("SLATER DESIGNS", ("FRK", "CYMATIC")),
    ("CHANNEL ISLANDS", ("MERICK", "MERRICK", "SCI FI", "SAMPLER", "TWO HAPPY")),
    ("PYZEL", ("PYZEL",)),
    ("DHD", ("DHD",)),
    ("HAYDEN SHAPES", ("HS ", "LOVE BUZZ", "HS LOOT")),
    ("CHILLI", ("CHILI", "CHILLI")),
    ("T. PATTERSON", ("T PATTERSON", "T. PATTERSON")),
    ("STEWART", ("STEWART",)),
    ("TAKAYAMA", ("TAKAYAMA",)),
    ("WALDEN", ("WALDEN",)),
    ("GERRY LOPEZ", ("JERRY LOPEZ", "GERRY LOPEZ")),
    ("STRETCH", ("STRECH", "STRETCH")),
    ("NSP", ("NSP",)),
    ("SOFTECH", ("SOFTEC",)),
]

LEN = re.compile(r"(\d)'(\d{1,2})")


def _units(cat, names):
    out = []
    for g in cat["gear"]:
        if g["name"] in names:
            out += [u["name"] for u in (g.get("units") or [])]
    return out


def _inches(name):
    m = LEN.search(name)
    return int(m.group(1)) * 12 + int(m.group(2)) if m else None


def _ft(inches):
    return "%d'%d" % (inches // 12, inches % 12)


def read(path=CATALOG):
    cat = json.load(open(path))
    hard, soft = _units(cat, HARD), _units(cat, SOFT)
    lens = {"hard": [i for i in map(_inches, hard) if i],
            "soft": [i for i in map(_inches, soft) if i]}

    # one row per foot, which is how a rack is actually read
    feet = sorted({i // 12 for v in lens.values() for i in v})
    rows = [(("%d'" % f),
             sum(1 for i in lens["hard"] if i // 12 == f),
             sum(1 for i in lens["soft"] if i // 12 == f)) for f in feet]

    found = []
    for label, keys in SHAPERS:
        blob = " ".join(hard + soft).upper()
        if any(k in blob for k in keys):
            found.append(label)

    other = {}
    for g in cat["gear"]:
        if g["name"] in OTHER:
            other[OTHER[g["name"]]] = len(g.get("units") or [])

    every = lens["hard"] + lens["soft"]
    return {
        "hard": len(hard), "soft": len(soft), "total": len(hard) + len(soft),
        "shortest": _ft(min(every)), "longest": _ft(max(every)),
        "rows": rows, "shapers": found, "other": other,
    }


if __name__ == "__main__":
    q = read()
    print("%(total)d boards -- %(hard)d hard, %(soft)d soft" % q)
    print("%(shortest)s to %(longest)s" % q)
    print("by foot:", q["rows"])
    print("shapers:", ", ".join(q["shapers"]))
    print("other:", q["other"])
