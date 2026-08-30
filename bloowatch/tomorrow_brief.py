#!/usr/bin/env python3
"""Tomorrow's board, read out of Bloowatch, written the way a person reads it.

The school still plans its days in Bloowatch, so that is where tomorrow lives.
This asks Bloowatch for one day of sessions and turns them into the message
the crew actually wants at nine at night: the hour, what it is, who is
teaching it, how full it is and who is on it.

    python3 tomorrow_brief.py                    tomorrow, printed
    python3 tomorrow_brief.py --date 2026-09-01  a particular day
    python3 tomorrow_brief.py --send             hand it to the WhatsApp function
    python3 tomorrow_brief.py --keys             what a session row actually has

Credentials come from the environment and are never written to disk or logged:

    BLOOWATCH_URL       https://shokogi.bloowatch.com
    BLOOWATCH_EMAIL
    BLOOWATCH_PASSWORD
    WA_TICK_SECRET      only for --send: what the function checks
    WA_FUNCTION_URL     only to point --send somewhere other than the school's

About --keys: Bloowatch's session row carries the people on it, but the export
this repository already has deliberately drops them, so the field's name was
never written down. --keys prints what one real row has on it, which settles it
in one run rather than in a guess. Until then the reader below tries every
shape the rest of their API uses, and simply says nothing where it finds none
-- a brief without names is still worth sending.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse

import requests

from daily_report import BloowatchError, login
from export_dataset import PANAMA, _get, _rows, school_id

FUNCTION = os.environ.get(
    "WA_FUNCTION_URL",
    "https://bxjwqvoscbzhetuwhyvk.supabase.co/functions/v1/whatsapp")


def hhmm(row):
    """Their starting_time is an RFC-1123 string, and occasionally missing."""
    raw = (row.get("starting_time") or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return dt.datetime.strptime(raw[:25].strip(), fmt).strftime("%H:%M")
        except ValueError:
            continue
    return "--:--"


def person(x):
    """A name out of whatever shape the row hands us."""
    if isinstance(x, str):
        return x.strip()
    if not isinstance(x, dict):
        return ""
    for key in ("full_name", "name", "client_name", "attendant_name"):
        v = (x.get(key) or "").strip() if isinstance(x.get(key), str) else ""
        if v:
            return v
    joined = " ".join(v for v in (x.get("first_name"), x.get("last_name")) if v)
    if joined.strip():
        return joined.strip()
    # one level down: their rows often wrap the person in client/user/attendant
    for key in ("client", "user", "attendant", "customer"):
        if isinstance(x.get(key), dict):
            got = person(x[key])
            if got:
                return got
    return ""


# Every key their API has been seen to hang people off a session by. The first
# one that yields a name wins; the rest are not looked at.
PEOPLE_KEYS = ("attendants", "attendees", "participants", "clients",
               "bookings", "session_attendants", "reservations")


def people_on(row):
    for key in PEOPLE_KEYS:
        got = row.get(key)
        if not got:
            continue
        names = [person(x) for x in got] if isinstance(got, list) else []
        names = [n for n in names if n]
        if names:
            return names
    return []


def crew_on(row):
    out = []
    for a in (row.get("assigned") or []):
        name = person(a)
        if name:
            out.append(name)
    return out


def sessions_for(s, base, sid, date):
    rows = _rows(_get(s, base, f"/schools/{sid}/sessions/",
                      date=date, offset=0, limit=200, ordering="starting_time"))
    out = []
    for x in rows:
        if x.get("cancelled") or x.get("canceled"):
            continue
        out.append({
            "time": hhmm(x),
            "title": (x.get("name") or "").strip() or "Session",
            "crew": crew_on(x),
            "people": people_on(x),
            "seats": x.get("max_attendants") or x.get("allowed_attendants") or 0,
            "spot": x.get("spot_name") or "",
            "note": (x.get("description") or "").strip(),
        })
    out.sort(key=lambda r: r["time"])
    return out


def compose(date, rows, names=True):
    """One line per session, and the people under it. Deliberately plain: this
    is read on a phone, in the dark, by somebody who is half asleep."""
    day = dt.date.fromisoformat(date).strftime("%a %d %b")
    if not rows:
        return f"{day} — nothing on the board."
    pax = sum(len(r["people"]) for r in rows)
    head = f"{day} — {len(rows)} session{'' if len(rows) == 1 else 's'}"
    if pax:
        head += f", {pax} on the water"
    lines = [head]
    for r in rows:
        seats = f"{len(r['people'])}/{r['seats']}" if r["seats"] else str(len(r["people"]))
        bits = [r["time"], r["title"], seats]
        bits.append(", ".join(r["crew"]) if r["crew"] else "unassigned")
        if r["spot"]:
            bits.append(r["spot"])
        lines.append(" · ".join(b for b in bits if b))
        if names and r["people"]:
            lines.append("   " + ", ".join(r["people"]))
    return "\n".join(lines)


def hand_over(text, date):
    """Give it to the function, which owns every rule about sending."""
    secret = os.environ.get("WA_TICK_SECRET", "")
    if not secret:
        raise BloowatchError("WA_TICK_SECRET is not set, so --send has nothing "
                             "to identify itself with")
    r = requests.post(f"{FUNCTION}/brief", timeout=60,
                      headers={"Content-Type": "application/json",
                               "x-wa-secret": secret},
                      json={"text": text, "date": date})
    body = {}
    try:
        body = r.json()
    except ValueError:
        pass
    if r.status_code >= 400 or not body.get("ok"):
        raise BloowatchError(
            f"the function refused it (HTTP {r.status_code}): "
            f"{body.get('error') or r.text[:200]}")
    return body


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="YYYY-MM-DD (default: tomorrow, Panama time)")
    ap.add_argument("--send", action="store_true",
                    help="hand the brief to the WhatsApp function")
    ap.add_argument("--no-names", action="store_true",
                    help="leave the people off, hours and instructors only")
    ap.add_argument("--keys", action="store_true",
                    help="print the keys of one real session row and stop")
    a = ap.parse_args()

    date = a.date or (dt.datetime.now(PANAMA).date() + dt.timedelta(days=1)).isoformat()

    try:
        s, base = login()
        sid = school_id(s, base)
        if a.keys:
            rows = _rows(_get(s, base, f"/schools/{sid}/sessions/",
                              date=date, offset=0, limit=5))
            if not rows:
                print(f"no sessions on {date} to look at", file=sys.stderr)
                return 1
            print(json.dumps(sorted(rows[0].keys()), indent=2))
            return 0
        rows = sessions_for(s, base, sid, date)
    except BloowatchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"error: could not reach Bloowatch: {e}", file=sys.stderr)
        return 1

    text = compose(date, rows, names=not a.no_names)
    print(text)

    # A link that opens WhatsApp with the brief already written. This is the
    # only way into the actual crew group -- their API has no group endpoint --
    # so it is one tap rather than an automation, and it is worth having.
    link = "https://wa.me/?text=" + urllib.parse.quote(text)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### {date}\n\n```\n{text}\n```\n\n"
                    f"[Open WhatsApp with this written]({link})\n")

    if a.send:
        try:
            out = hand_over(text, date)
        except (BloowatchError, requests.RequestException) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"\nhanded over: queued {out.get('queued')}, "
              f"sent {out.get('sent')}, failed {out.get('failed')}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
