#!/usr/bin/env python3
"""One command per evening send, so there is nothing left to decide.

    python3 evening.py forecast                 # both surfer groups
    python3 evening.py forecast --only he       # just the Hebrew one
    python3 evening.py forecast --dry-run       # build it, send nothing

Until now the 18:00 forecast was six commands with a hand-off in the
middle: `surfline.py --fetch` printed an argument line, and whoever was
running the routine pasted it into `forecast_message.py`. Every step like
that is a place where a reading can differ from the last one, and the
routines are read by a fresh model every single evening.

Two of the three failures this month came out of exactly that latitude.
On 13/09 the run hit a snag in git, decided to investigate it with a
command nobody had written down, and hung on the approval prompt that
followed. The evening before, a run decided that sending the rota an hour
early was near enough. Neither was a bug in any script; both were
judgment, exercised in a place that did not need any.

So the procedure moves into code and the routine's job becomes: run this,
report what it printed. There is no argument line to copy, no order to get
right, and no decision to make. What remains is the part that genuinely
needs judgment -- what to do when it fails -- and that is written in
ROUTINES.md.

**It refuses rather than guesses.** No Surfline hours, or a wind direction
Surfline itself labels differently, and it stops with a non-zero status
having sent nothing: a forecast invented for two hundred customers is far
worse than a forecast that did not arrive.

**Each group is sent to once, and independently.** A failure reaching the
Hebrew group is not a reason to withhold the English one, and the summary
line says exactly which of them went.
"""

import argparse
import datetime as dt
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import forecast_message as F                                    # noqa: E402
import surfline                                                 # noqa: E402
import tides                                                    # noqa: E402

PANAMA_OFFSET = dt.timedelta(hours=-5)          # Panama, all year round
GROUP = {"he": "surfers_he", "en": "surfers_en"}
TIDE_DAYS_WANTED = 3


def tomorrow():
    now = dt.datetime.utcnow() + PANAMA_OFFSET
    return (now.date() + dt.timedelta(days=1)).isoformat()


def sea(date):
    """Tomorrow's sea, or a reason not to send anything at all.

    Returns (summary, today_waves, problem). `problem` being set is always
    a refusal: the caller must send nothing, not fall back to a guess.
    """
    blob = surfline.fetch(days=2)
    surf, swells, wnd = blob["surf"], blob["swells"], blob["wind"]
    rows = surfline.hours(surf, swells, wnd, date)
    if not rows:
        return None, None, ("no Surfline hours for %s -- do not send, and "
                            "do not guess" % date)

    # The offshore call is the one number that can invert the whole message
    # without looking wrong, so a disagreement with Surfline's own label
    # stops the send rather than being published quietly.
    bad = surfline.offshore_disagreement(rows)
    if bad:
        return None, None, ("wind direction disagrees with Surfline's own "
                            "label at %s -- check BEACH_FACES"
                            % ", ".join(h for h, _, _ in bad))

    prev = (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()
    today = surfline.waves(surfline.hours(surf, swells, wnd, prev))
    return surfline.summary(rows), today, None


def message(date, s, today, lang, tide_note=True):
    """The forecast in one language.

    Deliberately mirrors forecast_message.main step for step rather than
    reaching into build() directly: that ordering -- the comparison line
    before the tide note, the wind line only when both speed and direction
    are known -- is the tested path, and test_evening pins this against the
    command-line one so the two cannot drift apart.
    """
    spot = ("The left side of the beach in front of Selina is lower and "
            "easier to practise on" if lang == "en" else
            "צד שמאל של החוף מול סלינה נמוך ונוח יותר לתרגול")

    compare = F.compare_line(today or "", s["waves"], lang, date=date,
                             period=s["period"], wind_kt=s["wind"] or None,
                             wind_deg=s["wind_dir"] or None,
                             faces=F.BEACH_FACES)

    note = ""
    if tide_note:
        t = F.tides_for(date)
        if t:
            note, _ = F.tide_range_note(t, lang)

    wind = ""
    if s["wind"] and s["wind_dir"]:
        wind = F.wind_line(s["wind"], s["wind_dir"], F.BEACH_FACES, lang,
                           s.get("onshore_from") or None,
                           s.get("onshore_eases"))

    return F.build(date, s["waves"], s["period"], compare, spot, note,
                   wind, lang)


def deliver(lang, text, dry_run):
    """Hand one language to send.py, the way the routine always has.

    Through the command line rather than by importing it: this is the one
    step that actually reaches customers, and it stays on the path that has
    been sending every night rather than a second one written tonight.
    """
    fd, path = tempfile.mkstemp(suffix="-%s.txt" % lang, text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    try:
        cmd = [sys.executable, os.path.join(HERE, "send.py"),
               "--to", GROUP[lang], "--text", path]
        if dry_run:
            cmd.append("--dry-run")
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        ok = out.returncode == 0
        return ok, (out.stdout or out.stderr or "").strip().splitlines()[-1:]
    finally:
        os.remove(path)


def forecast(args):
    date = args.date or tomorrow()
    langs = [args.only] if args.only else ["he", "en"]

    days = tides.ahead(tides.CATALOG)
    if days < TIDE_DAYS_WANTED:
        # Not a refusal: a forecast carrying an older tide beats no forecast.
        print("warning: only %d days of tide table left" % days,
              file=sys.stderr)

    s, today, problem = sea(date)
    if problem:
        print("error: " + problem, file=sys.stderr)
        return 1

    built = {}
    for lang in langs:
        text, err = message(date, s, today, lang, tide_note=not args.no_tide_note)
        if err:
            print("error: %s (%s)" % (err, lang), file=sys.stderr)
            return 1
        built[lang] = text

    if args.print:
        for lang in langs:
            print(built[lang])
            print()
        return 0

    sent, failed = [], []
    for lang in langs:
        ok, tail = deliver(lang, built[lang], args.dry_run)
        (sent if ok else failed).append(lang)
        if not ok:
            print("error: %s did not send: %s"
                  % (GROUP[lang], " ".join(tail)), file=sys.stderr)

    print("%s %s  waves %s m  period %s s  wind %s kt"
          % ("would send" if args.dry_run else "sent",
             ", ".join(GROUP[l] for l in sent) or "nothing",
             s["waves"], s["period"], s["wind"]))
    return 1 if failed else 0


def _run(*cmd, **kw):
    """One child process, with its tail kept for the report."""
    out = subprocess.run([sys.executable] + [os.path.join(HERE, cmd[0])] +
                         list(cmd[1:]), capture_output=True, text=True,
                         timeout=kw.get("timeout", 300))
    tail = (out.stderr or out.stdout or "").strip().splitlines()[-1:]
    return out.returncode == 0, (out.stdout or ""), " ".join(tail)


def board_png(date, crew_out, out):
    """A picture of tomorrow's board, photographed if possible and drawn if not.

    The owner was shown both and asked for the photograph, twice, in those
    words -- so the drawing is a fallback and never a preference. But a rota
    with a drawn board beats a rota with no board, and a browser that will
    not start on one evening must not take the whole 19:00 send down with it.
    Which one was used is returned, because that belongs in the report.
    """
    ok, _, tail = _run("shot.py", "--date", date, "--out", out,
                       "--crew-out", crew_out)
    if ok and os.path.exists(out) and os.path.getsize(out) > 0:
        return "photograph", tail
    print("warning: the planner could not be photographed (%s); drawing the "
          "board instead" % tail, file=sys.stderr)
    args = ["board.py", "--date", date, "--out", out]
    if os.path.exists(crew_out):
        args += ["--crew", crew_out]
    ok, _, tail = _run(*args)
    if ok and os.path.exists(out) and os.path.getsize(out) > 0:
        return "drawing", tail
    return "", tail


def rota(args):
    """19:00 — tomorrow's rota to the staff group, as one message with the board.

    The send and the snapshot are one act here for a reason. The 20:00 change
    check compares the board against the snapshot, so a snapshot saved for a
    rota that never went out makes it compare against something nobody saw,
    and a rota sent without a snapshot makes it blind. On 3/9/2026 four
    bookings landed between 19:00 and 20:00 and two of them were for somebody
    who had been wished a good day off at 19:15.

    So: the snapshot is written only after the group has actually been
    written to, and never otherwise.
    """
    date = args.date or tomorrow()
    png = args.image or os.path.join(tempfile.gettempdir(), "real.png")
    crew = os.path.join(tempfile.gettempdir(), "crew.json")

    kind, tail = board_png(date, crew, png)
    if not kind:
        print("error: no board could be produced: %s" % tail, file=sys.stderr)

    ok, text, tail = _run("rota.py", "--group", "--crew", crew)
    if not ok:
        print("error: the rota could not be built: %s" % tail, file=sys.stderr)
        print("RESULT rota=not-built sent=nothing snapshot=no")
        return 1

    # An empty day must not reach the group: twelve people reading "no
    # lessons yet" at seven in the evening read it as a fault, and somebody
    # calls. It is the owner's to see, not theirs.
    if "אין עדיין שיעורים" in text:
        print("error: tomorrow (%s) has no lessons on the board — nothing was "
              "sent to the staff group. Tell the owner directly." % date,
              file=sys.stderr)
        print("RESULT rota=empty sent=nothing snapshot=no")
        return 1

    fd, cap = tempfile.mkstemp(suffix="-cap.txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        cmd = ["send.py", "--to", "staff", "--text", cap]
        if kind:
            cmd += ["--file", png]
        if args.dry_run:
            cmd.append("--dry-run")
        ok, _, tail = _run(*cmd, timeout=600)

        # The board is the attachment; the rota is the message. Losing the
        # picture is a worse evening, losing the rota is a broken one.
        if not ok and kind:
            print("warning: sending with the board failed (%s); sending the "
                  "rota alone" % tail, file=sys.stderr)
            cmd = ["send.py", "--to", "staff", "--text", cap]
            if args.dry_run:
                cmd.append("--dry-run")
            ok, _, tail = _run(*cmd, timeout=300)
            kind = "none"
    finally:
        os.remove(cap)

    if not ok:
        print("error: the staff group was not written to: %s" % tail,
              file=sys.stderr)
        print("RESULT rota=built sent=nothing snapshot=no")
        return 1

    snap = "skipped (dry run)"
    if not args.dry_run:
        good, _, tail = _run("rota.py", "--snapshot", args.snapshot)
        snap = "saved" if good else "FAILED: " + tail
        if not good:
            print("error: the rota went out but the snapshot did not save — "
                  "the 20:00 change check is blind tonight: %s" % tail,
                  file=sys.stderr)

    print("RESULT rota=sent board=%s snapshot=%s" % (kind or "none", snap))
    return 0 if snap in ("saved", "skipped (dry run)") else 1


def personal(args):
    """19:15 — each instructor's own rota, and nobody else's.

    Every rule about who is written to lives in rota.plan and whatsapp.json,
    not here: the drift in those rules is one instructor's rota arriving on
    another instructor's phone, and that cannot be taken back.
    """
    date = args.date or tomorrow()
    crew = os.path.join(tempfile.gettempdir(), "crew.json")
    plan = os.path.join(tempfile.gettempdir(), "plan.json")

    # --out matters even though the picture is not wanted here: without it
    # shot.py writes board.png beside itself, inside the repository, and that
    # photograph carries client names, instructor names and the day's whole
    # board. It landed in the working tree the first evening this ran.
    ok, _, tail = _run("shot.py", "--date", date, "--crew-out", crew,
                       "--out", os.path.join(tempfile.gettempdir(),
                                             "personal-board.png"))
    if not ok:
        # Holiday greetings need the planner's own "away" marks. Losing them
        # costs a few greetings; stopping here costs everybody their rota.
        print("warning: who is away could not be read (%s) — sending without "
              "the day-off greetings" % tail, file=sys.stderr)

    args_ = ["rota.py", "--date", date, "--plan", plan]
    if os.path.exists(crew):
        args_ += ["--crew", crew]
    ok, out, tail = _run(*args_)
    if not ok:
        print("error: the rotas could not be built: %s" % tail, file=sys.stderr)
        print("RESULT planned=? sent=0")
        return 1

    try:
        with open(plan, encoding="utf-8") as f:
            import json
            planned = len(json.load(f))
        if not planned:
            print("RESULT planned=0 sent=0")
            return 0

        cmd = ["send.py", "--batch", plan, "--once-today"]
        if args.dry_run:
            cmd.append("--dry-run")
        ok, _, tail = _run(*cmd, timeout=900)
    finally:
        # Real phone numbers. Never left behind, never committed.
        for p in (plan, crew):
            if os.path.exists(p):
                os.remove(p)

    print("RESULT planned=%d sent=%s" % (planned, "ok" if ok else "FAILED"))
    if not ok:
        print("error: not every instructor was written to: %s" % tail,
              file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="what", required=True)

    f = sub.add_parser("forecast", help="tomorrow's sea, to both groups")
    f.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    f.add_argument("--only", choices=("he", "en"),
                   help="one group, for filling in a gap the other already has")
    f.add_argument("--dry-run", action="store_true",
                   help="build it and show where it would go")
    f.add_argument("--print", action="store_true",
                   help="print the messages and send nothing at all")
    f.add_argument("--no-tide-note", action="store_true")
    f.set_defaults(run=forecast)

    r = sub.add_parser("rota", help="tomorrow's rota to the staff group, "
                                    "with the board, and the snapshot after")
    r.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    r.add_argument("--image", default="",
                   help="where to leave the board picture (default /tmp)")
    r.add_argument("--snapshot",
                   default=os.path.expanduser("~/.shokogi/rota.json"),
                   help="the reference point the 20:00 change check reads")
    r.add_argument("--dry-run", action="store_true",
                   help="build it and show where it would go")
    r.set_defaults(run=rota)

    p = sub.add_parser("personal", help="each instructor's own rota")
    p.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(run=personal)

    a = ap.parse_args()
    return a.run(a)


if __name__ == "__main__":
    sys.exit(main())
