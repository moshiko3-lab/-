#!/usr/bin/env python3
"""Draw the day's board from a spec, with nothing but Pillow.

    python3 board.py --spec > day.json
    python3 draw_board.py day.json board.png

Why this exists rather than a screenshot of a web page: the only way a
picture reaches WhatsApp from here is through a sandbox that can reach the
TimelinesAI API, and that sandbox has no browser. Carrying a rendered PNG
into it means carrying forty kilobytes of base64 through a conversation in
six-kilobyte mouthfuls, every evening. Carrying the spec instead is two
kilobytes, and this file goes over once.

So this is the renderer, and the HTML one is gone. One renderer means the
picture the office gets is the picture that was checked.

Depends on Pillow built with raqm, which is what puts Hebrew the right way
round; without it the labels come out reversed and the numbers do not.
"""
import argparse
import json
import sys

from PIL import Image, ImageDraw, ImageFont

REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

INK = (12, 36, 48)
MUTED = (93, 118, 132)
LINE = (220, 214, 202)
SAND = (244, 239, 229)
WHITE = (255, 255, 255)
TIDE_BG = (241, 247, 249)

KINDS = {
    "lesson": ((11, 111, 128), (6, 82, 95)),
    "shift": ((217, 122, 26), (168, 89, 12)),
    "rental": ((106, 79, 168), (77, 55, 128)),
}

W = 1400          # the design's own width; everything else is measured off it
PAD = 30
NAMEW = 130
ROW = 59
TIDEH = 110
HEADH = 100


def has_hebrew(s):
    return any("֐" <= c <= "׿" for c in s)


class Pen:
    """A little wrapper that keeps the scale factor out of the drawing code."""

    def __init__(self, scale):
        self.s = scale
        self._f = {}

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self._f:
            self._f[key] = ImageFont.truetype(BLD if bold else REG,
                                              int(size * self.s))
        return self._f[key]

    def px(self, v):
        return int(round(v * self.s))

    def text(self, d, xy, s, size, colour, bold=False, anchor="la"):
        if not s:
            return
        kw = {"font": self.font(size, bold), "fill": colour, "anchor": anchor}
        if has_hebrew(s):
            kw["direction"] = "rtl"
        d.text((self.px(xy[0]), self.px(xy[1])), s, **kw)

    def width(self, s, size, bold=False):
        f = self.font(size, bold)
        kw = {"direction": "rtl"} if has_hebrew(s) else {}
        return f.getlength(s, **kw) / self.s

    def box(self, d, x0, y0, x1, y1, fill, radius=0):
        r = (self.px(x0), self.px(y0), self.px(x1), self.px(y1))
        if radius:
            d.rounded_rectangle(r, radius=self.px(radius), fill=fill)
        else:
            d.rectangle(r, fill=fill)

    def clip(self, s, size, room, bold=False):
        """Cut a label to the room it has, with an ellipsis if it lost any."""
        if self.width(s, size, bold) <= room:
            return s
        while s and self.width(s + "…", size, bold) > room:
            s = s[:-1]
        return (s + "…") if s else ""


def height(spec):
    rows = len(spec["rows"])
    h = HEADH + rows * ROW + PAD
    if spec.get("tide"):
        h += 16 + TIDEH
    if spec.get("key"):
        h += 26
    return h


def draw(spec, scale=2):
    p = Pen(scale)
    H = height(spec)
    im = Image.new("RGB", (p.px(W), p.px(H)), WHITE)
    d = ImageDraw.Draw(im)

    left = PAD + NAMEW                    # where the hour track begins
    right = W - PAD
    span = right - left
    lo, hi = spec["lo"], spec["hi"]

    def at(minute):
        return left + span * (minute - lo) / float(hi - lo)

    # --- head ---------------------------------------------------------------
    p.text(d, (PAD, 40), spec["title"], 26, INK, bold=True, anchor="ls")
    p.text(d, (right, 40), spec["sub"], 13, MUTED, anchor="rs")
    d.rectangle((p.px(PAD), p.px(52), p.px(right), p.px(52) + max(2, p.px(1))),
                fill=INK)

    for h in spec["hours"]:
        p.text(d, (at(h * 60), 72), "%02d" % h, 12, MUTED, anchor="ms")

    # --- the grid -----------------------------------------------------------
    y = HEADH
    for row in spec["rows"]:
        p.box(d, left, y, right, y + ROW - 1, SAND)
        for h in spec["hours"][1:]:
            x = at(h * 60)
            p.box(d, x, y, x + 0.5, y + ROW - 1, WHITE)
        d.rectangle((p.px(PAD), p.px(y + ROW - 1),
                     p.px(right), p.px(y + ROW - 1) + max(1, p.px(0.5))),
                    fill=LINE)
        p.text(d, (PAD, y + ROW / 2.0), row["who"], 15, INK, bold=True,
               anchor="lm")

        for b in row["bars"]:
            x0, x1 = at(b["x0"]), at(b["x1"])
            fill, edge = KINDS.get(b["kind"], KINDS["lesson"])
            p.box(d, x0, y + 5, x1 - 1, y + ROW - 6, fill, radius=5)
            p.box(d, x0, y + 5, x0 + 5, y + ROW - 6, edge, radius=2)
            room = (x1 - x0) - 16
            if b.get("sub"):
                p.text(d, (x0 + 9, y + 20), p.clip(b["label"], 11, room, True),
                       11, WHITE, bold=True, anchor="ls")
                p.text(d, (x0 + 9, y + 35), p.clip(b["sub"], 10.5, room),
                       10.5, (235, 242, 244), anchor="ls")
            else:
                p.text(d, (x0 + 9, y + 28), p.clip(b["label"], 11, room, True),
                       11, WHITE, bold=True, anchor="ls")
        y += ROW

    # --- the tide under it, on the same hours -------------------------------
    t = spec.get("tide")
    if t:
        y += 16
        p.box(d, left, y, right, y + TIDEH, TIDE_BG, radius=6)
        for h in spec["hours"][1:]:
            x = at(h * 60)
            p.box(d, x, y, x + 0.5, y + TIDEH, WHITE)
        p.text(d, (PAD, y + 10), t["label"], 13, INK, bold=True, anchor="lt")

        pts = t["points"]
        if len(pts) > 1:
            top = max(m for _, m in pts)
            bot = min(m for _, m in pts)
            rng = (top - bot) or 1.0
            xy = [(p.px(at(x)),
                   p.px(y + 12 + (TIDEH - 24) * (1 - (m - bot) / rng)))
                  for x, m in pts]
            d.line(xy, fill=KINDS["lesson"][0], width=max(2, p.px(1.6)),
                   joint="curve")

        for pk in t.get("peaks") or []:
            x = at(pk["x"])
            edge = "m"
            if x - left < span * 0.06:
                x, edge = x + 30, "m"
            elif right - x < span * 0.06:
                x, edge = x - 30, "m"
            base = y + 14 if pk["what"] == "high" else y + TIDEH - 52
            p.text(d, (x, base), pk["word"], 10, MUTED, anchor=edge + "t")
            p.text(d, (x, base + 13), pk["t"], 12, INK, bold=True,
                   anchor=edge + "t")
            p.text(d, (x, base + 28), "%.1f" % pk["m"], 11,
                   KINDS["lesson"][0], bold=True, anchor=edge + "t")
        y += TIDEH

    # --- what the colours mean ----------------------------------------------
    if spec.get("key"):
        y += 14
        x = left
        for k in spec["key"]:
            fill, _ = KINDS.get(k["kind"], KINDS["lesson"])
            p.box(d, x, y + 1, x + 13, y + 14, fill, radius=3)
            p.text(d, (x + 20, y + 2), k["word"], 12, MUTED, anchor="lt")
            x += 20 + p.width(k["word"], 12) + 22

    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", help="the JSON from board.py --spec, or - for stdin")
    ap.add_argument("out", help="where to write the PNG")
    ap.add_argument("--scale", type=float, default=2)
    ap.add_argument("--colours", type=int, default=32,
                    help="palette size. The picture is flat colour, so this "
                         "is lossless in practice and a third of the bytes.")
    a = ap.parse_args()
    spec = json.load(sys.stdin if a.spec == "-" else open(a.spec,
                                                          encoding="utf-8"))
    im = draw(spec, a.scale)
    if a.colours:
        im = im.quantize(colors=a.colours, method=Image.MEDIANCUT)
    im.save(a.out, optimize=True)
    print(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
