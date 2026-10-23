#!/usr/bin/env python3
"""What is out of the board store right now, and what is late coming back.

    python3 rentals.py                    # today
    python3 rentals.py --date 2026-10-25
    python3 rentals.py --json             # for the interface
    python3 rentals.py --models           # the whole store, model by model

The owner asked for this on 19/10/2026: an interface that pulls the hires
from Bloowatch live, says which board is out, with whom, and when it is due
back, so that the store can be controlled rather than remembered.

**Where the hires come from.** `/schools/<id>/rents/?date=YYYY-MM-DD`, which
is the one filter that endpoint honours -- it answers with every hire that
*spans* that day, not the ones booked on it, which is exactly the question
"what is out". Each row carries the unit, the customer, the two times and
the order. 15,103 of them exist; this asks for one day at a time.

**What a unit is, and what it is not.** The store has 262 units under eight
families, and only 165 distinct names: `7'0/BROWN/OM` is twelve of them.
Those twelve are not twelve boards somebody has to tell apart -- they are
twelve of the same model, as the owner put it: *"זה פשוט אותו גלשן בכמות"*.
So the unit of inventory here is **the model**, and the number that matters
is how many of a model are out against how many exist. A hire still names
its own unit id, because that is what Bloowatch booked and what makes two
hires of the same model two hires rather than one.

**The gap this fills.** Bloowatch records the booking and nothing after it:
`status` is `"booked"` on all 15,103 rows, including hires from months ago
that plainly came back. So Bloowatch can say what *should* be out and can
never say what *is*. This file reports the booking faithfully and marks
what is overdue against the clock; whether a board was actually collected
or actually returned is the one thing it does not know, and the interface
keeps that separately rather than writing a guess back here.

Read-only. Nothing in this file writes to Bloowatch, by design: `status` is
what Bloowatch's own availability check reads, so a board marked returned
here would start being offered to the next customer while it is still out.
"""

import argparse
import collections
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from daily_report import BloowatchError, login                 # noqa: E402
from export_dataset import PANAMA, _get, _rows, school_id      # noqa: E402

# Boards and suits, not beds. Three of the eight families are the tipis, and
# an accommodation unit in a board count would make the store look fuller
# than it is -- and a tipi "overdue" is a guest, not a missing board.
GEAR = "gear"

# How long before a board is due back it starts asking to be chased. Long
# enough to act on at the counter, short enough that a morning hire due at
# eight in the evening is not flagged all day.
SOON_HOURS = 3

# An order that was never confirmed, with a board already out against it, is
# the one thing worth seeing beside the hire itself.
UNPAID = ("Pending", "Cancelled", "Draft")


def _when(stamp):
    """Bloowatch's own date format, as an aware datetime in Panama time."""
    if not stamp:
        return None
    txt = str(stamp).strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S"):
        try:
            got = dt.datetime.strptime(txt[:31].strip(), fmt)
        except ValueError:
            continue
        return got if got.tzinfo else got.replace(tzinfo=PANAMA)
    return None


def today():
    return dt.datetime.now(PANAMA).date()


def store(session, base, sid):
    """Every model in the board store, with how many of it exist.

    Keyed by (family, model name), because a name is only unique inside its
    family -- and a softboard and a surfboard of the same length are not
    interchangeable, which is the whole point of counting by model.
    """
    models = {}
    for fam in _rows(_get(session, base, f"/schools/{sid}/rentals/")):
        if fam.get("archived") or fam.get("rental_type") != GEAR:
            continue
        for u in (fam.get("units") or []):
            key = (fam.get("name") or "", (u.get("name") or "").strip())
            m = models.setdefault(key, {
                "family": key[0], "model": key[1], "familyId": fam.get("id"),
                "units": [], "stock": 0,
                "service": [],          # next_check dates, for the ones set
            })
            m["units"].append(u.get("id"))
            m["stock"] += 1
            if u.get("next_check"):
                m["service"].append(u["next_check"])
    return models


# How far back to keep asking. `date=D` answers with the hires spanning D
# **and the ones that ended on D-1**, and then they are gone: a hire that
# ended on the 22nd is in the answer for the 23rd and absent from the 24th.
# Asked only about today, a board a fortnight late would have dropped out of
# the one screen whose job is to notice it -- the longer it stayed missing,
# the less likely anyone was to see it. So the window reaches back, and a
# hire whose time is up stays in view until somebody says it came back.
BACK_DAYS = 14


def window(session, base, sid, date, back=None):
    """Every hire still open on `date`, including the ones already overdue.

    One call per day back, deduplicated by hire id. Bloowatch never closes a
    hire -- `status` is "booked" on all of them for ever -- so "still open"
    means nothing here has said otherwise.
    """
    back = BACK_DAYS if back is None else back
    day = dt.date.fromisoformat(date) if isinstance(date, str) else date
    seen, out = set(), []
    for i in range(max(1, back + 1)):
        for row in hires(session, base, sid, (day - dt.timedelta(days=i)).isoformat()):
            if row.get("id") in seen:
                continue
            seen.add(row.get("id"))
            out.append(row)
    return out


def hires(session, base, sid, date):
    """Every hire Bloowatch returns for one day, newest first.

    `date` is the only filter `/rents/` honours. It is close to "active on",
    but not exactly -- see BACK_DAYS. Callers wanting the true open set go
    through `window()`.
    """
    rows, page = [], 1
    while page <= 20:
        got = _get(session, base, f"/schools/{sid}/rents/",
                   date=date, page_size=200, page=page, ordering="-id")
        batch = _rows(got)
        rows.extend(batch)
        if not isinstance(got, dict) or not got.get("next") or not batch:
            break
        page += 1
    else:
        raise BloowatchError(
            "more than 20 pages of hires on %s -- refusing to page further "
            "rather than report a part of the day as the whole of it" % date)
    return rows


def _person(row):
    names = [(c.get("customer_name") or "").strip()
             for c in (row.get("customers") or [])]
    names = [n for n in names if n]
    return ", ".join(names)


def shape(row):
    """One hire, as the interface needs it."""
    info = row.get("rental_unit_info") or {}
    fam = info.get("rental") or {}
    return {
        "id": row.get("id"),
        "unit": row.get("rental_unit"),
        "model": (info.get("name") or "").strip(),
        "family": fam.get("name") or "",
        "type": fam.get("rental_type") or "",
        "who": _person(row),
        "out": row.get("starting_time"),
        "due": row.get("ending_time"),
        "order": row.get("order_id"),
        "orderStatus": row.get("order_status") or "",
        "note": (row.get("notes") or "").strip(),
    }


def state(hire, now):
    """Where this hire stands against the clock.

    `booked` is deliberately not one of the answers. That is the only word
    Bloowatch ever uses and it says nothing about time, which is the thing
    the counter needs to know.
    """
    out, due = _when(hire["out"]), _when(hire["due"])
    if out and now < out:
        return "later"                      # booked, not collected yet
    if due and now > due:
        return "overdue"
    if due and (due - now) <= dt.timedelta(hours=SOON_HOURS):
        return "soon"
    return "out"


def _words(delta):
    mins = int(abs(delta).total_seconds() // 60)
    if mins < 60:
        return "%dm" % mins
    if mins < 60 * 48:
        h, m = divmod(mins, 60)
        return "%dh" % h if not m else "%dh %dm" % (h, m)
    return "%dd" % (mins // (60 * 24))


def late_by(hire, now):
    """How late, or how long left, as a phrase and as minutes."""
    due = _when(hire["due"])
    if not due:
        return {"mins": None, "words": ""}
    mins = int((due - now).total_seconds() // 60)
    return {"mins": mins, "words": _words(due - now)}


def board(date=None, now=None, session=None, base=None, sid=None):
    """The whole picture for one day: the store, the hires, and the counts."""
    if session is None:
        session, base = login()
    if sid is None:
        sid = school_id(session, base)
    date = date or today().isoformat()
    now = now or dt.datetime.now(PANAMA)

    models = store(session, base, sid)
    # Everything the window returns is either still running or past its
    # time with nobody having said it came back, so there is nothing to
    # filter out here beyond the tipis.
    rows = [shape(r) for r in window(session, base, sid, date)]
    rows = [h for h in rows if h["type"] == GEAR]

    out_per_model = collections.Counter()
    for h in rows:
        h["state"] = state(h, now)
        h["clock"] = late_by(h, now)
        h["unconfirmed"] = h["orderStatus"] in UNPAID
        if h["state"] in ("out", "soon", "overdue"):
            out_per_model[(h["family"], h["model"])] += 1

    fleet = []
    for key, m in sorted(models.items()):
        gone = out_per_model.get(key, 0)
        fleet.append(dict(m, out=gone, free=m["stock"] - gone))

    # A hire of a model that is not in the store, or more of a model out than
    # the store holds, is not a rounding error -- it is a board the school
    # thinks it has and does not, and it has to be said rather than clamped.
    unknown = sorted({(h["family"], h["model"]) for h in rows
                      if (h["family"], h["model"]) not in models})
    over = [f for f in fleet if f["free"] < 0]

    rows.sort(key=lambda h: (h["clock"]["mins"] is None,
                             h["clock"]["mins"] or 0))
    counts = collections.Counter(h["state"] for h in rows)
    return {
        "date": date,
        "now": now.isoformat(timespec="minutes"),
        "hires": rows,
        "fleet": fleet,
        "stock": sum(f["stock"] for f in fleet),
        "out": sum(f["out"] for f in fleet),
        "counts": dict(counts),
        "unconfirmed": [h for h in rows if h["unconfirmed"]],
        "unknownModels": [{"family": f, "model": m} for f, m in unknown],
        "oversold": over,
    }


def _print(data, models=False):
    c = data["counts"]
    print("%s — %d of %d boards out" % (data["date"], data["out"], data["stock"]))
    bits = [("%d overdue" % c["overdue"]) if c.get("overdue") else "",
            ("%d due soon" % c["soon"]) if c.get("soon") else "",
            ("%d not collected yet" % c["later"]) if c.get("later") else ""]
    line = ", ".join(b for b in bits if b)
    if line:
        print("  " + line)

    if data["oversold"]:
        print("\n** more out than the store holds **")
        for f in data["oversold"]:
            print("   %s / %s: %d out of %d"
                  % (f["family"], f["model"], f["out"], f["stock"]))
    if data["unknownModels"]:
        print("\n** hired out, not in the store list **")
        for u in data["unknownModels"]:
            print("   %s / %s" % (u["family"], u["model"]))

    if data["hires"]:
        print()
        for h in data["hires"]:
            mark = {"overdue": "LATE", "soon": "soon", "later": "    ",
                    "out": " out"}[h["state"]]
            when = h["clock"]["words"]
            when = ("%s late" % when) if h["state"] == "overdue" else ("%s left" % when)
            print("  %-4s %-26s %-20s %-12s %s%s"
                  % (mark, h["model"][:26], (h["who"] or "—")[:20],
                     when, "#%s" % h["order"],
                     "  UNCONFIRMED" if h["unconfirmed"] else ""))
    else:
        print("\nnothing is out on this day")

    if models:
        print("\n%-22s %-28s %5s %4s %5s"
              % ("family", "model", "stock", "out", "free"))
        for f in data["fleet"]:
            print("%-22s %-28s %5d %4d %5d"
                  % (f["family"][:22], f["model"][:28], f["stock"],
                     f["out"], f["free"]))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD in Panama, default today")
    ap.add_argument("--json", action="store_true",
                    help="the whole picture as JSON, for the interface")
    ap.add_argument("--models", action="store_true",
                    help="also list the store model by model")
    ap.add_argument("--out", help="write the JSON here instead of stdout")
    ap.add_argument("--for-page", metavar="DIR",
                    help="write snap_latest.json and snap_fleet.json here, "
                         "the two documents the board-store page reads")
    a = ap.parse_args()

    try:
        data = board(date=a.date)
    except BloowatchError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    if a.for_page:
        # Two documents, not one: the hires change through the day and the
        # fleet barely ever does, and separate documents are two writes
        # that cannot tread on each other.
        os.makedirs(a.for_page, exist_ok=True)
        keep = ("date", "now", "hires", "stock", "out", "counts",
                "unconfirmed", "unknownModels", "oversold")
        pair = (("snap_latest.json", {k: data[k] for k in keep}),
                ("snap_fleet.json", {"fleet": data["fleet"], "now": data["now"]}))
        for name, doc in pair:
            with open(os.path.join(a.for_page, name), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False)
        print("wrote %s and %s — %d hires, %d of %d boards out, %d overdue"
              % (pair[0][0], pair[1][0], len(data["hires"]), data["out"],
                 data["stock"], data["counts"].get("overdue", 0)))
    elif a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print("wrote %s — %d hires, %d boards out"
              % (a.out, len(data["hires"]), data["out"]))
    elif a.json:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    else:
        _print(data, models=a.models)

    # A board that is late is the whole reason this exists, so it is also the
    # exit status: a routine can act on it without parsing anything.
    return 1 if data["counts"].get("overdue") else 0


if __name__ == "__main__":
    sys.exit(main())
