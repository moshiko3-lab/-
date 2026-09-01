#!/usr/bin/env python3
"""The cash-up the office writes out by hand: web / credit lesson / cash lesson.

Every price the school charges is a whole number of dollars, so the day's
takings are whole too: 320 by card, 95 in cash. That is the test the office
applies without thinking about it, and it is why the figures written in the
margin are the payment-method totals and nothing else.

The report also states the same money cut the other way -- of the card takings,
how much was lessons and how much was board hire -- and that block arrives with
four decimal places, because a mixed order is split across its categories by
proportion. Those are shares of a payment, not money anybody took. So the
parser reads them and checks them against the method totals, and the closing
states the whole numbers.

A cash-up figure with cents in it means the report did arithmetic of its own,
and is called out rather than presented as takings. Likewise a split that does
not add back up, and a method with no split at all: a breakdown missing a line
is worse than no breakdown, because it still looks complete.

No real workbook is used here: the rows are written by hand so a day that does
not add up can be tested, which is the case that has to work.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import biff                                                       # noqa: E402
import daily_report as dr                                         # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def parse(rows):
    """Run the parser over handwritten rows instead of a workbook."""
    keep = biff.rows
    biff.rows = lambda data: rows
    try:
        return dr.parse_report(b"")
    finally:
        biff.rows = keep


# a real day's shape, in the report's own layout and order
DAY = [
    ["Shokogi surf school"],
    ["Date: August 27 2026"],
    ["Total Sales", 320.0],
    ["Methods", "No", "Qty"],
    ["Credit card", 5.0, 225.0],
    ["Cash", 4.0, 95.0],
    ["TVA", "No", "Qty"],
    ["Tax 0.0%", 24.0, 320.0],
    ["Account", "No", "Qty"],
    ["LESSONS", 8.0, 172.7273],
    ["BOARD RENTALS", 16.0, 147.2727],
    ["Account = Credit card", "Qty"],
    ["LESSONS", 112.7273],
    ["BOARD RENTALS", 112.2727],
    ["Account = Cash", "Qty"],
    ["BOARD RENTALS", 35.0],
    ["LESSONS", 60.0],
    ["Refunds"],
    ["Clients", "Products", "Payment method", "Amount", "Refund Date"],
    ["Total Refunds", 0.0],
    ["Payment Cancellations"],
    ["Clients", "Products", "Payment method", "Amount", "Cancellation Date"],
    ["Total Cancellations", 0.0],
]


def swap(rows, head, cells):
    """The same day with one row rewritten, for the days that go wrong."""
    out = []
    for r in rows:
        out.append(list(cells) if r and r[0] == head else list(r))
    return out


def main():
    rep = parse(DAY)

    # --- the split is read at all ------------------------------------------
    check("the day still parses as it did", rep["total"] == 320.0
          and rep["methods"]["Cash"]["amount"] == 95.0, str(rep["methods"]))
    check("both methods have a split", sorted(rep["cross"]) ==
          ["Cash", "Credit card"], str(sorted(rep["cross"])))
    check("the card's lessons are separated from its board hire",
          rep["cross"]["Credit card"] == {"LESSONS": 112.7273,
                                          "BOARD RENTALS": 112.2727},
          str(rep["cross"]["Credit card"]))
    check("and the cash likewise",
          rep["cross"]["Cash"] == {"BOARD RENTALS": 35.0, "LESSONS": 60.0},
          str(rep["cross"]["Cash"]))
    check("a clean day says nothing is wrong", rep["warnings"] == [],
          str(rep["warnings"]))

    # --- the tax block is still not mistaken for a split --------------------
    check("the tax block did not become a category",
          "Tax 0.0%" not in rep["categories"] and
          not any("Tax" in c for cs in rep["cross"].values() for c in cs),
          str(rep["categories"]))
    # the refund listing's own header row sits under "Refunds"; if the parser
    # were still inside a split section it would swallow "Clients" as a category
    check("the refund listing was not swallowed",
          not any("Clients" in cs for cs in rep["cross"].values()),
          str(rep["cross"]))

    # --- the cash-up: three whole numbers, and no shop ----------------------
    lines, total = dr.cash_up(rep)
    check("the cash-up is written in the office's own order",
          [n for n, _ in lines] == ["web", "credit lesson", "cash lesson"],
          str(lines))
    check("credit lesson is the card takings", dict(lines)["credit lesson"] == 225.0,
          str(lines))
    check("cash lesson is the cash takings", dict(lines)["cash lesson"] == 95.0,
          str(lines))
    check("web is nil on a day nothing came through the gateway",
          dict(lines)["web"] == 0.0, str(lines))
    check("and it adds to the day's total", total == 320.0, str(total))
    check("every figure in it is a whole number",
          all(float(v).is_integer() for _, v in lines), str(lines))
    check("the shop is not in it — it is a different till",
          not any("shop" in n for n, _ in lines), str(lines))

    # --- the categories are whole too, and still add to the day -------------
    # a real day: four categories whose shares carry four decimal places and
    # whose floors fall a dollar short of the takings
    whole = dr.whole_split({"BOARD RENTALS": 503.0, "LESSONS": 301.0296,
                            "PACKAGES": 219.3103, "PHOTOGRAPHY": 2.6601}, 1026.0)
    check("the categories are stated in whole dollars",
          all(isinstance(v, int) for v in whole.values()), str(whole))
    check("and they add to the day's takings exactly",
          sum(whole.values()) == 1026, str(sum(whole.values())))
    check("the odd dollar goes where the largest fraction was",
          whole["PHOTOGRAPHY"] == 3 and whole["LESSONS"] == 301, str(whole))
    check("a day whose parts already fit is left alone",
          dr.whole_split({"LESSONS": 60.0, "BOARD RENTALS": 35.0}, 95.0) ==
          {"LESSONS": 60, "BOARD RENTALS": 35})
    check("and a dollar too many is taken back, not left over",
          sum(dr.whole_split({"A": 10.9, "B": 10.9, "C": 10.9}, 32.0).values()) == 32)
    check("nothing to split is not an error", dr.whole_split({}, 0.0) == {})

    # --- the decimals stay out of the sheet ---------------------------------
    row = dr.summarise(rep)
    check("the sheet keeps the columns it always had",
          "Split" not in dr.COLUMNS and "Cross" not in dr.COLUMNS,
          str(dr.COLUMNS))
    check("and its money columns are the cash-up's own",
          (row["Credit"], row["Cash"], row["Web"]) == (225.0, 95.0, 0.0),
          str((row["Credit"], row["Cash"], row["Web"])))
    money = ("Total", "Credit", "Cash", "Web", "OtherPay", "Packages",
             "Lessons", "Rentals", "Photography", "Other")
    check("nothing with cents in it reached the row",
          all(float(row[c]).is_integer() for c in money),
          str({c: row[c] for c in money}))
    check("and the categories in the row add to its total",
          row["Packages"] + row["Lessons"] + row["Rentals"] +
          row["Photography"] + row["Other"] == row["Total"],
          str({c: row[c] for c in money}))

    # --- the split is still read, as a second route to the same number ------
    cats, methods, cell = dr.cross_table(rep)
    check("the table names its rows and columns",
          cats == ["LESSONS", "BOARD RENTALS"] and
          methods == ["Credit card", "Cash"], str(cats) + " / " + str(methods))
    check("and every cell adds back to the method it came from",
          abs(sum(cell(c, "Cash") for c in cats) - 95.0) < 0.01,
          str([cell(c, "Cash") for c in cats]))

    # --- a figure with cents in it is not takings ---------------------------
    cents = parse(swap(DAY, "Cash", ["Cash", 4.0, 94.8700]))
    check("a method total with cents in it is called out",
          any("not a whole number" in w for w in cents["warnings"]),
          str(cents["warnings"]))
    check("and the day is marked for checking",
          dr.summarise(cents)["Check"] == "CHECK!")

    # --- a split that does not add up is refused ----------------------------
    bad = parse(swap(DAY, "Cash", ["Cash", 4.0, 120.0]))
    check("a split that misses money is called out",
          any("split for Cash" in w for w in bad["warnings"]),
          str(bad["warnings"]))
    check("and the day is marked for checking",
          dr.summarise(bad)["Check"] == "CHECK!")

    # --- a method with no block at all --------------------------------------
    gone = [r for r in DAY if r[0] != "Account = Cash"
            and r != ["BOARD RENTALS", 35.0] and r != ["LESSONS", 60.0]]
    miss = parse(gone)
    check("a method with no split is said out loud",
          any("no split for Cash" in w for w in miss["warnings"]),
          str(miss["warnings"]))
    check("its money is not quietly dropped",
          miss["methods"]["Cash"]["amount"] == 95.0)

    # --- a split for a method that was never taken --------------------------
    ghost = parse(DAY + [["Account = Money transfer", "Qty"],
                         ["LESSONS", 40.0]])
    check("a split with no method behind it is called out",
          any("no method row" in w for w in ghost["warnings"]),
          str(ghost["warnings"]))

    # --- a day with no split blocks at all ----------------------------------
    plain = parse([r for r in DAY if not str(r[0]).startswith("Account = ")
                   and r not in (["LESSONS", 112.7273],
                                 ["BOARD RENTALS", 112.2727],
                                 ["BOARD RENTALS", 35.0], ["LESSONS", 60.0])])
    check("a report without the blocks is not treated as broken",
          plain["warnings"] == [], str(plain["warnings"]))
    check("and the cash-up still states the day in full",
          dr.cash_up(plain)[1] == 320.0, str(dr.cash_up(plain)))

    # --- a method the office has no line for still gets one -----------------
    moved = swap(DAY, "Cash", ["Money transfer", 4.0, 95.0])
    moved = swap(moved, "Account = Cash", ["Account = Money transfer", "Qty"])
    extra = parse(moved)
    names = [n for n, _ in dr.cash_up(extra)[0]]
    check("an unusual payment method gets a line of its own",
          "money transfer" in names, str(names))
    check("so the cash-up still adds to the day", dr.cash_up(extra)[1] == 320.0,
          str(dr.cash_up(extra)))

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
