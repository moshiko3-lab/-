#!/usr/bin/env python3
"""Regenerates wordmark.path from Fraunces Bold Italic.

    pip install fonttools
    python3 outline_wordmark.py path/to/Fraunces-BoldItalic.ttf

Emits the outlines of "the bee" normalised to font-size 100, baseline at
y=0, origin x=0, with the -0.5/62 em tracking used in the lockups baked in.
"""
import sys, os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.misc.transform import Transform

TEXT, TRACK = "the bee", -0.5 / 62 * 100

font = TTFont(sys.argv[1])
scale = 100.0 / font["head"].unitsPerEm
cmap, glyphs = font.getBestCmap(), font.getGlyphSet()


def run(pen):
    x = 0.0
    for ch in TEXT:
        g = cmap[ord(ch)]
        glyphs[g].draw(TransformPen(pen, Transform(scale, 0, 0, -scale, x, 0)))
        x += glyphs[g].width * scale + TRACK
    return x - TRACK


pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}")
advance = run(pen)
bounds = BoundsPen(glyphs); run(bounds)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wordmark.path")
open(out, "w").write(pen.getCommands())
print(f"advance {advance:.2f}  ink box {tuple(round(v, 2) for v in bounds.bounds)}")
print("update WORD_X0/Y0/X1/Y1 in generate.py if the ink box changed")
