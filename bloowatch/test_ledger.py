#!/usr/bin/env python3
"""Rebuilding the day from its payment rows, the way the office does it.

The office reads the payment list, sees what each order was for, and files the
whole payment under that heading. It gets whole dollars that way -- rentals
292, lessons 429 -- where the report's own category block gets 312.9375,
because the report divides a payment across an open tab by proportion.

The judgement is in the mixed tabs, and it is the only thing here worth
arguing about: 87 paid against a tab that holds board hire, a lesson and four
yoga mats is not attributable on its own. The rule is the first thing on the
tab, which is a convention, so every payment where it actually had to decide
is reported rather than buried. These checks pin that down: the rule is
applied, the deciding cases are all listed, and a tab of one kind never
appears as a decision.

The whole day of 30/08/2026 is reproduced here from the real shapes, so the
numbers below are the ones the office wrote by hand that evening. Nothing
touches the network.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ledger                                                     # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def line(kind, price=10.0):
    return {"product": {"product_class": "rental" if kind == "r" else "class",
                        "name": "BOARD" if kind == "r" else "LESSON"},
            "line_price_incl_tax": str(price)}


def order(oid, number, kinds):
    return {"id": oid, "order_number": number,
            "lines": [line(k) for k in kinds]}


def pay(pid, oid, number, amount, method, when="Sun, 30 Aug 2026 15:52:18 -0500",
        customer="someone"):
    return {"id": pid, "order": oid, "order_number": number,
            "amount": amount, "payment_method": method,
            "date_created": when, "customer": customer}


# 30/08/2026 as it happened: eleven payments across nine tabs, two of them
# holding more than one kind of thing
ORDERS = {
    1472585: order(1472585, "HXEFE", "rrrrrrr"),
    1472662: order(1472662, "VFPGA", "rrr"),
    1529706: order(1529706, "YESCX", "rcccc"),      # board, lesson, yoga...
    1536190: order(1536190, "RMVOV", "rr"),
    1551604: order(1551604, "TLSUJ", "cc"),
    1551694: order(1551694, "PALLY", "r"),
    1551814: order(1551814, "ZXGOA", "cr"),         # course, then a board
    1551840: order(1551840, "DELTR", "r"),
    1551843: order(1551843, "SBKNO", "c"),
}
PAYS = [
    # newest first, the way the API hands them over
    pay(1536745, 1551694, "PALLY", "45.0000", "Credit card",
        "Mon, 31 Aug 2026 17:27:00 -0500"),
    pay(1535587, 1529706, "YESCX", "87.0000", "Credit card"),
    pay(1535585, 1551604, "TLSUJ", "30.0000", "Credit card"),
    pay(1535565, 1551843, "SBKNO", "60.0000", "Cash"),
    pay(1535562, 1551840, "DELTR", "10.0000", "Credit card"),
    pay(1535557, 1472662, "VFPGA", "54.0000", "Credit card"),
    pay(1535540, 1472585, "HXEFE", "108.0000", "Credit card"),
    pay(1535527, 1551814, "ZXGOA", "309.0000", "Credit card"),
    pay(1535502, 1536190, "RMVOV", "13.0000", "Credit card"),
    pay(1535417, 1551694, "PALLY", "20.0000", "Credit card"),
    pay(1535315, 1551604, "TLSUJ", "15.0000", "Credit card"),
    pay(1535316, 1551604, "TLSUJ", "15.0000", "Credit card"),
    # and one from the day before, so the walk knows it has gone far enough
    pay(1534639, 1551843, "SBKNO", "50.0000", "Credit card",
        "Sat, 29 Aug 2026 16:11:07 -0500"),
]


class FakeOrders:
    """Stands in for the binary search, which is the only part that dials out."""

    def __init__(self, book):
        self.book, self.asked = book, []

    def get(self, oid):
        self.asked.append(oid)
        return self.book.get(oid)


class Page:
    def __init__(self, body):
        self.status_code, self._body = 200, body

    def json(self):
        return self._body


class FakeApi:
    """Hands out the payment list in pages, newest first, as the API does.

    The paging and the day filter are the parts most likely to go quietly
    wrong -- a day cut short at a page boundary loses money without saying so
    -- so they are exercised for real rather than stubbed over.
    """

    def __init__(self, pays, size=4):
        self.pays, self.size, self.pages = pays, size, 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.pages += 1
        i = (int((params or {}).get("page", 1)) - 1) * self.size
        rows = self.pays[i:i + self.size]
        return Page({"count": len(self.pays), "results": rows,
                     "next": "more" if i + self.size < len(self.pays) else None})


def read(pays=None, book=None):
    api = FakeApi(pays if pays is not None else PAYS)
    return ledger.read_day(api, "http://x", "2026-08-30",
                           FakeOrders(book if book is not None else ORDERS))


def main():
    # --- reading a row ------------------------------------------------------
    check("an amount is a number", ledger._amount("87.0000") == 87.0)
    check("a refund in accounting brackets is negative",
          ledger._amount("(50.0000)") == -50.0)
    check("a payment's day is its own, in Panama time",
          ledger._day("Sun, 30 Aug 2026 15:52:18 -0500").isoformat() == "2026-08-30")
    check("and an hour before midnight is still that day",
          ledger._day("Sun, 30 Aug 2026 23:40:00 -0500").isoformat() == "2026-08-30")

    # --- what a tab is filed under ------------------------------------------
    check("a tab of boards is board hire",
          ledger.heading(order(1, "A", "rrr")) == ("rentals", False))
    check("a tab of lessons is lessons",
          ledger.heading(order(1, "A", "cc")) == ("lessons", False))
    check("a mixed tab takes the first thing on it, and says it decided",
          ledger.heading(order(1, "A", "rcccc")) == ("rentals", True))
    check("the other way round too",
          ledger.heading(order(1, "A", "cr")) == ("lessons", True))
    check("an empty order decides nothing",
          ledger.heading({"lines": []}) == (None, False))
    check("and neither does an order that could not be read",
          ledger.heading(None) == (None, False))

    # --- the day ------------------------------------------------------------
    day = read()
    check("only that day's payments are counted", day["payments"] == 11,
          str(day["payments"]))
    check("the day's takings are the day's payments", day["total"] == 721.0,
          str(day["total"]))
    check("credit and cash are separated",
          (day["methods"]["Credit card"], day["methods"]["Cash"]) == (661.0, 60.0),
          str(day["methods"]))
    check("board hire comes to what the office wrote",
          day["activity"]["rentals"] == 292.0, str(day["activity"]))
    check("and lessons to the rest of it",
          day["activity"]["lessons"] == 429.0, str(day["activity"]))
    check("the two headings account for the whole day",
          sum(day["activity"].values()) == day["total"], str(day["activity"]))
    check("every figure is a whole number",
          all(float(v).is_integer() for v in day["methods"].values()) and
          all(float(v).is_integer() for v in day["activity"].values()),
          str(day["methods"]) + str(day["activity"]))
    check("a clean day says nothing is wrong", day["warnings"] == [],
          str(day["warnings"]))

    # --- and the split by how it was paid -----------------------------------
    check("cash is all lesson that day",
          day["cross"]["Cash"] == {"lessons": 60.0, "rentals": 0.0},
          str(day["cross"]))
    check("the card carries both",
          day["cross"]["Credit card"] == {"lessons": 369.0, "rentals": 292.0},
          str(day["cross"]))

    # --- the judgement is reported, never buried ----------------------------
    check("both tabs it had to decide are listed", len(day["mixed"]) == 2,
          str(day["mixed"]))
    check("each says what it decided and what was on the tab",
          {(m["order"], m["amount"], m["filed_as"]) for m in day["mixed"]} ==
          {("YESCX", 87.0, "rentals"), ("ZXGOA", 309.0, "lessons")},
          str(day["mixed"]))
    check("a tab of one kind is not reported as a decision",
          all(m["order"] not in ("HXEFE", "PALLY") for m in day["mixed"]),
          str(day["mixed"]))

    # --- an order that cannot be read is money left unplaced ----------------
    lost = read(book={k: v for k, v in ORDERS.items() if k != 1551814})
    check("its takings are still counted in full", lost["total"] == 721.0,
          str(lost["total"]))
    check("but it is not filed under a guess",
          sum(lost["activity"].values()) == 412.0, str(lost["activity"]))
    check("and the day is called out rather than quietly short",
          any("could not be read" in w for w in lost["warnings"]),
          str(lost["warnings"]))

    # --- a refund takes money back out --------------------------------------
    back = read(pays=[PAYS[0], PAYS[1],
                      pay(9, 1551843, "SBKNO", "(60.0000)", "Cash"), PAYS[-1]])
    check("a refund comes off the day", back["total"] == 27.0, str(back["total"]))
    check("and off the heading it was filed under",
          back["activity"]["lessons"] == -60.0, str(back["activity"]))

    # --- the walk itself ----------------------------------------------------
    api = FakeApi(PAYS, size=4)
    got = ledger.payments_for(api, "http://x", "2026-08-30")
    check("the day is read across page boundaries", len(got) == 11, str(len(got)))
    check("and the walk stops once it is past the day", api.pages == 4,
          str(api.pages))
    check("a day with nothing in it is not an error",
          ledger.payments_for(FakeApi(PAYS), "http://x", "2026-08-28") == [])

    # --- against the official report ----------------------------------------
    rep = {"total": 721.0, "methods": {"Credit card": {"amount": 661.0},
                                       "Cash": {"amount": 60.0}}}
    check("agreeing with the report is silent",
          ledger.check_against_report(day, rep) == [],
          str(ledger.check_against_report(day, rep)))
    off = {"total": 736.0, "methods": {"Credit card": {"amount": 676.0},
                                       "Cash": {"amount": 60.0}}}
    notes = ledger.check_against_report(day, off)
    check("a day the two disagree about is not quoted quietly",
          any("!=" in n for n in notes) and len(notes) == 2, str(notes))
    missing = {"total": 661.0, "methods": {"Credit card": {"amount": 661.0}}}
    check("and a method the report does not know about is named",
          any("not the report" in n for n in
              ledger.check_against_report(day, missing)),
          str(ledger.check_against_report(day, missing)))

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
