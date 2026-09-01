"""What the tests share: build once, then open a page on a phone screen.

Each test drives the built HTML, not the source. A test that imports the
source and checks a function would have passed on every one of the bugs
worth catching here -- those all live in the wiring between the script and
the page.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
_built = {}


def site():
    """Build the three pages once per test process, into a temp directory."""
    if "dir" not in _built:
        d = tempfile.mkdtemp(prefix="brows-site-")
        r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"),
                            "--out", d, "--quiet"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("build failed:\n" + r.stdout + r.stderr)
        _built["dir"] = d
    return _built["dir"]


def browser(pw):
    return pw.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--no-sandbox", "--disable-background-networking",
                                    "--disable-sync", "--no-first-run"])


def phone(b, seed=None, lang=None):
    """A page on a phone-sized screen, optionally with a book already in it."""
    ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)[:200]))
    script = ""
    if seed is not None:
        script += "localStorage.setItem('brows.db', %s);" % json.dumps(json.dumps(seed))
    if lang is not None:
        script += "localStorage.setItem('brows.lang', %s);" % json.dumps(lang)
    if script:
        pg.add_init_script(script)
    return pg


def open_page(pg, name, query=""):
    pg.goto("file://" + os.path.join(site(), name) + query)
    pg.wait_for_timeout(400)
    return pg


def db_of(pg):
    """The book as the page left it."""
    raw = pg.evaluate("localStorage.getItem('brows.db')")
    return json.loads(raw) if raw else None


def ok(cond, what):
    if not cond:
        raise AssertionError(what)
    print("  ok   " + what)


def done(name, pg=None):
    if pg is not None and pg.errors:
        raise AssertionError(name + " threw: " + "; ".join(pg.errors[:4]))
    print(name + ": passed")
