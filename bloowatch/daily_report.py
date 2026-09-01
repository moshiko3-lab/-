#!/usr/bin/env python3
"""Fetch SHOKOGI's official daily closing report straight from Bloowatch.

Bloowatch's own dashboard builds its daily report from
``/api/payments/daily-report?from_date=YYYY/MM/DD``. We ask for exactly the
same thing, so the numbers are the company's, not a reconstruction: no manual
download, no guessing how a mixed order splits between lessons and rentals.

Usage:
    python3 daily_report.py 2026-08-27 [2026-08-28 ...]
    python3 daily_report.py --json 2026-08-27

Credentials come from the environment and are never written to disk or logged:
    BLOOWATCH_URL       e.g. https://shokogi.bloowatch.com
    BLOOWATCH_EMAIL
    BLOOWATCH_PASSWORD

Notes for whoever maintains this:
  * The API's ``date_start`` / ``date_end`` filters are silently IGNORED on the
    payments and orders endpoints -- they return the most recent rows across
    all dates. Never trust them; this module does not use them.
  * Chromium in the sandbox cannot reach the host over TLS 1.3 (the relay drops
    the oversized ClientHello), which is why login goes through requests, not a
    browser.
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys

import requests

import biff

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# Categories Bloowatch reports under "Account". The first four are the ones the
# summary sheet has columns for; anything else is folded into "Other" and named
# in the notes, so a new category can never vanish silently.
MAIN_CATEGORIES = ("PACKAGES", "LESSONS", "BOARD RENTALS", "PHOTOGRAPHY")
METHODS = ("Credit card", "Cash", "Payment gateway")


class BloowatchError(RuntimeError):
    pass


def _env(name):
    v = os.environ.get(name)
    if not v:
        raise BloowatchError(
            f"{name} is not set. Configure BLOOWATCH_URL, BLOOWATCH_EMAIL and "
            f"BLOOWATCH_PASSWORD as environment variables on the environment "
            f"so they survive a container restart.")
    return v


def login(session=None):
    """Sign in and return (session, base_url). The token stays in the session."""
    base = _env("BLOOWATCH_URL").rstrip("/")
    s = session or requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": base + "/",
                      "X-Requested-With": "XMLHttpRequest"})
    # The dashboard posts {username, password} to /api/auth/login/ and gets
    # back {token, school, user}; the token then goes out as "Token <t>".
    r = s.post(f"{base}/api/auth/login/",
               json={"username": _env("BLOOWATCH_EMAIL"),
                     "password": _env("BLOOWATCH_PASSWORD")},
               timeout=45)
    token = None
    if r.status_code < 400:
        try:
            body = r.json()
            token = body.get("token")
        except ValueError:
            body = {}
    if not token:
        raise BloowatchError(
            f"login failed (HTTP {r.status_code}). Check BLOOWATCH_EMAIL / "
            f"BLOOWATCH_PASSWORD; the password is never printed here.")
    s.headers["Authorization"] = f"Token {token}"
    return s, base


def fetch_report(session, base, date):
    """Download one day's official report and return the raw .xls bytes."""
    d = dt.date.fromisoformat(date) if isinstance(date, str) else date
    r = session.get(f"{base}/api/payments/daily-report",
                    params={"from_date": d.strftime("%Y/%m/%d")}, timeout=90)
    if r.status_code != 200:
        raise BloowatchError(f"daily-report for {d} returned HTTP {r.status_code}")
    if not r.content.startswith(b"\xd0\xcf\x11\xe0"):
        raise BloowatchError(f"daily-report for {d} is not an .xls workbook")
    return r.content


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_report(data, expect_date=None):
    """Turn one report workbook into a plain dict."""
    rows = biff.rows(data)
    flat = [[c for c in r] for r in rows]

    out = {"date": None, "total": 0.0, "transactions": 0,
           "methods": {}, "categories": {}, "cross": {}, "refunds": 0.0,
           "cancellations": 0.0, "warnings": []}

    section = None
    method = None          # which "Account = <method>" block we are inside
    for r in flat:
        cells = [c for c in r if c not in ("", None)]
        if not cells:
            continue
        head = str(cells[0]).strip()

        m = re.match(r"^Date:\s*(.+)$", head)
        if m:
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    out["date"] = dt.datetime.strptime(m.group(1).strip(), fmt).date().isoformat()
                    break
                except ValueError:
                    continue
            continue

        if head == "Total Sales":
            out["total"] = _num(cells[1]) or 0.0
            continue
        if head == "Total Refunds":
            out["refunds"] = _num(cells[1]) or 0.0
            continue
        if head == "Total Cancellations":
            out["cancellations"] = _num(cells[1]) or 0.0
            continue

        # section headers
        if head == "Methods":
            section = "methods"; continue
        if head == "Account":
            section = "account"; continue
        m = re.match(r"^Account = (.+)$", head)
        if m:
            # the same money as "Methods", cut the other way: how much of the
            # credit card came from lessons and how much from board hire. This
            # is the split the office writes out by hand every evening.
            method = m.group(1).strip()
            out["cross"].setdefault(method, {})
            section = "cross"
            continue
        if head == "TVA" or head in ("Refunds", "Payment Cancellations"):
            # the tax block and the refund listing are detail the summary does
            # not use; skip until the next section we care about
            section = None
            continue

        if section == "methods" and len(cells) >= 3:
            n, amt = _num(cells[1]), _num(cells[2])
            if n is not None and amt is not None:
                out["methods"][head] = {"count": int(n), "amount": amt}
        elif section == "account" and len(cells) >= 3:
            amt = _num(cells[2])
            if amt is not None:
                out["categories"][head] = amt
        elif section == "cross" and method and len(cells) >= 2:
            amt = _num(cells[1])
            if amt is not None:
                out["cross"][method][head] = out["cross"][method].get(head, 0.0) + amt

    out["transactions"] = sum(v["count"] for v in out["methods"].values())

    # --- integrity checks: say so rather than quietly producing a wrong row ---
    ms = sum(v["amount"] for v in out["methods"].values())
    if abs(ms - out["total"]) > 0.01:
        out["warnings"].append(f"methods sum {ms:.2f} != total {out['total']:.2f}")
    cs = sum(out["categories"].values())
    if out["categories"] and abs(cs - out["total"]) > 0.01:
        out["warnings"].append(f"categories sum {cs:.2f} != total {out['total']:.2f}")
    # Every price the school charges is a whole number of dollars, so every
    # method's takings are whole too -- 513, 25, 15, never 512.87. A method
    # that comes back with cents in it is the report doing arithmetic of its
    # own, not the day's money, and the closing must not state it as takings.
    for name, v in sorted(out["methods"].items()):
        if abs(v["amount"] - round(v["amount"])) > 0.004:
            out["warnings"].append(f"{name} {v['amount']:.4f} is not a whole number")
    # The split has to add back up to the method it came out of, and no method
    # may be missing a block -- otherwise the office would be reading a
    # breakdown that quietly leaves money out.
    if out["cross"]:
        for name, cats in sorted(out["cross"].items()):
            want = out["methods"].get(name, {}).get("amount")
            got = sum(cats.values())
            if want is None:
                out["warnings"].append(f"split for {name} {got:.2f} has no method row")
            elif abs(got - want) > 0.01:
                out["warnings"].append(
                    f"split for {name} {got:.2f} != method {want:.2f}")
        for name in sorted(out["methods"]):
            if name not in out["cross"]:
                out["warnings"].append(f"no split for {name}")
    if expect_date and out["date"] and out["date"] != expect_date:
        out["warnings"].append(f"report is for {out['date']}, asked for {expect_date}")
    return out


def _ordered(names):
    """Main categories first, in their usual order, then the rest by name."""
    known = [c for c in MAIN_CATEGORIES if c in names]
    return known + sorted(n for n in names if n not in MAIN_CATEGORIES)


def cross_table(rep):
    """The split as a table: (categories, methods, cell(cat, method))."""
    cross = rep.get("cross") or {}
    methods = [m for m in METHODS if m in cross] + \
              sorted(m for m in cross if m not in METHODS)
    names = set()
    for cats in cross.values():
        names.update(cats)
    return _ordered(names), methods, lambda c, m: cross.get(m, {}).get(c, 0.0)


def whole_split(values, total):
    """Whole dollars that still add to the day's total exactly.

    The category figures arrive with four decimal places, and the decimals are
    not money: Bloowatch divides an order that covers a lesson and a board hire
    between the two by proportion. Those shares even drift between one reading
    and the next, which is how a summary ends up reporting that a finished day
    changed when nothing about it did.

    So they are stated in whole dollars. Rounding each one on its own would
    lose or gain a dollar against the day's takings, which is the one number
    that is beyond doubt -- instead the dollar goes to whichever category has
    the largest fraction left over, so the parts always add to the whole.
    """
    if not values:
        return {}
    floors = {k: int(v // 1) for k, v in values.items()}
    short = int(round(total)) - sum(floors.values())
    # hand out (or take back) the odd dollars, biggest leftover first
    order = sorted(values, key=lambda k: (values[k] - floors[k], k), reverse=short > 0)
    for k in order[:abs(short)]:
        floors[k] += 1 if short > 0 else -1
    return floors


def cash_up(rep):
    """The three figures the office writes out by hand at the end of the day.

    Not a new calculation: the day's payments added up by how they were paid,
    which is what the report's own "Methods" block already states. They are
    whole numbers because every price the school charges is whole -- and that
    is the point of stating them this way. The report's *other* breakdown, of
    each method across lessons and board hire, arrives with four decimal places
    because Bloowatch splits a mixed order across its categories by proportion.
    Those are shares of a payment, not money anybody took, so they have no
    place in a cash-up. They are still read, and still checked against these
    totals, because a second route to the same number is worth having.

    Returns [(label, amount)] in the order the office writes them, then the
    total. "Shop" takings are not here: they are a different till in a
    different system, and nothing in this report knows about them.
    """
    m = rep["methods"]
    out = [("web", m.get("Payment gateway", {}).get("amount", 0.0)),
           ("credit lesson", m.get("Credit card", {}).get("amount", 0.0)),
           ("cash lesson", m.get("Cash", {}).get("amount", 0.0))]
    for name in sorted(m):
        if name not in METHODS:
            out.append((name.lower(), m[name]["amount"]))
    return out, sum(v for _, v in out)


def summarise(rep):
    """Flatten a parsed report into the columns the summary sheet uses."""
    cats = dict(rep["categories"])
    other = {k: v for k, v in cats.items() if k not in MAIN_CATEGORIES}
    # Cash/credit/gateway are the usual three, but Check, Money transfer and
    # OTA Payment all turn up in real days. They are perfectly valid -- they
    # just need a column of their own, or their money would vanish from the
    # method breakdown while still counting toward the total.
    other_pay = {m: v["amount"] for m, v in rep["methods"].items() if m not in METHODS}
    # stated in whole dollars, and still adding to the day: see whole_split
    whole = whole_split(cats, rep["total"])
    notes = list(rep["warnings"])
    if other_pay:
        notes.append("also paid by " + ", ".join(f"{k} {v:.0f}" for k, v in sorted(other_pay.items())))
    if other:
        notes.append("other categories: " + ", ".join(f"{k} {whole[k]}" for k in sorted(other)))
    if rep["refunds"]:
        notes.append(f"refunds {rep['refunds']:.2f}")
    if rep["cancellations"]:
        notes.append(f"cancellations {rep['cancellations']:.2f}")
    d = dt.date.fromisoformat(rep["date"]) if rep["date"] else None
    return {
        "Date": rep["date"] or "",
        "Day": d.strftime("%a") if d else "",
        "Transactions": rep["transactions"],
        "Total": round(rep["total"], 2),
        "Credit": round(rep["methods"].get("Credit card", {}).get("amount", 0.0), 2),
        "Cash": round(rep["methods"].get("Cash", {}).get("amount", 0.0), 2),
        "Web": round(rep["methods"].get("Payment gateway", {}).get("amount", 0.0), 2),
        "OtherPay": round(sum(other_pay.values())),
        "Packages": whole.get("PACKAGES", 0),
        "Lessons": whole.get("LESSONS", 0),
        "Rentals": whole.get("BOARD RENTALS", 0),
        "Photography": whole.get("PHOTOGRAPHY", 0),
        "Other": sum(whole[k] for k in other),
        "Refunds": round(rep["refunds"], 2),
        "Check": "CHECK!" if rep["warnings"] else "OK",
        "Notes": "; ".join(notes),
    }


COLUMNS = ["Date", "Day", "Transactions", "Total", "Credit", "Cash", "Web",
           "OtherPay", "Packages", "Lessons", "Rentals", "Photography",
           "Other", "Refunds", "Check", "Notes"]


def get_days(dates, reports=False):
    s, base = login()
    out = []
    for d in dates:
        rep = parse_report(fetch_report(s, base, d), expect_date=d)
        out.append(rep if reports else summarise(rep))
    return out


def print_cash_up(rep):
    """The end-of-day block, laid out the way it is written by hand."""
    lines, total = cash_up(rep)
    cats = whole_split(rep["categories"], rep["total"])
    rows = lines + [("total", total)] + \
        [(k.lower(), v) for k, v in sorted(cats.items(), key=lambda kv: -kv[1])]
    width = max(len(n) for n, _ in rows)
    print(rep["date"] or "?")
    for i, (name, amt) in enumerate(rows):
        if i == len(lines) + 1:
            print()
        print(f"  {name.ljust(width)}  {amt:>8,.0f}")
    for w in rep["warnings"]:
        print(f"  CHECK! {w}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dates", nargs="+", help="dates as YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    ap.add_argument("--cash-up", action="store_true",
                    help="print the end-of-day block instead of a table")
    a = ap.parse_args()
    try:
        rows = get_days(a.dates, reports=a.cash_up)
    except BloowatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if a.cash_up:
        for rep in rows:
            print_cash_up(rep)
        return 0
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        # a proper writer, because Notes carries commas of its own
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in COLUMNS])
    return 0


if __name__ == "__main__":
    sys.exit(main())
