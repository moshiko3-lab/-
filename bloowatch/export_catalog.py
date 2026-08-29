#!/usr/bin/env python3
"""Export the Shokogi catalog out of Bloowatch, in the shape the manager app uses.

Products, rental gear and the activity calendars they belong to -- with prices,
session counts, tax, colours and durations, not just names.

    python3 export_catalog.py --out catalog.json
"""
import argparse
import datetime as dt
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


# Their product_class is coarse -- class / rental / item -- so the name settles
# the rest, the way their own eight types split it.
def ptype_of(p):
    cls = (p.get("product_class") or "").lower()
    name = (p.get("name") or "").upper()
    if cls == "rental":
        return "rental"
    if cls == "item":
        return "item"
    if "CAMP" in name:
        return "camp"
    if "TRIP" in name or "TOUR" in name:
        return "tour"
    if "COURSE" in name or "PACK" in name:
        return "course"
    return "class"


# their tide rows come back as 2026-8-29, which is not an ISO date
def _tide_date(v):
    try:
        y, m, d = (v or "").split("-")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, AttributeError):
        return None


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
        # all_prices is the pricing matrix, not a single number: lessons are
        # priced per head by how many share the session, rentals by how long
        # the board is out. Flattening it to one price loses the whole model.
        prices = []
        for a in (p.get("all_prices") or []):
            prices.append({
                "minPax": a.get("min_pax") or 1,
                "minQty": a.get("min_quantity") or 1,
                "hours": a.get("duration"),
                "unit": a.get("price_unit"),
                "price": num(a.get("price_incl_tax")),
            })
        prices.sort(key=lambda x: (x["hours"] or 0, x["minPax"]))

        products.append({
            "prices": prices,
            "rental": p.get("rental"),      # which gear the hire actually goes out with
            "name": p.get("name") or p.get("title"),
            "kind": kind_of(p),
            "ptype": ptype_of(p),
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

    # "units" is not a count -- it is the individual boards, each with its own
    # name, capacity and service dates. Keep them, that is the useful part.
    gear = []
    for r in _rows(_get(s, base, f"/schools/{sid}/rentals/")):
        if r.get("archived"):
            continue
        units = []
        for u in (r.get("units") or []):
            units.append({
                "name": u.get("name"),
                "maxPax": u.get("max_pax") or 1,
                "purchased": u.get("purchase_date"),
                "lastCheck": u.get("last_check"),
                "nextCheck": u.get("next_check"),
                "notes": (u.get("notes") or "").strip(),
            })
        gear.append({
            "id": r.get("id"),              # products point at this
            "name": r.get("name"),
            "units": units,
            "type": r.get("rental_type"),
            "description": (r.get("description") or "").strip(),
        })

    # Names and roles only. Personal phone numbers and email addresses are
    # deliberately left out: this file gets inlined into a page that can be
    # shared by URL, and a staff contact list should not travel that way.
    staff = []
    for st in _rows(_get(s, base, f"/schools/{sid}/staff/", show_archived="false")):
        name = " ".join(x for x in (st.get("first_name"), st.get("last_name")) if x).strip()
        if not name:
            continue
        role = (st.get("role") or "staff").strip()
        staff.append({"name": name, "role": role[:1].upper() + role[1:]})

    spots = []
    spot_ids = []
    for sp in _rows(_get(s, base, f"/schools/{sid}/spots/")):
        loc = (sp.get("location") or {}).get("coordinates") or [None, None]
        spots.append({"name": sp.get("name"), "lat": loc[1], "lon": loc[0],
                      "notes": (sp.get("description") or "").strip()})
        if sp.get("id"):
            spot_ids.append((sp["id"], sp.get("name")))

    # The tide table their agenda draws its curve from. The app is a static
    # page and cannot call anything at runtime, so a year of it is carried
    # across with everything else. Heights included: a 3.08 m high and a 0.15 m
    # low is a different day's surf from 2.1 and 0.9.
    tides = []
    if spot_ids:
        sp_id, sp_name = spot_ids[-1]
        start = dt.date.today() - dt.timedelta(days=14)
        # a month at a time; their endpoint refuses a whole year in one go
        for chunk in range(13):
            a = start + dt.timedelta(days=chunk * 30)
            b = a + dt.timedelta(days=30)
            try:
                got = _get(s, base, f"/spots/{sp_id}/tide/", school_id=sid,
                           **{"from": f"{a.year}-{a.month}-{a.day}",
                              "to": f"{b.year}-{b.month}-{b.day}"})
            except Exception:
                continue
            for block in (got or []):
                for day in (block.get("forecast") or []):
                    iso_day = _tide_date(day.get("date"))
                    if not iso_day:
                        continue
                    highs, lows = [], []
                    for when in ("morning", "evening"):
                        t = (day.get(f"high-tide {when} time") or "").strip()
                        h = (day.get(f"high-tide {when} height") or "").strip()
                        if t:
                            highs.append({"t": t, "m": h})
                        t = (day.get(f"low-tide {when} time") or "").strip()
                        h = (day.get(f"low-tide {when} height") or "").strip()
                        if t:
                            lows.append({"t": t, "m": h})
                    if highs or lows:
                        tides.append({"date": iso_day, "spot": sp_name,
                                      "highs": highs, "lows": lows})
        seen = set()
        uniq = []
        for row in sorted(tides, key=lambda r: r["date"]):
            if row["date"] in seen:
                continue
            seen.add(row["date"])
            uniq.append(row)
        tides = uniq

    # The schedule as it stands: sessions from a week back to a month ahead.
    # Participants are dropped -- they point at clients, which stay behind.
    sessions = []
    start = dt.date.today() - dt.timedelta(days=7)
    cat_by_id = {c["id"]: c for c in cats}
    for i in range(38):
        d = (start + dt.timedelta(days=i)).isoformat()
        try:
            rows = _rows(_get(s, base, f"/schools/{sid}/sessions/",
                              date=d, offset=0, limit=100, ordering="starting_time"))
        except Exception:
            continue
        for x in rows:
            st = x.get("starting_time") or ""
            try:
                hhmm = dt.datetime.strptime(st[:25].strip(),
                                            "%a, %d %b %Y %H:%M:%S").strftime("%H:%M")
            except ValueError:
                hhmm = "09:00"
            cat = cat_by_id.get(x.get("category"), {})
            dur = str(x.get("duration") or "01:00:00").split(":")
            try:
                mins = int(dur[0]) * 60 + int(dur[1])
            except (ValueError, IndexError):
                mins = 60
            sessions.append({
                "date": d, "time": hhmm,
                "title": x.get("name") or cat.get("name") or "Session",
                "category": cat.get("name") or "",
                "duration": mins,
                "capacity": x.get("max_attendants") or x.get("allowed_attendants") or 1,
            })

    return {"products": products, "gear": gear, "categories": cats,
            "spots": spots, "staff": staff, "sessions": sessions, "tides": tides}


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
    units = sum(len(g["units"]) for g in data["gear"])
    tiers = sum(len(p["prices"]) for p in data["products"])
    print(f"wrote {a.out}: {len(data['products'])} products ({tiers} price tiers), "
          f"{len(data['gear'])} gear types "
          f"({units} individual units), {len(data['staff'])} crew, "
          f"{len(data['categories'])} categories, {len(data['spots'])} spots, "
          f"{len(data['sessions'])} sessions, {len(data['tides'])} days of tide")
    return 0


if __name__ == "__main__":
    sys.exit(main())
