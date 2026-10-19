#!/usr/bin/env python3
"""The board store, and the four ways of getting it wrong.

**A board counted free that is out** is the failure this file exists for. It
does not look like an error anywhere: the counter hires it to the next
customer, two people arrive for one board, and nothing in any screen said so.

**A board called late that is not** is the other direction and costs more
than it looks. Chase a customer who has two days left and the next real
alert is the one nobody reads.

**A model is not a board.** Twelve units are named `7'0/BROWN/OM` and they
are twelve of the same model, so hiring one must take one off that model's
count -- not all twelve, and not a thirteenth that does not exist.

**And the tipis are not boards.** Three of the eight families are
accommodation. Counted in, the store reads twelve units fuller than it is,
and a guest still in their tipi reads as a missing surfboard.

Nothing here touches the network. The two live calls -- the store and the
day's hires -- are replaced with recorded shapes taken off the real API on
19/10/2026, so the parsing is tested against what Bloowatch actually sends.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rentals as R                                            # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


# Recorded off /schools/127/rentals/ -- two gear families and one tipi, with
# the duplicate-name case and a single-unit case both present.
STORE = [
    {"id": 6838, "name": "SHOKOGI SOFTBOARDS", "rental_type": "gear",
     "archived": False, "units": [
         {"id": 160033, "name": "7'0/BLUE/OM", "next_check": None},
         {"id": 160034, "name": "7'0/BLUE/OM", "next_check": "2026-12-01"},
         {"id": 160039, "name": "7'0/BROWN/OM", "next_check": None},
         {"id": 160051, "name": "6'6/BLUE/OM", "next_check": None},
     ]},
    {"id": 6840, "name": "SHOKOGI SURFBOARDS", "rental_type": "gear",
     "archived": False, "units": [
         {"id": 171405, "name": "F19/TORQ 6'6/SWOLLOW/GO KART",
          "next_check": None},
     ]},
    {"id": 6900, "name": "TIPI BIG", "rental_type": "accommodation",
     "archived": False, "units": [{"id": 9001, "name": "TIPI 1"}]},
    {"id": 6999, "name": "OLD STOCK", "rental_type": "gear",
     "archived": True, "units": [{"id": 9999, "name": "GONE"}]},
]


def rent(rid, unit, model, who, out, due, fam="SHOKOGI SOFTBOARDS",
         rtype="gear", order=1, status="Confirmed"):
    """One row in the shape /rents/ really answers with."""
    return {
        "id": rid, "type": "DEFAULT", "rental_unit": unit,
        "starting_time": out, "ending_time": due,
        "customers": [{"id": 1, "customer": 2, "notes": "",
                       "customer_name": who}] if who else [],
        "rental_unit_info": {
            "id": unit, "name": model, "max_pax": 1,
            "rental": {"id": 6838, "name": fam, "rental_type": rtype,
                       "archived": False}},
        "order_id": order, "order_status": status, "order_pax": 0,
        "status": "booked", "notes": "",
    }


NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=R.PANAMA)


def at(d, h, m=0):
    return dt.datetime(2026, 10, d, h, m,
                       tzinfo=R.PANAMA).strftime("%a, %d %b %Y %H:%M:%S -0500")


def main():
    # --- Bloowatch's own date format -----------------------------------
    got = R._when("Wed, 14 Oct 2026 06:00:00 -0500")
    check("the API's date format parses", got is not None
          and (got.year, got.month, got.day, got.hour) == (2026, 10, 14, 6),
          repr(got))
    check("and an empty one is not a crash", R._when("") is None
          and R._when(None) is None)
    check("nor is a format nobody expected",
          R._when("whenever it suits") is None)
    # Panama has no daylight saving, so a stamp without an offset is still a
    # Panama stamp -- naive, it would compare as UTC and read five hours out.
    naive = R._when("Wed, 14 Oct 2026 06:00:00")
    check("a stamp with no offset is read as Panama, not as UTC",
          naive is not None and naive.utcoffset() == dt.timedelta(hours=-5),
          repr(naive))

    # --- the store counts models, and leaves the tipis alone ------------
    models = R.store(None, None, None) if False else None
    R._get_real = R._get
    R._get = lambda s, b, p, **k: STORE
    try:
        models = R.store(None, None, 127)
    finally:
        R._get = R._get_real

    check("the two boards sharing a name are one model of stock 2",
          models[("SHOKOGI SOFTBOARDS", "7'0/BLUE/OM")]["stock"] == 2,
          str(models.get(("SHOKOGI SOFTBOARDS", "7'0/BLUE/OM"))))
    check("and a board with its own name is a model of stock 1",
          models[("SHOKOGI SURFBOARDS",
                  "F19/TORQ 6'6/SWOLLOW/GO KART")]["stock"] == 1)
    check("the tipi is not in the board store",
          not any(f == "TIPI BIG" for f, _ in models))
    check("nor is an archived family",
          not any(f == "OLD STOCK" for f, _ in models))
    check("the store holds 5 boards across 4 models",
          sum(m["stock"] for m in models.values()) == 5 and len(models) == 4,
          "%d boards, %d models" % (sum(m["stock"] for m in models.values()),
                                    len(models)))
    # A model is keyed by family too: a softboard and a surfboard of the same
    # name are not interchangeable, and merging them would offer the counter
    # a board of the wrong kind.
    check("a model is a name inside a family, not a name on its own",
          all(isinstance(k, tuple) and len(k) == 2 for k in models))
    check("and the unit ids are kept, so two hires of a model are two hires",
          models[("SHOKOGI SOFTBOARDS", "7'0/BLUE/OM")]["units"]
          == [160033, 160034])
    check("a service date is carried when Bloowatch has one",
          models[("SHOKOGI SOFTBOARDS",
                  "7'0/BLUE/OM")]["service"] == ["2026-12-01"])

    # --- where a hire stands against the clock --------------------------
    # `booked` must never be an answer: it is the only word Bloowatch uses,
    # on every one of its 15,103 rows, and it says nothing about time.
    cases = [
        ("collected, hours to run", at(19, 6), at(19, 20), "out"),
        ("due within the hour", at(19, 6), at(19, 13), "soon"),
        ("due exactly at the edge", at(19, 6), at(19, 15), "soon"),
        ("an hour past the edge is just out", at(19, 6), at(19, 16), "out"),
        ("a minute past due", at(19, 6), at(19, 11, 59), "overdue"),
        ("days past due", at(10, 6), at(12, 20), "overdue"),
        ("booked for tomorrow", at(20, 6), at(20, 20), "later"),
    ]
    for name, out, due, want in cases:
        h = R.shape(rent(1, 160033, "7'0/BLUE/OM", "x", out, due))
        check(name + " reads '%s'" % want, R.state(h, NOW) == want,
              R.state(h, NOW))

    # --- how late, in words somebody acts on ----------------------------
    h = R.shape(rent(1, 160033, "7'0/BLUE/OM", "x", at(19, 6), at(19, 11)))
    c = R.late_by(h, NOW)
    check("an hour late is negative minutes", c["mins"] == -60, str(c))
    check("and reads as an hour", c["words"] == "1h", c["words"])
    h = R.shape(rent(1, 160033, "7'0/BLUE/OM", "x", at(19, 6), at(19, 12, 40)))
    check("forty minutes left reads in minutes",
          R.late_by(h, NOW)["words"] == "40m", R.late_by(h, NOW)["words"])
    h = R.shape(rent(1, 160033, "7'0/BLUE/OM", "x", at(19, 6), at(29, 20)))
    check("ten days left reads in days",
          R.late_by(h, NOW)["words"] == "10d", R.late_by(h, NOW)["words"])

    # --- the whole picture, and the count that must not lie -------------
    HIRES = [
        rent(1, 160033, "7'0/BLUE/OM", "oriya", at(1, 13), at(30, 20)),
        rent(2, 160034, "7'0/BLUE/OM", "Yoav", at(1, 17), at(19, 11)),
        rent(3, 160051, "6'6/BLUE/OM", "Mark", at(10, 15), at(29, 20)),
        rent(4, 9001, "TIPI 1", "a guest", at(18, 15), at(12, 20),
             fam="TIPI BIG", rtype="accommodation"),
        rent(5, 160039, "7'0/BROWN/OM", "jim", at(20, 6), at(23, 20),
             order=77, status="Pending"),
    ]

    real_store, real_hires, real_login = R.store, R.hires, R.login
    R.store = lambda s, b, sid: models
    R.hires = lambda s, b, sid, date: HIRES
    R.login = lambda: (None, "https://x")
    try:
        data = R.board(date="2026-10-19", now=NOW, sid=127)
    finally:
        R.store, R.hires, R.login = real_store, real_hires, real_login

    check("the guest in the tipi is not a hired board",
          len(data["hires"]) == 4 and
          all(h["type"] == "gear" for h in data["hires"]),
          "%d hires" % len(data["hires"]))
    check("the store is 5 boards", data["stock"] == 5, str(data["stock"]))
    check("three are out", data["out"] == 3, str(data["out"]))

    per = {(f["family"], f["model"]): f for f in data["fleet"]}
    key = ("SHOKOGI SOFTBOARDS", "7'0/BLUE/OM")
    check("both of that model are out, so none is free",
          per[key]["out"] == 2 and per[key]["free"] == 0, str(per[key]))
    # The one that matters most: a hire that has not been collected yet must
    # not take a board off the shelf, or a model with one booking for next
    # week reads as unavailable all week.
    brown = per[("SHOKOGI SOFTBOARDS", "7'0/BROWN/OM")]
    check("a board booked for tomorrow is still free today",
          brown["out"] == 0 and brown["free"] == 1, str(brown))
    check("and the surfboard nobody hired is free",
          per[("SHOKOGI SURFBOARDS",
               "F19/TORQ 6'6/SWOLLOW/GO KART")]["free"] == 1)

    check("the overdue one is counted",
          data["counts"].get("overdue") == 1, str(data["counts"]))
    check("the late board is first in the list",
          data["hires"][0]["who"] == "Yoav", data["hires"][0]["who"])
    check("a board out against an unconfirmed order is flagged",
          [h["who"] for h in data["unconfirmed"]] == ["jim"],
          str([h["who"] for h in data["unconfirmed"]]))
    check("and the customer's name comes across",
          {h["who"] for h in data["hires"]} == {"oriya", "Yoav", "Mark", "jim"},
          str({h["who"] for h in data["hires"]}))

    # --- the two states the store should never be in --------------------
    # Both are silent by nature: the arithmetic still works, the screen still
    # renders, and the counter is told a board is free that is not.
    R.store = lambda s, b, sid: {
        ("SHOKOGI SOFTBOARDS", "7'0/BLUE/OM"):
            {"family": "SHOKOGI SOFTBOARDS", "model": "7'0/BLUE/OM",
             "familyId": 6838, "units": [160033], "stock": 1, "service": []}}
    R.hires = lambda s, b, sid, date: [
        rent(1, 160033, "7'0/BLUE/OM", "a", at(1, 6), at(30, 20)),
        rent(2, 160034, "7'0/BLUE/OM", "b", at(1, 6), at(30, 20)),
        rent(3, 777, "A BOARD NOBODY LISTED", "c", at(1, 6), at(30, 20)),
    ]
    try:
        bad = R.board(date="2026-10-19", now=NOW, sid=127)
    finally:
        R.store, R.hires = real_store, real_hires

    check("two out of a stock of one is reported, not clamped to zero",
          len(bad["oversold"]) == 1 and bad["oversold"][0]["free"] == -1,
          str(bad["oversold"]))
    check("and a model hired out that the store has never heard of is named",
          bad["unknownModels"] == [{"family": "SHOKOGI SOFTBOARDS",
                                    "model": "A BOARD NOBODY LISTED"}],
          str(bad["unknownModels"]))

    # --- it reads, and it never writes ----------------------------------
    # `status` is what Bloowatch's own availability check reads. A board
    # marked returned here would start being offered to the next customer
    # while it is still out, which is the exact failure this screen is for.
    src = open(os.path.join(HERE, "rentals.py"), encoding="utf-8").read()
    for verb in (".post(", ".patch(", ".put(", ".delete("):
        check("nothing in rentals.py calls %s" % verb.strip("(."),
              verb not in src)

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
