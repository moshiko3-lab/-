#!/usr/bin/env python3
"""Fail on a call to a function that does not exist.

`node --check` only parses. The browser check only reaches what it can click,
and a row menu that needs a booking to exist is not reachable on an empty
database -- which is exactly where `cancelForm` hid: parsed fine, threw the
first time somebody opened that menu.

So: read the built page, throw away everything that is not code, and compare
what is called against what is defined.

    python3 check_names.py index.html
"""
import re
import sys

# Names a regex cannot tell from a global: language keywords, host objects, and
# CSS function syntax. Anything genuinely global belongs in the page.
ALLOW = {
    "function", "if", "for", "while", "switch", "catch", "return", "typeof",
    "new", "in", "of", "var", "let", "const", "do", "else", "delete", "void",
    "String", "Number", "Boolean", "Array", "Object", "JSON", "Math", "Date",
    "RegExp", "Error", "Set", "Map", "Promise", "Symbol",
    "parseInt", "parseFloat", "isNaN", "isFinite",
    "setTimeout", "clearTimeout", "setInterval", "clearInterval",
    "requestAnimationFrame", "encodeURIComponent", "decodeURIComponent",
    "addEventListener", "removeEventListener", "scrollTo", "alert", "confirm",
    # writing a spreadsheet is bytes, and handing it over is a blob
    "Blob", "URL", "Uint8Array", "Int32Array", "unescape", "escape",
    # the shared book talks over the network and waits for answers
    "fetch", "Response", "navigator", "matchMedia",
    # CSS function syntax survives inside style strings
    "rgba", "rgb", "hsl", "hsla", "calc", "minmax", "repeat", "url",
    "translateX", "translateY", "translate", "scale", "rotate",
    "linear-gradient", "repeating-linear-gradient", "cubic-bezier",
}

# A regex literal only starts where a value is expected. After a name, a number
# or a closing bracket, a slash is division. This is the whole difference
# between reading `/"/g` as a pattern and reading it as an open string.
BEFORE_REGEX = set('(,=:[!&|?{};+-*%~^<>') | {"\n", "\r", "\t", " "}
KEYWORD_BEFORE = ("return", "typeof", "case", "in", "of", "do", "else", "new")


def strip_noise(js):
    """Blank out comments, string literals and regex literals, in that order.

    Order matters twice over: an apostrophe inside a comment ("a person's
    lane") would open a string and swallow the file, and a quote inside a
    regex (`/"/g`) would do the same.
    """
    out = []
    i, n = 0, len(js)
    while i < n:
        c = js[i]
        if c == "/" and i + 1 < n and js[i + 1] == "/":
            while i < n and js[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and js[i + 1] == "*":
            i += 2
            while i + 1 < n and not (js[i] == "*" and js[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if c in "\"'`":
            q = c
            i += 1
            while i < n:
                if js[i] == "\\":
                    i += 2
                    continue
                if js[i] == q:
                    i += 1
                    break
                i += 1
            out.append('""')
            continue
        if c == "/":
            prev = "".join(out[-24:]).rstrip()
            is_regex = (not prev) or prev[-1] in BEFORE_REGEX or \
                any(prev.endswith(k) for k in KEYWORD_BEFORE)
            if is_regex:
                i += 1
                in_class = False
                while i < n:
                    if js[i] == "\\":
                        i += 2
                        continue
                    if js[i] == "[":
                        in_class = True
                    elif js[i] == "]":
                        in_class = False
                    elif js[i] == "/" and not in_class:
                        i += 1
                        break
                    elif js[i] == "\n":
                        break
                    i += 1
                while i < n and js[i] in "gimsuy":
                    i += 1
                out.append("RE")
                continue
        out.append(c)
        i += 1
    return "".join(out)


def main(path):
    html = open(path, encoding="utf-8").read()
    m = re.search(r"<script>\n\(function\(\)\{(.*?)</script>", html, re.S)
    if not m:
        print("no inline script found", file=sys.stderr)
        return 1
    js = strip_noise(m.group(1))

    defined = set(re.findall(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", js))
    defined |= set(re.findall(r"\bvar\s+([A-Za-z_$][\w$]*)\s*=", js))
    # every function's parameters, so a callback name is not read as a global
    for params in re.findall(r"function[^(]*\(([^)]*)\)", js):
        for p in params.split(","):
            p = p.strip()
            if p:
                defined.add(p)

    called = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", js))
    missing = sorted(called - defined - ALLOW)
    if missing:
        print("these are called but never defined:\n  " + "\n  ".join(missing),
              file=sys.stderr)
        return 1
    print(f"{len(defined)} names resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "index.html"))
