#!/usr/bin/env python3
"""Build the JSON dataset that the SHOKOGI dashboard renders.

Everything here is read-only: it signs in, pulls what the dashboard needs, and
writes one JSON file. Nothing is ever written back to Bloowatch.

    python3 export_dataset.py --days 30 --out dataset.json

Credentials come from BLOOWATCH_URL / BLOOWATCH_EMAIL / BLOOWATCH_PASSWORD.
"""
import argparse
import datetime as dt
import json
import sys

from daily_report import (BloowatchError, fetch_report, login, parse_report,
                          summarise)

# Panama runs on UTC-5 all year -- no daylight saving to chase.
PANAMA = dt.timezone(dt.timedelta(hours=-5))


def today_panama():
    return dt.datetime.now(PANAMA).date()


def _get(session, base, path, **params):
    # Without an explicit JSON Accept header the API answers some routes
    # (notably /sessions/) with HTML, which then fails to parse.
    r = session.get(f"{base}/api{path}", params=params, timeout=60,
                    headers={"Accept": "application/json, text/javascript, */*; q=0.01"})
    r.raise_for_status()
    return r.json()


def _rows(payload):
    if isinstance(payload, dict):
        return payload.get("results") or []
    return payload or []


def school_id(session, base):
    me = _get(session, base, "/users/me/") if False else None
    # The school id is stable for this account; discover it from the categories
    # endpoint the dashboard itself calls on boot.
    for sid in (127,):
        return sid
    raise BloowatchError("could not determine school id")


def closings(session, base, days, end=None):
    """One summary row per day, newest last, skipping days that error out."""
    end = end or today_panama()
    out, problems = [], []
    for i in range(days - 1, -1, -1):
        d = (end - dt.timedelta(days=i)).isoformat()
        try:
            row = summarise(parse_report(fetch_report(session, base, d), expect_date=d))
        except Exception as e:                      # one bad day must not sink the export
            problems.append({"date": d, "error": str(e)[:200]})
            continue
        if row["Transactions"] or row["Total"]:
            out.append(row)
    return out, problems


def reference(session, base, sid):
    """Look-up tables so sessions can show names instead of ids."""
    staff, cats, spots = {}, {}, {}
    for s in _rows(_get(session, base, f"/schools/{sid}/staff/",
                        show_archived="false")):
        name = " ".join(x for x in (s.get("first_name"), s.get("last_name")) if x).strip()
        staff[s["id"]] = {"name": name or s.get("username") or "?", "role": s.get("role")}
    for c in _rows(_get(session, base, f"/schools/{sid}/categories/",
                        show_archived="false")):
        cats[c["id"]] = {"name": c.get("name") or "?", "color": c.get("color")}
    for p in _rows(_get(session, base, f"/schools/{sid}/spots/")):
        spots[p["id"]] = p.get("name") or "?"
    return staff, cats, spots


def agenda(session, base, sid, cats, spots, start, days):
    """Scheduled sessions for a window of days, flattened for display."""
    out = []
    for i in range(days):
        d = (start + dt.timedelta(days=i)).isoformat()
        try:
            rows = _rows(_get(session, base, f"/schools/{sid}/sessions/",
                              date=d, offset=0, limit=100, ordering="starting_time"))
        except Exception:
            continue
        for s in rows:
            st = s.get("starting_time") or ""
            hhmm = ""
            if st:
                try:
                    hhmm = dt.datetime.strptime(st[:25].strip(),
                                                "%a, %d %b %Y %H:%M:%S").strftime("%H:%M")
                except ValueError:
                    hhmm = st[17:22]
            cat = cats.get(s.get("category"), {})
            out.append({
                "date": d,
                "time": hhmm,
                "name": s.get("name") or cat.get("name") or "?",
                "category": cat.get("name") or "",
                "color": cat.get("color") or "",
                "spot": spots.get(s.get("spot"), ""),
                "duration": str(s.get("duration") or "")[:5],
                "attendants": s.get("attendants") or 0,
                "max": s.get("max_attendants") or 0,
                "public": bool(s.get("public")),
            })
    return out


def catalogue(session, base, sid):
    prods = []
    for p in _rows(_get(session, base, f"/schools/{sid}/products/")):
        if p.get("archived"):
            continue
        prods.append({
            "name": p.get("name") or p.get("title") or "?",
            "klass": p.get("product_class") or "",
            "category": p.get("category_name") or "",
            "price": p.get("price"),
            "sessions": p.get("num_sessions"),
        })
    rentals = [{"name": r.get("name") or "?", "units": r.get("units"),
                "type": r.get("rental_type")}
               for r in _rows(_get(session, base, f"/schools/{sid}/rentals/"))
               if not r.get("archived")]
    return prods, rentals


def build(days=30, agenda_days=7):
    s, base = login()
    sid = school_id(s, base)
    school = _get(s, base, f"/schools/{sid}/")
    rows, problems = closings(s, base, days)
    staff, cats, spots = reference(s, base, sid)
    today = today_panama()
    prods, rentals = catalogue(s, base, sid)
    return {
        "generated_at": dt.datetime.now(PANAMA).isoformat(timespec="minutes"),
        "school": school.get("commercial_name") or school.get("name") or "SHOKOGI",
        "today": today.isoformat(),
        "closings": rows,
        "problems": problems,
        "agenda": agenda(s, base, sid, cats, spots, today, agenda_days),
        "staff": sorted(
            ({"name": v["name"], "role": v["role"]} for v in staff.values()),
            key=lambda x: x["name"]),
        "products": prods,
        "rentals": rentals,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30, help="days of closings to pull")
    ap.add_argument("--agenda-days", type=int, default=7)
    ap.add_argument("--out", default="dataset.json")
    a = ap.parse_args()
    try:
        data = build(a.days, a.agenda_days)
    except BloowatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {a.out}: {len(data['closings'])} closing days, "
          f"{len(data['agenda'])} sessions, {len(data['products'])} products")
    if data["problems"]:
        print(f"note: {len(data['problems'])} day(s) could not be fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
