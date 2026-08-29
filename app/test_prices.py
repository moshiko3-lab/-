#!/usr/bin/env python3
"""Every tier of every product, checked against what the app would quote.

Their price list is a matrix, not a number: a lesson comes down as more people
share it, a board costs more the longer it is out. This drives the shared
pricing module over the whole imported catalogue -- all 35 products, every tier
-- and asks the one question that matters: ask for N people (or N hours) and do
you get back the tier they actually charge?

Two rules, and nothing else is invented here:
  * head-count ladder -- the tier is the largest minPax that N still clears;
  * duration ladder   -- the tier is the longest one the hire still clears,
                         and the smallest when the hire is shorter than any of
                         them. A tier priced in another unit is a separate
                         ladder (a board is $285 for 30h until closing, and
                         $10 for 60h from pickup -- comparing those undercuts
                         the hire), so it is quoted on its own terms, not
                         mixed in.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


DRIVER = r"""
const fs = require('fs');
function money(n, d) { return Number(n).toFixed(d === undefined ? 2 : d); }
eval(fs.readFileSync(process.argv[2], 'utf8'));
const cat = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const asks = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const byName = {};
cat.products.forEach(p => { byName[p.name] = p; });
console.log(JSON.stringify(asks.map(a => {
  const p = byName[a.name];
  if (!p) return null;
  return {price: priceFor(p, a.pax, a.hours),
          pax: hasPaxTiers(p), hours: hasHourTiers(p)};
})));
"""


def quote(asks):
    drv = os.path.join(HERE, "_pricedrv.js")
    askf = os.path.join(HERE, "_asks.json")
    with open(drv, "w") as f:
        f.write(DRIVER)
    with open(askf, "w") as f:
        json.dump(asks, f)
    try:
        r = subprocess.run(["node", drv, os.path.join(HERE, "pricing.js"),
                            os.path.join(HERE, "catalog.json"), askf],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr.strip()[:800])
            sys.exit(1)
        return json.loads(r.stdout)
    finally:
        for f in (drv, askf):
            if os.path.exists(f):
                os.remove(f)


def main():
    cat = json.load(open(os.path.join(HERE, "catalog.json")))
    products = cat["products"]
    check("the catalogue is there", len(products) >= 30, str(len(products)))

    asks, want, why = [], [], []

    def ask(p, pax, hours, expect, note):
        asks.append({"name": p["name"], "pax": pax, "hours": hours})
        want.append(expect)
        why.append(note)

    pax_products = hour_products = 0
    for p in products:
        tiers = p.get("prices") or []
        if not tiers:
            continue
        hourly = [t for t in tiers if t.get("hours")]
        if hourly:
            hour_products += 1
            # the ladder is the unit most of the tiers share; the odd ones out
            # are a different offer and are asked about on their own terms
            units = {}
            for t in hourly:
                units[t.get("unit") or ""] = units.get(t.get("unit") or "", 0) + 1
            main_unit = max(units, key=lambda u: units[u])
            ladder = sorted([t for t in hourly if (t.get("unit") or "") == main_unit],
                            key=lambda t: t["hours"])
            for t in ladder:
                ask(p, 1, t["hours"], t["price"],
                    "%s at %sh" % (p["name"], t["hours"]))
            # an hour under the shortest tier still pays the shortest tier
            if ladder and ladder[0]["hours"] > 0:
                ask(p, 1, 0.5, ladder[0]["price"],
                    "%s under its shortest tier" % p["name"])
            # halfway between two tiers pays the lower one
            if len(ladder) > 1:
                a, b = ladder[0], ladder[1]
                if b["hours"] - a["hours"] > 1:
                    mid = a["hours"] + (b["hours"] - a["hours"]) / 2.0
                    ask(p, 1, mid, a["price"],
                        "%s between %sh and %sh" % (p["name"], a["hours"], b["hours"]))
        else:
            paxes = sorted(tiers, key=lambda t: t.get("minPax") or 1)
            if len(paxes) > 1:
                pax_products += 1
            for i, t in enumerate(paxes):
                n = t.get("minPax") or 1
                ask(p, n, None, t["price"], "%s for %d" % (p["name"], n))
                # one short of the next tier still pays this one
                if i + 1 < len(paxes):
                    nxt = paxes[i + 1].get("minPax") or 1
                    if nxt - n > 1:
                        ask(p, nxt - 1, None, t["price"],
                            "%s for %d" % (p["name"], nxt - 1))
                else:
                    ask(p, n + 3, None, t["price"],
                        "%s for %d" % (p["name"], n + 3))

    check("every product with a head-count ladder is covered", pax_products >= 10,
          str(pax_products))
    check("and every one priced by the hour", hour_products >= 6, str(hour_products))

    got = quote(asks)
    check("the pricing module answered every ask", len(got) == len(asks) and
          all(g is not None for g in got))
    if len(got) != len(asks) or any(g is None for g in got):
        return 1

    bad = []
    for g, w, note in zip(got, want, why):
        if abs(float(g["price"]) - float(w)) > 0.004:
            bad.append("%s → %s, their price is %s" % (note, g["price"], w))
    check("every tier of every product quotes their own price",
          not bad, "; ".join(bad[:6]) + (" (+%d more)" % (len(bad) - 6) if len(bad) > 6 else ""))
    print("       %d asks across %d products" % (len(asks), len(products)))

    # the three lessons whose one-person tier is labelled "hourly" and the rest
    # are not: the label is not a second ladder, and reading it as one quoted a
    # single surfer the pair's price
    named = {"SURF LESSON 2024": (60.0, 40.0, 30.0),
             "2 SURF LESSON 2024": (120.0, 80.0, 60.0),
             "3X SURF LESSON COURSE 2024": (180.0, 120.0, 90.0)}
    present = [n for n in named if any(p["name"] == n for p in products)]
    check("their mixed-label lessons are in the catalogue", len(present) == 3,
          str(present))
    solo = quote([{"name": n, "pax": 1, "hours": None} for n in present])
    for n, g in zip(present, solo):
        check("one person on %s pays %s" % (n, named[n][0]),
              abs(float(g["price"]) - named[n][0]) < 0.004, str(g["price"]))

    # a hire is never quoted the long-stay rate by accident: 30h until closing
    # is $285 on a soft-board, and the 60h from-pickup tier is $10
    soft = [p for p in products if p["name"] == "SOFT-BOARDS RENTALS"]
    check("the soft-boards ladder is there", bool(soft))
    if soft:
        g = quote([{"name": "SOFT-BOARDS RENTALS", "pax": 1, "hours": 30},
                   {"name": "SOFT-BOARDS RENTALS", "pax": 1, "hours": 45}])
        check("30 hours on a soft-board is their $285",
              abs(float(g[0]["price"]) - 285.0) < 0.004, str(g[0]["price"]))
        check("and 45 hours is not the $10 long-stay rate",
              float(g[1]["price"]) > 200, str(g[1]["price"]))

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
