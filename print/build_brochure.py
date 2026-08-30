#!/usr/bin/env python3
"""Build the four-page brochure the school leaves in guest rooms.

    python3 print/build_brochure.py                     # -> print/shokogi-brochure.pdf
    python3 print/build_brochure.py --html out.html     # the page, unrendered
    python3 print/build_brochure.py --size a4           # 210x297 instead of Letter

The page is laid out in HTML and printed by headless Chromium, the same engine
the rest of this repository is tested in, so what a browser shows and what the
printer gets are the same thing.

Two things are deliberately not fetched at build time. The fonts sit next to
this file already base64'd into `fonts.css`, because a brochure that renders in
Figtree here and in Helvetica on someone else's machine is not one design. And
the logo is read out of `app/logo.png`, the same file the manager and the
booking page use, so the mark on paper cannot drift from the mark on screen.
"""

import argparse
import base64
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import content as C  # noqa: E402

# The brand, taken from the storefront theme the rest of the platform matches
# (bloowatch/site_template.html): pink on white, near-black text, Figtree with
# uppercase tracked labels, and the hexagon the logo is built out of.
PINK = "#f46e95"
PINK_DEEP = "#e04b78"
PINK_SOFT = "#fdeaf0"
INK = "#121011"
INK_2 = "#4a4145"
ES = "#7d7176"          # the Spanish line: present, clearly secondary
LINE = "#e6dfe2"
GROUND = "#faf7f8"

SIZES = {                # width, height, in CSS inches
    "letter": ("8.5in", "11in"),
    "a4": ("210mm", "297mm"),
}


# --------------------------------------------------------------------------
# The QR code
#
# Error correction H, because this is going on paper in a room with a lamp in
# it: a fingerprint, a curled corner or a crease costs modules, and H can lose
# up to a third of them and still read. That headroom is also what pays for the
# hexagon sitting in the middle -- it covers about a twentieth of the area,
# well inside what the level tolerates.
# --------------------------------------------------------------------------
def qr_svg(data, px, quiet=3, mark=True):
    import segno

    m = [list(row) for row in segno.make(data, error="h").matrix]
    n = len(m)
    span = n + quiet * 2

    # One path for the whole code: runs of dark modules on a row become a
    # single rectangle, which keeps the PDF small and the edges crisp.
    d = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                run = 1
                while x + run < n and row[x + run]:
                    run += 1
                d.append("M%d %dh%dv1h-%dz" % (x + quiet, y + quiet, run, run))
                x += run
            else:
                x += 1

    centre = ""
    if mark:
        # A hexagon knockout, drawn in module units so it scales with the code.
        r = span * 0.115
        cx = cy = span / 2.0
        pad = r * 1.30
        outer = _hexagon(cx, cy, pad)
        inner = _hexagon(cx, cy, r)
        centre = (
            '<path d="%s" fill="#fff"/>'
            '<path d="%s" fill="%s"/>'
            '<path d="%s" fill="#fff"/>'
            % (outer, inner, PINK, _hexagon(cx, cy, r * 0.52))
        )

    return (
        '<svg class="qr" width="%s" height="%s" viewBox="0 0 %d %d" '
        'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg" '
        'role="img" aria-label="Booking page QR code">'
        '<rect width="%d" height="%d" fill="#fff"/>'
        '<path d="%s" fill="%s"/>%s</svg>'
    ) % (px, px, span, span, span, span, "".join(d), INK, centre)


def _hexagon(cx, cy, r):
    """The logo's hexagon: flat left and right sides, points top and bottom."""
    w = r * 0.866
    return "M%.3f %.3fL%.3f %.3fL%.3f %.3fL%.3f %.3fL%.3f %.3fL%.3f %.3fZ" % (
        cx, cy - r,
        cx + w, cy - r / 2, cx + w, cy + r / 2,
        cx, cy + r,
        cx - w, cy + r / 2, cx - w, cy - r / 2,
    )


# --------------------------------------------------------------------------
# Icons: 24x24, one stroke weight, drawn rather than borrowed so the set is
# consistent and the file carries no third-party artwork.
# --------------------------------------------------------------------------
ICONS = {
    "board": '<path d="M12 2.5c4.6 5 4.6 14 0 19-4.6-5-4.6-14 0-19z"/><path d="M12 7v10"/>',
    "people": '<circle cx="9" cy="8.5" r="2.6"/><circle cx="16.6" cy="9.6" r="2"/>'
              '<path d="M4 19c0-2.8 2.2-5 5-5s5 2.2 5 5"/><path d="M15 14.3c2.6 0 4.7 2.1 4.7 4.7"/>',
    "stack": '<path d="M12 3l8.5 4.5L12 12 3.5 7.5 12 3z"/><path d="M3.5 12L12 16.5 20.5 12"/>'
             '<path d="M3.5 16.4L12 21l8.5-4.6"/>',
    "video": '<rect x="2.5" y="5.5" width="13" height="13" rx="2.5"/>'
             '<path d="M15.5 11l6-3.4v8.8l-6-3.4z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.4M12 19.6V22M2 12h2.4M19.6 12H22'
           'M5 5l1.7 1.7M17.3 17.3L19 19M19 5l-1.7 1.7M6.7 17.3L5 19"/>',
    "pin": '<path d="M12 21.5s7-6.6 7-11.4A7 7 0 1 0 5 10.1c0 4.8 7 11.4 7 11.4z"/>'
           '<circle cx="12" cy="10" r="2.6"/>',
    "paddle": '<path d="M9 2.6h6"/><path d="M12 2.6v11.2"/>'
              '<path d="M12 13.8c-3.6 1.7-4.5 4.6 0 7.6 4.5-3 3.6-5.9 0-7.6z"/>',
    "foil": '<path d="M4.6 4.4h14.8"/><path d="M12 4.4v14.9"/>'
            '<path d="M4.4 15.2c2.6-3 12.6-3 15.2 0"/><path d="M9.2 20h5.6"/>',
    "yoga": '<circle cx="12" cy="6" r="2.6"/><path d="M12 9.2v5.4"/>'
            '<path d="M3.5 19.5c2.6-3.4 5.4-5 8.5-5s5.9 1.6 8.5 5"/>',
    "ice": '<path d="M12 2.5v19M4 7l16 10M20 7L4 17"/>'
           '<path d="M9.4 4.4L12 6.9l2.6-2.5M9.4 19.6L12 17.1l2.6 2.5"/>',
    "camera": '<path d="M3 8.5h3.2l1.4-2.2h8.8l1.4 2.2H21a1 1 0 0 1 1 1v8.3a1 1 0 0 1-1 1H3'
              'a1 1 0 0 1-1-1V9.5a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.6" r="3.4"/>',
    "globe": '<circle cx="12" cy="12" r="9.2"/><path d="M2.8 12h18.4"/>'
             '<path d="M12 2.8c2.5 2.6 3.8 5.7 3.8 9.2S14.5 18.6 12 21.2C9.5 18.6 8.2 15.5 8.2 12'
             'S9.5 5.4 12 2.8z"/>',
}


def icon(name, size=19, colour="#fff", width=1.6):
    return (
        '<svg width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="%s" '
        'stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" '
        'aria-hidden="true">%s</svg>' % (size, size, colour, width, ICONS[name])
    )


def hex_badge(name):
    """An icon sitting inside the logo's hexagon, in brand pink."""
    return (
        '<span class="hexb">'
        '<svg viewBox="0 0 40 44" aria-hidden="true"><path d="%s" fill="%s"/></svg>'
        '<span class="hexi">%s</span></span>'
        % (_hexagon(20, 22, 21), PINK, icon(name))
    )


def hex_bullet():
    return ('<svg class="hexbul" viewBox="0 0 12 14" aria-hidden="true">'
            '<path d="%s" fill="%s"/></svg>' % (_hexagon(6, 7, 6), PINK))


# --------------------------------------------------------------------------
# The cover's swell lines: white, faint, and drawn wide enough to run off both
# edges so they read as passing lines rather than a decoration that stops.
# --------------------------------------------------------------------------
def swell(width=880, height=440, lines=9):
    import math

    out = []
    for i in range(lines):
        y = 40 + i * (height - 80) / (lines - 1.0)
        amp = 13 + 5 * math.sin(i * 0.9)
        pts = []
        for x in range(-40, width + 41, 10):
            pts.append("%.1f %.1f" % (x, y + amp * math.sin(x / 96.0 + i * 0.75)))
        # Faint on purpose: at any more than this the lines read as a rule
        # struck through the wordmark instead of as swell behind it.
        out.append('<path d="M%s" fill="none" stroke="#fff" stroke-width="1.4" '
                   'stroke-opacity="%.3f"/>' % ("L".join(pts), 0.055 + 0.030 * (i % 3)))
    return ('<svg class="swell" viewBox="0 0 %d %d" preserveAspectRatio="none" '
            'aria-hidden="true">%s</svg>' % (width, height, "".join(out)))


# --------------------------------------------------------------------------
def card(c):
    kind, en, es, body_en, body_es = c
    return """
      <article class="card">
        %s
        <h3>%s<small>%s</small></h3>
        <p class="en">%s</p>
        <p class="es">%s</p>
      </article>""" % (hex_badge(kind), en, es, body_en, body_es)


def section_page(d):
    return """
  <section class="page sheet">
    <div class="pad col">
      <p class="eyebrow">%s</p>
      <h2>%s<span class="es">%s</span></h2>
      <p class="lede">%s<span class="es">%s</span></p>
      <div class="grid">%s</div>
      %s
    </div>
    %s
  </section>""" % (
        d["eyebrow"], d["title_en"], d["title_es"], d["lede_en"], d["lede_es"],
        "".join(card(c) for c in d["cards"]), cta(), footer(),
    )


def cta():
    """The pink strip that ends a service page: a reader who has just read about
    a lesson should not have to turn back to the cover to book it."""
    return """
      <aside class="cta">
        <div class="qrwrap">%s</div>
        <div class="t">
          <b>%s<span>%s</span></b>
          <p>%s<i>%s</i></p>
          <span class="url">%s</span>
        </div>
      </aside>""" % (
        qr_svg(C.BOOKING_URL, "1.1in", quiet=2),
        C.CTA["title_en"], C.CTA["title_es"],
        C.CTA["body_en"], C.CTA["body_es"], C.BOOKING_LABEL,
    )


def footer():
    return ('<footer class="foot"><span>SHOKOGI · PLAYA VENAO · PANAMÁ</span>'
            '<span class="mono">%s</span></footer>' % C.BOOKING_LABEL)


def build(size="letter"):
    w, h = SIZES[size]
    fonts = open(os.path.join(HERE, "fonts.css")).read()
    logo = base64.b64encode(open(os.path.join(ROOT, "app", "logo.png"), "rb").read()).decode()

    rentals = "".join(
        '<li><b>%s</b><small>%s</small></li>' % (en, es) for en, es in C.RENTALS["items"])
    know = "".join(
        '<li>%s<span><b>%s</b><small>%s</small></span></li>' % (hex_bullet(), en, es)
        for en, es in C.KNOW["items"])

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Shokogi · Brochure</title>
<style>
%(fonts)s

@page { size: %(w)s %(h)s; margin: 0; }

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: Figtree, -apple-system, "Segoe UI", system-ui, sans-serif;
  color: %(ink)s; background: #55494e;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
  -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
}
.mono { font-family: "IBM Plex Mono", ui-monospace, monospace; }

/* One .page is one sheet. Fixed to the paper size and clipped, so a stray
   line of type can never push a seventh blank page out of the printer. */
.page {
  width: %(w)s; height: %(h)s; position: relative; overflow: hidden;
  background: #fff; page-break-after: always; break-after: page;
}
.page:last-child { page-break-after: auto; break-after: auto; }
@media screen { .page { margin: 22px auto; box-shadow: 0 8px 40px rgba(0,0,0,.45); } }

/* Ink stays inside this box on every page; only colour fields touch the edge,
   so a printer that cannot go borderless loses trim, never a word. */
.pad { position: absolute; inset: 0.62in 0.66in 0.78in; }

.eyebrow {
  font-family: "IBM Plex Mono", monospace; font-size: 9.2px; font-weight: 600;
  letter-spacing: .19em; text-transform: uppercase; color: %(pinkdeep)s;
  margin: 0 0 13px;
}
h2 {
  font-size: 33px; font-weight: 800; letter-spacing: -.02em; line-height: 1.04;
  margin: 0 0 9px;
}
h2 .es {
  display: block; font-size: 17px; font-weight: 600; letter-spacing: -.01em;
  color: %(es)s; margin-top: 3px;
}
.lede { font-size: 12.6px; line-height: 1.5; color: %(ink2)s; margin: 0 0 21px; max-width: 6.1in; }
.lede .es { display: block; color: %(es)s; font-size: 11.4px; margin-top: 2px; }

.rule { height: 3px; width: 46px; background: %(pink)s; border-radius: 2px; margin: 0 0 15px; }

/* ---------------- cards ---------------- */
/* The grid takes whatever height the heading and the strip leave it and hands
   it to the three rows equally, so a page is never two thirds full with an
   inch and a half of nothing under it. */
.pad.col { display: flex; flex-direction: column; }
.grid {
  display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: repeat(3, 1fr);
  gap: 13px; flex: 1 1 auto; min-height: 0;
}
.card {
  border: 1px solid %(line)s; border-radius: 13px; padding: 15px 15px 16px;
  background: #fff; position: relative;
  display: flex; flex-direction: column; justify-content: flex-start;
}
.card h3 {
  font-size: 12.4px; font-weight: 800; letter-spacing: .045em; text-transform: uppercase;
  margin: 11px 0 6px; line-height: 1.25;
}
.card h3 small {
  display: block; font-size: 9.6px; font-weight: 600; letter-spacing: .05em;
  color: %(es)s; margin-top: 2px;
}
.card p { margin: 0; }
.card .en { font-size: 11.5px; line-height: 1.45; color: %(ink2)s; }
.card .es { font-size: 10.4px; line-height: 1.42; color: %(es)s; margin-top: 5px; }

.hexb { position: relative; display: inline-flex; width: 34px; height: 37px; }
.hexb svg { position: absolute; inset: 0; width: 100%%; height: 100%%; }
.hexi {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
}
.hexi svg { position: static; width: 19px; height: 19px; }

.cta {
  flex: none; margin-top: 14px; background: %(pink)s; border-radius: 13px;
  padding: 13px 18px; display: flex; align-items: center; gap: 17px; color: #fff;
}
.cta .qrwrap { background: #fff; border-radius: 8px; padding: 6px; flex: none; }
.cta .qr { width: 1.1in; height: 1.1in; display: block; }
.cta .t b { display: block; font-size: 16px; font-weight: 800; letter-spacing: -.012em; }
.cta .t b span {
  display: block; font-size: 11.6px; font-weight: 600; letter-spacing: 0;
  color: rgba(255,255,255,.88); margin-top: 1px;
}
.cta .t p { margin: 7px 0 0; font-size: 11.2px; line-height: 1.4; }
.cta .t p i { display: block; font-style: normal; color: rgba(255,255,255,.84); }
.cta .t .url {
  display: block; margin-top: 8px; font-family: "IBM Plex Mono", monospace;
  font-size: 10.6px; font-weight: 500;
}

.foot {
  position: absolute; left: 0.66in; right: 0.66in; bottom: 0.42in;
  display: flex; justify-content: space-between; align-items: center;
  border-top: 1px solid %(line)s; padding-top: 8px;
  font-size: 8.6px; font-weight: 600; letter-spacing: .13em; text-transform: uppercase;
  color: #a2969b;
}
.foot .mono { letter-spacing: .04em; text-transform: none; }

/* ---------------- page 1, the cover ----------------
   The pink field carries the identity and the promise; the white below it
   carries what the school actually does and the code that books it. The lower
   half centres itself between the fold and the paper's edge rather than being
   pinned at measured offsets, so nothing has to be re-measured when a line of
   the offer changes. */
.cover { background: %(pink)s; }
.swell { position: absolute; left: 0; top: 0; width: 100%%; height: 61%%; }
.cover .white {
  position: absolute; left: 0; right: 0; bottom: 0; height: 39%%; background: #fff;
}
.cover .glow {
  position: absolute; left: 0; right: 0; top: 12%%; height: 46%%;
  background: radial-gradient(ellipse 60%% 54%% at 50%% 50%%,
    rgba(244,110,149,.94) 0%%, rgba(244,110,149,.66) 46%%, rgba(244,110,149,0) 78%%);
}
.cover .crest {
  position: absolute; left: 0; right: 0; top: 1.14in; display: flex; justify-content: center;
}
.cover .crest span {
  width: 1.5in; height: 1.5in; background: #fff; border-radius: 25px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 14px 40px rgba(120, 30, 60, .22);
}
.cover .crest img { width: 78%%; height: 78%%; object-fit: contain; }

.cover .name {
  position: absolute; left: 0; right: 0; top: 3.04in; text-align: center; color: #fff;
}
.cover .name b {
  display: block; font-size: 60px; font-weight: 900; letter-spacing: .21em;
  text-indent: .21em; line-height: 1;
}
.cover .name .sub {
  display: block; margin-top: 15px; font-family: "IBM Plex Mono", monospace;
  font-size: 10.5px; font-weight: 500; letter-spacing: .34em; text-indent: .34em;
  color: rgba(255,255,255,.92);
}
.cover .name .est {
  display: block; margin-top: 10px; font-family: "IBM Plex Mono", monospace;
  font-size: 8.8px; letter-spacing: .26em; text-indent: .26em; color: rgba(255,255,255,.74);
}

.cover .tag {
  position: absolute; left: 0.86in; right: 0.86in; top: 5.02in; text-align: center; color: #fff;
}
.cover .tag b { display: block; font-size: 18px; font-weight: 700; line-height: 1.34; }
.cover .tag span {
  display: block; margin-top: 6px; font-size: 13px; font-weight: 500;
  line-height: 1.34; color: rgba(255,255,255,.85);
}

.cover .lower {
  position: absolute; left: 0.72in; right: 0.72in; top: 61%%; bottom: 0;
  padding-bottom: 0.5in;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 30px;
}
.cover .offer { text-align: center; }
.cover .offer .eyebrow { margin-bottom: 11px; }
.cover .offer p {
  margin: 0 0 6px; font-family: "IBM Plex Mono", monospace; font-size: 11px;
  font-weight: 500; letter-spacing: .075em; color: %(ink2)s;
}
.cover .offer p:last-child { margin-bottom: 0; }

.cover .book {
  display: flex; align-items: center; gap: 20px;
  border: 1px solid %(line)s; border-radius: 15px; padding: 15px 20px; background: %(ground)s;
}
.cover .book .qrwrap { background: #fff; border-radius: 9px; padding: 7px; flex: none; }
.cover .book .qr { width: 1.16in; height: 1.16in; display: block; }
.cover .book .t b {
  display: block; font-size: 13px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
}
.cover .book .t i {
  display: block; font-style: normal; font-size: 10.6px; font-weight: 600;
  letter-spacing: .09em; text-transform: uppercase; color: %(es)s; margin-top: 3px;
}
.cover .book .t u {
  display: block; text-decoration: none; margin-top: 9px;
  font-family: "IBM Plex Mono", monospace; font-size: 10.2px; color: %(pinkdeep)s;
}

/* ---------------- page 4 ---------------- */
.chips { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; list-style: none; padding: 0; margin: 0; }
.chips li {
  border: 1px solid %(line)s; border-left: 3px solid %(pink)s; border-radius: 0 9px 9px 0;
  padding: 8px 12px; background: %(ground)s;
}
.chips b { display: block; font-size: 11.4px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; }
.chips small { display: block; font-size: 9.8px; color: %(es)s; margin-top: 1px; }
.note {
  margin: 11px 0 0; font-size: 11.4px; color: %(ink2)s;
}
.note span { color: %(es)s; }

.know { list-style: none; padding: 0; margin: 0; }
.know li { display: flex; gap: 10px; align-items: flex-start; padding: 7px 0; }
.know li + li { border-top: 1px solid %(linesoft)s; }
.hexbul { width: 11px; height: 13px; flex: none; margin-top: 3px; }
.know b { display: block; font-size: 11.7px; font-weight: 600; line-height: 1.4; }
.know small { display: block; font-size: 10.4px; color: %(es)s; line-height: 1.4; margin-top: 1px; }

.bookbig {
  margin-top: 20px; background: %(pink)s; border-radius: 16px; padding: 20px 22px;
  display: flex; align-items: center; gap: 22px; color: #fff;
}
.bookbig .qrwrap { background: #fff; border-radius: 12px; padding: 9px; flex: none; }
.bookbig .qr { width: 1.62in; height: 1.62in; display: block; }
.bookbig .eyebrow { color: rgba(255,255,255,.82); margin-bottom: 9px; }
.bookbig h3 { font-size: 22px; font-weight: 800; letter-spacing: -.015em; margin: 0; line-height: 1.14; }
.bookbig h3 span { display: block; font-size: 13.5px; font-weight: 600; color: rgba(255,255,255,.86); margin-top: 2px; }
.bookbig p { margin: 10px 0 0; font-size: 11.6px; line-height: 1.45; color: rgba(255,255,255,.95); }
.bookbig p.es { font-size: 10.6px; color: rgba(255,255,255,.87); margin-top: 3px; }
.bookbig .url {
  display: block; margin-top: 13px; font-family: "IBM Plex Mono", monospace;
  font-size: 11.4px; font-weight: 500; word-break: break-all;
}
.bookbig .mail {
  display: block; margin-top: 9px; padding-top: 9px; border-top: 1px solid rgba(255,255,255,.3);
  font-size: 10.4px; color: rgba(255,255,255,.86);
}
.bookbig .mail b { font-family: "IBM Plex Mono", monospace; font-weight: 500; color: #fff; }
</style>
</head>
<body>

<!-- ============================ 1. cover ============================ -->
<section class="page cover">
  %(swell)s
  <div class="glow"></div>
  <div class="white"></div>
  <div class="crest"><span><img src="data:image/png;base64,%(logo)s" alt="Shokogi"></span></div>
  <div class="name">
    <b>%(wordmark)s</b>
    <span class="sub">%(sub_en)s · %(sub_es)s</span>
    <span class="est">%(eyebrow)s</span>
  </div>
  <div class="tag">
    <b>%(tagline_en)s</b>
    <span>%(tagline_es)s</span>
  </div>
  <div class="lower">
    <div class="offer">
      <p class="eyebrow">%(offer_eyebrow)s</p>
      %(offer)s
    </div>
    <div class="book">
      <div class="qrwrap">%(qr_small)s</div>
      <span class="t">
        <b>%(scan_en)s</b>
        <i>%(scan_es)s</i>
        <u>%(url_label)s</u>
      </span>
    </div>
  </div>
</section>

<!-- ====================== 2. lessons, 3. the rest ====================== -->
%(surf)s
%(more)s

<!-- ======================= 4. rentals and booking ======================= -->
<section class="page sheet">
  <div class="pad">
    <p class="eyebrow">%(r_eyebrow)s</p>
    <h2>%(r_title_en)s<span class="es">%(r_title_es)s</span></h2>
    <ul class="chips">%(rentals)s</ul>
    <p class="note">%(r_note_en)s <span>%(r_note_es)s</span></p>

    <p class="eyebrow" style="margin-top:26px">%(k_eyebrow)s</p>
    <ul class="know">%(know)s</ul>

    <div class="bookbig">
      <div class="qrwrap">%(qr_big)s</div>
      <div>
        <p class="eyebrow">%(b_eyebrow)s</p>
        <h3>%(b_title_en)s<span>%(b_title_es)s</span></h3>
        <p>%(b_body_en)s</p>
        <p class="es">%(b_body_es)s</p>
        <span class="url">%(url_label)s</span>
        <span class="mail">%(b_or_en)s · %(b_or_es)s <b>%(email)s</b></span>
      </div>
    </div>
  </div>
  %(foot)s
</section>

</body>
</html>
""" % {
        "fonts": fonts, "w": w, "h": h,
        "ink": INK, "ink2": INK_2, "es": ES, "pink": PINK, "pinkdeep": PINK_DEEP,
        "line": LINE, "linesoft": "#f0eaec", "ground": GROUND, "pinksoft": PINK_SOFT,
        "logo": logo, "swell": swell(),
        "wordmark": C.COVER["wordmark"], "sub_en": C.COVER["sub_en"],
        "sub_es": C.COVER["sub_es"], "eyebrow": C.COVER["eyebrow"],
        "tagline_en": C.COVER["tagline_en"], "tagline_es": C.COVER["tagline_es"],
        "scan_en": C.COVER["scan_en"], "scan_es": C.COVER["scan_es"],
        "offer_eyebrow": C.COVER["offer_eyebrow"],
        "offer": "".join("<p>%s</p>" % line for line in C.COVER["offer"]),
        "qr_small": qr_svg(C.BOOKING_URL, "1.16in"),
        "qr_big": qr_svg(C.BOOKING_URL, "1.62in"),
        "url_label": C.BOOKING_LABEL, "email": C.EMAIL,
        "surf": section_page(C.SURF), "more": section_page(C.MORE),
        "r_eyebrow": C.RENTALS["eyebrow"], "r_title_en": C.RENTALS["title_en"],
        "r_title_es": C.RENTALS["title_es"], "r_note_en": C.RENTALS["note_en"],
        "r_note_es": C.RENTALS["note_es"], "rentals": rentals,
        "k_eyebrow": C.KNOW["eyebrow"], "know": know,
        "b_eyebrow": C.BOOK["eyebrow"], "b_title_en": C.BOOK["title_en"],
        "b_title_es": C.BOOK["title_es"], "b_body_en": C.BOOK["body_en"],
        "b_body_es": C.BOOK["body_es"], "b_or_en": C.BOOK["or_en"],
        "b_or_es": C.BOOK["or_es"],
        "foot": footer(),
    }


def chrome():
    """Whichever Chromium this machine has. Playwright's copy comes first
    because that is the one the rest of the tests here already drive."""
    for p in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
              "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        if os.path.exists(p):
            return p
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("no chromium found: install one, or use --html and print by hand")


def render(html, out):
    tmp = tempfile.mkdtemp(prefix="shokogi-brochure-")
    src = os.path.join(tmp, "brochure.html")
    with open(src, "w") as f:
        f.write(html)
    subprocess.run(
        [chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
         "--virtual-time-budget=6000",
         "--print-to-pdf=" + os.path.abspath(out), "file://" + src],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=tmp,
    )
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", choices=sorted(SIZES), default="letter")
    ap.add_argument("--out", default=None, help="the PDF to write")
    ap.add_argument("--html", default=None, help="write the HTML here instead of a PDF")
    a = ap.parse_args()

    html = build(a.size)
    if a.html:
        with open(a.html, "w") as f:
            f.write(html)
        print("wrote %s" % a.html)
        return

    out = a.out or os.path.join(
        HERE, "shokogi-brochure%s.pdf" % ("" if a.size == "letter" else "-" + a.size))
    render(html, out)
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()
