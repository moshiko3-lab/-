#!/usr/bin/env python3
"""Render the Shokogi manager app to one self-contained HTML file.

    python3 build.py --out index.html

No data is baked in -- the app starts empty and keeps everything the user
enters in their own browser. Only the badge is inlined.
"""
import argparse
import base64
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def render(template=None):
    tpl = template or os.path.join(HERE, "app_template.html")
    with open(tpl, encoding="utf-8") as f:
        out = f.read()
    logo = os.path.join(HERE, "logo.png")
    if os.path.exists(logo):
        with open(logo, "rb") as f:
            out = out.replace("/*__LOGO__*/", base64.b64encode(f.read()).decode())
    if "/*__LOGO__*/" in out:
        raise RuntimeError("logo placeholder was not replaced")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--template")
    a = ap.parse_args()
    html = render(a.template)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {a.out} ({len(html)//1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
