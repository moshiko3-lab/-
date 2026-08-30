#!/usr/bin/env python3
"""Build the six-page brochure the school leaves in guest rooms.

    python3 print/build_brochure.py                     # -> print/shokogi-brochure.pdf
    python3 print/build_brochure.py --html out.html     # the pages, unrendered
    python3 print/build_brochure.py --size a4           # 210x297 instead of Letter

Laid out in HTML and printed by headless Chromium, the same engine the rest of
this repository is tested in, so what a browser shows and what the printer gets
are the same thing.

Three things are deliberately not fetched at build time. The fonts sit next to
this file already base64'd into `fonts.css`, because a brochure that renders in
Cormorant here and in Times on someone else's machine is not one design. The
logo is read out of `app/logo.png`, the same file the manager and the booking
page use, so the mark on paper cannot drift from the mark on screen. And the
pictures come from `print/images/` if they are there and from `art.py` if they
are not -- see `images/README.md`, because a photograph of this beach beats a
drawing of it every time.
"""

import argparse
import base64
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import art  # noqa: E402
import content as C  # noqa: E402
import quiver  # noqa: E402

# --------------------------------------------------------------------------
# The palette.
#
# The storefront's pink is still the brand and still the only colour on the
# page -- but a sheet that is mostly pink reads as a flyer, so here it is an
# accent on warm paper and deep ink rather than a field. The ink and the cream
# are what make it look like it cost something; the pink is what makes it
# Shokogi. `rose` is that pink darkened just enough to stay legible at 9px on
# cream, which the storefront pink is not.
# --------------------------------------------------------------------------
P = {
    # the water
    "sea": "#0F2C34", "sea2": "#17515E", "tube": "#0A2129",
    # the beach
    "paper": "#F6F1E7", "sand": "#E9DCC6", "rule": "#D9C9AE",
    # type on the beach, and on the water
    "ink": "#14262C", "ink2": "#45585F", "ink3": "#8A9AA0",
    "onink": "#F1EBE0", "onink2": "#A7BDC2", "onink3": "#6E888F",
    # the accents. The pink is the school's; the amber and the coral are the
    # hour it is worth surfing, and the reason the page stops reading as a
    # design studio's and starts reading as a surf shop's.
    "pink": "#F46E95", "rose": "#D24870",
    "amber": "#F2A03D", "coral": "#F4735C", "sun": "#EFA24E",
    # the quiver chart's two series
    "chart_a": "#0A8AA1", "chart_b": "#C93F68",
}

SIZES = {"letter": ("8.5in", "11in"), "a4": ("210mm", "297mm")}


# --------------------------------------------------------------------------
# Pictures
#
# Every picture on the page is a slot. A photograph in print/images/ wins; with
# none there the drawing fills it, so the brochure is always finished and never
# a grey box with "image here" in it. The two are interchangeable because both
# fill the same box the same way -- dropping a photo in changes no layout.
# --------------------------------------------------------------------------
SLOTS = {
    # no ground on the cover's wave: the striped sun is behind it and has to
    # show through everywhere the water is not
    "cover":  lambda: art.wave(1000, 640, deep=P["tube"], body=P["sea2"],
                               foam=P["paper"]),
    "place":  lambda: art.lineup(1200, 482, ink=P["ink"], line=P["rose"],
                                 ground=P["sand"]),
    "surf":   lambda: art.swell(1200, 560, seed=5, lines=13, stroke=P["pink"],
                                ground=P["sea2"], width=1.9, opacity=.95),
    # the same disc as the cover, but only its crown, coming up out of the
    # bottom of the band -- a different sight of the same sun rather than the
    # cover's picture used twice
    "beyond": lambda: art.stripes(1200, 300, ground=P["sand"],
                                  colours=(P["amber"], "#F4894C", P["coral"],
                                           P["pink"], P["rose"])),
    "camps":  lambda: art.swell(1200, 420, seed=17, lines=12, stroke=P["amber"],
                                ground=P["sea2"], width=1.9, opacity=.95),
    "boards": lambda: art.boards_row(1200, 300, stroke=P["ink"],
                                     ground=P["sand"], width=1.0),
    "shop":   lambda: art.stripes(1200, 260, ground=P["paper"],
                                  colours=(P["amber"], "#F4894C", P["coral"],
                                           P["pink"], P["rose"])),
    "back":   lambda: art.wave(1000, 640, deep=P["sea"], body="#153F4A",
                               foam="#295A65", spray="#295A65", rider=False,
                               ground=P["sea"]),
}
PHOTO_TYPES = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}


def photos():
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, "images", "*"))):
        slot, ext = os.path.splitext(os.path.basename(path))
        if slot in SLOTS and ext.lower() in PHOTO_TYPES:
            out.setdefault(slot, path)
    return out


def picture(slot, cls=""):
    path = photos().get(slot)
    if path:
        kind = PHOTO_TYPES[os.path.splitext(path)[1].lower()]
        data = base64.b64encode(open(path, "rb").read()).decode()
        return ('<img class="pic %s" src="data:image/%s;base64,%s" alt="">'
                % (cls, kind, data))
    return '<span class="pic %s">%s</span>' % (cls, SLOTS[slot]())


# --------------------------------------------------------------------------
# The QR code
#
# Error correction H, because this is going on paper in a room with a lamp in
# it: a fingerprint, a curled corner or a crease costs modules, and H can lose
# up to a third of them and still read. That headroom is also what pays for the
# hexagon in the middle -- it covers about a twentieth of the area, well inside
# what the level tolerates. test_brochure.py reads every code back off the
# rendered page rather than taking any of that on trust.
# --------------------------------------------------------------------------
def qr_svg(data, px, quiet=3, dark=None, light="#fff", mark=True):
    import segno

    dark = dark or P["ink"]
    m = [list(row) for row in segno.make(data, error="h").matrix]
    n = len(m)
    span = n + quiet * 2

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
        r, cx = span * 0.115, span / 2.0
        centre = ('<path d="%s" fill="%s"/><path d="%s" fill="%s"/>'
                  '<path d="%s" fill="%s"/>'
                  % (hexagon(cx, cx, r * 1.32), light,
                     hexagon(cx, cx, r), P["pink"],
                     hexagon(cx, cx, r * 0.5), light))

    return ('<svg class="qr" width="%s" height="%s" viewBox="0 0 %d %d" '
            'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg" '
            'role="img" aria-label="Booking page QR code">'
            '<rect width="%d" height="%d" fill="%s"/><path d="%s" fill="%s"/>%s</svg>'
            % (px, px, span, span, span, span, light, "".join(d), dark, centre))


def hexagon(cx, cy, r):
    """The logo's hexagon: flat left and right sides, points top and bottom."""
    w = r * 0.866
    return "M%.3f %.3fL%.3f %.3fL%.3f %.3fL%.3f %.3fL%.3f %.3fL%.3f %.3fZ" % (
        cx, cy - r, cx + w, cy - r / 2, cx + w, cy + r / 2,
        cx, cy + r, cx - w, cy + r / 2, cx - w, cy - r / 2)


# --------------------------------------------------------------------------
# Small parts
# --------------------------------------------------------------------------
def folio(i, style=""):
    label = C.FOLIO[i]
    if not label:
        return ""
    return ('<footer class="folio" style="%s"><span>%s</span>'
            '<span class="n">%02d</span></footer>' % (style, label, i + 1))


def display(text, cls=""):
    return '<h2 class="display %s">%s</h2>' % (cls, text.replace("\n", "<br>"))


def rule():
    return '<span class="hr"></span>'


PAGE_PX = {"letter": (816, 1056), "a4": (794, 1123)}
_SIZE = ["letter"]


def screen(colour, opacity):
    """The dot screen a page wears over its flat colour."""
    w, h = PAGE_PX[_SIZE[0]]
    return art.halftone(w, h, colour=colour, opacity=opacity)


CSS = Template("""
$fonts

@page { size: $w $h; margin: 0; }

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: Figtree, -apple-system, "Segoe UI", system-ui, sans-serif;
  color: $ink; background: #4b5a60;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
  -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
}

/* One .page is one sheet. Fixed to the paper and clipped, so a stray line of
   type can never push a seventh sheet out of the printer. */
.page {
  width: $w; height: $h; position: relative; overflow: hidden;
  background: $paper; page-break-after: always; break-after: page;
}
.page:last-child { page-break-after: auto; break-after: auto; }
.page.sea  { background: $sea;  color: $onink; }
.page.sand { background: $sand; }
@media screen { .page { margin: 24px auto; box-shadow: 0 10px 50px rgba(0,0,0,.5); } }

/* Ink lives inside the frame; only pictures and colour reach the paper's edge,
   so a printer that cannot go borderless loses trim and never a word. */
.frame { position: absolute; left: $m; right: $m; top: $mt; bottom: $mb; }
.band { position: absolute; left: 0; right: 0; overflow: hidden; }
.pic { display: block; width: 100%; height: 100%; overflow: hidden; }
img.pic { object-fit: cover; }
.pic svg { display: block; width: 100%; height: 100%; }

/* ---------------------------------------------------------------- type ---
   Archivo carries a width axis, and the display sizes run wide: set broad and
   heavy it holds a page the way a surf brand's type does, where a fine serif
   at the same size reads as a hotel. Figtree, the storefront's own sans, still
   does the reading. */
.d {
  font-family: Archivo, "Helvetica Neue", Arial, sans-serif;
  font-variation-settings: "wdth" 118, "wght" 800;
  text-transform: uppercase; letter-spacing: -.004em; line-height: .94;
  margin: 0; color: inherit;
}
h2.d { font-size: 44px; }
h2.d.big { font-size: 54px; }
.d.sub {
  font-variation-settings: "wdth" 108, "wght" 500;
  text-transform: none; font-size: 20px; line-height: 1.12; letter-spacing: 0;
  color: $ink3; margin-top: 10px;
}
.sea .d.sub { color: $onink3; }

.eyebrow {
  font-family: "IBM Plex Mono", ui-monospace, monospace; font-weight: 500;
  font-size: 8.6px; letter-spacing: .215em; text-transform: uppercase;
  color: $rose; margin: 0;
}
.sea .eyebrow { color: $pink; }
.meta {
  font-family: "IBM Plex Mono", ui-monospace, monospace; font-weight: 400;
  font-size: 8.4px; letter-spacing: .18em; text-transform: uppercase;
  color: $ink3; margin: 0;
}
.sea .meta { color: $onink3; }

/* the rule is four stripes now, not one bar: the same 1972 idea shrunk to
   the size of a divider */
.hr {
  display: block; width: 62px; height: 9px; margin: 18px 0;
  background: linear-gradient(to bottom,
    $amber 0 2.4px, transparent 2.4px 3.6px,
    $coral 3.6px 5.6px, transparent 5.6px 6.6px,
    $pink 6.6px 8.2px, transparent 8.2px 9px);
}

p.en { font-size: 11.4px; line-height: 1.62; color: $ink2; margin: 0; }
p.es { font-size: 11px; line-height: 1.6; color: $ink3; margin: 0; }
.sea p.en { color: $onink2; }
.sea p.es { color: $onink3; }
p.en + p.en, p.es + p.es { margin-top: 11px; }

.folio {
  position: absolute; left: $m; right: $m; bottom: 0.44in;
  display: flex; justify-content: space-between; align-items: baseline;
  border-top: 1px solid $rule; padding-top: 7px;
  font-family: "IBM Plex Mono", monospace; font-size: 8px; letter-spacing: .19em;
  text-transform: uppercase; color: $ink3;
}
.sea .folio { border-color: rgba(241,235,224,.20); color: $onink3; }
.folio .n { color: $rose; letter-spacing: .1em; }
.sea .folio .n { color: $pink; }

/* ---------------------------------------------------------------- cover ---
   Three layers, back to front: the striped sun, the water, the name. The sun
   is the oldest thing in surf print and the reason this page stops looking
   like a brochure and starts looking like something off a shop wall. */
.cover .sunband { position: absolute; left: 0; right: 0; top: 0.42in; height: 6.1in; }
.cover .band { left: 0; right: 0; bottom: 0; height: 4.35in; }
/* the dot screen, over the flat colour on every page that has any. Without
   a width and a height an inline <svg> is 300x150 and the screen covers one
   corner of the sheet, which is exactly what it did the first time. */
.screen { position: absolute; inset: 0; width: 100%; height: 100%; }
.cover .top {
  position: absolute; left: $m; right: $m; top: 0.62in;
  display: flex; align-items: center; justify-content: space-between;
}
.cover .top img { width: 0.62in; height: 0.62in; object-fit: contain; }
.cover .lockup { position: absolute; left: $m; right: $m; top: 5.62in; }
.cover .lockup b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 122, "wght" 800;
  font-size: 96px; line-height: .86; letter-spacing: -.016em;
  text-transform: uppercase; color: $paper;
}
.cover .lockup .sub { margin-top: 4px; color: $onink2; letter-spacing: .26em; font-size: 9.4px; }
.cover .lockup .where { margin-top: 9px; color: $onink2; letter-spacing: .2em; font-size: 8.4px; }
.cover .patch { position: absolute; right: 0.66in; bottom: 0.62in; width: 1.34in; }
.cover .patch svg { display: block; width: 100%; transform: rotate(-9deg); }

/* -------------------------------------------------------------- opening --- */
.opening .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0.42in; margin-top: 26px; }
.opening .band { top: 5.78in; height: 3.42in; }
/* the patch goes on the water, not over the words: it overlapped the Spanish
   column the first time and made a paragraph unreadable */
.opening .patch {
  position: absolute; right: 0.74in; top: 7.82in; width: 1.28in;
}
.opening .patch svg { display: block; width: 100%; transform: rotate(7deg); }
.opening .facts {
  position: absolute; left: $m; right: $m; bottom: 0.98in;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  border-top: 2px solid $ink; padding-top: 12px;
}
.opening .facts div + div { border-left: 1px solid $rule; padding-left: 16px; }
.opening .facts div { padding-right: 16px; }
.opening .facts b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 104, "wght" 700;
  font-size: 11px; letter-spacing: .04em; text-transform: uppercase;
}
.opening .facts small {
  display: block; margin-top: 3px; font-family: "IBM Plex Mono", monospace;
  font-size: 7.6px; letter-spacing: .15em; color: $ink3;
}

/* ----------------------------------------------------------------- list --- */
.rows { display: grid; }
.rows.two { grid-template-columns: 1fr 1fr; column-gap: 0.42in; }
.row { border-top: 1px solid $rule; padding: 13px 0 15px; display: flex; gap: 12px; }
.sea .row { border-color: rgba(241,235,224,.20); }
.row .n {
  font-family: "IBM Plex Mono", monospace; font-size: 8.4px; letter-spacing: .1em;
  color: $rose; padding-top: 4px; flex: none;
}
.sea .row .n { color: $pink; }
.row h3 {
  margin: 0; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 106, "wght" 700;
  font-size: 13px; letter-spacing: .015em; text-transform: uppercase; color: inherit;
}
.row h3 small {
  display: block; font-family: "IBM Plex Mono", monospace; font-weight: 400;
  font-size: 8.2px; letter-spacing: .15em; color: $ink3; margin-top: 4px;
}
.sea .row h3 small { color: $onink3; }
.row p { margin: 8px 0 0; }
.row p.en { font-size: 11px; line-height: 1.55; }
.row p.es { font-size: 10.3px; line-height: 1.52; margin-top: 5px; }

/* --------------------------------------------------------------- beyond --- */
.beyond .band { top: 0; height: 2.72in; }
.beyond .row { padding: 10px 0 11px; }
.beyond .row p.en { font-size: 10.5px; }
.beyond .row p.es { font-size: 9.9px; }

.bookline {
  border-top: 2px solid $ink; margin-top: 16px; padding-top: 15px;
  display: flex; align-items: center; gap: 17px;
}
.bookline .qr { width: 1.06in; height: 1.06in; display: block; flex: none; }
.bookline b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 108, "wght" 700;
  font-size: 15px; text-transform: uppercase; letter-spacing: .01em;
}
.bookline i { display: block; font-style: normal; font-size: 11px; color: $ink3; margin-top: 3px; }
.bookline .url {
  display: block; margin-top: 10px; font-family: "IBM Plex Mono", monospace;
  font-size: 10px; letter-spacing: .04em; color: $rose;
}

/* ---------------------------------------------------------------- guide ---
   The strip a surf brand puts in front of its wetsuits: four states a reader
   might be in, and the one product that answers each. */
.guide {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0 0.28in;
  border-top: 2px solid $onink; padding-top: 13px; margin-top: 20px;
}
.sea .guide { border-color: $onink; }
.guide div + div { border-left: 1px solid rgba(241,235,224,.22); padding-left: 0.2in; }
.guide b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 104, "wght" 700;
  font-size: 10.5px; letter-spacing: .035em; text-transform: uppercase;
}
.guide small {
  display: block; font-family: "IBM Plex Mono", monospace; font-size: 7.4px;
  letter-spacing: .13em; color: $onink3; margin-top: 3px;
}
.guide p { margin: 8px 0 0; font-size: 10.2px; line-height: 1.45; color: $onink2; }
.guide p i { display: block; font-style: normal; color: $onink3; font-size: 9.6px; margin-top: 3px; }

/* ---------------------------------------------------------------- camps ---
   Four durations, each led by its own number, because a number is what the
   reader is actually choosing between. */
.camps .band { top: 0; height: 2.82in; }
.camps .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 0.44in; }
.camps .cell { border-top: 1px solid $rule; padding: 15px 0 17px; }
.camps .num {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 112, "wght" 800;
  font-size: 31px; line-height: 1; letter-spacing: -.02em; color: $rose;
}
.camps .num em { font-style: normal; font-size: 15px; color: $ink3; margin-left: 6px; }
.camps h3 {
  margin: 9px 0 0; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 106, "wght" 700;
  font-size: 13px; letter-spacing: .015em; text-transform: uppercase;
}
.camps h3 small {
  display: block; font-family: "IBM Plex Mono", monospace; font-weight: 400;
  font-size: 8.2px; letter-spacing: .15em; color: $ink3; margin-top: 4px;
}
.camps p { margin: 8px 0 0; }

/* ----------------------------------------------------------------- shop --- */
.shop .band { top: 0; height: 1.82in; }
.shop .blocks { margin-top: 22px; }
.shop .blk { border-top: 2px solid $ink; padding: 13px 0 16px; }
.shop .blk + .blk { border-top-width: 1px; border-color: $rule; }
.shop .blk b {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 110, "wght" 800;
  font-size: 16px; letter-spacing: .01em; text-transform: uppercase;
}
.shop .blk b em { font-style: normal; color: $ink3; font-size: 11px; margin-left: 9px;
  font-variation-settings: "wdth" 104, "wght" 500; }
.shop .blk span {
  display: block; margin-top: 9px; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 100, "wght" 600;
  font-size: 11.4px; letter-spacing: .05em; line-height: 1.72; color: $ink2;
}

/* --------------------------------------------------------------- quiver --- */
.rentals .band { top: 0; height: 1.78in; }
.stats {
  display: grid; grid-template-columns: repeat(3, 1fr);
  border-top: 2px solid $ink; margin-top: 16px; padding-top: 11px;
}
.stats div + div { border-left: 1px solid $rule; padding-left: 0.24in; }
.stats b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 116, "wght" 800;
  font-size: 30px; line-height: 1; letter-spacing: -.015em;
}
.stats small {
  display: block; margin-top: 5px; font-family: "IBM Plex Mono", monospace;
  font-size: 7.8px; letter-spacing: .17em; text-transform: uppercase; color: $ink3;
}
.chart { margin-top: 15px; background: $paper; padding: 13px 16px 7px; }
.chart .pic { height: 1.58in; }
.chart figcaption {
  margin-top: 4px; font-size: 9.4px; line-height: 1.5; color: $ink2;
  display: flex; gap: 10px; flex-wrap: wrap;
}
.chart figcaption i { font-style: normal; color: $ink3; }
.racks { border-top: 1px solid $rule; margin-top: 16px; padding-top: 11px; }
.racks b {
  font-family: "IBM Plex Mono", monospace; font-size: 8.2px; letter-spacing: .17em;
  text-transform: uppercase; color: $rose;
}
.racks span {
  display: block; margin-top: 7px; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 100, "wght" 600;
  font-size: 10.6px; letter-spacing: .055em; line-height: 1.7; color: $ink;
}
.chips {
  display: grid; grid-template-columns: 1fr 1fr; column-gap: 0.42in;
  margin: 0; padding: 0; list-style: none;
}
.chips li {
  border-top: 1px solid $rule; padding: 8px 0 9px;
  display: flex; align-items: baseline; gap: 10px;
}
.chips b {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 106, "wght" 700;
  font-size: 12.5px; letter-spacing: .015em; text-transform: uppercase;
}
.chips small {
  font-family: "IBM Plex Mono", monospace; font-size: 8.6px; letter-spacing: .1em;
  color: $ink3; margin-left: auto;
}

/* the two things left to say, on the back where they are read last */
.know { background: $paper; color: $ink; padding: 18px 22px 16px; text-align: left; }
.know ul { list-style: none; margin: 10px 0 0; padding: 0; }
.know li { display: flex; gap: 10px; padding: 6px 0; }
.know li + li { border-top: 1px solid $rule; }
.know .hex { width: 9px; height: 11px; flex: none; margin-top: 4px; }
.know b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 100, "wght" 600;
  font-size: 10.6px; line-height: 1.42;
}
.know small { display: block; font-size: 9.6px; color: $ink3; line-height: 1.45; margin-top: 2px; }
.know figure {
  margin: 12px 0 0; padding-top: 12px; border-top: 1px solid $rule;
  display: flex; align-items: center; gap: 16px;
}
.know figure .pic { width: 2.5in; height: 0.5in; flex: none; }
.know figcaption { font-size: 9px; line-height: 1.45; color: $ink2; }
.know figcaption i { display: block; font-style: normal; color: $ink3; margin-top: 2px; }

/* ----------------------------------------------------------------- back --- */
.back .band { left: 0; right: 0; bottom: 0; height: 4.0in; }
.back .inner {
  position: absolute; left: $m; right: $m; top: 0.86in;
  display: flex; flex-direction: column; align-items: center; text-align: center;
}
.back .inner img { width: 0.78in; height: 0.78in; object-fit: contain; }
.back .d { margin-top: 20px; font-size: 46px; }
.back .say { max-width: 3.6in; margin: 13px 0 0; font-size: 11px; line-height: 1.6; color: $onink2; }
.back .say i { display: block; font-style: normal; color: $onink3; font-size: 10.2px; margin-top: 5px; }
.back .know { margin-top: 22px; width: 4.5in; }
.back .qrcard { margin-top: 20px; background: $paper; padding: 13px; }
.back .qrcard .qr { width: 1.62in; height: 1.62in; display: block; }
.back .url {
  margin-top: 18px; font-family: "IBM Plex Mono", monospace; font-size: 10.4px;
  letter-spacing: .06em; color: $onink;
}
.back .mail { margin-top: 8px; font-size: 10px; color: $onink2; }
.back .mail b { font-family: "IBM Plex Mono", monospace; font-weight: 400; color: $onink; }
.back .stamp {
  position: absolute; left: $m; right: $m; bottom: 0.56in; text-align: center; color: $onink3;
}
""")


def build(size="letter"):
    w, h = SIZES[size]
    fonts = open(os.path.join(HERE, "fonts.css")).read()
    raw = base64.b64encode(open(os.path.join(ROOT, "app", "logo.png"), "rb").read()).decode()
    logo = '<img src="data:image/png;base64,%s" alt="Shokogi">' % raw

    _SIZE[0] = size
    css = CSS.substitute(fonts=fonts, w=w, h=h, m="0.72in", mt="0.72in", mb="0.72in", **P)
    pages = [cover_page(logo), opening_page(), surf_page(), camps_page(),
             beyond_page(), rentals_page(), shop_page(), back_page(logo)]
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<title>Shokogi &middot; Brochure</title>\n<style>%s</style>\n</head>\n'
            '<body>\n%s\n</body>\n</html>\n' % (css, "\n".join(pages)))


def cover_page(logo):
    c = C.COVER
    return """
<section class="page sea cover">
  <div class="sunband">%s</div>
  <div class="band">%s</div>
  %s
  <div class="top">
    %s
    <p class="meta">%s</p>
  </div>
  <div class="lockup">
    <b>%s</b>
    <span class="hr"></span>
    <p class="meta sub">%s &nbsp;·&nbsp; %s</p>
    <p class="meta where">%s &nbsp;·&nbsp; %s</p>
  </div>
  <div class="patch">%s</div>
</section>""" % (
        art.sunset(1000, 780, ground=None,
                   colours=(P["amber"], "#F4894C", P["coral"], P["pink"], P["rose"])),
        picture("cover"), screen(P["paper"], .13),
        logo, c["est"], c["wordmark"],
        c["rule_en"], c["rule_es"], c["place"], c["coords"],
        art.stamp(120, c["patch_top"], c["patch_bottom"], P["paper"],
                  mark='<path d="%s" fill="%s"/>' % (hexagon(0, 0, 26), P["pink"])))


def opening_page():
    o = C.OPENING
    facts = "".join('<div><b>%s</b><small>%s</small></div>' % f for f in o["facts"])
    return """
<section class="page opening">
  <div class="frame" style="bottom:auto">
    <p class="eyebrow">%s</p>
    <h2 class="d big" style="margin-top:14px">%s</h2>
    <p class="d sub">%s</p>
    <div class="cols">
      <div>%s</div>
      <div>%s</div>
    </div>
  </div>
  <div class="band">%s</div>
  <div class="patch">%s</div>
  <div class="facts">%s</div>
  %s
</section>""" % (
        o["eyebrow"], o["display_en"].replace("\n", "<br>"),
        o["display_es"].replace("\n", " "),
        "".join('<p class="en">%s</p>' % t for t in o["body_en"]),
        "".join('<p class="es">%s</p>' % t for t in o["body_es"]),
        picture("place"),
        art.stamp(120, C.COVER["patch2_top"], C.COVER["patch2_bottom"], P["ink"],
                  id_="st2",
                  mark='<text text-anchor="middle" y="13" font-family="Archivo" '
                       'font-size="38" font-weight="800" fill="%s">09</text>' % P["ink"]),
        facts, folio(1))


def _rows(items, start=1):
    return "".join(
        '<article class="row"><span class="n">%02d</span><div>'
        '<h3>%s<small>%s</small></h3>'
        '<p class="en">%s</p><p class="es">%s</p></div></article>'
        % (i + start, en, es, ben, bes)
        for i, (en, es, ben, bes) in enumerate(items))


def surf_page():
    s, g = C.SURF, C.START
    guide = "".join('<div><b>%s</b><small>%s</small><p>%s<i>%s</i></p></div>' % it
                    for it in g["items"])
    return """
<section class="page sea surf">
  <div class="band" style="top:0;height:3.36in">%s</div>
  <div class="frame" style="top:3.92in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:14px">%s</h2>
    <p class="d sub">%s</p>
    <p class="eyebrow" style="margin-top:24px">%s</p>
    <div class="guide">%s</div>
    <div class="rows two" style="margin-top:26px">%s</div>
  </div>
  %s
</section>""" % (picture("surf"), s["eyebrow"], s["title_en"], s["title_es"],
                 g["eyebrow"], guide, _rows(s["items"]), folio(2))


def camps_page():
    c = C.CAMPS
    cells = "".join(
        '<div class="cell"><p class="num">%s<em>%s</em></p>'
        '<h3>%s<small>%s</small></h3>'
        '<p class="en">%s</p><p class="es">%s</p></div>'
        % (num, unit, en, es, ben, bes)
        for en, es, num, unit, ben, bes in c["groups"])
    return """
<section class="page sea camps">
  <div class="band">%s</div>
  <div class="frame" style="top:3.38in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:14px">%s</h2>
    <p class="d sub">%s</p>
    <p class="en" style="margin-top:16px;max-width:5.2in">%s</p>
    <p class="es" style="margin-top:5px;max-width:5.2in">%s</p>
    <div class="grid" style="margin-top:24px">%s</div>
    <p class="meta" style="margin-top:16px;max-width:6in">%s</p>
    <p class="meta" style="margin-top:4px;max-width:6in">%s</p>
  </div>
  %s
</section>""" % (picture("camps"), c["eyebrow"], c["title_en"], c["title_es"],
                 c["lede_en"], c["lede_es"], cells,
                 c["note_en"], c["note_es"], folio(3))


def shop_page():
    h = C.SHOP
    blocks = "".join('<div class="blk"><b>%s<em>%s</em></b><span>%s</span></div>' % b
                     for b in h["blocks"])
    return """
<section class="page shop">
  <div class="band">%s</div>
  <div class="frame" style="top:2.42in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:14px">%s</h2>
    <p class="d sub">%s</p>
    <p class="en" style="margin-top:15px;max-width:5.6in">%s</p>
    <p class="es" style="margin-top:5px;max-width:5.6in">%s</p>
    <div class="blocks">%s</div>
    <p class="meta" style="margin-top:15px;color:%s;max-width:6in">%s</p>
    <p class="meta" style="margin-top:4px;max-width:6in">%s</p>
    <div class="bookline">
      %s
      <div>
        <b>%s</b><i>%s</i>
        <span class="url">%s</span>
      </div>
    </div>
  </div>
  %s
</section>""" % (picture("shop"), h["eyebrow"], h["title_en"], h["title_es"],
                 h["lede_en"], h["lede_es"], blocks,
                 P["ink2"], h["note_en"], h["note_es"],
                 qr_svg(C.BOOKING_URL, "1.06in", quiet=2, light=P["paper"]),
                 h["cta_en"], h["cta_es"], C.BOOKING_LABEL,
                 folio(6))


def beyond_page():
    b = C.BEYOND
    return """
<section class="page beyond">
  <div class="band">%s</div>
  <div class="frame" style="top:3.28in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:14px">%s</h2>
    <p class="d sub">%s</p>
    <div class="rows two" style="margin-top:22px">%s</div>
    <div class="bookline">
      %s
      <div>
        <b>%s</b><i>%s</i>
        <span class="url">%s</span>
      </div>
    </div>
  </div>
  %s
</section>""" % (picture("beyond"), b["eyebrow"],
                 b["title_en"].replace("\n", " "), b["title_es"],
                 _rows(b["items"]),
                 qr_svg(C.BOOKING_URL, "1.06in", quiet=2, light=P["paper"]),
                 C.BOOK["inline_en"], C.BOOK["inline_es"], C.BOOKING_LABEL, folio(4))


def rentals_page():
    r = C.RENTALS
    q = quiver.read()
    chips = "".join('<li><b>%s</b><small>%s</small></li>' % it for it in r["items"])
    stats = "".join('<div><b>%s</b><small>%s · %s</small></div>' % st for st in (
        (q["total"], r["stat_boards"][0], r["stat_boards"][1]),
        ("%s–%s" % (q["shortest"], q["longest"]), r["stat_range"][0], r["stat_range"][1]),
        (len(q["shapers"]), r["stat_shapers"][0], r["stat_shapers"][1])))
    return """
<section class="page sand rentals">
  <div class="band">%s</div>
  <div class="frame" style="top:2.34in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:14px">%s</h2>
    <p class="d sub">%s</p>
    <p class="en" style="margin-top:14px;max-width:5.4in">%s</p>
    <p class="es" style="margin-top:5px;max-width:5.4in">%s</p>
    <div class="stats">%s</div>
    <figure class="chart">
      <span class="pic">%s</span>
      <figcaption><span>%s</span><i>%s</i></figcaption>
    </figure>
    <div class="racks"><b>%s &nbsp;·&nbsp; %s</b><span>%s</span></div>
    <ul class="chips" style="margin-top:18px">%s</ul>
    <p class="meta" style="margin-top:12px;color:%s">%s &nbsp;·&nbsp; %s</p>
  </div>
  %s
</section>""" % (
        picture("boards"),
        r["eyebrow"], r["title_en"], r["title_es"],
        r["lede_en"], r["lede_es"], stats,
        art.quiver_chart(980, 248, q["rows"], hard_c=P["chart_a"], soft_c=P["chart_b"],
                         ink=P["ink"], muted=P["ink3"], surface=P["paper"],
                         labels=r["legend"]),
        r["chart_en"], r["chart_es"],
        r["racks_en"], r["racks_es"], " · ".join(q["shapers"]),
        chips, P["ink2"], r["note_en"], r["note_es"], folio(4))


def back_page(logo):
    b, k = C.BOOK, C.KNOW
    hexb = ('<svg class="hex" viewBox="0 0 10 12" aria-hidden="true">'
            '<path d="%s" fill="%s"/></svg>' % (hexagon(5, 6, 5), P["pink"]))
    know = "".join('<li>%s<div><b>%s</b><small>%s</small></div></li>' % (hexb, en, es)
                   for en, es in k["items"])
    return """
<section class="page sea back">
  <div class="band">%s</div>
  %s
  <div class="inner">
    %s
    <h2 class="d">%s</h2>
    <p class="say">%s<i>%s</i></p>
    <div class="know">
      <p class="eyebrow">%s</p>
      <ul>%s</ul>
      <figure>%s<figcaption>%s<i>%s</i></figcaption></figure>
    </div>
    <div class="qrcard">%s</div>
    <p class="url">%s</p>
    <p class="mail">%s · %s &nbsp; <b>%s</b></p>
  </div>
  <p class="meta stamp">%s &nbsp;·&nbsp; %s &nbsp;·&nbsp; %s</p>
</section>""" % (
        picture("back"), screen(P["paper"], .10),
        logo, b["title_en"], b["body_en"], b["body_es"],
        k["eyebrow"], know,
        '<span class="pic">%s</span>' % art.tide(420, 84, stroke=P["rose"],
                                                 ground=P["paper"], width=1.0),
        k["tide_caption_en"], k["tide_caption_es"],
        qr_svg(C.BOOKING_URL, "1.62in"), C.BOOKING_LABEL,
        b["or_en"], b["or_es"], C.EMAIL,
        C.COVER["wordmark"], C.COVER["place"], C.COVER["est"])


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
         "--virtual-time-budget=12000",
         "--print-to-pdf=" + os.path.abspath(out), "file://" + src],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=tmp)
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
    have = sorted(photos())
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))
    print("photographs: %s" % (", ".join(have) if have else
                               "none yet -- every picture is drawn (see images/README.md)"))


if __name__ == "__main__":
    main()
