#!/usr/bin/env python3
"""Render a SHOKOGI artboard to a print-ready PDF or a pixel-exact PNG.

Headless Chromium is the renderer, because the same HTML then behaves the same
on the web and on paper. Two things it gets wrong unless you are careful, and
which this script handles for you:

  * a stray text node after the artboard pushes a blank second page into the
    PDF, and nothing warns you -- so the page count is checked after writing;
  * a screenshot is 96 dpi unless the device scale factor says otherwise, and
    a 96 dpi flyer looks soft the moment it is printed.

Chromium also refuses to open a window narrower than 500 css pixels, so any
artboard under that -- a6, dl, a business card -- is rendered in a wider window
and cut back to size. brand.css keeps the artboard hard against the left edge,
including on rtl pages, so that cut lands where it should.

    python3 render.py flyer.html --preset a4 --out flyer.pdf
    python3 render.py flyer.html --preset a4 --out flyer.png --dpi 300
    python3 render.py cover.html --preset ig-post --out cover.png

Run with no preset to list them.
"""
import argparse, glob, os, re, shutil, struct, subprocess, sys, zlib

# width, height, unit. mm presets are for paper, px presets for screens.
PRESETS = {
    "a3":            (297, 420, "mm"),
    "a4":            (210, 297, "mm"),
    "a4-landscape":  (297, 210, "mm"),
    "a5":            (148, 210, "mm"),
    "a6":            (105, 148, "mm"),
    "dl":            (99, 210, "mm"),        # the rack-card flyer
    "letter":        (215.9, 279.4, "mm"),
    "poster-50x70":  (500, 700, "mm"),
    "square-print":  (210, 210, "mm"),
    "business-card": (85, 55, "mm"),
    "ig-post":       (1080, 1080, "px"),
    "ig-story":      (1080, 1920, "px"),     # also WhatsApp status
    "fb-cover":      (1640, 624, "px"),
    "yt-banner":     (2560, 1440, "px"),
    "li-banner":     (1584, 396, "px"),
    "og":            (1200, 630, "px"),      # link preview card
    "icon-180":      (180, 180, "px"),       # apple-touch-icon
    "icon-192":      (192, 192, "px"),       # web app manifest
    "icon-512":      (512, 512, "px"),       # web app manifest, install prompt
}


def chrome():
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",
                "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    for name in ("chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("no chromium found; set --chrome")


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    # Chromium always complains about dbus in a container. That is not a failure.
    noise = (b"dbus", b"Failed to call method", b"shared_image", b"GPU", b"gpu/")
    err = b"\n".join(l for l in p.stderr.splitlines()
                     if not any(n in l for n in noise))
    if err.strip():
        print(err.decode(errors="replace")[:800], file=sys.stderr)
    return p.returncode


def crop_png(path, w, h):
    """Cut the image down to the top-left w x h box, in place.

    Headless Chromium keeps about 87 css pixels of the window for browser
    furniture that is not there, so a window sized to the artboard renders a
    viewport shorter than the artboard and the bottom of the piece is lost.
    Asking for a taller window and cutting the result back is the reliable fix,
    and it does not depend on that number staying 87.
    """
    d = open(path, "rb").read()
    pos, idat = 8, b""
    while pos < len(d):
        ln = struct.unpack(">I", d[pos:pos+4])[0]
        typ, data = d[pos+4:pos+8], d[pos+8:pos+8+ln]
        if typ == b"IHDR":
            iw, ih, bd, ct = struct.unpack(">IIBB", data[:10])
        elif typ == b"IDAT":
            idat += data
        pos += 12 + ln
    if (iw, ih) == (w, h):
        return
    nch = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    stride = iw * nch
    raw = zlib.decompress(idat)

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p-a), abs(p-b), abs(p-c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    lines, prev, i = [], bytearray(stride), 0
    for _ in range(ih):
        f = raw[i]; i += 1
        line = bytearray(raw[i:i+stride]); i += stride
        for x in range(stride):
            a = line[x-nch] if x >= nch else 0
            b = prev[x]
            c = prev[x-nch] if x >= nch else 0
            if f == 1:   line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4: line[x] = (line[x] + paeth(a, b, c)) & 255
        lines.append(line); prev = line

    w, h = min(w, iw), min(h, ih)
    body = b"".join(b"\x00" + bytes(l[:w*nch]) for l in lines[:h])

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, bd, ct, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(body, 6)))
        fh.write(chunk(b"IEND", b""))


def pdf_pages(path):
    d = open(path, "rb").read()
    return len(re.findall(rb"/Type\s*/Page[^s]", d)) or 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("--preset", help="one of: " + ", ".join(sorted(PRESETS)))
    ap.add_argument("--out", default="out.pdf")
    ap.add_argument("--dpi", type=int, default=300, help="PNG only; 300 for print, 96 for screen")
    ap.add_argument("--chrome")
    ap.add_argument("--wait", type=int, default=4000, help="ms for fonts and images to settle")
    a = ap.parse_args()

    if not a.input or not a.preset:
        for name, (w, h, u) in sorted(PRESETS.items()):
            print("  %-14s %g x %g %s" % (name, w, h, u))
        return
    if a.preset not in PRESETS:
        raise SystemExit("unknown preset %r; run without arguments to list them" % a.preset)

    w, h, unit = PRESETS[a.preset]
    src = "file://" + os.path.abspath(a.input)
    exe = a.chrome or chrome()
    base = [exe, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
            "--force-color-profile=srgb", "--virtual-time-budget=%d" % a.wait]

    if a.out.lower().endswith(".pdf"):
        # The page size comes from the document's own @page rule, which is why
        # every template carries one. Chromium honours it and ignores --window-size.
        if run(base + ["--no-pdf-header-footer", "--print-to-pdf=" + a.out, src]):
            raise SystemExit("chromium failed to write the pdf")
        n = pdf_pages(a.out)
        box = re.findall(rb"/MediaBox\s*\[([^\]]+)\]", open(a.out, "rb").read())
        mm = [round(float(x) / 72 * 25.4, 1) for x in box[0].split()[2:]] if box else []
        print("%s  %s mm  %d page%s" % (a.out, " x ".join(map(str, mm)), n, "" if n == 1 else "s"))
        if n > 1:
            print("  second page: something after the artboard overflows it. Give the\n"
                  "  wrapper font-size:0 and check the artboard is exactly %g%s tall."
                  % (h, unit), file=sys.stderr)
        if mm and unit == "mm" and abs(mm[0] - w) > 1.5:
            print("  page is %s mm but the preset is %g mm: the @page rule in the html\n"
                  "  does not match --preset." % (mm[0], w), file=sys.stderr)
    else:
        # A screenshot is taken in CSS pixels; the scale factor turns those into
        # real pixels. 300 dpi on a 210 mm page is 2480 px, which is what a
        # printer wants and what --dpi 300 produces.
        css_w = w if unit == "px" else w / 25.4 * 96
        css_h = h if unit == "px" else h / 25.4 * 96
        scale = 1.0 if unit == "px" else a.dpi / 96.0
        if run(base + ["--screenshot=" + a.out,
                       "--window-size=%d,%d" % (round(css_w), round(css_h) + 240),
                       "--force-device-scale-factor=%g" % scale, src]):
            raise SystemExit("chromium failed to write the png")
        px_w, px_h = round(css_w * scale), round(css_h * scale)
        crop_png(a.out, px_w, px_h)
        print("%s  %d x %d px%s" % (a.out, px_w, px_h,
                                    "  (%d dpi)" % a.dpi if unit == "mm" else ""))


if __name__ == "__main__":
    main()
