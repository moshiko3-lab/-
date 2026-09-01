#!/usr/bin/env python3
"""Refuse to publish a page that carries real people.

The manager can be built with the school's own client list baked in -- names,
phone numbers, email addresses -- which is right on a laptop at the counter and
wrong on a public address. That file is not in the repository, so a build made
in CI cannot have it; this is the guard that says so out loud rather than
trusting it, and fails the publish if it is ever wrong.

The studio pages under site/studio are held to the same rule. What they are
allowed to carry is the studio's own contact number, which is meant to be
public and is read out of brows/salon.json rather than waved through.

    python3 .github/no_pii.py site
"""
import json
import os
import re
import sys

# An email address that is not one of ours, and a Panamanian mobile as their
# export writes it. Both appear in a build made with clients.json and in no
# other build.
PATTERNS = [
    ("an email address", re.compile(
        r"[\w.+-]+@(?!bloowatch\.com|shokogi|example\.)[\w-]+\.[\w.]{2,}")),
    ("a phone number", re.compile(r"\+507[  ]?\d[\d  -]{5,}")),
    # the studio pages store numbers as bare digits with the country code,
    # which is how they reach wa.me and how a leaked client list would look
    ("a phone number", re.compile(r"\b507\d{7,8}\b")),
]
# The seeded catalogue legitimately names the school's own staff, and the page
# names its author and its own domain; nothing here is a customer.
ALLOW = re.compile(r"(shokogipanama|noreply@|@bloowatch\.com|@2x|@media|@font-face|@keyframes|@supports|@charset|@import)")


def studio_own_numbers():
    """The studio's own contact number is meant to be on the page."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = set()
    for path in (os.path.join(here, "brows", "salon.json"),):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            phone = (json.load(f).get("settings") or {}).get("phone") or ""
        digits = re.sub(r"\D+", "", phone)
        if digits:
            out.add(digits)
            out.add(digits[3:] if digits.startswith("507") else "507" + digits)
    return out


def each_file(root):
    for here, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith((".html", ".js", ".json")):
                yield os.path.relpath(os.path.join(here, name), root)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "site"
    own = studio_own_numbers()
    bad = []
    for name in sorted(each_file(root)):
        with open(os.path.join(root, name), encoding="utf-8", errors="replace") as f:
            text = f.read()
        for what, rx in PATTERNS:
            hits = [h for h in rx.findall(text)
                    if not ALLOW.search(h) and re.sub(r"\D+", "", h) not in own]
            if hits:
                # the count, never a sample: a failing log is read by more
                # people than the page would have been
                bad.append("%s carries %s (%d of them)" % (name, what, len(hits)))
        # the client list is injected into one tag and nowhere else; without
        # the file the build writes null into it
        m = re.search(r'<script id="people"[^>]*>(.{0,40})', text, re.S)
        if m and m.group(1).strip()[:4] != "null":
            bad.append("%s was built with clients.json" % name)
    if bad:
        print("REFUSING TO PUBLISH:")
        for b in bad:
            print("  " + b)
        return 1
    print("checked %s — no client data in the build" % root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
