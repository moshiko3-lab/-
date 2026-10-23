#!/usr/bin/env python3
"""Send today's Bloowatch hires to the Shokogi Boards desk app.

    python3 push_boards.py --dry-run        # show what would be sent
    python3 push_boards.py                  # send
    python3 push_boards.py --days 2         # today and tomorrow
    python3 push_boards.py --manifest       # the active ids, for closing the rest

The owner asked for this on 23/10/2026: every board-rental booking in
Bloowatch should appear in the desk app by itself as a rental waiting for
a board, update when the booking changes, and go away when it is
cancelled.

**Why this side pushes rather than that side pulling.** Bloowatch has no
webhooks and no API key -- its only credential is the owner's dashboard
password, which can read customers, take payments and delete bookings.
Giving that to a web app on a hosting platform would put the whole school
in one web form, with no way to scope it down and no way to revoke it
without breaking the forecast, the rota, the reminders and the board
store at the same time. The desk app already offers a receiving endpoint
(`POST /api/bloowatch/webhook`, guarded by a shared secret and an owner
switch in its own Settings), written as a deliberate seam: "No Bloowatch
endpoints are assumed." So the only credential that crosses is that
secret, and it can do exactly one thing -- file a rental.

**Everything active is sent on every run, and nothing is remembered.**
Their endpoint matches on `bloowatch_booking_id` and updates in place, so
a repeat is free. The alternative -- keeping a note of what was already
sent -- buys a handful of saved requests and costs a whole class of
failure: a routine container is thrown away after every run, and a lost
note is a hire that silently never arrives. With six hires out on a
normal day the saving was never worth it.

**The booking id is the hire, not the order.** One order can carry
several boards: on 19/10/2026 order 1567060 had two, a 7'0 and a 6'6, for
the same customer. Keyed on the order they would collapse into one rental
and a board would be handed out with nothing on the screen to say so.

**What this file does not do: cancellations.** The endpoint creates and
updates; it cannot remove. `--manifest` prints every booking id that is
still live, which is what the desk app needs in order to close the ones
that have gone -- that endpoint does not exist yet (see RENTALS.md).

Nothing here writes to Bloowatch. It reads, and it posts to the desk app.
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import requests                                                # noqa: E402

import rentals                                                 # noqa: E402
from daily_report import BloowatchError, login                 # noqa: E402
from export_dataset import PANAMA, _get, school_id             # noqa: E402

# Their parser rejects a booking with no name, and their customer matching
# works on the phone's digits and falls back to the name. A hire Bloowatch
# recorded against nobody cannot be filed as either, so it is reported
# here rather than sent as a blank customer.
TIMEOUT = 45


def _env(name):
    v = os.environ.get(name)
    if not v:
        raise BloowatchError(
            "%s is not set. Configure BOARDS_URL and BOARDS_SECRET as "
            "environment variables on the environment; the secret is never "
            "printed and never committed." % name)
    return v


class Phones(object):
    """The customer's phone, which a hire row does not carry.

    `/rents/` gives `customer_name` and a customer id, nothing more. The
    number lives on `/schools/<id>/customers/<cid>/`, so it costs one call
    per person -- cached for the run, because the same guest usually has
    several boards.
    """

    def __init__(self, session, base, sid):
        self.s, self.base, self.sid, self.seen = session, base, sid, {}

    def of(self, cid):
        if not cid:
            return ""
        if cid not in self.seen:
            try:
                got = _get(self.s, self.base,
                           "/schools/%s/customers/%s/" % (self.sid, cid))
                self.seen[cid] = (got.get("phone") or "").strip()
            except Exception:                                   # noqa: BLE001
                # A missing number is not a reason to drop the hire: the
                # desk app matches on the name when there is no phone.
                self.seen[cid] = ""
        return self.seen[cid]


def _iso(stamp):
    """Bloowatch's own format as ISO 8601, which is what their parser reads."""
    when = rentals._when(stamp)
    return when.isoformat() if when else ""


def bookings(date=None, days=1, session=None, base=None, sid=None):
    """Every live hire over the window, in the shape the desk app accepts."""
    if session is None:
        session, base = login()
    if sid is None:
        sid = school_id(session, base)
    start = dt.date.fromisoformat(date) if date else rentals.today()
    phones = Phones(session, base, sid)

    out, skipped, seen = [], [], set()
    for i in range(max(1, days)):
        day = (start + dt.timedelta(days=i)).isoformat()
        # window(), not hires(): a board already days late must keep being
        # sent, or the desk app loses exactly the rental it most needs.
        for row in rentals.window(session, base, sid, day):
            hire = rentals.shape(row)
            if hire["type"] != rentals.GEAR:
                continue                    # the tipis are not boards
            if hire["id"] in seen:
                continue                    # a long hire spans both days
            seen.add(hire["id"])

            who = (row.get("customers") or [{}])[0]
            name = (hire["who"] or "").strip()
            starts, due = _iso(hire["out"]), _iso(hire["due"])

            # Exactly the three things their parser refuses. Caught here so
            # the run reports them instead of collecting 400s.
            if not name:
                skipped.append({"id": hire["id"], "why": "no customer name"})
                continue
            if not starts or not due:
                skipped.append({"id": hire["id"], "why": "unreadable times"})
                continue
            if due <= starts:
                skipped.append({"id": hire["id"],
                                "why": "ends at or before it starts"})
                continue

            out.append({
                "booking_id": str(hire["id"]),   # the hire, never the order
                "name": name,
                "phone": phones.of(who.get("customer")),
                "starts_at": starts,
                "due_at": due,
                # not read by their parser today; carried so the desk can
                # show which board without another lookup later
                "unit_name": hire["model"],
                "order_id": hire["order"],
                "order_status": hire["orderStatus"],
            })
    out.sort(key=lambda b: b["starts_at"])
    return out, skipped


def send(book, url, secret, session=None):
    s = session or requests.Session()
    r = s.post(url.rstrip("/") + "/api/bloowatch/webhook",
               json=book, timeout=TIMEOUT,
               headers={"x-webhook-secret": secret,
                        "Content-Type": "application/json"})
    try:
        body = r.json()
    except ValueError:
        body = {"error": (r.text or "")[:160]}
    return r.status_code, body


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD in Panama, default today")
    ap.add_argument("--days", type=int, default=1,
                    help="how many days from --date to include (default 1)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the payloads and send nothing")
    ap.add_argument("--manifest", action="store_true",
                    help="print the live booking ids and nothing else")
    a = ap.parse_args()

    try:
        books, skipped = bookings(date=a.date, days=a.days)
    except BloowatchError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    if a.manifest:
        print(json.dumps({"active": [b["booking_id"] for b in books],
                          "as_of": dt.datetime.now(PANAMA).isoformat(
                              timespec="minutes")}, ensure_ascii=False))
        return 0

    for s in skipped:
        print("skipped %s — %s" % (s["id"], s["why"]), file=sys.stderr)

    if a.dry_run:
        for b in books:
            print(json.dumps(b, ensure_ascii=False))
        print("\nwould send %d booking(s); %d skipped" % (len(books), len(skipped)))
        return 0

    try:
        url, secret = _env("BOARDS_URL"), _env("BOARDS_SECRET")
    except BloowatchError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    sess, sent, failed = requests.Session(), 0, []
    for b in books:
        code, body = send(b, url, secret, session=sess)
        if code in (200, 201):
            sent += 1
            continue
        # 401 is the secret, 409 is the owner's own switch in their
        # Settings -- neither is worth repeating 6 times, so stop.
        failed.append({"id": b["booking_id"], "code": code,
                       "error": body.get("error", "")})
        if code in (401, 409):
            break

    for f in failed:
        print("FAILED %s — HTTP %s %s" % (f["id"], f["code"], f["error"]),
              file=sys.stderr)

    import report
    report.result("boards push", "RESULT sent=%d failed=%d skipped=%d"
                  % (sent, len(failed), len(skipped)), echo=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
