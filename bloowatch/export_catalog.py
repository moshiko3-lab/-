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


# Their staff records carry two-letter codes; the app shows people the word.
LANG_NAMES = {
    "en": "English", "es": "Spanish", "he": "Hebrew", "fr": "French",
    "pt": "Portuguese", "de": "German", "it": "Italian", "nl": "Dutch",
    "ru": "Russian",
}


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

        # Two different categories, which their own list keeps in two columns:
        # category_name is the ACTIVITY CALENDAR the sessions land on (SURF
        # PACK), product_categories is the shop's own grouping (PACKAGES).
        # Collapsing them, as this export used to, loses the shop side.
        products.append({
            "prices": prices,
            "rental": p.get("rental"),      # which gear the hire actually goes out with
            "name": p.get("name") or p.get("title"),
            "kind": kind_of(p),
            "ptype": ptype_of(p),
            "category": p.get("category_name") or "",
            # how long a session on that calendar runs -- SURF PACK an hour,
            # FOIL FREE TOW an hour and a half. It is where Bloowatch takes a
            # new session's length from, so without it every session opened on
            # a hardcoded number instead of theirs.
            "categoryDuration": p.get("category_session_duration") or "",
            "shopCategory": (p.get("product_categories") or [None])[0] or "",
            "pos": p.get("order"),
            # is_public is their SOLD ONLINE column: only two of the 35 are on
            # the public site, so a booking page that lists everything is wrong.
            "soldOnline": bool(p.get("is_public")),
            "startHours": p.get("start_hours") or [],
            "stock": (p.get("available_stock")
                      if p.get("has_limited_stock") else None),
            "subProducts": bool(p.get("has_sub_products")),
            "clientPicksInstructor": bool(p.get("customer_assign_instructor")),
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

    # What the board needs, and no more. Phone numbers, email addresses, home
    # addresses and birthdays are deliberately left out: this file gets inlined
    # into a page that can be shared by URL, and a staff contact list should
    # not travel that way. Activities and languages are not personal in that
    # sense -- they are what decides who can be put on a session.
    cat_name_by_id = {c["id"]: c["name"] for c in cats if c.get("id")}
    staff = []
    for st in _rows(_get(s, base, f"/schools/{sid}/staff/", show_archived="false")):
        name = " ".join(x for x in (st.get("first_name"), st.get("last_name")) if x).strip()
        if not name:
            continue
        role = (st.get("role") or "staff").strip()
        staff.append({
            "name": name,
            "role": role[:1].upper() + role[1:],
            # the activity calendars this person is cleared for: their staff
            # page says only these are proposed when the session is built
            "activities": [cat_name_by_id[c] for c in (st.get("categories") or [])
                           if c in cat_name_by_id],
            "langs": [LANG_NAMES.get(l, l) for l in (st.get("languages") or [])],
            "pos": st.get("order"),
            "onPlanning": st.get("show_in_agenda") is not False,
            # freelancers here for a season, which is most of the instructors
            "seasonFrom": st.get("working_season_starting_day") or "",
            "seasonTo": st.get("working_season_ending_day") or "",
        })

    spots = []
    spot_ids = []
    for sp in _rows(_get(s, base, f"/schools/{sid}/spots/")):
        loc = (sp.get("location") or {}).get("coordinates") or [None, None]
        spots.append({"name": sp.get("name"), "lat": loc[1], "lon": loc[0],
                      "notes": (sp.get("description") or "").strip()})
        if sp.get("id"):
            spot_ids.append((sp["id"], sp.get("name")))
    spot_name_by_id = {i: n for i, n in spot_ids}

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
            # who is teaching it, by name -- the board's staff view is empty
            # without this, which is the view the school actually rosters from
            crew = []
            for a in (x.get("assigned") or []):
                nm = " ".join(y for y in (a.get("first_name"), a.get("last_name"))
                              if y).strip()
                if nm:
                    crew.append(nm)
            sessions.append({
                "date": d, "time": hhmm,
                "title": x.get("name") or cat.get("name") or "Session",
                "category": cat.get("name") or "",
                "duration": mins,
                "capacity": x.get("max_attendants") or x.get("allowed_attendants") or 1,
                "staff": crew,
                "spot": spot_name_by_id.get(x.get("spot"), ""),
                # their level is an id into a list this export does not fetch,
                # so it is left out rather than written down as a number the
                # app would read as a word
                "minCapacity": x.get("min_attendants") or 0,
                "allDay": bool(x.get("all_day_event")),
                "isPublic": x.get("public") is not False,
                "note": (x.get("description") or "").strip(),
            })

    return {"products": products, "gear": gear, "categories": cats,
            "spots": spots, "staff": staff, "sessions": sessions, "tides": tides}


def crew_numbers(session=None, base=None, sid=None):
    """The crew's own WhatsApp numbers, on their own, kept out of the catalogue.

    A reminder that cannot reach anybody is not a reminder, so these have to
    come across -- but they are the one thing in the staff record that must
    not be inlined into a page that can be shared by URL. They go in a file of
    their own, which the build picks up if it is there and the publish check
    refuses if it ever reaches a public build.
    """
    if session is None:
        session, base = login()
    if sid is None:
        sid = school_id(session, base)
    out = []
    for st in _rows(_get(session, base, f"/schools/{sid}/staff/",
                         show_archived="false")):
        name = " ".join(x for x in (st.get("first_name"), st.get("last_name"))
                        if x).strip()
        phone = (st.get("phone") or "").strip()
        if name and phone:
            out.append({"name": name, "phone": phone})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="catalog.json")
    ap.add_argument("--crew-out", default="",
                    help="also write the crew's WhatsApp numbers here, e.g. "
                         "crew.json. Gitignored on purpose: this file holds "
                         "personal mobile numbers and the catalogue does not.")
    a = ap.parse_args()
    try:
        data = build()
        crew = crew_numbers() if a.crew_out else None
    except BloowatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    if crew is not None:
        with open(a.crew_out, "w", encoding="utf-8") as f:
            json.dump(crew, f, ensure_ascii=False, indent=1)
        no = [s["name"] for s in data["staff"]
              if not any(c["name"] == s["name"] for c in crew)]
        print("wrote %s: %d crew with a number%s" % (
            a.crew_out, len(crew),
            (", none for " + ", ".join(no)) if no else ""))
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
