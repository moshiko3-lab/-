#!/usr/bin/env python3
"""The desk app is a different school's worth of trust, so the payload has
to be right before it leaves.

Four ways this goes wrong, and none of them look like an error:

**A booking the desk app refuses** comes back 400 and the hire simply
never appears. Their parser rejects three things -- no name, an unparseable
time, an end at or before the start -- so those are caught here and
reported, not posted.

**The wrong id** is the quiet one. One order can carry several boards; on
19/10/2026 order 1567060 had two for the same customer. Keyed on the order
they collapse into one rental, and a board goes out with nothing on the
desk screen to say so.

**The wrong clock.** Bloowatch answers `Wed, 21 Oct 2026 11:14:00 -0500`;
their parser calls `Date.parse`, which needs ISO 8601. Send the raw string
and every booking is rejected; send it without the offset and every board
is five hours out.

**The secret in the open.** It must never reach a log line, a report or
the journal.

Nothing here touches the network, and nothing here can post.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import push_boards as P                                        # noqa: E402
import rentals as R                                            # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def at(d, h, m=0):
    return dt.datetime(2026, 10, d, h, m,
                       tzinfo=R.PANAMA).strftime("%a, %d %b %Y %H:%M:%S -0500")


def rent(rid, unit, model, who, out, due, cust=1, order=1,
         status="Confirmed", rtype="gear"):
    return {
        "id": rid, "type": "DEFAULT", "rental_unit": unit,
        "starting_time": out, "ending_time": due,
        "customers": ([{"id": 1, "customer": cust, "notes": "",
                        "customer_name": who}] if who is not None else []),
        "rental_unit_info": {
            "id": unit, "name": model, "max_pax": 1,
            "rental": {"id": 6838, "name": "SHOKOGI SOFTBOARDS",
                       "rental_type": rtype, "archived": False}},
        "order_id": order, "order_status": status,
        "status": "booked", "notes": "",
    }


def main():
    # --- Bloowatch's clock, as their parser needs to read it -------------
    iso = P._iso("Wed, 21 Oct 2026 11:14:00 -0500")
    check("the time goes out as ISO 8601", iso.startswith("2026-10-21T11:14"),
          iso)
    check("and keeps Panama's offset, or every board is five hours out",
          iso.endswith("-05:00"), iso)
    check("an unreadable time is empty, not a crash", P._iso("nonsense") == "")

    # --- the payload, end to end ----------------------------------------
    HIRES = {
        "2026-10-23": [
            # one order, two boards, one customer: the case that must stay two
            rent(101, 160051, "6'6/BLUE/OM", "Mark davey", at(23, 9), at(29, 20),
                 cust=7, order=1567060),
            rent(102, 160039, "7'0/BROWN/OM", "Mark davey", at(23, 9), at(29, 20),
                 cust=7, order=1567060),
            # the three their parser would refuse
            rent(103, 160033, "7'0/BLUE/OM", None, at(23, 9), at(23, 20)),
            rent(104, 160034, "7'0/BLUE/OM", "No Times", "", ""),
            rent(105, 160035, "7'0/BLUE/OM", "Backwards", at(23, 20), at(23, 9)),
            # a tipi is not a board
            rent(106, 9001, "TIPI 1", "a guest", at(23, 9), at(25, 20),
                 rtype="accommodation"),
        ],
        "2026-10-24": [
            # the same long hire again: one booking, not two
            rent(101, 160051, "6'6/BLUE/OM", "Mark davey", at(23, 9), at(29, 20),
                 cust=7, order=1567060),
            rent(107, 160057, "6'0/LIGHT BLUE/OM", "Dana", at(24, 8), at(24, 20),
                 cust=9),
        ],
    }

    real_hires, real_get, real_login = R.hires, P._get, P.login
    calls = []

    def fake_get(s, b, path, **k):
        calls.append(path)
        return {"phone": "+507 6000 0000" if "/7/" in path else "", "id": 7}

    P._get = fake_get
    R.hires = lambda s, b, sid, date: HIRES.get(date, [])
    P.login = lambda: (None, "https://x")
    try:
        books, skipped = P.bookings(date="2026-10-23", days=2, sid=127)
    finally:
        R.hires, P._get, P.login = real_hires, real_get, real_login

    ids = [b["booking_id"] for b in books]
    check("two boards on one order stay two bookings",
          "101" in ids and "102" in ids, str(ids))
    check("and the id is the hire, never the order",
          all(b["booking_id"] != str(b["order_id"]) for b in books), str(ids))
    check("a long hire seen on both days is sent once",
          ids.count("101") == 1, str(ids))
    check("the tipi is not sent", "106" not in ids, str(ids))
    check("tomorrow's hire is included with --days 2", "107" in ids, str(ids))

    why = {s["id"]: s["why"] for s in skipped}
    check("a hire with no customer is skipped, not sent blank",
          "103" not in ids and 103 in why, str(why))
    check("an unreadable time is skipped", "104" not in ids and 104 in why)
    check("and so is an end before the start",
          "105" not in ids and 105 in why, str(why))
    check("every skip says why, for the report",
          all(w for w in why.values()), str(why))

    # Their parser's own rules, applied to what we actually built.
    for b in books:
        check("%s has every field their parser requires" % b["booking_id"],
              b["booking_id"] and b["name"]
              and b["starts_at"] < b["due_at"], json.dumps(b, ensure_ascii=False))

    check("the phone is fetched from the customer, not invented",
          any("/customers/7/" in c for c in calls), str(calls))
    mark = [b for b in books if b["booking_id"] == "101"][0]
    check("and lands on the booking", mark["phone"] == "+507 6000 0000",
          mark["phone"])
    check("a customer is looked up once however many boards they take",
          len([c for c in calls if "/customers/7/" in c]) == 1, str(calls))
    dana = [b for b in books if b["booking_id"] == "107"][0]
    check("a customer with no number still goes, matched on the name",
          dana["phone"] == "" and dana["name"] == "Dana", str(dana))

    check("bookings come out in the order they start",
          [b["starts_at"] for b in books] == sorted(b["starts_at"] for b in books))

    # --- the secret never appears anywhere ------------------------------
    src = open(os.path.join(HERE, "push_boards.py"), encoding="utf-8").read()
    check("the secret comes from the environment",
          "BOARDS_SECRET" in src and 'os.environ.get(name)' in src)
    # The real risk is not where it is read but where it is written: one
    # print or report line carrying it puts it in the WhatsApp journal.
    loud = [ln.strip() for ln in src.splitlines()
            if ("print(" in ln or "report.result(" in ln) and "secret" in ln]
    check("and never reaches a print or a report line", not loud, str(loud))
    check("the RESULT line carries counts only",
          "RESULT sent=%d failed=%d skipped=%d" in src)
    check("and a refused secret stops the run instead of repeating it",
          "code in (401, 409)" in src)

    # --- it reads Bloowatch and writes only to the desk app -------------
    check("nothing here writes to Bloowatch",
          ".post(" in src and "/api/bloowatch/webhook" in src
          and "bloowatch.com" not in src)

    print("\n" + ("all checks passed" if not fails
                  else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
