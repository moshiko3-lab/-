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
import subprocess
import re
import sys

# An email address that is not one of ours, and a Panamanian mobile as their
# export writes it. Both appear in a build made with clients.json and in no
# other build.
PATTERNS = [
    # c.us and g.us are how WhatsApp spells a chat id, not a mail host. They
    # look like addresses to this pattern and are not, and the source pass
    # walks files full of them.
    ("an email address", re.compile(
        r"[\w.+-]+@(?!bloowatch\.com|shokogi|example\.|c\.us|g\.us)"
        r"[\w-]+\.[\w.]{2,}")),
    ("a phone number", re.compile(r"\+507[  ]?\d[\d  -]{5,}")),
    # the studio pages store numbers as bare digits with the country code,
    # which is how they reach wa.me and how a leaked client list would look.
    # Half its clients are Israeli, so that shape has to be caught too.
    ("a phone number", re.compile(r"\b507\d{7,8}\b")),
    ("a phone number", re.compile(r"\b972\d{8,9}\b")),
]
# The seeded catalogue legitimately names the school's own staff, and the page
# names its author and its own domain; nothing here is a customer.
ALLOW = re.compile(r"(shokogipanama|noreply@|@bloowatch\.com|@2x|@media|@font-face|@keyframes|@supports|@charset|@import)")

# A run of zeros this long is not a subscriber anywhere. Test fixtures and
# documentation examples use that shape deliberately, so that a number in
# the repository is either obviously invented or a genuine mistake, and
# never something a reader has to look up to tell apart.
INVENTED = re.compile(r"0{5}")

# The owner's own address, in the owner's own repository. It is here on
# purpose: SENDING.md documents mailing it when WhatsApp cannot be reached,
# and a runbook that will not name where to send is not a runbook. Every
# other address still fails. Worth revisiting if this repo ever stops being
# the owner's -- move it to an environment variable and the allowance goes.
OWNER = re.compile(r"moshiko3@gmail\.com")


def studio_own_numbers():
    """The studio's own contact number is meant to be on the page.

    It is read from both places that carry it -- the snapshot the public
    pages are built from, and the defaults compiled into every page -- so
    that a build made without the snapshot does not fail over the studio's
    own number while still failing over anybody else's."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = set()
    salon = os.path.join(here, "brows", "salon.json")
    if os.path.exists(salon):
        with open(salon, encoding="utf-8") as f:
            out.add((json.load(f).get("settings") or {}).get("phone") or "")
    lib = os.path.join(here, "brows", "lib.js")
    if os.path.exists(lib):
        with open(lib, encoding="utf-8") as f:
            out.update(re.findall(r'phone:\s*"(\d+)"', f.read()))
    return {re.sub(r"\D+", "", p) for p in out if re.sub(r"\D+", "", p)}


def each_file(root):
    for here, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith((".html", ".js", ".json")):
                yield os.path.relpath(os.path.join(here, name), root)


# Source files that legitimately hold the school's own contacts. crew.json
# and clients.json are not here because they are not in the repository at
# all; these are the ones that are.
SOURCE_SKIP = ("app/", "site/", "brows/salon.json", "brows/lib.js")


def tracked_source():
    """Every text file git actually publishes, relative to the repo root.

    `site/` is the build and has its own pass; `app/` holds the files that
    are deliberately kept out of git. Everything else is source that anyone
    can read on GitHub the moment it is pushed.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = subprocess.run(["git", "-C", here, "ls-files", "-z"],
                         capture_output=True, text=True, timeout=120)
    for name in out.stdout.split("\0"):
        if not name or name.startswith(SOURCE_SKIP):
            continue
        if not name.endswith((".py", ".md", ".json", ".js", ".html", ".yml",
                              ".yaml", ".txt", ".sh")):
            continue
        yield name


def school_own_number():
    """The school's own WhatsApp line, which the repository has to name.

    whatsapp.json is the addressing book: it holds the account the messages
    are sent *from*, and gifs.json names the same line. That is the school's
    own business number, exactly as brows/salon.json holds the studio's, and
    it is read from the file rather than written down twice.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    book = os.path.join(here, "bloowatch", "whatsapp.json")
    try:
        with open(book, encoding="utf-8") as f:
            phone = (json.load(f).get("account") or {}).get("phone") or ""
    except (OSError, ValueError):
        return set()
    digits = re.sub(r"\D+", "", str(phone))
    return {digits} if digits else set()


def check_source():
    """The same rule, applied to the code rather than to the build.

    The build pass has run since the start and never once looked at the
    source, which is how the owner's own mobile number sat in send.py's
    docstring and in SENDING.md, in a public repository, for weeks. It was
    caught on 15/09/2026 by a routine that refused to send to it -- not by
    any check here.

    An example number is not worth a real one. Write +507XXXXXXX.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    own = studio_own_numbers() | school_own_number()
    bad = []
    for name in sorted(tracked_source()):
        path = os.path.join(here, name)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        for what, rx in PATTERNS:
            hits = [h for h in rx.findall(text)
                    if not ALLOW.search(h) and not OWNER.search(h)
                    and not INVENTED.search(h)
                    and re.sub(r"\D+", "", h) not in own]
            if hits:
                bad.append("%s carries %s (%d of them)" % (name, what,
                                                           len(hits)))
    if bad:
        print("REFUSING: a tracked source file carries someone's contact "
              "details, and this repository is public.")
        for b in bad:
            print("  " + b)
        print("Use +507XXXXXXX in an example. A real number in a docstring "
              "is still a real number.")
        return 1
    print("checked the tracked source — no phone numbers or addresses in it")
    return 0


def main():
    if "--source" in sys.argv[1:]:
        return check_source()
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
