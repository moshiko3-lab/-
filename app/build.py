#!/usr/bin/env python3
"""Render the Shokogi manager app to one self-contained HTML file.

    python3 build.py --out index.html

No data is baked in -- the app starts empty and keeps everything the user
enters in their own browser. Only the badge is inlined.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def render(template=None):
    tpl = template or os.path.join(HERE, "app_template.html")
    with open(tpl, encoding="utf-8") as f:
        out = f.read()
    cat = os.path.join(HERE, "catalog.json")
    if os.path.exists(cat):
        with open(cat, encoding="utf-8") as f:
            blob = json.dumps(json.load(f), ensure_ascii=False, separators=(",", ":"))
        out = out.replace("/*__SEED__*/", blob.replace("</script>", "<\\/script>"))
    else:
        out = out.replace("/*__SEED__*/", "null")

    logo = os.path.join(HERE, "logo.png")
    if os.path.exists(logo):
        with open(logo, "rb") as f:
            out = out.replace("/*__LOGO__*/", base64.b64encode(f.read()).decode())
    for token in ("/*__LOGO__*/", "/*__SEED__*/"):
        if token in out:
            raise RuntimeError(f"template placeholder {token} was not replaced")
    return out


def check_js(html):
    """Parse the page's inline script, so a typo fails the build instead of
    shipping a blank app. Skipped silently where node is unavailable."""
    m = re.search(r"<script>(.*)</script>", html, re.S)
    if not m:
        raise RuntimeError("no inline script found in the page")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(m.group(1))
        path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    except FileNotFoundError:
        return "node not available, syntax not checked"
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError("the page's script does not parse:\n" + (r.stderr or "")[:900])
    return "script parses"


def check_runtime(path):
    """Open the built page in Chromium and fail on any uncaught error.

    node --check only parses; it cannot see a name that does not exist until
    the line runs. That gap shipped a broken board once already."""
    chrome = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    if not os.path.exists(chrome):
        return "chromium not available, runtime not checked"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright not available, runtime not checked"
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=chrome,
                              args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1500, "height": 1000}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
        pg.goto("file://" + os.path.abspath(path))
        pg.wait_for_timeout(2500)
        tabs = pg.query_selector_all("nav.tabs button")
        # click through every screen; a render that throws only shows up here
        for i in range(len(tabs)):
            pg.query_selector_all("nav.tabs button")[i].click()
            pg.wait_for_timeout(700)
        n = len(tabs)
        b.close()
    if errors:
        raise RuntimeError("the page throws at runtime:\n  " + "\n  ".join(errors[:6]))
    return f"{n} screens render clean"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--template")
    a = ap.parse_args()
    html = render(a.template)
    try:
        note = check_js(html)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    try:
        runtime = check_runtime(a.out)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {a.out} ({len(html)//1024} KB) — {note}, {runtime}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
