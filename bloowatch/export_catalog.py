#!/usr/bin/env python3
"""Export the Shokogi catalog out of Bloowatch, in the shape the manager app uses.

Products, rental gear and the activity calendars they belong to -- with prices,
session counts, tax, colours and durations, not just names.

    python3 export_catalog.py --out catalog.json
"""
import argparse
import json
import sys

from daily_report import BloowatchError, login
from export_dataset import _get, _rows, school_id

# Bloowatch's product_class plus its category tell us what a thing really is.
# The manager app groups takings by these, so the mapping matters.
def kind_of(p):
    cls = (p.get("product_class") or "").lower()
    cat = (p.get("category_name") or "").upper()
    name = (p.get("name") or "").upper()
    if cls == "rental" or "RENTAL" in name:
        return "rental"
    if "PHOTO" in cat or "PHOTO" in name:
        return "photo"
    if any(w in name for w in ("COURSE", "CAMP", "PACK")):
        return "course"
    if cls == "item":
        return "other"
    return "lesson"


def num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def build():
    s, base = login()
    sid = school_id(s, base)

    cats = []
    for c in _rows(_get(s, base, f"/schools/{sid}/categories/", show_archived="false")):
        cats.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "color": c.get("color"),
            "duration": c.get("session_duration"),
        })

    products = []
    for p in _rows(_get(s, base, f"/schools/{sid}/products/")):
        if p.get("archived"):
            continue
        products.append({
            "name": p.get("name") or p.get("title"),
            "kind": kind_of(p),
            "category": p.get("category_name") or "",
            "price": num(p.get("price")) or 0,
            "publicPrice": num(p.get("public_price")),
            "sessions": p.get("num_sessions") or 1,
            "nights": p.get("num_nights") or None,
            "tax": num(p.get("tax_rate")) or 0,
            "color": p.get("color") or "",
            "private": bool(p.get("private_session")),
            "description": (p.get("description") or "").strip(),
        })

    gear = []
    for r in _rows(_get(s, base, f"/schools/{sid}/rentals/")):
        if r.get("archived"):
            continue
        gear.append({
            "name": r.get("name"),
            "units": r.get("units"),
            "type": r.get("rental_type"),
            "description": (r.get("description") or "").strip(),
        })

    spots = []
    for sp in _rows(_get(s, base, f"/schools/{sid}/spots/")):
        loc = (sp.get("location") or {}).get("coordinates") or [None, None]
        spots.append({"name": sp.get("name"), "lat": loc[1], "lon": loc[0],
                      "notes": (sp.get("description") or "").strip()})

    return {"products": products, "gear": gear, "categories": cats, "spots": spots}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="catalog.json")
    a = ap.parse_args()
    try:
        data = build()
    except BloowatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"wrote {a.out}: {len(data['products'])} products, {len(data['gear'])} gear, "
          f"{len(data['categories'])} categories, {len(data['spots'])} spots")
    return 0


if __name__ == "__main__":
    sys.exit(main())
