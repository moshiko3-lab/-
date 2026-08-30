#!/usr/bin/env python3
"""Fetch the SHOKOGI brand webfonts and emit an @font-face stylesheet.

Headless Chromium in a sandbox has no Hebrew font and no Figtree, so a page
that merely names them renders in DejaVu and the whole piece looks generic.
This downloads the real files once, caches them next to the skill, and writes
CSS that points at the cache.

    python3 fonts.py --out fonts.css              # file:// urls, fast
    python3 fonts.py --out fonts.css --embed      # base64, for a file you send

Use --embed for anything that leaves this machine (an emailed flyer, an HTML
page a client opens); the file:// form only resolves here.
"""
import argparse, base64, os, re, subprocess, sys

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")

# Latin display + text, Hebrew text, and the mono used for figures and codes.
FAMILIES = "family=Figtree:wght@400;500;600;700;800;900&family=Heebo:wght@400;500;700;800;900&family=IBM+Plex+Mono:wght@400;500;600"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def fetch(url, binary=True):
    # Google serves woff2 only to a browser UA; without it you get truetype,
    # which is four times the size and still fine, but the cache would be wrong.
    out = subprocess.run(["curl", "-sSfL", "-A", UA, url], capture_output=True)
    if out.returncode != 0:
        raise SystemExit("could not fetch %s\n%s" % (url, out.stderr.decode()[:400]))
    return out.stdout if binary else out.stdout.decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fonts.css")
    ap.add_argument("--embed", action="store_true", help="inline the fonts as base64")
    a = ap.parse_args()

    os.makedirs(CACHE, exist_ok=True)
    css = fetch("https://fonts.googleapis.com/css2?%s&display=swap" % FAMILIES, binary=False)

    for url in sorted(set(re.findall(r"https://fonts\.gstatic\.com[^)]+", css))):
        name = url.rsplit("/", 1)[-1]
        path = os.path.join(CACHE, name)
        if not os.path.exists(path):
            with open(path, "wb") as fh:
                fh.write(fetch(url))
            print("cached %s" % name, file=sys.stderr)
        if a.embed:
            with open(path, "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            css = css.replace(url, "data:font/woff2;base64,%s" % b64)
        else:
            css = css.replace(url, "file://" + os.path.abspath(path))

    with open(a.out, "w") as fh:
        fh.write(css)
    print("%s  (%d KB)" % (a.out, os.path.getsize(a.out) // 1024))


if __name__ == "__main__":
    main()
