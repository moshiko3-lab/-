#!/usr/bin/env python3
"""Build the tri-fold: one sheet, folded in three, for the counter and the racks.

    python3 print/build_trifold.py                    # -> print/shokogi-trifold.pdf
    python3 print/build_trifold.py --html out.html    # the sheet, unrendered

The booklet in `build_brochure.py` is for a guest room, where somebody has time.
This is the other thing a surf school needs: one sheet that folds to pocket
size, sits in a rack by a door, and can be handed across a counter. Same brand,
same drawings, same words out of `content.py` -- a different job.

Two pages, each 11 x 8.5 landscape, each divided into three panels:

    page 1, the outside     [ before you come ] [ find us ] [ FRONT COVER ]
    page 2, the inside      [ in the water ] [ come for a week ] [ the rack ]

The panels are equal thirds. A shop doing a tight letter-fold usually wants the
panel that tucks in about 1.5 mm narrower than the other two; that is a change
to make with the printer rather than a guess to bake in here, and `print/README`
says so.
"""

import argparse
import base64
import os
import sys
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import art  # noqa: E402
import content as C  # noqa: E402
import quiver  # noqa: E402
from build_brochure import P, chrome, hexagon, picture, qr_svg, render  # noqa: E402

SHEET = ("11in", "8.5in")
PANEL_PX = (1056, 816)          # the sheet in CSS pixels, for the dot screen


CSS = Template("""
$fonts
$script

@page { size: $w $h; margin: 0; }

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: Figtree, -apple-system, system-ui, sans-serif; color: $ink;
  background: #4b5a60;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
  -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
}

.sheet {
  width: $w; height: $h; position: relative; overflow: hidden;
  display: grid; grid-template-columns: repeat(3, 1fr);
  page-break-after: always; break-after: page; background: $paper;
}
.sheet:last-child { page-break-after: auto; break-after: auto; }
@media screen { .sheet { margin: 24px auto; box-shadow: 0 10px 50px rgba(0,0,0,.5); } }

/* The folds, shown on screen and gone on paper: a designer needs to see them
   and a printer must never be given them. */
@media screen {
  .fold { position: absolute; top: 0; bottom: 0; width: 0;
          border-left: 1px dashed rgba(0,0,0,.28); }
  .fold.a { left: 33.3333%; } .fold.b { left: 66.6667%; }
}
@media print { .fold { display: none; } }

.panel { position: relative; overflow: hidden; padding: 0.42in 0.34in 0.40in; }
.panel.sea { background: $sea; color: $onink; }
.panel.aqua { background: $aqua; }
.panel.sand { background: $sand; }

/* Every band ends in a wave instead of a rule. Right angles everywhere is
   what made the last version read as an estate agent's brochure. */
.band .edge { position: absolute; left: 0; right: 0; bottom: -1px; height: 0.5in; }
.band .edge svg { display: block; width: 100%; height: 100%; }
.screen { position: absolute; inset: 0; width: 100%; height: 100%; }
.band { position: absolute; left: 0; right: 0; overflow: hidden; }
.pic { display: block; width: 100%; height: 100%; overflow: hidden; }
.pic svg { display: block; width: 100%; height: 100%; }
.inner { position: relative; }

/* ---------------------------------------------------------------- type --- */
.d {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 116, "wght" 800;
  text-transform: uppercase; letter-spacing: -.004em; line-height: .94; margin: 0;
}
h2.d { font-size: 32px; }
.script {
  font-family: "Kaushan Script", cursive; font-size: 30px; line-height: 1.04;
  color: $rose; margin: 2px 0 0; letter-spacing: .005em;
}
.sea .script { color: $amber; }
.aqua .script { color: $ink; }
.eyebrow {
  font-family: "IBM Plex Mono", monospace; font-weight: 500; font-size: 8px;
  letter-spacing: .2em; text-transform: uppercase; color: $rose; margin: 0;
}
.sea .eyebrow { color: $amber; }
.aqua .eyebrow { color: $ink; }
.meta {
  font-family: "IBM Plex Mono", monospace; font-size: 7.4px; letter-spacing: .16em;
  text-transform: uppercase; color: $ink3; margin: 0;
}
.sea .meta { color: $onink2; }
.aqua .meta { color: rgba(6,50,65,.82); }
p.en { font-size: 9.8px; line-height: 1.5; color: $ink2; margin: 0; }
p.es { font-size: 8.8px; line-height: 1.48; color: $ink3; margin: 3px 0 0; }
.sea p.en { color: $onink2; }
.sea p.es { color: $onink3; }

.sub {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 106, "wght" 500;
  font-size: 12px; color: $ink3; margin: 5px 0 0;
}
.sea .sub { color: $onink3; }

/* The reference's move, and a good one: everything that is a group of facts
   sits in its own rounded card rather than between two hairlines. */
.card {
  background: $sand; border-radius: 12px; padding: 8px 11px 9px; margin-top: 7px;
}
.sea .card { background: rgba(255,255,255,.09); }
.aqua .card { background: rgba(255,255,255,.34); }
.card.sand { background: $sand; }
/* the three camps, in three colours, because a run of identical grey cards is
   a price list and a run of coloured ones is a poster */
.card.hot { background: $pink; }
.card.hot h3, .card.hot .numrow b { color: #fff; }
.card.hot h3 small { color: rgba(255,255,255,.8); }
.card.sun { background: $amber; }
.card.sun h3, .card.sun .numrow b { color: $ink; }
.card.sun h3 small { color: rgba(6,50,65,.62); }
.card.wet { background: $aqua; }
.card.wet h3, .card.wet .numrow b { color: #fff; }
.card.wet h3 small { color: rgba(255,255,255,.82); }
.card h3 {
  margin: 0; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 106, "wght" 700;
  font-size: 10.8px; letter-spacing: .02em; text-transform: uppercase;
}
.card h3 small {
  display: block; font-family: "IBM Plex Mono", monospace; font-weight: 400;
  font-size: 7px; letter-spacing: .13em; color: $ink3; margin-top: 3px;
}
.sea .card h3 small { color: $onink3; }
.card p { margin: 5px 0 0; }
.card p.en { font-size: 8.5px; line-height: 1.36; }
.card p.es { font-size: 8px; line-height: 1.34; margin-top: 3px; }

.rowlist { list-style: none; margin: 9px 0 0; padding: 0; }
.rowlist li { display: flex; gap: 8px; align-items: baseline; padding: 4px 0; }
.rowlist li + li { border-top: 1px solid $rule; }
.sea .rowlist li + li { border-color: rgba(255,255,255,.2); }
.aqua .rowlist li + li { border-color: rgba(6,50,65,.2); }
.rowlist b {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 104, "wght" 700;
  font-size: 9.6px; letter-spacing: .02em; text-transform: uppercase;
}
.rowlist small {
  font-family: "IBM Plex Mono", monospace; font-size: 7.2px; letter-spacing: .08em;
  color: $ink3; margin-left: auto; text-align: right;
}
.sea .rowlist small { color: $onink3; }

.numrow { display: flex; align-items: baseline; gap: 7px; }
.numrow b {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 114, "wght" 800;
  font-size: 19px; letter-spacing: -.015em; color: $rose;
}
.sea .numrow b { color: $pink; }
.numrow b { font-size: 23px; }
.numrow span {
  font-family: "IBM Plex Mono", monospace; font-size: 7px; letter-spacing: .14em;
  color: $ink3;
}
.card.hot .numrow span, .card.wet .numrow span { color: rgba(255,255,255,.8); }
.card.sun .numrow span { color: rgba(6,50,65,.6); }
.sea .numrow span { color: $onink3; }

.stats { display: flex; gap: 0; border-top: 2px solid $ink; padding-top: 8px; margin-top: 10px; }
.stats div { flex: 1; }
.stats div + div { border-left: 1px solid $rule; padding-left: 9px; }
.stats b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 114, "wght" 800; font-size: 19px; line-height: 1;
}
.stats small {
  display: block; margin-top: 3px; font-family: "IBM Plex Mono", monospace;
  font-size: 6.4px; letter-spacing: .13em; color: $ink3;
}

.hr {
  display: block; width: 46px; height: 8px; margin: 11px 0;
  background: linear-gradient(to bottom,
    $amber 0 2px, transparent 2px 3.2px, $coral 3.2px 5px,
    transparent 5px 6px, $pink 6px 7.4px, transparent 7.4px 8px);
}

.foot {
  position: absolute; left: 0.34in; right: 0.34in; bottom: 0.34in;
  border-top: 1px solid $rule; padding-top: 6px;
  display: flex; justify-content: space-between;
}
.sea .foot { border-color: rgba(255,255,255,.22); }
.aqua .foot { border-color: rgba(6,50,65,.22); }

/* ---------------------------------------------------------------- cover --- */
.cover .sunband { position: absolute; left: 0; right: 0; top: 0.42in; height: 3.2in; }
.cover .band { bottom: 0; height: 3.62in; }
.cover .mark { position: relative; }
.cover .mark img { width: 0.62in; height: 0.62in; object-fit: contain; }
.cover .lockup { position: absolute; left: 0.34in; right: 0.34in; top: 3.66in; }
.cover .lockup b {
  display: block; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 122, "wght" 800;
  font-size: 43px; line-height: .9; letter-spacing: -.015em;
  text-transform: uppercase; color: $paper;
}
.cover .line1 {
  font-family: Archivo, sans-serif; font-variation-settings: "wdth" 112, "wght" 700;
  font-size: 15px; text-transform: uppercase; color: $onink; margin: 14px 0 0;
  letter-spacing: -.005em;
}
.cover .patch { position: absolute; right: 0.3in; bottom: 0.34in; width: 1.02in; }
.before .patch { position: absolute; left: 0.34in; bottom: 0.72in; width: 1.12in; }
.patch svg { display: block; width: 100%; transform: rotate(-8deg); }

/* ----------------------------------------------------------------- back --- */
.back .qrcard { background: $paper; border-radius: 14px; padding: 12px; margin-top: 12px; }
.back .qrcard .qr { width: 100%; height: auto; display: block; }
.back .url {
  margin-top: 11px; font-family: "IBM Plex Mono", monospace; font-size: 10.4px;
  letter-spacing: .04em; color: $ink;
}
.back .mail { margin-top: 5px; font-size: 9.2px; color: $ink; }
.back .mail b { font-family: "IBM Plex Mono", monospace; font-weight: 400; color: $ink; }
.back .racks { margin-top: 14px; border-top: 1px solid rgba(6,50,65,.22); padding-top: 9px; }
.back .racks span {
  display: block; margin-top: 6px; font-family: Archivo, sans-serif;
  font-variation-settings: "wdth" 100, "wght" 600;
  font-size: 8.4px; letter-spacing: .05em; line-height: 1.72; color: $ink;
}
""")


def edge(fill, seed=2):
    """The wave that eats into the bottom of a band, cut in the colour of the
    panel underneath it."""
    return ('<span class="edge">%s</span>'
            % art.wave_edge(360, 48, fill, seed=seed, flip=True, amp=0.62))


def screen(colour, opacity):
    return art.halftone(PANEL_PX[0] / 3.0, PANEL_PX[1], cell=11.0,
                        colour=colour, opacity=opacity)


def build():
    fonts = open(os.path.join(HERE, "fonts.css")).read()
    script = open(os.path.join(HERE, "fonts-script.css")).read()
    raw = base64.b64encode(open(os.path.join(ROOT, "app", "logo.png"), "rb").read()).decode()
    logo = '<img src="data:image/png;base64,%s" alt="Shokogi">' % raw
    css = CSS.substitute(fonts=fonts, script=script, w=SHEET[0], h=SHEET[1], **P)
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<title>Shokogi &middot; Tri-fold</title>\n<style>%s</style>\n</head>\n<body>\n'
            '<section class="sheet">%s%s%s<i class="fold a"></i><i class="fold b"></i></section>\n'
            '<section class="sheet">%s%s%s<i class="fold a"></i><i class="fold b"></i></section>\n'
            '</body>\n</html>\n'
            % (css, panel_before(), panel_find(logo), panel_cover(logo),
               panel_water(), panel_week(), panel_rack()))


# --------------------------------------------------------------- outside ---
def panel_cover(logo):
    c = C.COVER
    return """
<div class="panel sea cover">
  <div class="sunband">%s</div>
  <div class="band">%s</div>
  %s
  <div class="inner mark">%s</div>
  <div class="lockup">
    <b>%s</b>
    <p class="line1">%s</p>
    <p class="script">%s</p>
    <span class="hr"></span>
    <p class="meta">%s &nbsp;·&nbsp; %s</p>
    <p class="meta" style="margin-top:5px">%s &nbsp;·&nbsp; %s</p>
  </div>
  <div class="patch">%s</div>
</div>""" % (
        art.sunset(1000, 700, ground=None,
                   colours=(P["amber"], "#F4894C", P["coral"], P["pink"], P["rose"])),
        art.wave(1000, 640, deep=P["tube"], body=P["sea2"], foam=P["paper"],
                 fit="xMidYMax slice"),
        screen(P["paper"], .11), logo,
        c["wordmark"], C.COVER["line_bold"], C.COVER["line_script"],
        c["rule_en"], c["rule_es"], c["place"], c["est"],
        art.stamp(120, c["patch_top"], c["patch_bottom"], P["paper"], id_="tf1",
                  mark='<path d="%s" fill="%s"/>' % (hexagon(0, 0, 26), P["pink"])))


def panel_find(logo):
    b, q = C.BOOK, quiver.read()
    return """
<div class="panel aqua back">
  %s
  <div class="inner">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:9px">%s</h2>
    <p class="script" style="font-size:22px">%s</p>
    <div class="qrcard">%s</div>
    <p class="url">%s</p>
    <p class="mail">%s · %s<br><b>%s</b></p>
    <p class="meta" style="margin-top:9px">%s</p>
    <div class="racks">
      <p class="eyebrow">%s &nbsp;·&nbsp; %s</p>
      <span>%s</span>
    </div>
  </div>
</div>""" % (
        screen(P["paper"], .09),
        C.SHOP["eyebrow"], b["title_en"], C.COVER["find_script"],
        qr_svg(C.BOOKING_URL, "100%"), C.BOOKING_LABEL,
        b["or_en"], b["or_es"], C.EMAIL,
        "%s &nbsp;·&nbsp; %s" % (C.COVER["place"], C.COVER["coords"]),
        C.RENTALS["racks_en"], C.RENTALS["racks_es"], " · ".join(q["shapers"]))


def panel_before():
    o, k = C.OPENING, C.KNOW
    facts = "".join('<li><b>%s</b><small>%s</small></li>' % f for f in o["facts"])
    items = "".join('<div class="card"><p class="en">%s</p><p class="es">%s</p></div>'
                    % it for it in k["items"])
    return """
<div class="panel before">
  <div class="inner">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:9px">%s</h2>
    <p class="script" style="font-size:21px">%s</p>
    <p class="en" style="margin-top:11px">%s</p>
    <p class="es">%s</p>
    <ul class="rowlist">%s</ul>
    %s
    <div class="card" style="padding:10px 12px">
      <span class="pic" style="height:0.52in;display:block">%s</span>
      <p class="es" style="margin-top:6px">%s<br>%s</p>
    </div>
  </div>
  <div class="patch">%s</div>
  <div class="foot"><p class="meta">%s</p><p class="meta">%s</p></div>
</div>""" % (
        k["eyebrow"], C.COVER["before_title"], C.COVER["before_script"],
        o["body_en"][2], o["body_es"][2], facts, items,
        art.tide(420, 84, stroke=P["rose"], ground=P["paper"], width=1.0),
        k["tide_caption_en"], k["tide_caption_es"],
        art.stamp(120, C.COVER["patch2_top"], C.COVER["patch2_bottom"], P["rose"],
                  id_="tf2",
                  mark='<text text-anchor="middle" y="13" font-family="Archivo" '
                       'font-size="38" font-weight="800" fill="%s">09</text>' % P["rose"]),
        C.COVER["wordmark"], C.COVER["est"])


# ---------------------------------------------------------------- inside ---
def panel_water():
    s, g = C.SURF, C.START
    start = "".join('<li><b>%s</b><small>%s</small></li>' % (en, ben)
                    for en, es, ben, bes in g["items"])
    cards = "".join('<div class="card"><h3>%s<small>%s</small></h3>'
                    '<p class="en">%s</p><p class="es">%s</p></div>' % it
                    for it in s["items"])
    return """
<div class="panel water">
  <div class="band" style="top:0;height:1.52in">%s%s</div>
  <div class="inner" style="margin-top:1.30in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:9px">%s</h2>
    <p class="script" style="font-size:24px">%s</p>
    <p class="eyebrow" style="margin-top:12px">%s</p>
    <ul class="rowlist">%s</ul>
    %s
  </div>
  <div class="foot"><p class="meta">%s</p><p class="meta">01</p></div>
</div>""" % (picture("surf"), edge(P["paper"], 2), s["eyebrow"], s["title_en"], C.COVER["water_script"],
             g["eyebrow"], start, cards, C.FOLIO[2])


def panel_week():
    c, b = C.CAMPS, C.BEYOND
    tone = ("wet", "hot", "sun")
    camps = "".join('<div class="card %s"><div class="numrow"><b>%s</b><span>%s</span></div>'
                    '<h3 style="margin-top:5px">%s<small>%s</small></h3></div>'
                    % (tone[i], num, unit, en, es)
                    for i, (en, es, num, unit, ben, bes) in enumerate(c["groups"][:3]))
    rest = "".join('<li><b>%s</b><small>%s</small></li>' % (en, es)
                   for en, es, ben, bes in b["items"])
    return """
<div class="panel week">
  <div class="band" style="top:0;height:1.52in">%s%s</div>
  <div class="inner" style="margin-top:1.30in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:9px">%s</h2>
    <p class="script" style="font-size:24px">%s</p>
    %s
    <p class="eyebrow" style="margin-top:13px">%s</p>
    <ul class="rowlist">%s</ul>
  </div>
  <div class="foot"><p class="meta">%s</p><p class="meta">02</p></div>
</div>""" % (picture("camps"), edge(P["paper"], 5), c["eyebrow"], c["title_en"],
             C.COVER["week_script"], camps,
             b["eyebrow"], rest, C.FOLIO[3])


def panel_rack():
    r, h = C.RENTALS, C.SHOP
    q = quiver.read()
    chips = "".join('<li><b>%s</b><small>%s</small></li>' % it for it in r["items"])
    blocks = "".join('<div class="card sand"><h3>%s<small>%s</small></h3>'
                     '<p class="en" style="font-size:8.6px;letter-spacing:.03em">%s</p></div>'
                     % b for b in h["blocks"][:3])
    return """
<div class="panel rack">
  <div class="band" style="top:0;height:1.52in">%s%s</div>
  <div class="inner" style="margin-top:1.30in">
    <p class="eyebrow">%s</p>
    <h2 class="d" style="margin-top:9px">%s</h2>
    <p class="script" style="font-size:24px">%s</p>
    <div class="stats">
      <div><b>%d</b><small>%s</small></div>
      <div><b>%s</b><small>%s</small></div>
      <div><b>%d</b><small>%s</small></div>
    </div>
    <ul class="rowlist" style="margin-top:10px">%s</ul>
    <p class="meta" style="margin-top:8px;color:%s">%s</p>
    <p class="eyebrow" style="margin-top:13px">%s</p>
    %s
  </div>
  <div class="foot"><p class="meta">%s</p><p class="meta">03</p></div>
</div>""" % (
        picture("boards"), edge(P["paper"], 9),
        r["eyebrow"], r["title_en"], C.COVER["rack_script"],
        q["total"], r["stat_boards"][0],
        "%s–%s" % (q["shortest"], q["longest"]), r["stat_range"][0],
        len(q["shapers"]), r["stat_shapers"][0],
        chips, P["ink2"], r["note_en"], h["eyebrow"], blocks, C.FOLIO[5])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None)
    ap.add_argument("--html", default=None)
    a = ap.parse_args()
    html = build()
    if a.html:
        with open(a.html, "w") as f:
            f.write(html)
        print("wrote %s" % a.html)
        return
    out = a.out or os.path.join(HERE, "shokogi-trifold.pdf")
    render(html, out)
    print("wrote %s (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()
