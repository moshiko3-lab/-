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
round; without it the labels come out reversed and the numbers do not. It
also depends on DejaVu, which is the only family both machines have.
"""
import argparse
import json
import sys

from PIL import Image, ImageDraw, ImageFont

REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# The office reads the Bloowatch board all day, so this one wears the same
# clothes: pale blocks with a darker rule down their leading edge, dark text
# on them rather than white, a hatched ground where nothing is booked, and a
# periwinkle band carrying the date and the hours. Familiar beats striking --
# a picture the team can read without being taught to read it.
INK = (30, 41, 56)
SLATE = (86, 99, 117)
MUTED = (140, 150, 165)
HAIR = (228, 231, 238)          # separators between rows
GRID = (236, 239, 245)          # the hour lines inside the day
HATCH = (245, 246, 250)         # the diagonal weave of an empty hour
BAND = (226, 232, 243)          # the date and hour band
BAND_INK = (46, 62, 92)
WHITE = (255, 255, 255)
TIDE_BG = (247, 249, 252)
TIDE_FILL = (226, 236, 246)
TIDE_LINE = (94, 122, 176)

# fill, leading edge, text
KINDS = {
    "lesson": ((240, 223, 237), (168, 108, 152), (74, 45, 66)),
    "shift": ((223, 231, 245), (92, 121, 176), (35, 52, 82)),
    "rental": ((222, 239, 228), (82, 148, 108), (28, 64, 43)),
}

W = 1400          # the design's own width; everything else is measured off it
PAD = 34
NAMEW = 136
ROW = 62
TIDEH = 118
BANDH = 26
HEADH = 100
FOOTH = 46


def has_hebrew(s):
    return any("֐" <= c <= "׿" for c in s)


class Pen:
    """Keeps the scale factor and the font cache out of the drawing code."""

    def __init__(self, scale):
        self.s = scale
        self._f = {}

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self._f:
            self._f[key] = ImageFont.truetype(BLD if bold else REG,
                                              int(round(size * self.s)))
        return self._f[key]

    def px(self, v):
        return int(round(v * self.s))

    def text(self, d, xy, s, size, colour, bold=False, anchor="la",
             spacing=None):
        if not s:
            return
        kw = {"font": self.font(size, bold), "fill": colour, "anchor": anchor}
        if has_hebrew(s):
            kw["direction"] = "rtl"
        elif spacing:
            kw["features"] = None
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

    def rule(self, d, x0, y, x1, colour, weight=1):
        d.rectangle((self.px(x0), self.px(y), self.px(x1),
                     self.px(y) + max(1, self.px(weight))), fill=colour)

    def hatch(self, im, d, x0, y0, x1, y1, step=9):
        """The weave the board upstairs puts in an hour nobody has booked."""
        self.box(d, x0, y0, x1, y1, WHITE)
        w, h = self.px(x1) - self.px(x0), self.px(y1) - self.px(y0)
        if w <= 0 or h <= 0:
            return
        tile = Image.new("RGB", (w, h), WHITE)
        td = ImageDraw.Draw(tile)
        gap = self.px(step)
        for k in range(-h, w + h, gap):
            td.line((k, h, k + h, 0), fill=HATCH, width=max(1, self.px(1)))
        im.paste(tile, (self.px(x0), self.px(y0)))

    def split(self, s):
        """Break a label into two lines at the most natural seam it has."""
        for sep in (", ", " · ", " "):
            if sep in s:
                a, _, b = s.partition(sep)
                return a.rstrip(","), b
        return s, ""

    def clip(self, s, size, room, bold=False):
        """Cut a label to the room it has, with an ellipsis if it lost any."""
        if not s or self.width(s, size, bold) <= room:
            return s
        while s and self.width(s + "…", size, bold) > room:
            s = s[:-1]
        return (s + "…") if s else ""


def height(spec):
    h = HEADH + len(spec["rows"]) * ROW
    if spec.get("tide"):
        h += 22 + TIDEH
    return h + FOOTH


def draw(spec, scale=2):
    p = Pen(scale)
    im = Image.new("RGB", (p.px(W), p.px(height(spec))), WHITE)
    d = ImageDraw.Draw(im)

    left = PAD + NAMEW                    # where the hour track begins
    right = W - PAD
    span = right - left
    lo, hi = spec["lo"], spec["hi"]

    def at(minute):
        return left + span * (minute - lo) / float(hi - lo)

    # --- masthead -----------------------------------------------------------
    p.text(d, (PAD, 40), spec["sub"], 18, INK, bold=True, anchor="ls")
    if spec.get("stat"):
        p.text(d, (right, 40), spec["stat"], 12.5, MUTED, anchor="rs")

    # the band the hours sit in, the way the board upstairs carries them
    p.box(d, PAD, 58, right, 58 + BANDH, BAND)
    p.text(d, (PAD + 12, 58 + BANDH / 2.0), spec.get("band") or "", 12.5,
           BAND_INK, bold=True, anchor="lm")
    for i, h in enumerate(spec["hours"]):
        anchor = "mm"
        if i == len(spec["hours"]) - 1:
            anchor = "rm"                 # or half of it hangs off the edge
        elif i == 0:
            anchor = "lm"
        p.text(d, (at(h * 60), 58 + BANDH / 2.0), "%02d:00" % h, 11,
               BAND_INK, anchor=anchor)

    # --- the day ------------------------------------------------------------
    y = HEADH
    for row in spec["rows"]:
        p.hatch(im, d, left, y, right, y + ROW)
        for h in spec["hours"][1:-1]:
            x = at(h * 60)
            p.box(d, x, y, x + 0.6, y + ROW, GRID)
        p.rule(d, PAD, y + ROW, right, HAIR)
        p.text(d, (left - 12, y + ROW / 2.0), row["who"].upper(), 12.5, SLATE,
               bold=True, anchor="rm")

        for b in row["bars"]:
            x0, x1 = at(b["x0"]), at(b["x1"])
            fill, edge, ink = KINDS.get(b["kind"], KINDS["lesson"])
            p.box(d, x0, y + 7, x1 - 1, y + ROW - 7, fill, radius=3)
            p.box(d, x0, y + 7, x0 + 3.5, y + ROW - 7, edge)

            room = (x1 - x0) - 18
            when = b.get("when") or ""
            wlen = p.width(when, 10)
            if when and room > p.width(b["label"], 11, True) + wlen + 26:
                p.text(d, (x1 - 9, y + ROW / 2.0), when, 10, edge, anchor="rm")
                room -= wlen + 16
            top, sub = b["label"], b.get("sub") or ""
            if not sub and p.width(top, 11, True) > room:
                # two names on an hour-wide block fit stacked, and stacked they
                # are still both names -- clipped they are "Jim, Nie…"
                top, sub = p.split(top)
            if sub:
                p.text(d, (x0 + 10, y + 21), p.clip(top, 11, room, True),
                       11, ink, bold=True, anchor="ls")
                p.text(d, (x0 + 10, y + 37), p.clip(sub, 10, room), 10,
                       edge, anchor="ls")
            else:
                p.text(d, (x0 + 10, y + ROW / 2.0),
                       p.clip(top, 11, room, True), 11, ink, bold=True,
                       anchor="lm")
        y += ROW

    # --- the tide under it, on the same hours -------------------------------
    t = spec.get("tide")
    if t:
        y += 22
        p.box(d, left, y, right, y + TIDEH, TIDE_BG, radius=8)
        for h in spec["hours"][1:-1]:
            x = at(h * 60)
            p.box(d, x, y, x + 0.6, y + TIDEH, WHITE)
        p.text(d, (left - 14, y + 12), t["label"], 13, INK, bold=True,
               anchor="rt")

        pts = t["points"]
        if len(pts) > 1:
            top = max(m for _, m in pts)
            bot = min(m for _, m in pts)
            rng = (top - bot) or 1.0
            top_y, bot_y = y + 26, y + TIDEH - 16

            def ty(m):
                return bot_y - (bot_y - top_y) * (m - bot) / rng

            xy = [(p.px(at(x)), p.px(ty(m))) for x, m in pts]
            # the water is an area, not a wire: filled, it reads as a level
            d.polygon(xy + [(p.px(right), p.px(bot_y + 8)),
                            (p.px(left), p.px(bot_y + 8))], fill=TIDE_FILL)
            d.line(xy, fill=TIDE_LINE, width=max(2, p.px(1.7)),
                   joint="curve")

            for pk in t.get("peaks") or []:
                x, my = at(pk["x"]), ty(pk["m"])
                r = p.px(3.5)
                d.ellipse((p.px(x) - r, p.px(my) - r, p.px(x) + r,
                           p.px(my) + r), fill=TIDE_LINE,
                          outline=WHITE, width=max(1, p.px(1)))
                anchor, tx = "m", x
                if x - left < 46:
                    anchor, tx = "l", left + 6
                elif right - x < 46:
                    anchor, tx = "r", right - 6
                if pk["what"] == "high":
                    base = my + 12
                else:
                    base = my - 48
                p.text(d, (tx, base), pk["word"], 10, MUTED, anchor=anchor + "t")
                p.text(d, (tx, base + 13), pk["t"], 12.5, INK, bold=True,
                       anchor=anchor + "t")
                p.text(d, (tx, base + 29), "%.1f" % pk["m"], 10.5,
                       TIDE_LINE, bold=True, anchor=anchor + "t")
        y += TIDEH

    # --- what the colours mean ----------------------------------------------
    y += 16
    p.rule(d, PAD, y, right, HAIR)
    y += 13
    x = PAD
    for k in spec.get("key") or []:
        fill, edge, _ = KINDS.get(k["kind"], KINDS["lesson"])
        p.box(d, x, y + 2, x + 12, y + 14, fill, radius=2)
        p.box(d, x, y + 2, x + 3, y + 14, edge)
        p.text(d, (x + 19, y + 2), k["word"], 11.5, SLATE, anchor="lt")
        x += 19 + p.width(k["word"], 11.5) + 24
    if spec.get("foot"):
        p.text(d, (right, y + 2), spec["foot"], 11.5, MUTED, anchor="rt")

    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("spec", help="the JSON from board.py --spec, or - for stdin")
    ap.add_argument("out", help="where to write the PNG")
    ap.add_argument("--scale", type=float, default=2)
    ap.add_argument("--colours", type=int, default=48,
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
