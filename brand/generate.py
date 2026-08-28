#!/usr/bin/env python3
"""Logo file set for the dinghy "the bee".

Built for one production method: single-colour cut vinyl at small size.
No floating islands, no hairlines, no sharp tips. Every shape is a separate
positive piece; corner rounding comes from stroking each path in its own
fill colour with a round join.

The wordmark is real outlines (Fraunces Bold Italic, in wordmark.path,
normalised to font-size 100 with the baseline at y=0), so no file here
depends on a font being installed. See outline_wordmark.py to regenerate it.
"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))

NAVY  = "#12283F"
HONEY = "#E8A33D"
FOAM  = "#F7F4EC"
CUT   = "#000000"

# ---- the mark, on a 100-unit grid -----------------------------------------
WING_L = "M50 43 C38 46 24 43 16 34 C25 28 42 30 50 43 Z"
WING_R = "M50 43 C62 46 76 43 84 34 C75 28 58 30 50 43 Z"
MARK_X, MARK_Y, MARK_W, MARK_H = 14.5, 29.0, 71.0, 64.0   # ink box

# ---- the wordmark, at font-size 100, baseline y=0, origin x=0 -------------
WORD_D = open(os.path.join(OUT, "wordmark.path")).read().strip()
WORD_X0, WORD_Y0, WORD_X1, WORD_Y1 = 4.51, -71.95, 335.26, 1.35   # ink box


def bee(wing, bar):
    """Two swept wings, a head, three tapering bands.

    The bands read twice: the stripes of a bee seen from above, and the wake
    of a small boat. Nothing is a hole, so it weeds and lifts cleanly."""
    return (f'<g fill="{wing}" stroke="{wing}" stroke-width="3" stroke-linejoin="round">'
            f'<path d="{WING_L}"/><path d="{WING_R}"/></g>'
            f'<g fill="{bar}"><circle cx="50" cy="45" r="7"/>'
            f'<rect x="26" y="55" width="48" height="10" rx="5"/>'
            f'<rect x="32" y="69" width="36" height="10" rx="5"/>'
            f'<rect x="39" y="83" width="22" height="10" rx="5"/></g>')


def mark_at(x, y, height):
    """Place the mark with its ink box top-left at (x, y)."""
    s = height / MARK_H
    return (f'<g transform="translate({x:g} {y:g}) scale({s:.4f}) '
            f'translate({-MARK_X:g} {-MARK_Y:g})">{bee("%s", "%s")}</g>', s)


def mark_g(x, y, height, wing, bar):
    s = height / MARK_H
    return (f'<g transform="translate({x:g} {y:g}) scale({s:.4f}) '
            f'translate({-MARK_X:g} {-MARK_Y:g})">{bee(wing, bar)}</g>')


def word_g(x, baseline, size, fill, centre=False):
    """Place the wordmark. x is the ink left edge, or the ink centre if centre."""
    s = size / 100.0
    ox = x - (WORD_X0 + WORD_X1) / 2 * s if centre else x - WORD_X0 * s
    return (f'<path transform="translate({ox:.2f} {baseline:.2f}) scale({s:.4f})" '
            f'd="{WORD_D}" fill="{fill}"/>')


def word_metrics(size):
    s = size / 100.0
    return (WORD_X1 - WORD_X0) * s, -WORD_Y0 * s, WORD_Y1 * s   # width, above, below


def svg(view, inner, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" '
            f'aria-label="{label}">{inner}</svg>\n')


def write(name, content):
    open(os.path.join(OUT, name), "w").write(content)
    print("wrote", name)


# ---------------------------------------------------------------- the mark
PAD = 2


def mark_file(wing, bar, label):
    return svg(f"{MARK_X-PAD:g} {MARK_Y-PAD:g} {MARK_W+2*PAD:g} {MARK_H+2*PAD:g}",
               bee(wing, bar), label)


write("mark-two-tone.svg", mark_file(HONEY, NAVY, "the bee mark"))
write("mark-navy.svg",     mark_file(NAVY, NAVY, "the bee mark, navy"))
write("mark-honey.svg",    mark_file(HONEY, HONEY, "the bee mark, honey"))
write("mark-foam.svg",     mark_file(FOAM, FOAM, "the bee mark, foam"))

# ------------------------------------------------------- bow lockup (wide)
# Mark left, name right. Goes along the hull side, forward of amidships.
BOW_H, BOW_SIZE, BOW_GAP, BOW_PAD = 88, 62, 28, 8


def bow(wing, bar, text, label):
    mw = MARK_W * BOW_H / MARK_H
    tw, above, below = word_metrics(BOW_SIZE)
    tx = BOW_PAD + mw + BOW_GAP
    base = BOW_PAD + BOW_H / 2 + (above - below) / 2
    return svg(f"0 0 {tx + tw + BOW_PAD:.0f} {BOW_PAD*2 + BOW_H:.0f}",
               mark_g(BOW_PAD, BOW_PAD, BOW_H, wing, bar)
               + word_g(tx, base, BOW_SIZE, text), label)


write("logo-bow-two-tone.svg", bow(HONEY, NAVY, NAVY, "the bee"))
write("logo-bow-navy.svg",     bow(NAVY, NAVY, NAVY, "the bee, navy"))
write("logo-bow-foam.svg",     bow(FOAM, FOAM, FOAM, "the bee, foam"))

# -------------------------------------------------- transom lockup (stacked)
TR_H, TR_SIZE, TR_GAP, TR_PAD = 96, 54, 18, 8


def transom(wing, bar, text, label):
    mw = MARK_W * TR_H / MARK_H
    tw, above, below = word_metrics(TR_SIZE)
    w = max(mw, tw) + TR_PAD * 2
    base = TR_PAD + TR_H + TR_GAP + above
    return svg(f"0 0 {w:.0f} {base + below + TR_PAD:.0f}",
               mark_g(w / 2 - mw / 2, TR_PAD, TR_H, wing, bar)
               + word_g(w / 2, base, TR_SIZE, text, centre=True), label)


write("logo-transom-two-tone.svg", transom(HONEY, NAVY, NAVY, "the bee, stacked"))
write("logo-transom-navy.svg",     transom(NAVY, NAVY, NAVY, "the bee, stacked, navy"))
write("logo-transom-foam.svg",     transom(FOAM, FOAM, FOAM, "the bee, stacked, foam"))

# ------------------------------------------ name alone (gunwale, oar, trailer)
def wordmark_file(fill, label, size=62, pad=6):
    tw, above, below = word_metrics(size)
    return svg(f"0 0 {tw + pad*2:.0f} {above + below + pad*2:.0f}",
               word_g(pad, pad + above, size, fill), label)


write("wordmark-navy.svg", wordmark_file(NAVY, "the bee wordmark"))
write("wordmark-foam.svg", wordmark_file(FOAM, "the bee wordmark, foam"))

# ---------------------------------------------------------------- roundel
def roundel(ring, wing, bar, label):
    h = 52
    return svg("0 0 120 120",
               f'<circle cx="60" cy="60" r="60" fill="{ring}"/>'
               + mark_g(60 - MARK_W * h / MARK_H / 2, 60 - h / 2, h, wing, bar), label)


write("roundel-navy.svg",  roundel(NAVY, HONEY, FOAM, "the bee roundel"))
write("roundel-honey.svg", roundel(HONEY, NAVY, NAVY, "the bee roundel, honey"))

# ------------------------------------------------------------- cut files
# One colour, nothing to separate. These go to the vinyl cutter.
write("cut-mark.svg",     mark_file(CUT, CUT, "the bee mark, cut file"))
write("cut-bow.svg",      bow(CUT, CUT, CUT, "the bee bow lockup, cut file"))
write("cut-transom.svg",  transom(CUT, CUT, CUT, "the bee transom lockup, cut file"))
