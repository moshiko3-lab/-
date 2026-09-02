#!/usr/bin/env python3
"""A photograph of the board itself, taken from Bloowatch.

    python3 shot.py                        # tomorrow, to board.png
    python3 shot.py --date 2026-09-02 --out /tmp/wed.png
    python3 shot.py --full page.png        # keep the whole page too

We draw our own version of this board in board.py, and it is a good likeness.
This is the thing itself: the same planner the office reads all day, on the
ACTIVITIES tab in the STAFF - 7D HORIZONTAL view, cropped to the one day, with
the crew's names down the side.

Everything here is written to survive a bad night, because it runs unattended
at seven in the evening and a rota that does not go out is worse than a rota
that goes out plain. Every step that touches the network is retried; every
step that looks for something on the page waits for it rather than sleeping a
guessed number of seconds; and the picture is checked before it is handed
back, because a blank screenshot is worse than none -- it reads as a day with
nothing booked on it.

Two things about the browser are not obvious and both cost an hour to find:

  * The TLS handshake. Through this container's egress proxy a TLS 1.3
    handshake is dropped mid-exchange and every page load comes back
    ERR_CONNECTION_RESET, while curl to the same host succeeds -- which sends
    you looking for a login problem that is not there. Capping at TLS 1.2
    fixes it today; because that is a fact about the proxy and not about
    Bloowatch, HANDSHAKES lists the alternatives to try in order, so the day
    the proxy changes this gets slower rather than going dark.
  * The browser is the one already on the box. Playwright's own download is
    not available here, so the binary is found rather than fetched.

Nothing here writes to Bloowatch. It signs in, changes the view, and reads.
"""
import argparse
import datetime as dt
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PANAMA = dt.timezone(dt.timedelta(hours=-5))
BASE = "https://shokogi.bloowatch.com"
VIEW = "STAFF - 7D HORIZONTAL"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DOW = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

# In the order worth trying. The first works today; the rest are here so that
# a change at the proxy costs a slower run instead of a silent failure.
HANDSHAKES = [
    ["--ssl-version-max=tls1.2"],
    [],
    ["--disable-features=EncryptedClientHello,PostQuantumKyber,TLS13EarlyData"],
    ["--ssl-version-max=tls1.2", "--disable-quic", "--disable-http2"],
]

QUIET = ["--no-sandbox", "--disable-dev-shm-usage", "--no-first-run",
         "--disable-background-networking", "--disable-component-update",
         "--disable-sync", "--disable-extensions", "--mute-audio"]


def chromium():
    """Whichever Chromium this machine happens to carry.

    None means Playwright's own, which is right wherever it installed one
    itself; the explicit paths are for a machine that carries a browser
    Playwright did not put there.
    """
    # newer builds keep it in chrome-linux64, older ones in chrome-linux
    home = os.path.expanduser("~/.cache/ms-playwright")
    if glob.glob(home + "/chromium-*/chrome-linux*/chrome"):
        return None
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/usr/bin/chromium", "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/opt/pw-browsers/chromium_headless_shell-*/chrome-linux/"
                "headless_shell"):
        found = sorted(glob.glob(pat))
        if found:
            return found[-1]
    raise SystemExit("no chromium on this machine")


def label(date):
    """How the board writes a day at the head of its own block: WED 2 SEP."""
    d = dt.date.fromisoformat(date)
    return "%s %d %s" % (DOW[d.weekday()], d.day, MONTHS[d.month - 1])


def _launch(pw, args):
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    how = {"args": QUIET + args}
    where = chromium()
    if where:
        how["executable_path"] = where
    if proxy:
        how["proxy"] = {"server": proxy}
    return pw.chromium.launch(**how)


def _reach(p, url, tries=3, timeout=60000):
    """Load a page, giving the network more than one chance at it."""
    last = None
    for i in range(tries):
        try:
            p.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return
        except Exception as e:                                  # noqa: BLE001
            last = e
            p.wait_for_timeout(2000 * (i + 1))
    raise last


def _sign_in(p, email, password):
    """Sign in, unless this browser is already signed in."""
    _reach(p, BASE + "/signin", timeout=90000)
    try:
        p.wait_for_selector("input[type=password]", timeout=20000)
    except Exception:                                          # noqa: BLE001
        if "/signin" not in p.url:
            return                                   # already through
        raise
    p.fill("input[type=text]", email)
    p.fill("input[type=password]", password)
    p.click("button")
    # signed in is when the app stops showing the sign-in form
    for _ in range(60):
        p.wait_for_timeout(1000)
        if "/signin" not in p.url:
            return
    raise RuntimeError("still on the sign-in page after a minute")


def _wait_for(p, js, arg=None, seconds=60, every=1000):
    """Poll the page until it says yes, instead of sleeping and hoping."""
    for _ in range(seconds):
        got = p.evaluate(js, arg) if arg is not None else p.evaluate(js)
        if got:
            return got
        p.wait_for_timeout(every)
    return None


def _choose_view(p):
    """Put the board on the staff view, however the menu is labelled today."""
    if _wait_for(p, "() => document.body.innerText.includes('%s')" % VIEW,
                 seconds=3):
        return True                                  # already on it
    p.wait_for_selector("a.dropdown-toggle", timeout=45000)
    p.locator("a.dropdown-toggle", has_text="ACTIVITIES").first.click()
    # Ember listens for a real mouse event, not element.click(), so the item
    # is found by its own text and then actually clicked on. The exact label
    # is tried first and "staff ... horizontal" second, so a rename or a
    # change of case costs nothing.
    at = _wait_for(p, """(want) => {
      const items = document.querySelectorAll(
        '.dropdown-menu a, .dropdown-menu li, .dropdown-menu span');
      const pick = (test) => {
        for (const e of items) {
          const t = (e.innerText || '').trim();
          if (t && test(t)) {
            const r = e.getBoundingClientRect();
            if (r.width > 0) return {x: r.x + r.width / 2, y: r.y + r.height / 2};
          }
        }
        return null;
      };
      return pick(t => t === want)
          || pick(t => t.toUpperCase() === want.toUpperCase())
          || pick(t => /STAFF/i.test(t) && /HORIZONTAL/i.test(t));
    }""", VIEW, seconds=20)
    if not at:
        return False
    p.mouse.click(at["x"], at["y"])
    return True


def _find_day(p, day, seconds=90):
    """Wait for the board to draw, then hand back the day's own box."""
    return _wait_for(p, """(day) => {
      // the board renders one .cp-Panel per day, each headed "WED 2 SEP"
      for (const e of document.querySelectorAll('.cp-Panel')) {
        if ((e.innerText || '').trim().startsWith(day)) {
          const r = e.getBoundingClientRect();
          if (r.height < 100) return null;           // still drawing
          return {x: Math.max(0, r.x + window.scrollX),
                  y: Math.max(0, r.y + window.scrollY - 2),
                  width: Math.min(r.width,
                                  document.documentElement.scrollWidth - r.x),
                  height: r.height + 1};
        }
      }
      return null;
    }""", day, seconds=seconds)


def _crew(p, box):
    """The day's rows, in the order the board lists them.

    Reading them as text rather than as pixels is what lets the picture be
    drawn where it is sent: the labels are a few hundred bytes, and a
    photograph is a hundred kilobytes that has to be copied by hand.

    Every row is one line down the left-hand column -- a person, or one of
    the grey group headings -- and a row is off if its own strip says so.
    """
    return p.evaluate("""(box) => {
      const skip = /^(\\d{1,2}:\\d{2}|Time Off|\\d+\\s*\\/\\s*\\d+)$/i;
      const wide = 160;                     // the label column, in CSS pixels
      const seen = new Map(), off = new Set();
      for (const e of document.querySelectorAll('.cp-Panel *')) {
        const r = e.getBoundingClientRect();
        const y = r.y + window.scrollY, x = r.x + window.scrollX;
        if (y < box.y || y > box.y + box.height) continue;
        const t = (e.innerText || '').trim().split('\\n')[0].trim();
        if (/^\\s*Time Off\\s*$/i.test(t)) { off.add(Math.round(y / 8)); }
        // labels hang off the very left of the panel; a booking block starts
        // where its hour is, so this alone tells the two apart -- and it
        // keeps the long group headings, which overflow the column
        if (x - box.x > 24 || r.width > wide + 90) continue;
        if (r.height < 12 || r.height > 60) continue;
        if (!t || t.length > 40 || skip.test(t)) continue;
        // rows sit on a fixed pitch, but their labels are nested a pixel or
        // two apart, so bucket them and keep the longest name in each bucket
        const key = Math.round(y / 8);
        if (!seen.has(key) || seen.get(key).length < t.length) seen.set(key, t);
      }
      const rows = [...seen.entries()].sort((a, b) => a[0] - b[0]);
      const out = [];
      for (const [key, name] of rows) {
        const last = out[out.length - 1];
        if (last && key - last.key <= 1) {          // two reads of one row
          if (name.length > last.name.length) last.name = name;
          continue;
        }
        out.push({key: key, name: name,
                  off: [...off].some(o => Math.abs(o - key) <= 2)});
      }
      return out.map(r => ({name: r.name, off: r.off}));
    }""", box)


def looks_drawn(path, least=6):
    """A blank board is worse than no board: it reads as a day with nothing on.

    So the picture has to carry more than a handful of colours before it is
    handed back -- an empty grid is white, one grey and one hairline.
    """
    try:
        from PIL import Image
    except ImportError:
        return True
    im = Image.open(path).convert("RGB")
    return len(im.quantize(colors=64).getcolors(1 << 16) or []) >= least


def _attempt(pw, args, date, out, email, password, full, width, scale,
             cookies=None, keep=None, crew_out=None):
    day = label(date)
    b = _launch(pw, args)
    try:
        ctx = b.new_context(viewport={"width": width, "height": 1300},
                            device_scale_factor=scale,
                            storage_state=cookies or None)
        p = ctx.new_page()
        p.set_default_timeout(45000)
        if cookies:
            # the signed-in session came from somewhere else; no password here
            _reach(p, BASE + "/agenda/activities", timeout=90000)
        else:
            _sign_in(p, email, password)
        if keep:
            _reach(p, BASE + "/agenda/activities")
            _wait_for(p, "() => !!document.querySelector('a.dropdown-toggle')",
                      seconds=45)
            ctx.storage_state(path=keep)
            b.close()
            return keep
        _reach(p, BASE + "/agenda/activities")
        if not _wait_for(p, "() => !!document.querySelector('a.dropdown-toggle')",
                         seconds=45):
            raise RuntimeError("the agenda never finished loading")
        if not _choose_view(p):
            raise RuntimeError("could not find the %r view" % VIEW)
        if not _wait_for(
                p, "() => /NAFTUL|VLADI|YONATAN/i.test(document.body.innerText)",
                seconds=45):
            raise RuntimeError("the board did not switch to %r" % VIEW)
        box = _find_day(p, day)
        if not box:
            raise RuntimeError("no block headed %r on the board" % day)
        rows = _crew(p, box)
        if full:
            p.screenshot(path=full, full_page=True)
        if out:
            p.screenshot(path=out, clip=box)
    finally:
        b.close()
    if crew_out:
        # one visit to the board gives both the picture and the labels; a
        # second visit for the labels alone is a second browser start
        with open(crew_out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    if not out:
        return rows
    if not looks_drawn(out):
        raise RuntimeError("the board came out blank")
    return out


def shoot(date, out, email, password, full=None, width=2200, scale=2,
          rounds=2, log=print, cookies=None, keep=None, crew_out=None):
    """Take the shot, trying every handshake we know before giving up."""
    from playwright.sync_api import sync_playwright

    trouble = []
    with sync_playwright() as pw:
        for r in range(rounds):
            for args in HANDSHAKES:
                how = " ".join(args) or "default TLS"
                try:
                    got = _attempt(pw, args, date, out, email, password, full,
                                   width, scale, cookies, keep, crew_out)
                    if r or args != HANDSHAKES[0]:
                        log("took it with %s" % how)
                    return got
                except Exception as e:                         # noqa: BLE001
                    why = str(e).split("\n")[0][:120]
                    trouble.append("%s: %s" % (how, why))
                    log("  %s did not work — %s" % (how, why))
            if r + 1 < rounds:
                log("  waiting a moment and going round again")
                time.sleep(20)
    raise SystemExit("could not photograph the board:\n  " + "\n  ".join(trouble))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="YYYY-MM-DD, default tomorrow in Panama")
    ap.add_argument("--out", default=os.path.join(HERE, "board.png"))
    ap.add_argument("--full", default="", help="also keep the whole page")
    ap.add_argument("--width", type=int, default=2200,
                    help="the wider the viewport, the more of the day the "
                         "board fits across")
    ap.add_argument("--rounds", type=int, default=2,
                    help="how many times to work through the handshakes")
    ap.add_argument("--keep-session", default="",
                    help="sign in and write the session to this file, then "
                         "stop. The file is a signed-in browser, not a "
                         "password: it is what lets the picture be taken on "
                         "the machine that sends it, without that machine "
                         "ever seeing the password. Treat it as a secret and "
                         "never commit it.")
    ap.add_argument("--session", default="",
                    help="use a session written by --keep-session instead of "
                         "signing in. BLOOWATCH_EMAIL/PASSWORD are then not "
                         "needed at all.")
    ap.add_argument("--crew-out", default="",
                    help="write the day's rows to this file as well as taking "
                         "the picture, so one visit to the board serves both. "
                         "rota.py --crew reads it to name whoever is off.")
    ap.add_argument("--crew", action="store_true",
                    help="print the day's rows as JSON instead of taking a "
                         "picture. A few hundred bytes of labels can be "
                         "carried to the machine that sends the message; a "
                         "photograph cannot.")
    a = ap.parse_args()
    date = a.date or (dt.datetime.now(PANAMA).date()
                      + dt.timedelta(days=1)).isoformat()
    email = os.environ.get("BLOOWATCH_EMAIL")
    password = os.environ.get("BLOOWATCH_PASSWORD")
    if not a.session and (not email or not password):
        print("error: BLOOWATCH_EMAIL and BLOOWATCH_PASSWORD are not set",
              file=sys.stderr)
        return 1
    got = shoot(date, "" if (a.crew or a.keep_session) else a.out,
                email, password, a.full or None, a.width, rounds=a.rounds,
                log=lambda m: print(m, file=sys.stderr),
                cookies=a.session or None, keep=a.keep_session or None,
                crew_out=a.crew_out or None)
    if a.crew:
        json.dump(got, sys.stdout, ensure_ascii=False)
        print()
    else:
        print(got)
    return 0


if __name__ == "__main__":
    sys.exit(main())
