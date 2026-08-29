#!/usr/bin/env python3
"""Render the Shokogi control room to a single self-contained HTML file.

    python3 build_site.py --out index.html

Pulls a fresh dataset from Bloowatch, then inlines it into site_template.html
so the result is one file that can be dropped onto any static host -- no
server, no build step, no API keys sitting in the page.
"""
import argparse
import base64
import json
import os
import sys

from export_dataset import build

HERE = os.path.dirname(os.path.abspath(__file__))


def render(data, template=None):
    tpl_path = template or os.path.join(HERE, "site_template.html")
    with open(tpl_path, encoding="utf-8") as f:
        tpl = f.read()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # the payload lives inside a <script> block, so its own tags must not close it
    blob = blob.replace("</script>", "<\\/script>")
    out = tpl.replace("/*__DATA__*/", blob)

    # the badge is inlined as a data URI so the page stays a single file
    logo = os.path.join(HERE, "logo.png")
    if os.path.exists(logo):
        with open(logo, "rb") as f:
            out = out.replace("/*__LOGO__*/", base64.b64encode(f.read()).decode())

    for token in ("/*__DATA__*/", "/*__LOGO__*/"):
        if token in out:
            raise RuntimeError(f"template placeholder {token} was not replaced")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=45)
    ap.add_argument("--agenda-days", type=int, default=10)
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--template")
    a = ap.parse_args()
    try:
        data = build(a.days, a.agenda_days)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    html = render(data, a.template)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {a.out} ({len(html)//1024} KB) — "
          f"{len(data['closings'])} days, {len(data['agenda'])} activities")
    return 0


if __name__ == "__main__":
    sys.exit(main())
