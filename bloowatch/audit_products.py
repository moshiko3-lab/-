#!/usr/bin/env python3
"""Every product, field by field, against what Bloowatch actually holds.

Reads a raw /products/ payload straight from their API and the catalog the
manager is built from, and says three things per field: what we carry and
match, what we carry and differ on, and what they hold that we drop. A field
we deliberately leave out is named here as deliberate rather than quietly
missing, so the list is the whole truth about the gap.

    python3 audit_products.py --raw products.json --catalog ../app/catalog.json

The raw file is whatever /api/schools/<id>/products/ returns -- a list, or the
paginated {"results": [...]}. With BLOOWATCH_EMAIL / BLOOWATCH_PASSWORD /
BLOOWATCH_URL in the environment, --fetch takes a fresh one instead.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# What we take, and where it lands in the catalogue the app is built from.
# The value is (catalog key, how to read the raw one).
MAPPED = {
    "name": ("name", lambda p: p.get("name")),
    "num_sessions": ("sessions", lambda p: p.get("num_sessions") or 1),
    "num_nights": ("nights", lambda p: p.get("num_nights") or None),
    "category_name": ("category", lambda p: p.get("category_name") or ""),
    "category_session_duration": ("categoryDuration",
                                  lambda p: p.get("category_session_duration") or ""),
    "color": ("color", lambda p: p.get("color") or ""),
    "is_public": ("soldOnline", lambda p: bool(p.get("is_public"))),
    "order": ("pos", lambda p: p.get("order")),
    "rental": ("rental", lambda p: p.get("rental")),
    "tax_rate": ("tax", lambda p: float(p.get("tax_rate") or 0)),
    "private_session": ("private", lambda p: bool(p.get("private_session"))),
    "description": ("description", lambda p: (p.get("description") or "").strip()),
    "has_sub_products": ("subProducts", lambda p: bool(p.get("has_sub_products"))),
    "customer_assign_instructor": ("clientPicksInstructor",
                                   lambda p: bool(p.get("customer_assign_instructor"))),
    "start_hours": ("startHours", lambda p: p.get("start_hours") or []),
    "price": ("price", lambda p: float(p.get("price") or 0)),
    "public_price": ("publicPrice", lambda p: p.get("public_price")),
}

# Fields we read but reshape, checked on their own below.
RESHAPED = ("all_prices", "product_categories", "available_stock",
            "has_limited_stock", "archived")

# Theirs, and left out on purpose. Each says why, because "missing" and
# "decided against" are different answers to the same question.
DELIBERATE = {
    "id": "their id; ours are our own, and the name is what matches on import",
    "date_created": "bookkeeping of their record, not of the product",
    "date_updated": "same",
    "in_orders": "derived: whether the product was ever sold",
    "out_of_stock": "derived from the stock we already carry",
    "product_class": "read, and folded into our kind/ptype",
    "school_category": "the id behind category_name, which we carry by name",
    "product_category": "the id behind product_categories, carried by name",
    "tax": "their tax band id; tax_rate is the number that matters",
    "is_mapped_to_eb": "an Eventbrite link the school does not use",
    "has_start_hours": "implied by start_hours being non-empty",
    "has_custom_fields": "no custom product fields are set on any product",
    "has_age_validation": "implied by age_validation",
    "has_seasonal_prices": "implied by a seasonal tier existing",
    "has_trips": "implied by their trips list",
    "product_images": "no product carries one",
    "product_translations": "the school runs one language",
    "allow_session_creation": "their booking-flow flag, not a product property",
    "booking_session_option": "same",
    "availability_periods": "empty on every product",
    "spots": "empty on every product",
    "age_validation": "empty on every product",
}


def load_raw(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d["results"] if isinstance(d, dict) and "results" in d else d


def fetch_raw():
    sys.path.insert(0, HERE)
    from daily_report import login                      # noqa: E402
    from export_dataset import _get, _rows, school_id   # noqa: E402
    s, base = login()
    return list(_rows(_get(s, base, f"/schools/{school_id(s, base)}/products/")))


def same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a or 0) - float(b or 0)) < 0.004
        except (TypeError, ValueError):
            return False
    if a is None and b in ("", None, 0):
        return True
    if b is None and a in ("", None, 0):
        return True
    return a == b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--catalog", default=os.path.join(HERE, "..", "app", "catalog.json"))
    a = ap.parse_args()

    raw = fetch_raw() if a.fetch else load_raw(a.raw)
    with open(a.catalog, encoding="utf-8") as f:
        cat = json.load(f)
    ours = {p["name"]: p for p in cat["products"]}

    live = [p for p in raw if not p.get("archived")]
    print("%d products in Bloowatch (%d archived), %d in the catalogue\n"
          % (len(live), len(raw) - len(live), len(cat["products"])))

    missing = [p["name"] for p in live if p["name"] not in ours]
    extra = [n for n in ours if n not in {p["name"] for p in live}]
    if missing:
        print("NOT IMPORTED: " + ", ".join(missing))
    if extra:
        print("IN OURS BUT NOT THEIRS: " + ", ".join(extra))

    bad = {}
    for p in live:
        mine = ours.get(p["name"])
        if not mine:
            continue
        for their_key, (our_key, read) in MAPPED.items():
            want = read(p)
            got = mine.get(our_key)
            if not same(want, got):
                bad.setdefault(their_key, []).append(
                    "%s: theirs %r, ours %r" % (p["name"], want, got))
        # the price matrix, tier for tier
        theirs = sorted([(t.get("min_pax") or 1, t.get("duration"),
                          t.get("price_unit"), round(float(t.get("price_incl_tax") or 0), 2))
                         for t in (p.get("all_prices") or [])])
        mineT = sorted([(t.get("minPax") or 1, t.get("hours"), t.get("unit"),
                         round(float(t.get("price") or 0), 2))
                        for t in (mine.get("prices") or [])])
        if theirs != mineT:
            bad.setdefault("all_prices", []).append(
                "%s: %d tiers theirs, %d ours" % (p["name"], len(theirs), len(mineT)))
        # the shop grouping and the stock
        shop = (p.get("product_categories") or [None])[0] or ""
        if (mine.get("shopCategory") or "") != shop:
            bad.setdefault("product_categories", []).append(
                "%s: theirs %r, ours %r" % (p["name"], shop, mine.get("shopCategory")))
        stock = p.get("available_stock") if p.get("has_limited_stock") else None
        if not same(stock, mine.get("stock")):
            bad.setdefault("available_stock", []).append(
                "%s: theirs %r, ours %r" % (p["name"], stock, mine.get("stock")))

    checked = list(MAPPED) + list(RESHAPED)
    print("CHECKED %d fields on every product:" % len(checked))
    for k in sorted(checked):
        rows = bad.get(k)
        if rows:
            print("  DIFFERS  %-28s %d product(s)" % (k, len(rows)))
            for r in rows[:6]:
                print("             " + r)
            if len(rows) > 6:
                print("             (+%d more)" % (len(rows) - 6))
        else:
            print("  same     %s" % k)

    seen = set(checked) | set(DELIBERATE)
    unknown = sorted({k for p in raw for k in p} - seen)
    print("\nLEFT OUT ON PURPOSE (%d):" % len(DELIBERATE))
    for k in sorted(DELIBERATE):
        print("  %-28s %s" % (k, DELIBERATE[k]))
    if unknown:
        print("\nNOT ACCOUNTED FOR — decide about these:")
        for k in unknown:
            vals = {json.dumps(p.get(k), default=str)[:40] for p in raw}
            print("  %-28s e.g. %s" % (k, ", ".join(sorted(vals)[:3])))
        return 1
    print("\nEvery field they hold is either carried or named above.")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
