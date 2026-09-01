#!/usr/bin/env python3
"""The day rebuilt from the payments themselves, one row at a time.

The daily report states the day's money by category too, but it gets there by
proportion: a payment against an order that is still open divides across that
order's lines by their value, which is where 312.9375 comes from. Nobody took
312.9375. The office does it the other way -- it reads the payment list, sees
what the order was for, and puts the whole payment under that heading -- and
gets whole dollars: rentals 292, lessons 429.

    python3 ledger.py 2026-08-30

This does the same thing, from the same rows.

    payment 87  ->  order 1529706  ->  its first line is a board hire
                ->  the 87 counts as board hire

**Where the judgement is.** An order here is a running tab: seven board hires
on one order, paid off in parts. Two of the nine tabs settled on 30/08 carried
more than one kind of thing, so a payment against them is not attributable on
its own -- 87 paid on a tab holding 198 of board hire, 54 of lesson and 100 of
yoga. The office rule is that the payment takes the heading of the first thing
on the tab. That is a convention, not a fact, so every tab where it actually
had to decide is listed in `mixed` and reported, and never buried.

Bloowatch's API will not filter, so the orders behind a day's payments are
found by binary search over the school's own order list -- about forty small
requests for a day, and the probes are shared between orders and between days.
"""
import argparse
import datetime as dt
import email.utils
import re
import sys

from daily_report import BloowatchError, login

SCHOOL = 127
# Bloowatch's own word for it: everything that is not a board going out is a
# lesson of some kind -- a class, a course, a camp, a yoga mat.
RENTAL_CLASS = "rental"


def _amount(v):
    """Payment amounts arrive as strings, refunds in accounting parentheses."""
    t = str(v).strip()
    neg = t.startswith("(") and t.endswith(")")
    n = float(re.sub(r"[()]", "", t) or 0)
    return -n if neg else n


def _day(v):
    """'Sun, 30 Aug 2026 15:52:18 -0500' -> date, already in Panama time."""
    return email.utils.parsedate_to_datetime(v).date()


def payments_for(session, base, date, page_size=200, max_pages=25):
    """Every payment recorded on one day.

    The API ignores its own date filters, so the list is walked newest first
    and stopped once it is past the day asked for.
    """
    want = dt.date.fromisoformat(date) if isinstance(date, str) else date
    out, page = [], 1
    while page <= max_pages:
        r = session.get(f"{base}/api/schools/{SCHOOL}/payments/",
                        params={"page_size": page_size, "page": page},
                        headers={"Accept": "application/json"}, timeout=60)
        if r.status_code != 200:
            raise BloowatchError(f"payments page {page} returned HTTP {r.status_code}")
        body = r.json()
        rows = body.get("results") or []
        if not rows:
            break
        for p in rows:
            if _day(p["date_created"]) == want:
                out.append(p)
        if _day(rows[-1]["date_created"]) < want or not body.get("next"):
            return out
        page += 1
    raise BloowatchError(
        f"walked {max_pages} pages of payments without reaching {want}; "
        f"the day is further back than this is willing to page")


class Orders:
    """Finds an order by id, without a filter to do it with.

    The school's orders come back newest first and their ids only ever go up,
    so the list is sorted and can be searched. Probes are remembered, which is
    what makes a second order on the same day cheap and a second day cheaper
    still.
    """

    def __init__(self, session, base):
        self.s, self.base = session, base
        self.at, self.by_id, self.total, self.calls = {}, {}, None, 0

    def _at(self, i):
        if i not in self.at:
            self.calls += 1
            r = self.s.get(f"{self.base}/api/schools/{SCHOOL}/orders/",
                           params={"page_size": 1, "page": i + 1, "ordering": "-id"},
                           headers={"Accept": "application/json"}, timeout=60)
            if r.status_code != 200:
                raise BloowatchError(f"orders page {i + 1} returned HTTP {r.status_code}")
            body = r.json()
            rows = body.get("results") or []
            self.total = body.get("count")
            self.at[i] = rows[0] if rows else None
            if self.at[i]:
                self.by_id[self.at[i]["id"]] = self.at[i]
        return self.at[i]

    def get(self, oid):
        if oid in self.by_id:
            return self.by_id[oid]
        if self.total is None:
            self._at(0)
        lo, hi = 0, (self.total or 1) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            o = self._at(mid)
            if o is None:
                return None
            if o["id"] == oid:
                return o
            lo, hi = (mid + 1, hi) if o["id"] > oid else (lo, mid - 1)
        return None


def heading(order):
    """What the office would file this order under, and whether it had to pick.

    Returns (heading, mixed) -- mixed is true when the tab held more than one
    kind of thing, which is exactly when the answer is a convention.
    """
    lines = (order or {}).get("lines") or []
    if not lines:
        return None, False
    kinds = ["rentals" if (l["product"].get("product_class") == RENTAL_CLASS)
             else "lessons" for l in lines]
    return kinds[0], len(set(kinds)) > 1


def read_day(session, base, date, orders=None):
    """One day, rebuilt from its payments."""
    orders = orders or Orders(session, base)
    pays = payments_for(session, base, date)

    out = {"date": date, "payments": len(pays), "total": 0.0,
           "methods": {}, "activity": {"lessons": 0.0, "rentals": 0.0},
           "cross": {}, "mixed": [], "unknown": [], "warnings": []}

    for p in pays:
        amt = _amount(p["amount"])
        method = p["payment_method"] or "?"
        out["total"] += amt
        out["methods"][method] = out["methods"].get(method, 0.0) + amt

        order = orders.get(p["order"])
        head, mixed = heading(order)
        if head is None:
            out["unknown"].append(p["order_number"] or p["order"])
            continue
        out["activity"][head] += amt
        out["cross"].setdefault(method, {"lessons": 0.0, "rentals": 0.0})
        out["cross"][method][head] += amt
        if mixed:
            out["mixed"].append({
                "order": p["order_number"] or p["order"], "amount": amt,
                "filed_as": head, "customer": p.get("customer") or "",
                "holds": sorted({("rentals" if l["product"].get("product_class")
                                  == RENTAL_CLASS else "lessons")
                                 for l in order["lines"]})})

    # Every price the school charges is whole, so every one of these is whole.
    for name, v in sorted(out["methods"].items()):
        if abs(v - round(v)) > 0.004:
            out["warnings"].append(f"{name} {v:.4f} is not a whole number")
    placed = sum(out["activity"].values())
    if out["unknown"]:
        out["warnings"].append(
            f"{len(out['unknown'])} payment(s) whose order could not be read: "
            + ", ".join(str(x) for x in out["unknown"][:5]))
    elif abs(placed - out["total"]) > 0.004:
        out["warnings"].append(
            f"filed {placed:.2f} against takings of {out['total']:.2f}")
    return out


def check_against_report(day, report):
    """The ledger and the official report have to agree on the money.

    They are two different routes to the same day -- one adds up the payment
    rows, the other is Bloowatch's own summary -- so a disagreement means one
    of them is wrong and neither should be quoted until it is understood.
    """
    notes = []
    if abs(day["total"] - report["total"]) > 0.01:
        notes.append(f"ledger {day['total']:.2f} != report {report['total']:.2f}")
    for name, v in sorted(report["methods"].items()):
        got = day["methods"].get(name, 0.0)
        if abs(got - v["amount"]) > 0.01:
            notes.append(f"{name}: ledger {got:.2f} != report {v['amount']:.2f}")
    for name in sorted(day["methods"]):
        if name not in report["methods"]:
            notes.append(f"{name} is in the ledger but not the report")
    return notes


def render(day):
    rows = [("web", day["methods"].get("Payment gateway", 0.0)),
            ("credit lesson", day["methods"].get("Credit card", 0.0)),
            ("cash lesson", day["methods"].get("Cash", 0.0))]
    for name in sorted(day["methods"]):
        if name not in ("Payment gateway", "Credit card", "Cash"):
            rows.append((name.lower(), day["methods"][name]))
    rows.append(("total", day["total"]))
    rows.append((None, None))
    rows.append(("lessons", day["activity"]["lessons"]))
    rows.append(("rentals", day["activity"]["rentals"]))

    width = max(len(n) for n, _ in rows if n)
    print(f"{day['date']}   {day['payments']} payments")
    for name, amt in rows:
        print("" if name is None else f"  {name.ljust(width)}  {amt:>8,.0f}")
    for m in day["mixed"]:
        print(f"  note: {m['amount']:,.0f} on order {m['order']} filed as "
              f"{m['filed_as']} — that tab holds {' and '.join(m['holds'])}")
    for w in day["warnings"]:
        print(f"  CHECK! {w}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dates", nargs="+", help="dates as YYYY-MM-DD")
    ap.add_argument("--verify", action="store_true",
                    help="also read the official report and check they agree")
    a = ap.parse_args()
    try:
        s, base = login()
        orders = Orders(s, base)
        for d in a.dates:
            day = read_day(s, base, d, orders)
            if a.verify:
                from daily_report import fetch_report, parse_report
                rep = parse_report(fetch_report(s, base, d), expect_date=d)
                for n in check_against_report(day, rep):
                    day["warnings"].append(n)
            render(day)
    except BloowatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
