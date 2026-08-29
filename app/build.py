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
    # the pricing matrix is shared: the manager and the booking site must
    # arrive at the same number for the same product
    with open(os.path.join(HERE, "pricing.js"), encoding="utf-8") as f:
        out = out.replace("/*__PRICING__*/", f.read())
    cat = os.path.join(HERE, "catalog.json")
    if os.path.exists(cat):
        with open(cat, encoding="utf-8") as f:
            blob = json.dumps(json.load(f), ensure_ascii=False, separators=(",", ":"))
        out = out.replace("/*__SEED__*/", blob.replace("</script>", "<\\/script>"))
    else:
        out = out.replace("/*__SEED__*/", "null")

    # Real clients, when a clients.json has been exported beside the catalog.
    # It is not in the repository and not in every build: it holds names, phone
    # numbers and email addresses, so a page built with it should not go on a
    # public address. Build without the file and the page simply has no
    # clients, which is the state the school starts from.
    people = os.path.join(HERE, "clients.json")
    if "/*__PEOPLE__*/" in out:
        if os.path.exists(people):
            with open(people, encoding="utf-8") as f:
                blob = json.dumps(json.load(f), ensure_ascii=False,
                                  separators=(",", ":"))
            out = out.replace("/*__PEOPLE__*/",
                              blob.replace("</script>", "<\\/script>"))
        else:
            out = out.replace("/*__PEOPLE__*/", "null")

    logo = os.path.join(HERE, "logo.png")
    if os.path.exists(logo):
        with open(logo, "rb") as f:
            out = out.replace("/*__LOGO__*/", base64.b64encode(f.read()).decode())
    for token in ("/*__LOGO__*/", "/*__SEED__*/", "/*__PRICING__*/", "/*__PEOPLE__*/"):
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


def check_minisite(path):
    """Walk the booking site the way a customer would: catalogue, product,
    cart, checkout. It shares nothing with the manager's own check."""
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
        pg = b.new_context(viewport={"width": 1200, "height": 900}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
        pg.goto("file://" + os.path.abspath(path))
        pg.wait_for_timeout(1200)
        cards = len(pg.query_selector_all(".card"))
        book = pg.query_selector('.card button')
        if book:
            book.click()
            pg.wait_for_timeout(600)
            add = pg.query_selector('.modal button:has-text("Add to cart")')
            if add:
                add.click()
                pg.wait_for_timeout(500)
        pg.click("#btn-cart")
        pg.wait_for_timeout(500)
        cont = pg.query_selector('button:has-text("Continue")')
        if cont:
            cont.click()
            pg.wait_for_timeout(600)
        b.close()
    if errors:
        raise RuntimeError("the booking site throws at runtime:\n  " + "\n  ".join(errors[:6]))
    return f"{cards} products offered, cart and checkout render clean"


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
        tabs = pg.query_selector_all("#tabs button")
        n = len(tabs)
        dialogs = 0
        # Clicking through the screens only proves they render. Most of the app
        # lives in dialogs, and a missing function there stays invisible until
        # somebody opens one -- which is how a deleted block shipped twice.
        for i in range(n):
            pg.query_selector_all("#tabs button")[i].click()
            pg.wait_for_timeout(700)
            opened = 0
            for btn in pg.query_selector_all("section:not([hidden]) button"):
                if opened >= 4:
                    break
                try:
                    label = (btn.inner_text() or "").strip().lower()
                except Exception:
                    continue
                # openers only: nothing that saves, deletes or wipes
                if not label or len(label) > 34:
                    continue
                if any(w in label for w in ("del", "wipe", "archive", "clear",
                                            "restore", "export", "import",
                                            "backup", "cancel", "remove")):
                    continue
                if not any(w in label for w in ("new", "add", "edit", "record",
                                                "assign", "price", "docs",
                                                "columns", "tides", "manifest",
                                                "breakdown", "open", "client list")):
                    continue
                try:
                    btn.click(timeout=2500)
                    pg.wait_for_timeout(650)
                    if not pg.get_attribute("#scrim", "hidden") is None:
                        continue
                    dialogs += 1
                    opened += 1
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(350)
                    while pg.get_attribute("#scrim", "hidden") is None:
                        pg.keyboard.press("Escape")
                        pg.wait_for_timeout(250)
                except Exception:
                    try:
                        pg.keyboard.press("Escape")
                        pg.wait_for_timeout(250)
                    except Exception:
                        pass
        # Row menus are the one place a missing function hides: the name is
        # only reached when somebody opens the menu and picks the item, so it
        # parses fine and throws in front of a user. cancelForm did exactly
        # that. Open every kebab and take every entry that is not destructive.
        menus = 0
        for i in range(n):
            pg.query_selector_all("#tabs button")[i].click()
            pg.wait_for_timeout(600)
            kebabs = pg.query_selector_all("section:not([hidden]) .kebab")
            for kb in kebabs[:3]:
                try:
                    kb.click(timeout=2000)
                    pg.wait_for_timeout(300)
                except Exception:
                    continue
                items = pg.query_selector_all(".rowmenu button:not(.danger)")
                for j in range(len(items)):
                    live = pg.query_selector_all(".rowmenu button:not(.danger)")
                    if j >= len(live):
                        break
                    try:
                        live[j].click(timeout=2000)
                        pg.wait_for_timeout(450)
                        menus += 1
                    except Exception:
                        pass
                    for _ in range(3):
                        pg.keyboard.press("Escape")
                        pg.wait_for_timeout(200)
                    try:
                        kb.click(timeout=1500)
                        pg.wait_for_timeout(250)
                    except Exception:
                        break
                pg.keyboard.press("Escape")
                pg.wait_for_timeout(200)
        b.close()
    if errors:
        raise RuntimeError("the page throws at runtime:\n  " + "\n  ".join(errors[:6]))
    return f"{n} screens, {dialogs} dialogs and {menus} menu actions render clean"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--template")
    ap.add_argument("--minisite", action="store_true",
                    help="build the public booking site instead of the manager")
    a = ap.parse_args()
    tpl = a.template or os.path.join(
        HERE, "minisite_template.html" if a.minisite else "app_template.html")
    html = render(tpl)
    try:
        note = check_js(html)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    names = subprocess.run(
        [sys.executable, os.path.join(HERE, "check_names.py"), a.out],
        capture_output=True, text=True)
    if names.returncode != 0:
        print("error: " + (names.stderr or names.stdout).strip(), file=sys.stderr)
        return 1
    try:
        runtime = check_minisite(a.out) if a.minisite else check_runtime(a.out)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {a.out} ({len(html)//1024} KB) — {note}, "
          f"{names.stdout.strip()}, {runtime}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
