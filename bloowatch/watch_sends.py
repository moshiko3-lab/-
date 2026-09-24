#!/usr/bin/env python3
"""Which of tonight's messages were due by now, and which never arrived.

    python3 watch_sends.py
    python3 watch_sends.py --json
    python3 watch_sends.py --now 19:30        # reason about an earlier moment

`audit_reminders.py` does this for the daytime reminder slots. This does it
for the three evening sends that go to the largest audiences: the 18:00
forecast to both surfer groups, the 19:00 rota to the staff group, and the
19:15 personal rotas.

**Why it exists.** On 13/09/2026 the 18:00 forecast routine fired on time,
stopped on a permission prompt three minutes in, and sat there. It sent
nothing, it reported nothing, and because a run that hangs never finishes
it raised no completion notification either. The owner found out at 19:00,
by looking at the group himself and asking. Nothing in the system knew.

A routine cannot be relied on to report its own failure -- the failures
that matter are exactly the ones that stop it from reporting. So this asks
the other side of the wire: **Green-API's outgoing journal**, the record of
what actually reached WhatsApp, which survives the sending container dying
mid-sentence.

**What counts as evidence.** For the rotas, the heading that names
tomorrow's date, taken from `rota._heading` rather than spelled out here,
so it cannot drift away from the message it is looking for. For the
forecast, its own opening line. In both cases the message must have gone
to the right chat: the same heading reaches every instructor privately, so
"somebody got tomorrow's date" is not evidence that the *group* did.

**It only reports.** Deciding to re-send is the routine's job, using the
ordinary scripts, because a tool that both detects and sends is one bug
away from sending twice -- and a group that gets the forecast twice is a
group people leave.

Exit status is 1 when something due is missing.
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import approval                                                # noqa: E402
import audit_reminders as A                                    # noqa: E402
import daily_report                                            # noqa: E402
import rota                                                    # noqa: E402
import send                                                    # noqa: E402

PANAMA = rota.PANAMA

# The forecast's own opening line, in both languages, from
# forecast_message.build and _build_en. test_watch pins these against that
# file so a reworded greeting fails loudly instead of quietly making every
# evening look fine.
FORECAST_HE = "ערב טוב חברים"
FORECAST_EN = "Good evening everyone"

# A run is not late the moment it is due: the 19:00 rota takes a minute to
# photograph the board. Nothing is called missing until this much past.
GRACE_MINUTES = 20


def due_times(date):
    """What is due tonight, in Panama time, and what proves it arrived."""
    def at(h, m):
        return dt.datetime.combine(date, dt.time(h, m), tzinfo=PANAMA)
    return [
        {"what": "forecast_he", "due": at(18, 0),
         "group": "surfers_he", "marker": FORECAST_HE},
        {"what": "forecast_en", "due": at(18, 0),
         "group": "surfers_en", "marker": FORECAST_EN},
        {"what": "staff_rota", "due": at(19, 0),
         "group": "staff", "marker": None},          # filled in per tomorrow
        {"what": "personal_rotas", "due": at(19, 15),
         "group": None, "marker": None},
    ]


def _said_to(said, jid, marker):
    return any(marker in text for text in said.get(jid, []))


def audit(now=None, tomorrow=None):
    now = now or dt.datetime.now(PANAMA)
    today = now.date()
    tom = tomorrow or (today + dt.timedelta(days=1))

    ident = os.environ.get("GREENAPI_ID", "")
    token = os.environ.get("GREENAPI_TOKEN", "")
    if not (ident and token and os.environ.get("GREENAPI_URL")):
        raise SystemExit("error: GREENAPI_ID, GREENAPI_TOKEN and "
                         "GREENAPI_URL must be set. Never guess a token.")

    book = rota._book()
    groups = book.get("groups", {})

    # One fetch, then a cutoff per item, rather than one window for all of
    # them. The forecast opens with the same greeting every night, so asking
    # "is this greeting anywhere in the last day" is answered by yesterday's
    # forecast for ever -- which is exactly what happened on 14/09/2026: the
    # 18:00 forecast never went out and this check said everything was fine.
    # Each item is now asked about its own evening: sent at or after the
    # moment it was due, give or take the few minutes a routine takes to
    # start.
    raw = A.journal(ident, token)

    # A forecast the office has not released is not a forecast that went
    # astray. Without this the 18:25 net would find it missing, the recovery
    # routine would send it, and the approval the owner asked for on
    # 24/9/2026 would be undone half an hour later by the safety net built
    # to protect the same message.
    verdict = approval.state(ident, token, now=now)
    stopped, _ = approval.held(verdict)

    missing = []
    for item in due_times(today):
        if now < item["due"] + dt.timedelta(minutes=GRACE_MINUTES):
            continue                                   # not late yet
        if stopped and item["what"].startswith("forecast"):
            continue

        said = A.by_chat(raw, since=item["due"] - dt.timedelta(minutes=10))

        if item["what"] == "personal_rotas":
            missing.extend(_personal(said, tom, book))
            continue

        marker = item["marker"] or rota._heading(tom.isoformat(), "he")
        where = send.target(item["group"], groups)
        if _said_to(said, where["jid"], marker):
            continue
        missing.append({"what": item["what"],
                        "due": item["due"].strftime("%H:%M"),
                        "to": item["group"],
                        "for": tom.isoformat()})
    return missing


def _personal(said, tom, book):
    """Every instructor who teaches tomorrow and was not written to.

    plan() owns every rule about who may be messaged -- the quiet list, the
    sending number, the missing-number rule, and who reads English. Asking
    it rather than restating it keeps those rules in one place, so somebody
    deliberately left off the list is never reported as a failure.
    """
    session, base = daily_report.login()
    lessons = rota.lessons_for(session, base, tom.isoformat())
    if not lessons:
        return []

    from export_catalog import crew_numbers
    numbers = crew_numbers()
    people = sorted(rota.by_person(lessons))
    sends, _ = rota.plan(lambda n, lang: "x", people,
                         numbers=numbers, book=book)

    out = []
    for one in sends:
        where = send.target(one["phone"], {})
        lang = "en" if one.get("lang") == "en" else "he"
        marker = rota._heading(tom.isoformat(), lang)
        if _said_to(said, where["jid"], marker):
            continue
        out.append({"what": "personal_rota",
                    "due": "19:15",
                    "to": one.get("name") or "?",
                    "for": tom.isoformat()})
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true",
                    help="machine-readable, for a routine to act on")
    ap.add_argument("--now", help="HH:MM in Panama, instead of the clock")
    a = ap.parse_args()

    now = None
    if a.now:
        h, _, m = a.now.partition(":")
        now = dt.datetime.now(PANAMA).replace(
            hour=int(h), minute=int(m or 0), second=0, microsecond=0)

    missing = audit(now=now)

    if a.json:
        print(json.dumps(missing, ensure_ascii=False))
    elif not missing:
        print("everything due by now went out")
    else:
        for m in missing:
            print("MISSING  %-16s due %s  to %s  (for %s)"
                  % (m["what"], m["due"], m["to"], m["for"]))

    # Filed either way, and that matters more here than anywhere else: a
    # safety net that only speaks up when it finds something is
    # indistinguishable from one that is not running at all.
    #
    # The approval state rides on the same line, and it is the only place it
    # is written down. From 24/9/2026 the forecast waits for a typed word and
    # the ten-minute tick that carries it files nothing while it waits --
    # eighteen identical lines an evening would bury the journal. Without
    # this, a night nobody approved and a night the routines never fired
    # look exactly alike in the morning, which is the confusion this whole
    # file exists to prevent.
    import report
    state = approval.state(now=now)
    report.result("safety net", "RESULT missing=%d %s approval=%s" % (
        len(missing), ",".join(m["what"] for m in missing) or "all sent",
        state["decision"]),
        echo=not a.json)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
