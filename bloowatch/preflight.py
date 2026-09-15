#!/usr/bin/env python3
"""Is everything tomorrow needs actually in place, before anyone needs it.

    python3 preflight.py
    python3 preflight.py --json

Every routine in ROUTINES.md begins by assuming four things: the WhatsApp
credentials resolve, the WhatsApp number is still authorised, Bloowatch
still accepts the login, and the tide table reaches far enough forward.
When one of them is false the routine does the right thing -- it stops and
says so -- but it says so **at the moment the message was due**, which is
the worst moment to find out. On 13/09/2026 that moment was 18:02 and the
forecast simply never went out.

This runs the same four checks at half past four in the morning, while
there is a whole day left to fix whatever is broken. It sends nothing and
changes nothing.

**It reports where each secret came from, not just that it exists.** That
distinction is the whole point of the file. `send.py` reads the
environment first and falls back to `.env` beside it, so "the token is
present" is true in two very different worlds: one where the environment
supplies it and the routines need carry no copy, and one where six routine
prompts each write their own copy and a single refresh in the Green-API
console silently invalidates all six. That is not hypothetical either --
it is what happened on 2/9/2026. Until this prints `environment` for all
three GREENAPI keys, the `printf` step cannot come out of the routines.

Exit status is 1 when something is actually broken, so a routine can act
on the status alone and stay quiet on a good morning.
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SECRETS = ("GREENAPI_ID", "GREENAPI_TOKEN", "GREENAPI_URL",
           "BLOOWATCH_URL", "BLOOWATCH_EMAIL", "BLOOWATCH_PASSWORD")

# Where the morning's answer is left for anyone who was not in the room.
# Each run happens in its own container, which is then thrown away, so a
# result that is only printed is a result only its own session ever sees.
# Committing it makes the check readable from anywhere and gives the one
# question nobody could answer from a transcript -- when did this start
# failing? -- an actual history.
STATUS = os.path.join(HERE, "status", "preflight.json")

# Taken before anything imports send.py, because importing it loads `.env`
# into os.environ and the difference between the two sources is exactly
# what this file exists to report. Order matters here; do not move it.
FROM_ENVIRONMENT = {k: bool(os.environ.get(k)) for k in SECRETS}

import send                                                    # noqa: E402

TIDE_DAYS_WANTED = 3


def sources():
    """Where each secret resolved from: the environment, `.env`, or nowhere."""
    out = {}
    for key in SECRETS:
        if FROM_ENVIRONMENT[key]:
            out[key] = "environment"
        elif os.environ.get(key):
            out[key] = ".env file"
        else:
            out[key] = "MISSING"
    return out


def whatsapp_state():
    """What Green-API says about the number, in its own words."""
    import urllib.request
    ident = os.environ.get("GREENAPI_ID", "")
    token = os.environ.get("GREENAPI_TOKEN", "")
    base = os.environ.get("GREENAPI_URL", "").rstrip("/")
    if not (ident and token and base):
        return "no credentials"
    url = "%s/waInstance%s/getStateInstance/%s" % (base, ident, token)
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as exc:                       # noqa: BLE001
        # The reason belongs in the report verbatim: a 401 (token replaced
        # in the console) and a proxy 403 (domain no longer allowed) need
        # opposite responses, and guessing between them wastes a morning.
        return "unreachable: %s" % _brief(exc)
    return str(body.get("stateInstance") or body)


def bloowatch_state():
    try:
        import daily_report
        daily_report.login()
    except Exception as exc:                       # noqa: BLE001
        return "login failed: %s" % _brief(exc)
    return "ok"


def tide_days():
    try:
        import tides
        return tides.ahead(tides.CATALOG)
    except Exception as exc:                       # noqa: BLE001
        return "unreadable: %s" % _brief(exc)


def deps():
    """Can this container actually run tonight's jobs? "ok" or what is wrong.

    Added 15/9/2026, because this file said the morning was ready and the
    evening was not. The 18:00 forecast fired, cloned, ran, and died on
    `ModuleNotFoundError: No module named 'playwright'`. Looking back
    through the journal afterwards: **no automatic container had ever sent
    the forecast or the rota.** Only the reminders, which are the one job
    that needs no browser.

    This check had reported green through all of it, and honestly -- it
    reads the secrets, asks WhatsApp whether it is authorized, logs in to
    Bloowatch over HTTP and counts the tide table. Not one of those touches
    a browser. **A readiness check that does not exercise what the evening
    needs is not a readiness check**, and the silence it bought was worse
    than no check: the two safety nets watch the gateway, which correctly
    reported that nothing was sent, so all three were telling the truth and
    none could say why.

    The browser is not started here -- launching Chromium at half past four
    to prove it exists would be slower and would fail for reasons that have
    nothing to do with the morning. The import and the binary are what went
    missing, so the import and the binary are what this looks for.
    """
    missing = []
    for mod in ("playwright", "requests"):
        try:
            __import__(mod)
        except Exception:                          # noqa: BLE001
            missing.append(mod)
    if missing:
        return "missing: " + ", ".join(missing)
    try:
        import shot
        shot.chromium()
    except Exception as exc:                       # noqa: BLE001
        return "no chromium: %s" % _brief(exc)
    return "ok"


def _brief(exc):
    """One line, and never the password: exceptions can carry the request."""
    text = str(exc).replace("\n", " ")
    for key in SECRETS:
        value = os.environ.get(key)
        if value and len(value) > 6 and value in text:
            text = text.replace(value, "<%s>" % key)
    return text[:160]


def check(network=True):
    src = sources()
    report = {
        "when": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "secrets": src,
        "whatsapp": whatsapp_state() if network else "not checked",
        "bloowatch": bloowatch_state() if network else "not checked",
        "tide_days_ahead": tide_days(),
        "deps": deps(),
    }

    problems = []
    for key, where in src.items():
        if where == "MISSING":
            problems.append("%s is not set anywhere" % key)
    if network and report["whatsapp"] != "authorized":
        problems.append("WhatsApp is %s (needs: authorized)" % report["whatsapp"])
    if network and report["bloowatch"] != "ok":
        problems.append("Bloowatch %s" % report["bloowatch"])
    if report["deps"] != "ok":
        # A problem and not a warning: without these the forecast and the
        # rota do not go out at all, and they fail half way through rather
        # than before the send. `sh bloowatch/routine_setup.sh` is the fix.
        problems.append("this container cannot run the evening — %s"
                        % report["deps"])

    warnings = []
    days = report["tide_days_ahead"]
    if isinstance(days, int):
        if days < TIDE_DAYS_WANTED:
            # Not fatal on purpose: ROUTINES.md section 2 says a forecast
            # carrying yesterday's tide beats no forecast at all.
            warnings.append("only %d days of tide left; refresh soon" % days)
    else:
        warnings.append("tide table %s" % days)
    if all(src[k] == ".env file" for k in
           ("GREENAPI_ID", "GREENAPI_TOKEN", "GREENAPI_URL")):
        warnings.append("GREENAPI_* still come from .env, not the environment "
                        "— the routines each carry their own copy of the token")

    report["problems"] = problems
    report["warnings"] = warnings
    return report


def record(report, path=STATUS):
    """Leave the answer somewhere that outlives this container.

    Only ever the report, which names where each secret came from and never
    what it is -- test_preflight pins that the value reaches neither the
    output nor any field of this file. The repository is public.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return path


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true",
                    help="machine-readable, for a routine to act on")
    ap.add_argument("--no-network", action="store_true",
                    help="only resolve the secrets; touch nothing remote")
    ap.add_argument("--record", action="store_true",
                    help="also write the report to status/preflight.json, "
                         "for committing: a container's printout dies with it")
    a = ap.parse_args()

    report = check(network=not a.no_network)
    if a.record:
        print("wrote " + record(report))

    if a.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        for key, where in report["secrets"].items():
            print("  %-20s %s" % (key, where))
        print("  %-20s %s" % ("whatsapp", report["whatsapp"]))
        print("  %-20s %s" % ("bloowatch", report["bloowatch"]))
        print("  %-20s %s" % ("tide days ahead", report["tide_days_ahead"]))
        print()
        for w in report["warnings"]:
            print("WARN  " + w)
        for p in report["problems"]:
            print("FAIL  " + p)
        if not report["problems"]:
            print("ready for tomorrow" if not report["warnings"]
                  else "usable, with the warnings above")

    # `report` is already the name of this function's own findings, so the
    # module comes in under another one rather than renaming a variable
    # that appears twenty times above.
    import report as _filing
    _filing.result("preflight", "RESULT problems=%d warnings=%d tide_days=%s"
                   % (len(report["problems"]), len(report["warnings"]),
                      report["tide_days_ahead"]), echo=not a.json)
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
