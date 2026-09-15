#!/usr/bin/env python3
"""The check that evening.py says exactly what the old six commands said.

Collapsing the forecast routine into one command is only safe if the
message it produces is byte for byte the message the documented path
produced. Otherwise the routine stops drifting and the *text* starts --
which is worse, because nobody is watching the wording once the command
looks tidy.

So this builds the same forecast twice: once through evening.message, and
once by running forecast_message.py exactly as ROUTINES.md section 2 spells
it out, and requires the two to be identical. Change either side alone and
this fails.

The refusals are pinned too. No Surfline hours, or a wind direction
Surfline itself labels the other way, must stop the send -- a forecast
invented for two hundred customers is far worse than one that never
arrived.

Nothing here touches the network or sends anything.
"""

import os as _os
_os.environ["SHOKOGI_NO_REPORT"] = "1"   # a test run must never put a message on WhatsApp
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evening                                                  # noqa: E402
import forecast_message                                         # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


SUMMARY = {"waves": "0.4-0.8", "period": "13", "wind": "3-7",
           "wind_dir": "200", "onshore_from": "", "onshore_eases": False,
           "hours": 13}
TODAY = "0.3-0.9"
DATE = "2026-09-15"
# The sky and the energy now reach build() too, so the two paths have to be
# handed the same ones or they are not building the same message.
SKY = [(8, "LIGHT_RAIN"), (9, "DRIZZLE"), (17, "THUNDER_STORMS")]
ENERGY = 140.0


def via_cli(lang, s=SUMMARY, today=TODAY, date=DATE):
    cmd = [sys.executable, os.path.join(HERE, "forecast_message.py"),
           "--lang", lang, "--date", date,
           "--waves", s["waves"], "--period", s["period"],
           "--wind", s["wind"], "--wind-dir", s["wind_dir"],
           "--waves-today", today, "--tide-note",
           "--rain", forecast_message.rain_line(SKY, lang),
           "--energy", str(ENERGY)]
    if s.get("onshore_from"):
        cmd += ["--onshore-from", s["onshore_from"]]
    if s.get("onshore_eases"):
        cmd += ["--onshore-eases"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit("the documented path itself failed: " + out.stderr)
    return out.stdout.rstrip("\n")


def main():
    # --- the two paths must agree, in both languages --------------------
    for lang in ("he", "en"):
        mine, err = evening.message(DATE, dict(SUMMARY, sky=SKY,
                                                    energy=ENERGY),
                                    TODAY, lang)
        check("evening builds a %s forecast without error" % lang, not err,
              str(err))
        theirs = via_cli(lang)
        check("the %s forecast is identical to the documented path" % lang,
              mine == theirs,
              "first difference at %d" % next(
                  (i for i, (a, b) in enumerate(zip(mine, theirs)) if a != b),
                  min(len(mine), len(theirs))))

    # An onshore afternoon changes the wind line; the two paths have to
    # agree about that too, since it is assembled from three arguments.
    windy = dict(SUMMARY, onshore_from="13:00", onshore_eases=True)
    mine, err = evening.message(DATE, dict(windy, sky=SKY, energy=ENERGY),
                                TODAY, "he")
    check("an onshore afternoon builds", not err, str(err))
    check("and still matches the documented path",
          mine == via_cli("he", s=windy))

    # --- both groups read the same sea ----------------------------------
    he, _ = evening.message(DATE, dict(SUMMARY, sky=SKY, energy=ENERGY),
                            TODAY, "he")
    en, _ = evening.message(DATE, dict(SUMMARY, sky=SKY, energy=ENERGY),
                            TODAY, "en")
    for number in (SUMMARY["waves"], SUMMARY["period"]):
        check("both languages carry %s" % number,
              number in he and number in en)
    check("and they are not the same message", he != en)

    # --- refusing beats guessing ----------------------------------------
    import surfline
    keep = (surfline.fetch, surfline.hours, surfline.offshore_disagreement)
    try:
        surfline.fetch = lambda days=2: {"surf": [], "swells": [], "wind": []}
        surfline.hours = lambda *a, **k: []
        s, today, problem = evening.sea(DATE)
        check("no Surfline hours is a refusal", problem and s is None,
              repr(problem))
        check("and it says not to guess", "do not guess" in (problem or ""))

        surfline.hours = lambda *a, **k: [{"hour": "09:00"}]
        surfline.offshore_disagreement = lambda rows: [("09:00", 1, 2)]
        s, today, problem = evening.sea(DATE)
        check("a disputed wind direction is a refusal",
              problem and s is None, repr(problem))
        check("and it names the hour", "09:00" in (problem or ""))
    finally:
        surfline.fetch, surfline.hours, surfline.offshore_disagreement = keep

    # --- the group names cannot be swapped ------------------------------
    check("Hebrew goes to the Hebrew group",
          evening.GROUP["he"] == "surfers_he")
    check("English goes to the English group",
          evening.GROUP["en"] == "surfers_en")

    _forecast_changes()
    _chart_attachment()
    _evening_sends()

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0




# ---------------------------------------------------------------------------
# The Surfline chart, added 15/9/2026. The caption limit is the whole risk:
# the English forecast measured 1015 characters against a 1024 limit, and a
# caption that does not fit is truncated silently.
# ---------------------------------------------------------------------------

def _chart_attachment():
    import evening as E
    import send as S

    calls = []

    def fake_one(lang, text, picture, dry_run, timeout=300):
        calls.append({"lang": lang, "chars": len(text), "file": bool(picture),
                      "text": text})
        return fake_one.ok, ["said so"]

    real = E._one
    E._one = fake_one
    try:
        short = "x" * 100
        long = "x" * (S.CAPTION_MAX + 1)

        # --- no picture: one message, as it has always been -------------
        del calls[:]
        fake_one.ok = True
        E.deliver("he", short, False, "")
        check("with no chart the forecast is one plain message",
              len(calls) == 1 and not calls[0]["file"], repr(calls))

        # --- a caption that fits: one message carrying both -------------
        del calls[:]
        E.deliver("he", short, False, "/tmp/chart.png")
        check("a forecast that fits goes as one message with the chart",
              len(calls) == 1 and calls[0]["file"], repr(calls))

        # --- a caption that does not: never truncated -------------------
        # This is the case worth having a test for. 1015 of 1024 is nine
        # characters of headroom and the rain line alone is seventy.
        del calls[:]
        E.deliver("en", long, False, "/tmp/chart.png")
        check("a forecast too long for a caption is split, not cut",
              len(calls) == 2, repr([c["chars"] for c in calls]))
        check("the chart goes first, under a short caption",
              calls and calls[0]["file"]
              and calls[0]["chars"] <= S.CAPTION_MAX, repr(calls[:1]))
        check("and the whole forecast follows, entire and on its own",
              calls[-1]["text"] == long and not calls[-1]["file"],
              "%d chars, file=%s" % (calls[-1]["chars"], calls[-1]["file"]))

        # --- a chart that will not send never costs the forecast --------
        del calls[:]
        seen = {"n": 0}

        def flaky(lang, text, picture, dry_run, timeout=300):
            seen["n"] += 1
            calls.append({"file": bool(picture), "text": text})
            return (not picture), ["upload refused"]

        E._one = flaky
        ok, _ = E.deliver("he", short, False, "/tmp/chart.png")
        check("a chart that will not upload still lets the forecast go",
              ok and seen["n"] == 2 and not calls[-1]["file"], repr(calls))
    finally:
        E._one = real


# ---------------------------------------------------------------------------
# What the owner asked for on 15/9/2026: the current warning gone, a light
# word about rain, and the recommended hours kept away from a low on a day
# with no energy behind the swell.
# ---------------------------------------------------------------------------

def _forecast_changes():
    import forecast_message as FM

    # --- the sentence about the current is gone -------------------------
    # It was the one line in the message that read as a reason to stay out
    # of the water, and it went to both surfer groups every spring tide.
    for lang in ("he", "en"):
        msg, err = evening.message(DATE, dict(SUMMARY, sky=SKY, energy=ENERGY),
                                   TODAY, lang)
        check("no %s forecast warns about the current" % lang,
              not err and "זרם חזק" not in msg and "⚠️" not in msg
              and "stronger current" not in msg.lower(), (err or "")[:60])
        check("but the %s one still says the tide moves fast" % lang,
              ("ישתנה באופן יותר מהיר" in msg) or ("change faster" in msg),
              msg[-200:])

    # --- a dry day says nothing about the sky ---------------------------
    # A line that appears every evening to announce good weather is a line
    # people stop reading, and then they miss the one that matters.
    check("a clear day gets no weather line",
          FM.rain_line([(8, "CLEAR"), (12, "MOSTLY_CLOUDY")]) == "")
    check("and neither does a missing weather feed",
          FM.rain_line([]) == "" and FM.rain_line(None) == "")

    # --- a wet one says one thing, and it is an invitation --------------
    # He narrowed this himself: rain drops the wind and leaves the sea good
    # to surf, and nothing else. No hours, no storm timings, no advice to
    # go earlier -- a message that lists shower times reads like a reason
    # to stay home.
    light = FM.rain_line([(8, "LIGHT_RAIN"), (9, "DRIZZLE")])
    heavy = FM.rain_line([(17, "THUNDER_STORMS"), (18, "THUNDER_STORMS")])
    far = FM.rain_line([(9, "RAIN"), (17, "RAIN"), (18, "RAIN")])
    for what, line in (("showers", light), ("storms", heavy),
                       ("two separate spells", far)):
        check("%s: the line says what the rain does to the sea" % what,
              "מוריד את הרוח" in line and "טוב לגלישה" in line, line)
        check("%s: and carries no hours" % what,
              not any(ch.isdigit() for ch in line), line)
    check("every kind of wet day gets the same sentence",
          light == heavy == far, "%r / %r / %r" % (light, heavy, far))
    check("and English says the same thing",
          "knocks the wind down" in FM.rain_line([(8, "RAIN")], "en")
          and not any(ch.isdigit() for ch in FM.rain_line([(8, "RAIN")], "en")),
          FM.rain_line([(8, "RAIN")], "en"))

    # --- a weak sea keeps further off the low ---------------------------
    # The owner, in his own words: a low sea with weak energy has no wave at
    # the low, so do not point people at it.
    # These are the hours he wrote out by hand for 15/9 against highs at
    # 06:07 and 18:31 and a low at 12:21. They are the whole specification:
    # ninety minutes off every high, the experienced straight through the
    # low, the beginners split around it.
    t = FM.tides_for(DATE)
    _, _, strong_mid, strong_beg = FM.windows(t, weak=False)
    _, _, weak_mid, weak_beg = FM.windows(t, weak=True)
    check("a weak day gives the experienced one window through the low",
          weak_mid == [("08:00", "17:00")], repr(weak_mid))
    check("and splits the beginners around it",
          weak_beg == [("08:00", "11:00"), ("13:30", "17:00")], repr(weak_beg))
    check("on an ordinary day the two blocks stay the same",
          strong_mid == strong_beg, "%r vs %r" % (strong_mid, strong_beg))
    check("and an ordinary day is unchanged from what he approved",
          strong_mid == [("07:00", "11:00"), ("13:30", "18:00")],
          repr(strong_mid))
    # The threshold is his, not a guess: "עד 250 זה יחסית חלש", 15/9/2026.
    # It stood at 150 before that, which was mine -- placed just above the
    # one day he had called weak (131 kJ) and treating 16/9 and 17/9 at 209
    # and 210 as ordinary. He says they are weak too.
    check("the weak line is the owner's 250, not a guess around one day",
          FM.WEAK_ENERGY == 250, str(FM.WEAK_ENERGY))
    check("and 250 itself counts as weak, because he said 'up to 250'",
          FM.build(DATE, "0.8", "10", "", "x", "", "", "he",
                   energy=250.0)[0] ==
          FM.build(DATE, "0.8", "10", "", "x", "", "", "he",
                   energy=100.0)[0])
    check("while the day above it is an ordinary one",
          FM.build(DATE, "0.8", "10", "", "x", "", "", "he",
                   energy=251.0)[0] !=
          FM.build(DATE, "0.8", "10", "", "x", "", "", "he",
                   energy=250.0)[0])
    # The days he has already ruled on, by the number he gave.
    for day, kj, want in (("15/9", 131.0, True), ("16/9", 209.0, True),
                          ("17/9", 210.0, True), ("18/9", 132.0, True),
                          ("19/9", 112.0, True)):
        check("%s at %g kJ is a weak day" % (day, kj),
              (kj <= FM.WEAK_ENERGY) is want)
    check("and so is the clearance off a high", FM.CLEAR_OF_HIGH_WEAK == 90)

    # --- the near-low advice stays; he kept it in his own correction ----
    for e in (50.0, 200.0):
        msg, _ = evening.message(DATE, dict(SUMMARY, sky=SKY, energy=e),
                                 TODAY, "he")
        check("energy=%g still tells them what the low is like" % e,
              "קרוב לשפל" in msg)


# ---------------------------------------------------------------------------
# The 19:00 and 19:15 sends, added 14/09/2026 when they stopped being five
# commands each. What is pinned is not that they work -- the dry runs show
# that -- but the three rules that cost something real when they were broken.
# ---------------------------------------------------------------------------

def _evening_sends():
    import evening as E

    calls = []

    class Fake:
        """evening._run, with every child process replaced by an answer."""

        def __init__(self, answers, text="*לו״ז יום ב׳*\n07:00 · שיעור"):
            self.answers = answers          # {script: ok}
            self.text = text

        def __enter__(self):
            self.real = E._run
            def run(*cmd, **kw):
                calls.append(cmd[0])
                ok = self.answers.get(cmd[0], True)
                if cmd[0] == "shot.py" and ok:
                    # shot.py's real side effect is the file it leaves behind.
                    for i, c in enumerate(cmd):
                        if c in ("--out", "--crew-out"):
                            open(cmd[i + 1], "w").write("{}")
                if cmd[0] == "board.py" and ok:
                    for i, c in enumerate(cmd):
                        if c == "--out":
                            open(cmd[i + 1], "w").write("png")
                if cmd[0] == "rota.py" and "--plan" in cmd and ok:
                    import json as J
                    for i, c in enumerate(cmd):
                        if c == "--plan":
                            J.dump([{"name": "A", "phone": "+1", "lang": "he",
                                     "text": "x"}], open(cmd[i + 1], "w"))
                return ok, (self.text if cmd[0] == "rota.py" else ""), "said so"
            E._run = run
            return self

        def __exit__(self, *a):
            E._run = self.real
            return False

    class Args:
        def __init__(self, **kw):
            self.date = "2026-09-15"
            self.image = os.path.join(tempfile.gettempdir(), "t-real.png")
            self.dry_run = False
            self.__dict__.update(kw)

    # --- a rota that did not go out must not leave a snapshot behind ----
    # The 20:00 change check reads that snapshot. One saved for a rota
    # nobody received makes it compare tomorrow's board against a message
    # that was never sent, and it then stays silent about every change.
    del calls[:]
    with Fake({"send.py": False}):
        code = E.rota(Args())
    check("a staff rota that failed to send exits 1", code == 1, str(code))
    # `calls` holds script names, so this asks for the script by name. The
    # older spelling looked for "--snapshot" in that same list and could
    # therefore never fail, whatever rota() did.
    check("and no snapshot is written for it",
          "snapshot.py" not in calls, repr(calls))

    # --- and one that did go out must leave exactly one -----------------
    del calls[:]
    with Fake({}):
        code = E.rota(Args())
    check("a staff rota that went out exits 0", code == 0, str(code))
    check("and saves the snapshot through snapshot.py, not a local file",
          calls.count("snapshot.py") == 1, repr(calls))

    # --- an empty day is the owner's to see, not the group's ------------
    del calls[:]
    with Fake({}, text="*לו״ז יום ב׳*\n\nאין עדיין שיעורים."):
        code = E.rota(Args())
    check("a day with no lessons is not sent to the staff group",
          code == 1 and "send.py" not in calls, "%s %r" % (code, calls))

    # --- the board is the attachment; the rota is the message -----------
    # A night the picture will not upload is a worse evening, not a broken
    # one, so the text goes on its own rather than nothing going at all.
    del calls[:]
    seen = {"n": 0}
    import evening as EV
    real = EV._run
    def flaky(*cmd, **kw):
        if cmd[0] == "send.py":
            seen["n"] += 1
            return (seen["n"] > 1), "", "upload refused"
        if cmd[0] == "shot.py":
            for i, c in enumerate(cmd):
                if c in ("--out", "--crew-out"):
                    open(cmd[i + 1], "w").write("{}")
        return True, "*לו״ז יום ב׳*\n07:00 · שיעור", ""
    EV._run = flaky
    try:
        code = EV.rota(Args())
    finally:
        EV._run = real
    check("a board that will not upload still lets the rota go",
          code == 0 and seen["n"] == 2, "exit %s after %d sends"
          % (code, seen["n"]))

    # --- nor a photograph of the board inside the repository ------------
    # shot.py's default --out is board.png beside itself. The picture is a
    # photograph of the real planner: client names, instructor names, the
    # whole day. The repository is public, and on 14/09/2026 it reached the
    # working tree because this call omitted --out.
    del calls[:]
    outs = []
    import evening as EV2
    real2 = EV2._run
    def watch(*cmd, **kw):
        if cmd[0] == "shot.py":
            outs.append("--out" in cmd)
            for i, c in enumerate(cmd):
                if c in ("--out", "--crew-out"):
                    open(cmd[i + 1], "w").write("{}")
        if cmd[0] == "rota.py" and "--plan" in cmd:
            import json as J
            for i, c in enumerate(cmd):
                if c == "--plan":
                    J.dump([], open(cmd[i + 1], "w"))
        return True, "", ""
    EV2._run = watch
    try:
        EV2.personal(Args())
    finally:
        EV2._run = real2
    check("the personal run never lets shot.py default its output path",
          outs == [True], repr(outs))
    check("and no board.png is left in the repository",
          not os.path.exists(os.path.join(
              os.path.dirname(os.path.abspath(__file__)), "board.png")))

    # --- the personal rotas never leave phone numbers on disk -----------
    plan = os.path.join(tempfile.gettempdir(), "plan.json")
    crew = os.path.join(tempfile.gettempdir(), "crew.json")
    with Fake({"send.py": False}):
        code = E.personal(Args())
    check("a failed personal send exits 1", code == 1, str(code))
    check("and leaves no plan or crew file behind",
          not os.path.exists(plan) and not os.path.exists(crew))

    # --- 20:00: no reference point is a stop, never a re-send -----------
    # This is the check that quietly stopped working when the routines moved
    # to fresh containers: 19:00 wrote the snapshot to a file and 20:00 came
    # up on a different machine, found nothing, and reported a clean run.
    # A missing baseline must be loud and must send nothing.
    del calls[:]
    with Fake({"snapshot.py": False}):
        code = E.changes(Args())
    check("20:00 with no snapshot exits 1", code == 1, str(code))
    check("and sends nothing at all", "send.py" not in calls, repr(calls))

    # --- a quiet hour is a quiet hour -----------------------------------
    del calls[:]
    with Fake({}, text="nothing changed since the rota was sent"):
        code = E.changes(Args())
    check("20:00 with an unchanged board exits 0 and sends nothing",
          code == 0 and "send.py" not in calls, "%s %r" % (code, calls))

    # --- a change reaches the group and the people it touches -----------
    del calls[:]
    with Fake({}, text="*עדכון ללו״ז*\n09:00 · נוסף"):
        code = E.changes(Args())
    check("20:00 with a changed board exits 0", code == 0, str(code))
    check("and writes to the group and to the affected instructors",
          calls.count("send.py") == 2, repr(calls))
    check("and leaves no snapshot or plan on disk",
          not os.path.exists(os.path.join(tempfile.gettempdir(),
                                          "rota-snapshot.json"))
          and not os.path.exists(os.path.join(tempfile.gettempdir(),
                                              "changes.json")))

    # --- a change nobody was told about is a failure, not a quiet run ---
    del calls[:]
    with Fake({"send.py": False}, text="*עדכון ללו״ז*\n09:00 · נוסף"):
        code = E.changes(Args())
    check("a change the group was not told about exits 1", code == 1,
          str(code))

    for p in (Args().image,):
        if os.path.exists(p):
            os.remove(p)


if __name__ == "__main__":
    sys.exit(main())
