#!/usr/bin/env python3
"""Build the three pages of the studio, each to one self-contained HTML file.

    python3 brows/build.py --out site/

Three pages come out:

    index.html   the therapist's own diary, in Hebrew
    book.html    the page a client books from, English or Hebrew
    form.html    the release, waiver and health declaration she signs

Nothing is fetched at runtime -- no CDN, no font, no framework. A page that
opens from a memory stick behaves exactly like the one on the web, which is
what you want in a studio whose wifi drops.

Two files feed the build and are optional:

    cloud.json   {"url": "...", "key": "..."}  the shared book, when there is one
    salon.json   a snapshot of the services and hours, for the public pages to
                 show when there is no shared book

Neither may hold a service key or a password. The key in cloud.json is
Supabase's publishable key, which is meant to sit in a public page; what
guards the data is supabase.sql, not the key.
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# template, app script, output, extra placeholders it needs
PAGES = [
    ("manager_template.html", "manager.js", "index.html", []),
    ("book_template.html",    "book.js",    "book.html",  ["i18n", "salon"]),
    ("form_template.html",    "form.js",    "form.html",  ["i18n", "consent", "salon"]),
]


def icon_data_uri(name):
    with open(os.path.join(HERE, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def head_for(name):
    """What turns a page into something that lives on a home screen.

    The touch icon is inlined, so a page opened from a file or a memory
    stick still has one. The manifest is a real file beside the pages --
    Android wants one to open the diary full screen, without a browser bar
    around it, and it is the diary that is opened forty times a day."""
    # inlined once: iOS reads this one, and it is the phone most likely to
    # be holding the diary. The favicon points at the file beside the page,
    # so the same picture is not carried twice in every download.
    out = ['<link rel="apple-touch-icon" href="%s">' % icon_data_uri("icon-180.png"),
           '<link rel="icon" href="icon-192.png">']
    if name == "index.html":
        out += ['<link rel="manifest" href="manifest.webmanifest">',
                '<meta name="apple-mobile-web-app-title" content="היומן">']
    return "\n".join(out)


MANIFEST = {
    "name": "היומן", "short_name": "היומן", "lang": "he", "dir": "rtl",
    "start_url": "./index.html", "scope": "./", "display": "standalone",
    "orientation": "portrait", "background_color": "#faf7f4",
    "theme_color": "#faf7f4",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png",
         "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "any maskable"},
    ],
}


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def data_file(name):
    """A data file beside the build, as JSON text -- or None when absent."""
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cloud_config():
    cfg = data_file("cloud.json") or {}
    blob = json.dumps(cfg).lower()
    for forbidden in ("service_role", "service_key", "password", "secret"):
        if forbidden in blob:
            raise RuntimeError(
                "cloud.json carries something that must never reach a public page: "
                + forbidden)
    return {"url": cfg.get("url", ""), "key": cfg.get("key", "")}


def js_literal(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def render(template, app, extras, name):
    out = read(template)
    subs = {
        "/*__HEAD__*/": head_for(name),
        "/*__STYLE__*/": read("style.css"),
        "/*__LIB__*/": read("lib.js"),
        # the whole declaration is replaced, so cloud.js still parses on its own
        "/*__CLOUD__*/": re.sub(r'var CLOUD = \{[^}]*\};',
                                "var CLOUD = " + js_literal(cloud_config()) + ";",
                                read("cloud.js"), count=1),
        "/*__APP__*/": read(app),
    }
    if "i18n" in extras:
        subs["/*__I18N__*/"] = read("i18n.js")
    if "consent" in extras:
        subs["/*__CONSENT__*/"] = read("consent.js")
    if "salon" in extras:
        salon = data_file("salon.json")
        subs["/*__SALON__*/"] = ("var SALON = " +
                                 (js_literal(salon) if salon else "null") + ";")
    for token, value in subs.items():
        if token not in out:
            raise RuntimeError(f"{template}: no place to put {token}")
        out = out.replace(token, value)
    left = re.findall(r"/\*__[A-Z]+__\*/", out)
    if left:
        raise RuntimeError(f"{template}: placeholders left unfilled: {left}")
    return out


def check_js(html, what):
    """Parse the page's script. A typo here is a blank page for a client."""
    m = re.search(r"<script>(.*)</script>", html, re.S)
    if not m:
        raise RuntimeError(f"{what}: no inline script")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as f:
        f.write(m.group(1))
        path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    except FileNotFoundError:
        return "node missing, script not parsed"
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise RuntimeError(f"{what}: the script does not parse\n" + (r.stderr or "")[:800])
    return "script parses"


def drive(page, name):
    """Walk the page the way a thumb would. Each page gets its own walk --
    node --check only parses, and a name that does not exist is invisible
    until the line runs. That is exactly how a page ships blank."""
    if name == "index.html":
        for tab in page.query_selector_all("#tabs button"):
            tab.click()
            page.wait_for_timeout(220)
        page.click('#tabs button[data-tab="today"]')
        page.click("#btn-new")
        page.wait_for_timeout(300)
        page.click("#modal [data-close]")
    elif name == "book.html":
        page.click("#lang")                      # both languages, one page load
        page.wait_for_timeout(150)
        page.click("#lang")
        page.wait_for_timeout(150)
        card = page.query_selector(".pick")
        if card:
            card.click()
            page.wait_for_timeout(300)
            slot = page.query_selector(".slot")
            if slot:
                slot.click()
                page.wait_for_timeout(300)
                page.fill("#b-name", "Test")
                page.fill("#b-phone", "61234567")
    elif name == "form.html":
        page.click("#lang")
        page.wait_for_timeout(150)
        page.click("#lang")
        page.wait_for_timeout(150)
        box = page.query_selector('#t-box input[data-t="lift"]')
        if box:
            box.check()
            page.wait_for_timeout(250)
        # the radios themselves are invisible on purpose -- the label is the
        # target, the way a thumb finds it
        for q in page.query_selector_all("#q-box .q")[:3]:
            q.query_selector(".yn label:last-child").click()
            page.wait_for_timeout(80)
        page.fill("#p-name", "Test Client")
        page.fill("#p-phone", "61234567")
        page.click("#send")            # must complain, not submit
        page.wait_for_timeout(300)


def check_runtime(path, name):
    if not os.path.exists(CHROME):
        return "no chromium, runtime not checked"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "no playwright, runtime not checked"
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--no-sandbox", "--disable-background-networking",
                                    "--disable-sync", "--no-first-run"])
        # a phone's screen, because that is the only thing these pages open on.
        # is_mobile stays off on purpose: it turns on Chromium's page-scale
        # emulation, and then the clicks land at the wrong pixels here.
        ctx = b.new_context(viewport={"width": 390, "height": 844},
                            has_touch=True)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
        pg.on("console", lambda m: errors.append("console: " + m.text[:160])
              if m.type == "error" else None)
        pg.goto("file://" + os.path.abspath(path))
        pg.wait_for_timeout(600)
        drive(pg, name)
        body = pg.inner_text("body")
        b.close()
    if errors:
        raise RuntimeError(f"{name}: throws at runtime\n  " + "\n  ".join(errors[:6]))
    if len(body.strip()) < 40:
        raise RuntimeError(f"{name}: page renders empty")
    return "renders clean"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "site"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    outdir = os.path.abspath(a.out)
    os.makedirs(outdir, exist_ok=True)
    cloud = cloud_config()
    if not a.quiet:
        print("shared book:", cloud["url"] or "none -- the pages work on one phone")

    # Without a shared book, this number is the whole delivery mechanism: a
    # booking page with nowhere to send a request can only copy the details
    # to the clipboard and hope. Worth saying out loud at build time rather
    # than discovering it from a client who never got an answer.
    salon = data_file("salon.json") or {}
    dest = (salon.get("settings") or {}).get("phone") or ""
    if not a.quiet:
        if dest:
            print("requests go to: wa.me/%s" % re.sub(r"\D+", "", dest))
        elif not cloud["url"]:
            print("requests go to: NOBODY -- salon.json has no phone, so the "
                  "booking page can only copy the details to the clipboard")

    # The icons and the manifest go down first: the pages point at them, and
    # the runtime check below fails a page that asks for a file that is not
    # there -- which is how this ordering was found in the first place.
    with open(os.path.join(outdir, "manifest.webmanifest"), "w",
              encoding="utf-8") as f:
        json.dump(MANIFEST, f, ensure_ascii=False, indent=1)
    for icon in ("icon-192.png", "icon-512.png"):
        shutil.copyfile(os.path.join(HERE, icon), os.path.join(outdir, icon))
    if not a.quiet:
        print("  manifest.webmanifest + icons")

    for template, app, name, extras in PAGES:
        html = render(template, app, extras, name)
        note = check_js(html, name)
        path = os.path.join(outdir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        run = check_runtime(path, name)
        if not a.quiet:
            print(f"  {name:<12} {len(html)//1024:>4} KB   {note}, {run}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
