#!/usr/bin/env python3
"""The check that tells the two kinds of "present" apart.

preflight.py answers one question the other checks cannot: did this secret
come from the environment, or from the `.env` file beside send.py? Both
make a routine work today. Only the first one means the token lives in a
single place, and a routine carrying its own copy is how a refresh in the
Green-API console took five routines down at once on 2/9/2026.

The distinction rests entirely on one line of import order -- the snapshot
of os.environ has to be taken before `import send`, because importing send
loads `.env` into os.environ and after that the two sources are
indistinguishable. Nothing about that line looks load-bearing, which is
exactly why it is pinned here: move it and this fails loudly instead of
quietly reporting `environment` for everything forever.

Runs preflight as a subprocess, because that import order is only real in
a fresh process. Touches no network.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

TOKEN = "tokenvalue0000000000000000000000deadbeef"
KEYS = ("GREENAPI_ID", "GREENAPI_TOKEN", "GREENAPI_URL",
        "BLOOWATCH_URL", "BLOOWATCH_EMAIL", "BLOOWATCH_PASSWORD")

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def run(tmp, env_file_lines, environ):
    """preflight --json --no-network, in a directory we control."""
    for f in os.listdir(HERE):
        if f.endswith(".py") or f.endswith(".json"):
            link = os.path.join(tmp, f)
            if not os.path.exists(link):
                os.symlink(os.path.join(HERE, f), link)
    path = os.path.join(tmp, ".env")
    if env_file_lines is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(env_file_lines) + "\n")

    clean = {k: v for k, v in os.environ.items() if k not in KEYS}
    clean.update(environ)
    out = subprocess.run([sys.executable, os.path.join(tmp, "preflight.py"),
                          "--json", "--no-network"],
                         capture_output=True, text=True, env=clean, timeout=120)
    return json.loads(out.stdout), out.stdout + out.stderr


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # --- the distinction itself ------------------------------------
        report, _ = run(tmp,
                        ["GREENAPI_TOKEN=" + TOKEN],
                        {"GREENAPI_ID": "111", "GREENAPI_URL": "https://x"})
        src = report["secrets"]
        check("a secret from the environment is reported as such",
              src["GREENAPI_ID"] == "environment", src["GREENAPI_ID"])
        check("a secret that only `.env` supplied is reported as the file",
              src["GREENAPI_TOKEN"] == ".env file", src["GREENAPI_TOKEN"])
        check("a secret nobody supplies is MISSING",
              src["BLOOWATCH_PASSWORD"] == "MISSING",
              src["BLOOWATCH_PASSWORD"])

        # The environment must win over the file, or a stale `.env` left in
        # a container would quietly outrank the value the owner just set.
        report, _ = run(tmp,
                        ["GREENAPI_TOKEN=" + TOKEN],
                        {"GREENAPI_TOKEN": "from-the-environment"})
        check("the environment outranks the file when both have it",
              report["secrets"]["GREENAPI_TOKEN"] == "environment",
              report["secrets"]["GREENAPI_TOKEN"])

        # --- a missing secret has to fail, not merely be noted ----------
        check("a missing secret is a problem, not a warning",
              any("BLOOWATCH_PASSWORD" in p for p in report["problems"]),
              repr(report["problems"]))

        # --- and the report must never carry the value ------------------
        report, raw = run(tmp, ["GREENAPI_TOKEN=" + TOKEN], {})
        check("the token's value never appears in the output",
              TOKEN not in raw)
        check("nor in any field of the report",
              TOKEN not in json.dumps(report, ensure_ascii=False))

        # --- the file it leaves behind must be safe to commit -----------
        # It goes into a public repository, so this is the one place where
        # "the token never appears" has to be true of a file on disk and
        # not only of what was printed.
        out = os.path.join(tmp, "status", "preflight.json")
        clean = {k: v for k, v in os.environ.items() if k not in KEYS}
        clean["GREENAPI_TOKEN"] = TOKEN
        subprocess.run([sys.executable, os.path.join(tmp, "preflight.py"),
                        "--record", "--no-network"],
                       capture_output=True, text=True, env=clean, timeout=120)
        with open(out, encoding="utf-8") as fh:
            written = fh.read()
        check("the recorded file says where the token came from",
              '"GREENAPI_TOKEN": "environment"' in written, written[:200])
        check("and never what it is", TOKEN not in written)

        # --- the warning that says the migration is not finished --------
        report, _ = run(tmp,
                        ["GREENAPI_ID=1", "GREENAPI_TOKEN=" + TOKEN,
                         "GREENAPI_URL=https://x"], {})
        check("all three from the file raises the still-copied warning",
              any("routines each carry" in w for w in report["warnings"]),
              repr(report["warnings"]))

        report, _ = run(tmp, None,
                        {"GREENAPI_ID": "1", "GREENAPI_TOKEN": TOKEN,
                         "GREENAPI_URL": "https://x"})
        check("and it is silent once the environment supplies them",
              not any("routines each carry" in w for w in report["warnings"]),
              repr(report["warnings"]))

    print()
    if fails:
        print("%d failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
