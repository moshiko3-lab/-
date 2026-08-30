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
    "ink": "#14100E", "ink2": "#4A413A", "ink3": "#8B7F74",
    "paper": "#F7F2EA", "sand": "#EBE1D3", "rule": "#DED3C4",
    "pink": "#F46E95", "rose": "#C9436B",
    "onink": "#EFE7DA", "onink2": "#B3A697", "onink3": "#7C7167",
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
    "cover":  lambda: art.contours(850, 1100, seed=11, lines=34, stroke=P["pink"],
                                   ground=P["ink"], width=.75, opacity=.78,
                                   grid=(110, 140)),
    "coast":  lambda: art.contours(560, 900, seed=29, lines=30, stroke=P["rose"],
                                   ground=P["paper"], width=.65, opacity=.85,
                                   grid=(100, 150)),
    "surf":   lambda: art.swell(1200, 420, seed=5, lines=18, stroke=P["pink"],
                                ground=P["ink"], width=1.0, opacity=.9),
    "beyond": lambda: art.contours(520, 980, seed=91, lines=26, stroke=P["rose"],
                                   ground=P["sand"], width=.7, opacity=.9,
                                   grid=(80, 150)),
    "boards": lambda: art.boards_row(1200, 300, stroke=P["rose"],
                                     ground=P["sand"], width=.95),
    "back":   lambda: art.contours(850, 1100, seed=63, lines=30, stroke=P["pink"],
                                   ground=P["ink"], width=.7, opacity=.62,
                                   grid=(110, 140)),
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


CSS = Template("""
$fonts

@page { size: $w $h; margin: 0; }

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: Figtree, -apple-system, "Segoe UI", system-ui, sans-serif;
  color: $ink; background: #6b6259;
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
.page.dark { background: $ink; color: $onink; }
@media screen { .page { margin: 24px auto; box-shadow: 0 10px 50px rgba(0,0,0,.5); } }

/* Ink lives inside the frame; only pictures and colour reach the paper's edge,
   so a printer that cannot go borderless loses trim and never a word. */
.frame { position: absolute; left: $m; right: $m; top: $mt; bottom: $mb; }

.pic { display: block; width: 100%; height: 100%; overflow: hidden; }
img.pic { object-fit: cover; }
.pic svg { display: block; width: 100%; height: 100%; }
.band { position: absolute; left: 0; right: 0; overflow: hidden; }

/* ---------------------------------------------------------------- type --- */
.eyebrow {
  font-family: "IBM Plex Mono", ui-monospace, monospace; font-weight: 500;
  font-size: 8.6px; letter-spacing: .215em; text-transform: uppercase;
  color: $rose; margin: 0;
}
.dark .eyebrow { color: $pink; }
.meta {
  font-family: "IBM Plex Mono", ui-monospace, monospace; font-weight: 400;
  font-size: 8.4px; letter-spacing: .18em; text-transform: uppercase;
  color: $ink3; margin: 0;
}
.dark .meta { color: $onink3; }

.display {
  font-family: "Cormorant Garamond", Georgia, serif; font-weight: 300;
  font-size: 45px; line-height: 1.06; letter-spacing: .004em;
  margin: 14px 0 0; color: $ink;
}
.dark .display { color: $onink; }
.display.es {
  font-style: italic; font-size: 24px; line-height: 1.14; color: $ink3;
  margin-top: 9px; letter-spacing: .01em;
}
.dark .display.es { color: $onink2; }
.display.sm { font-size: 38px; }

.hr { display: block; width: 34px; height: 1px; background: $pink; margin: 20px 0; }

p.en { font-size: 11.4px; line-height: 1.62; color: $ink2; margin: 0; font-weight: 400; }
p.es { font-size: 10.5px; line-height: 1.6; color: $ink3; margin: 7px 0 0; }
p.en + p.en, p.es + p.es { margin-top: 11px; }

/* --------------------------------------------------------------- folio --- */
.folio {
  position: absolute; left: $m; right: $m; bottom: 0.44in;
  display: flex; justify-content: space-between; align-items: baseline;
  border-top: 1px solid $rule; padding-top: 7px;
  font-family: "IBM Plex Mono", monospace; font-size: 8px; letter-spacing: .19em;
  text-transform: uppercase; color: $ink3;
}
.folio .n { color: $rose; letter-spacing: .1em; }

/* ---------------------------------------------------------------- cover --- */
.cover .band { top: 0; bottom: 0; }
.cover .veil {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(20,16,14,.88) 0%, rgba(20,16,14,.40) 40%,
              rgba(20,16,14,.58) 70%, rgba(20,16,14,.94) 100%);
}
/* Mark, name and rule are one lockup, sitting a little above centre where the
   eye lands first, with the field open above and below it. */
.cover .lockup {
  position: absolute; left: $m; right: $m; top: 3.05in; text-align: center;
}
.cover .lockup img { width: 1.16in; height: 1.16in; object-fit: contain; }
.cover .lockup b {
  display: block; margin-top: 40px; font-family: "Cormorant Garamond", Georgia, serif;
  font-weight: 300; font-size: 64px; line-height: 1; letter-spacing: .30em;
  text-indent: .30em; color: $onink;
}
.cover .lockup .line {
  display: block; width: 46px; height: 1px; background: $pink; margin: 26px auto;
}
.cover .lockup .sub { color: $onink2; letter-spacing: .32em; font-size: 9px; }
.cover .foot {
  position: absolute; left: $m; right: $m; bottom: 0.84in;
  display: flex; justify-content: space-between; color: $onink3;
}

/* -------------------------------------------------------------- opening --- */
/* The picture runs off three edges of the sheet and the type keeps to its own
   column: the whitespace between them is the layout, not a gap left over. */
.opening .col-pic { position: absolute; right: 0; top: 0; bottom: 0; width: 3.02in; }
.opening .frame { right: 3.48in; display: flex; flex-direction: column; }
.opening .facts { margin-top: auto; border-top: 1px solid $rule; padding-top: 15px; }
.opening .facts div { padding: 9px 0; }
.opening .facts div + div { border-top: 1px solid $rule; }
.opening .facts small {
  display: block; margin-top: 4px; font-family: "IBM Plex Mono", monospace;
  font-size: 7.6px; letter-spacing: .16em; color: $ink3; opacity: .74;
}

/* ----------------------------------------------------------------- list --- */
.rows { display: grid; gap: 0; }
.rows.two { grid-template-columns: 1fr 1fr; column-gap: 0.44in; }
.row { border-top: 1px solid $rule; padding: 13px 0 15px; display: flex; gap: 13px; }
.row .n {
  font-family: "IBM Plex Mono", monospace; font-size: 8.4px; letter-spacing: .1em;
  color: $pink; padding-top: 3px; flex: none;
}
.row h3 {
  margin: 0; font-size: 11.4px; font-weight: 700; letter-spacing: .105em;
  text-transform: uppercase; color: $ink;
}
.row h3 small {
  display: block; font-family: "IBM Plex Mono", monospace; font-weight: 400;
  font-size: 8.2px; letter-spacing: .155em; color: $ink3; margin-top: 4px;
}
.row p { margin: 8px 0 0; }
.row p.en { font-size: 11px; line-height: 1.55; }
.row p.es { font-size: 10.2px; line-height: 1.52; margin-top: 5px; }

/* --------------------------------------------------------------- beyond --- */
.beyond .col-pic { position: absolute; left: 0; top: 0; bottom: 0; width: 2.66in; }
.beyond .frame { left: 3.12in; bottom: 1.02in; display: flex; flex-direction: column; }
.beyond .rows { flex: 1 1 auto; }
.beyond .row { padding: 8px 0 9px; }
.beyond .row p.en { font-size: 10.6px; }
.beyond .row p.es { font-size: 9.9px; }

.bookline {
  border-top: 1px solid $rule; margin-top: 12px; padding-top: 13px;
  display: flex; align-items: center; gap: 16px;
}
.bookline .qr { width: 0.94in; height: 0.94in; display: block; flex: none; }
.bookline b { display: block; font-size: 11.6px; font-weight: 600; }
.bookline i { display: block; font-style: normal; font-size: 10.6px; color: $ink3; margin-top: 2px; }
.bookline .url {
  display: block; margin-top: 9px; font-family: "IBM Plex Mono", monospace;
  font-size: 9.6px; letter-spacing: .04em; color: $rose;
}

/* -------------------------------------------------------------- rentals --- */
.chips {
  display: grid; grid-template-columns: 1fr 1fr; column-gap: 0.44in;
  margin: 0; padding: 0; list-style: none;
}
.chips li {
  border-top: 1px solid $rule; padding: 10px 0 11px;
  display: flex; align-items: baseline; gap: 10px;
}
.chips b { font-size: 11.2px; font-weight: 700; letter-spacing: .105em; text-transform: uppercase; }
.chips small {
  font-family: "IBM Plex Mono", monospace; font-size: 8.6px; letter-spacing: .1em;
  color: $ink3; margin-left: auto;
}

.know { background: $sand; border-radius: 2px; padding: 24px 28px 22px; }
.know ul { list-style: none; margin: 12px 0 0; padding: 0; }
.know li { display: flex; gap: 11px; padding: 7px 0; }
.know li + li { border-top: 1px solid rgba(20,16,14,.09); }
.know .hex { width: 8px; height: 10px; flex: none; margin-top: 5px; }
.know b { display: block; font-size: 10.8px; font-weight: 600; line-height: 1.45; }
.know small { display: block; font-size: 9.9px; color: $ink3; line-height: 1.45; margin-top: 2px; }
.know figure {
  margin: 16px 0 0; padding-top: 15px; border-top: 1px solid rgba(20,16,14,.11);
  display: flex; align-items: center; gap: 20px;
}
.know figure .pic { width: 3.1in; height: 0.66in; flex: none; }
.know figcaption { font-size: 9.4px; line-height: 1.5; color: $ink2; }
.know figcaption i { display: block; font-style: normal; color: $ink3; margin-top: 2px; }

/* ----------------------------------------------------------------- back --- */
.back .band { top: 0; bottom: 0; }
.back .veil { position: absolute; inset: 0; background: rgba(20,16,14,.62); }
.back .inner {
  position: absolute; left: $m; right: $m; top: 1.55in; bottom: 1.5in;
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; text-align: center;
}
.back .inner img { width: 1.04in; height: 1.04in; object-fit: contain; }
.back .display { margin-top: 22px; }
.back .say { max-width: 3.55in; margin: 20px 0 0; font-size: 10.8px; line-height: 1.6; color: $onink2; }
.back .say i { display: block; font-style: normal; color: $onink3; font-size: 10px; margin-top: 5px; }
.back .qrcard { margin-top: 32px; background: $paper; border-radius: 3px; padding: 15px; }
.back .qrcard .qr { width: 1.92in; height: 1.92in; display: block; }
.back .url {
  margin-top: 20px; font-family: "IBM Plex Mono", monospace; font-size: 10.4px;
  letter-spacing: .06em; color: $onink;
}
.back .mail { margin-top: 9px; font-size: 10px; color: $onink2; }
.back .mail b { font-family: "IBM Plex Mono", monospace; font-weight: 400; color: $onink; }
.back .sign { margin-top: 34px; }
.back .stamp {
  position: absolute; left: $m; right: $m; bottom: 0.6in; text-align: center; color: $onink3;
}
""")


def build(size="letter"):
    w, h = SIZES[size]
    fonts = open(os.path.join(HERE, "fonts.css")).read()
    raw = base64.b64encode(open(os.path.join(ROOT, "app", "logo.png"), "rb").read()).decode()
    logo = '<img src="data:image/png;base64,%s" alt="Shokogi">' % raw

    css = CSS.substitute(fonts=fonts, w=w, h=h, m="0.78in", mt="0.78in", mb="0.78in", **P)
    pages = [cover_page(logo), opening_page(), surf_page(),
             beyond_page(), rentals_page(), back_page(logo)]
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<title>Shokogi &middot; Brochure</title>\n<style>%s</style>\n</head>\n'
            '<body>\n%s\n</body>\n</html>\n' % (css, "\n".join(pages)))


def cover_page(logo):
    return """
<section class="page dark cover">
  <div class="band">%s</div>
  <div class="veil"></div>
  <div class="lockup">
    %s
    <b>%s</b>
    <span class="line"></span>
    <p class="meta sub">%s &nbsp;·&nbsp; %s</p>
  </div>
  <div class="foot">
    <p class="meta">%s</p>
    <p class="meta">%s</p>
  </div>
</section>""" % (picture("cover"), logo, C.COVER["wordmark"],
                 C.COVER["rule_en"], C.COVER["rule_es"],
                 C.COVER["place"], C.COVER["est"])


def opening_page():
    o = C.OPENING
    facts = "".join('<div><p class="eyebrow">%s</p><small>%s</small></div>' % f
                    for f in o["facts"])
    return """
<section class="page opening">
  <div class="col-pic">%s</div>
  <div class="frame">
    <p class="eyebrow">%s</p>
    %s
    %s
    %s
    %s
    %s
    <div class="facts">%s</div>
  </div>
  %s
</section>""" % (
        picture("coast"), o["eyebrow"],
        display(o["display_en"]), display(o["display_es"], "es"), rule(),
        "".join('<p class="en">%s</p>' % t for t in o["body_en"]),
        "".join('<p class="es">%s</p>' % t for t in o["body_es"]),
        facts, folio(1, "right:3.48in"))


def _rows(items):
    return "".join(
        '<article class="row"><span class="n">%02d</span><div>'
        '<h3>%s<small>%s</small></h3>'
        '<p class="en">%s</p><p class="es">%s</p></div></article>'
        % (i + 1, en, es, ben, bes)
        for i, (en, es, ben, bes) in enumerate(items))


def surf_page():
    s = C.SURF
    return """
<section class="page surf">
  <div class="band" style="top:0;height:3.92in">%s</div>
  <div class="frame" style="top:4.46in">
    <p class="eyebrow">%s</p>
    %s
    %s
    <p class="en" style="margin-top:16px;max-width:5.1in">%s</p>
    <p class="es" style="max-width:5.1in">%s</p>
    <div class="rows two" style="margin-top:26px">%s</div>
  </div>
  %s
</section>""" % (picture("surf"), s["eyebrow"],
                 display(s["title_en"], "sm"), display(s["title_es"], "es"),
                 s["lede_en"], s["lede_es"], _rows(s["items"]), folio(2))


def beyond_page():
    b = C.BEYOND
    return """
<section class="page beyond">
  <div class="col-pic">%s</div>
  <div class="frame">
    <p class="eyebrow">%s</p>
    %s
    %s
    <div class="rows" style="margin-top:18px">%s</div>
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
                 display(b["title_en"], "sm"), display(b["title_es"], "es"),
                 _rows(b["items"]),
                 qr_svg(C.BOOKING_URL, "0.94in", quiet=2, light=P["paper"]),
                 C.BOOK["inline_en"], C.BOOK["inline_es"], C.BOOKING_LABEL,
                 folio(3, "left:3.12in"))


def rentals_page():
    r, k = C.RENTALS, C.KNOW
    chips = "".join('<li><b>%s</b><small>%s</small></li>' % it for it in r["items"])
    hexb = ('<svg class="hex" viewBox="0 0 10 12" aria-hidden="true">'
            '<path d="%s" fill="%s"/></svg>' % (hexagon(5, 6, 5), P["pink"]))
    items = "".join('<li>%s<div><b>%s</b><small>%s</small></div></li>' % (hexb, en, es)
                    for en, es in k["items"])
    return """
<section class="page rentals">
  <div class="band" style="top:0;height:2.125in">%s</div>
  <div class="frame" style="top:2.72in">
    <p class="eyebrow">%s</p>
    %s
    %s
    <ul class="chips" style="margin-top:22px">%s</ul>
    <p class="meta" style="margin-top:15px;color:%s">%s &nbsp;·&nbsp; %s</p>
    <div class="know" style="margin-top:34px">
      <p class="eyebrow">%s</p>
      <ul>%s</ul>
      <figure>
        <span class="pic">%s</span>
        <figcaption>%s<i>%s</i></figcaption>
      </figure>
    </div>
  </div>
  %s
</section>""" % (
        picture("boards"), r["eyebrow"],
        display(r["title_en"], "sm"), display(r["title_es"], "es"),
        chips, P["ink2"], r["note_en"], r["note_es"], k["eyebrow"], items,
        art.tide(420, 90, stroke=P["rose"], ground=P["sand"], width=.9),
        k["tide_caption_en"], k["tide_caption_es"], folio(4))


def back_page(logo):
    b = C.BOOK
    return """
<section class="page dark back">
  <div class="band">%s</div>
  <div class="veil"></div>
  <div class="inner">
    %s
    %s
    %s
    <p class="say">%s<i>%s</i></p>
    <div class="qrcard">%s</div>
    <p class="url">%s</p>
    <p class="mail">%s · %s &nbsp; <b>%s</b></p>
    <p class="meta sign">%s &nbsp;·&nbsp; %s</p>
  </div>
  <p class="meta stamp">%s &nbsp;·&nbsp; %s &nbsp;·&nbsp; %s</p>
</section>""" % (
        picture("back"), logo, display(b["title_en"]), display(b["title_es"], "es"),
        b["body_en"], b["body_es"],
        qr_svg(C.BOOKING_URL, "1.92in"), C.BOOKING_LABEL,
        b["or_en"], b["or_es"], C.EMAIL, b["sign_en"], b["sign_es"],
        C.COVER["wordmark"], C.COVER["place"], C.COVER["est"])


# --------------------------------------------------------------------------
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
