#!/usr/bin/env python3
"""A small animated send-off for whoever the planner has marked away.

    python3 dayoff.py "Yuval,Gur,Ella" out.gif

The rota is a list of work, and the people who are not working vanish from
it. Naming them costs one line; this costs a second message and says the
thing the line cannot -- that a day off at a surf school is the whole
point of working at one.

Drawn rather than fetched. A GIF search would need a key, a licence and a
network round trip on a schedule that has to be dependable at seven in the
evening; this needs Pillow, which is already here, and it comes out the
same every time.
"""

import argparse
import math
import sys

from PIL import Image, ImageDraw, ImageFont

REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 720, 720
FRAMES, MS = 24, 90

SKY_TOP = (86, 170, 214)
SKY_LOW = (168, 220, 236)
SUN = (255, 222, 120)
SEA = (44, 132, 176)
SEA_LOW = (30, 108, 150)
FOAM = (236, 248, 252)
SAND = (238, 214, 168)
SAND_DARK = (222, 194, 146)
TRUNK = (128, 94, 62)
LEAF = (58, 148, 96)
LEAF_DARK = (40, 118, 76)
BOARD = (246, 246, 248)
BOARD_STRIPE = (226, 86, 106)
INK = (28, 52, 68)

HORIZON = int(H * 0.52)
SHORE = int(H * 0.66)


def font(path, size):
    return ImageFont.truetype(path, size)


def sky(d):
    for y in range(HORIZON):
        f = y / float(HORIZON)
        d.line((0, y, W, y), fill=tuple(
            int(a + (b - a) * f) for a, b in zip(SKY_TOP, SKY_LOW)))


def sun(d, t):
    # a slow breath, so the loop never sits perfectly still
    r = 62 + 3 * math.sin(t * 2 * math.pi)
    cx, cy = W * 0.78, HORIZON * 0.34
    d.ellipse((cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16),
              fill=(255, 236, 176))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SUN)


def sea(d, t):
    d.rectangle((0, HORIZON, W, SHORE), fill=SEA)
    d.rectangle((0, HORIZON, W, HORIZON + 6), fill=SEA_LOW)
    # three ranks of swell, each drifting at its own pace
    for i, (y, speed, amp) in enumerate(((0.22, 1.0, 5), (0.55, 1.6, 7),
                                         (0.84, 2.3, 9))):
        base = HORIZON + (SHORE - HORIZON) * y
        shift = t * W * speed
        pts = []
        for x in range(-40, W + 41, 8):
            pts.append((x, base + amp * math.sin((x + shift) / 46.0)))
        d.line(pts, fill=FOAM, width=3 + i, joint="curve")


def beach(d, t):
    d.rectangle((0, SHORE, W, H), fill=SAND)
    # the water's edge running up the sand and back
    reach = 16 * math.sin(t * 2 * math.pi)
    pts = []
    for x in range(-40, W + 41, 8):
        pts.append((x, SHORE + 10 + reach + 6 * math.sin((x - t * W) / 60.0)))
    d.line(pts + [(W + 40, SHORE - 20), (-40, SHORE - 20)], fill=FOAM, width=7,
           joint="curve")
    for k in range(9):                       # a little texture in the sand
        y = SHORE + 40 + k * 22
        d.line((0, y, W, y + 4), fill=SAND_DARK, width=2)


def palm(d, t):
    """A palm leaning over the frame, its fronds moving in the wind."""
    sway = math.sin(t * 2 * math.pi) * 0.05
    x0, y0 = 118, H - 40                     # foot of the trunk
    top = (x0 + 104 + 26 * math.sin(t * 2 * math.pi), SHORE - 268)
    trunk = []
    for i in range(21):
        f = i / 20.0
        trunk.append((x0 + (top[0] - x0) * f + 30 * math.sin(f * 1.7),
                      y0 + (top[1] - y0) * f))
    for i, wide in enumerate((22, 18, 14)):  # a trunk that tapers as it rises
        cut = int(len(trunk) * (i + 1) / 3.0)
        d.line(trunk[:cut + 1], fill=TRUNK, width=wide, joint="curve")

    # fronds spring up and out of the crown, then droop under their own
    # weight -- an arc, not a spoke, which is what made it look like a spider
    for k in range(8):
        a = math.radians(-172 + k * 24) + sway
        L = 172 if k % 2 else 148
        arc = []
        for j in range(11):
            f = j / 10.0
            arc.append((top[0] + math.cos(a) * L * f,
                        top[1] + math.sin(a) * L * f + 92 * f * f))
        d.line(arc, fill=LEAF if k % 2 else LEAF_DARK,
               width=14, joint="curve")
        for j in (4, 6, 8):                  # a hint of the leaflets
            px, py = arc[j]
            nx, ny = arc[j - 1]
            dx, dy = px - nx, py - ny
            d.line((px - dy * 0.5, py + dx * 0.5,
                    px + dy * 0.5, py - dx * 0.5),
                   fill=LEAF_DARK if k % 2 else LEAF, width=5)
    d.ellipse((top[0] - 17, top[1] - 17, top[0] + 17, top[1] + 17),
              fill=TRUNK)


def board(d):
    """A surfboard planted in the sand, because that is the whole idea."""
    cx, cy = W - 150, SHORE + 40
    box = (cx - 34, cy - 210, cx + 34, cy + 130)
    d.ellipse((cx - 46, cy + 108, cx + 46, cy + 142), fill=SAND_DARK)
    d.rounded_rectangle(box, radius=34, fill=BOARD, outline=(206, 210, 216),
                        width=3)
    d.rounded_rectangle((cx - 8, cy - 190, cx + 8, cy + 110), radius=8,
                        fill=BOARD_STRIPE)


def words(im, names, lang):
    d = ImageDraw.Draw(im)
    line = ("תהנה ביום חופש" if len(names) == 1 else "תהנו ביום חופש") \
        if lang == "he" else \
        ("Enjoy your day off" if len(names) == 1 else "Enjoy your day off")
    who = " · ".join(names)

    def plate(y, text, size, path, colour):
        f = font(path, size)
        kw = {"direction": "rtl"} if lang == "he" and any(
            "֐" <= c <= "׿" for c in text) else {}
        w = d.textlength(text, font=f, **kw)
        d.rounded_rectangle((W / 2 - w / 2 - 26, y - 12,
                             W / 2 + w / 2 + 26, y + size + 16),
                            radius=18, fill=(255, 255, 255, 255))
        d.text((W / 2, y + size / 2 + 2), text, font=f, fill=colour,
               anchor="mm", **kw)
        return y + size + 34

    y = 44
    y = plate(y, who, 46, BLD, INK)
    plate(y, line, 34, REG, (58, 96, 122))


def frame(t, names, lang):
    im = Image.new("RGB", (W, H), SKY_TOP)
    d = ImageDraw.Draw(im)
    sky(d)
    sun(d, t)
    sea(d, t)
    beach(d, t)
    palm(d, t)
    board(d)
    words(im, names, lang)
    return im


def make(names, out, lang="he", frames=FRAMES):
    ims = [frame(i / float(frames), names, lang) for i in range(frames)]
    ims = [im.quantize(colors=96, method=Image.MEDIANCUT) for im in ims]
    ims[0].save(out, save_all=True, append_images=ims[1:], duration=MS,
                loop=0, optimize=True, disposal=2)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("names", help="comma separated, e.g. \"Yuval,Ella\"")
    ap.add_argument("out")
    ap.add_argument("--lang", choices=("he", "en"), default="he")
    a = ap.parse_args()
    names = [n.strip() for n in a.names.split(",") if n.strip()]
    if not names:
        print("nobody is off", file=sys.stderr)
        return 1
    print(make(names, a.out, a.lang))
    return 0


if __name__ == "__main__":
    sys.exit(main())
