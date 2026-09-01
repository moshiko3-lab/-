#!/usr/bin/env python3
"""The split the office writes out by hand: web / credit lesson / cash lesson.

Bloowatch's daily report already carries it. The report says the day took 320
by card and 95 in cash, and then says it again the other way round -- of that
card money, how much was lessons and how much was board hire. Until now the
parser skipped those blocks, so every evening somebody read them off the screen
and wrote them in the margin.

The numbers matter more than most: they are what the day's cash gets counted
against. So the parser refuses to hand over a split it cannot prove -- each
method's own rows have to add back up to the method's total, and a method with
no block at all is said out loud rather than quietly left out. A breakdown that
is missing a line is worse than no breakdown, because it still looks complete.

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

    # --- the sheet's column, and the table the email lays out ---------------
    row = dr.summarise(rep)
    check("the sheet gets the split as one line",
          row["Split"] == "Credit card LESSONS 112.73 + BOARD RENTALS 112.27; "
                          "Cash LESSONS 60.00 + BOARD RENTALS 35.00",
          repr(row["Split"]))
    check("with no comma in it to break the CSV", "," not in row["Split"],
          repr(row["Split"]))
    check("the split is a column of the sheet", "Split" in dr.COLUMNS)
    check("and the shaped copy is not, so the sheet keeps its columns",
          "Cross" not in dr.COLUMNS)
    cats, methods, cell = dr.cross_table(rep)
    check("the table names its rows and columns",
          cats == ["LESSONS", "BOARD RENTALS"] and
          methods == ["Credit card", "Cash"], str(cats) + " / " + str(methods))
    check("and every cell adds back to the method it came from",
          abs(sum(cell(c, "Cash") for c in cats) - 95.0) < 0.01,
          str([cell(c, "Cash") for c in cats]))

    # --- what Yuval reads off it -------------------------------------------
    check("credit lessons is a number the closing can state",
          abs(rep["cross"]["Credit card"]["LESSONS"] - 112.7273) < 0.01)
    check("cash lessons likewise",
          abs(rep["cross"]["Cash"]["LESSONS"] - 60.0) < 0.01)

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
    check("and its sheet row simply has nothing in the column",
          dr.summarise(plain)["Split"] == "",
          repr(dr.summarise(plain)["Split"]))

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
