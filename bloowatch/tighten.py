"""Trim a Bloowatch board photograph down to what is actually booked.

The planner draws a row for every member of the crew and a grey divider for
every group, so a quiet day is mostly empty rows and the day itself is a thin
band across the top. WhatsApp will not show a picture that wide, and squeezing
one until it fits is what made the first attempts unreadable.

So: drop the rows with nothing on them, then cut the day into a few stacked
strips. Nothing is resampled - every pixel that survives is the pixel Bloowatch
drew - and the result is both smaller and easier to read.

    python3 tighten.py board.png tight.png [--strips 3] [--colours 16]
"""

import argparse
import sys

from PIL import Image

NAMEW = 306          # the crew-name column, repeated on every strip
GAP = 12             # white space between strips


def rows(im):
    """Where the horizontal rules are, read off the crew-name column."""
    px = im.load()
    w, h = im.size
    flat = []
    for y in range(h):
        lo, hi, total, n = 255, 0, 0, 0
        for x in range(10, min(NAMEW - 16, w), 3):
            v = sum(px[x, y]) // 3
            lo, hi, total, n = min(lo, v), max(hi, v), total + v, n + 1
        if hi - lo < 14 and 195 < total // n < 245:
            flat.append(y)
    if not flat:
        return 0, []
    runs = []
    for y in flat:
        if runs and y - runs[-1][-1] <= 2:
            runs[-1].append(y)
        else:
            runs.append([y])
    lines = [r[0] for r in runs]
    head = lines[1] if len(lines) > 1 else 0
    pitch = min(b - a for a, b in zip(lines[1:], lines[2:])) if len(lines) > 3 else 0
    if pitch < 8:
        return head, []
    bands = []
    y = head
    while y + pitch <= h:
        bands.append((y, y + pitch))
        y += pitch
    return head, bands


def busy(im, y0, y1):
    """Is there a booking on this row, as opposed to a group divider or nothing?

    A divider runs the whole width and starts hard against the left edge of the
    timeline; a booking starts where its hour is.
    """
    px = im.load()
    w = im.size[0]
    y = (y0 + y1) // 2 + 4
    spans, start = [], None
    for x in range(NAMEW, w):
        r, g, b = px[x, y][:3]
        solid = max(r, g, b) - min(r, g, b) > 10 or (r + g + b) // 3 < 215
        if solid and start is None:
            start = x
        elif not solid and start is not None:
            if x - start > 25:
                spans.append((start, x))
            start = None
    if start is not None and w - start > 25:
        spans.append((start, w))
    if not spans:
        return False
    return spans[0][0] - NAMEW > 100


def tighten(im, strips=3, overlap=0.12, only_booked=True):
    head, bands = rows(im)
    keep = ([b for b in bands if busy(im, *b)] or bands) if only_booked else bands
    rowh = keep[0][1] - keep[0][0]

    short = Image.new("RGB", (im.size[0], head + rowh * len(keep)), "white")
    short.paste(im.crop((0, 0, im.size[0], head)), (0, 0))
    for i, (y0, y1) in enumerate(keep):
        short.paste(im.crop((0, y0, im.size[0], y1)), (0, head + rowh * i))

    w, h = short.size
    day = w - NAMEW
    # Each strip reaches a little into the next one, so a lesson that lands on a
    # seam is still readable whole on one of them.
    span = int(day / (strips - overlap * (strips - 1))) if strips > 1 else day
    step = (day - span) // (strips - 1) if strips > 1 else 0
    cut = [(NAMEW + step * i, NAMEW + step * i + span) for i in range(strips)]
    cut[-1] = (w - span, w)
    wide = NAMEW + span
    out = Image.new("RGB", (wide, h * strips + GAP * (strips - 1)), "white")
    for i, (a, b) in enumerate(cut):
        top = (h + GAP) * i
        out.paste(short.crop((0, 0, NAMEW, h)), (0, top))
        out.paste(short.crop((a, 0, b, h)), (NAMEW, top))
    return out, len(keep), len(bands)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--strips", type=int, default=3)
    ap.add_argument("--colours", type=int, default=64,
                    help="palette size. 64 is indistinguishable from the "
                         "original here; at 32 the ink starts going brown and "
                         "at 8 the names turn pink, which is what made the "
                         "first sends look smeared.")
    ap.add_argument("--rows", choices=("booked", "all"), default="all",
                    help="'all' is the board as the office sees it, every "
                         "member of the crew and the group dividers. 'booked' "
                         "drops the rows with nothing on them.")
    a = ap.parse_args()

    im = Image.open(a.src).convert("RGB")
    out, kept, all_rows = tighten(im, a.strips, only_booked=a.rows == "booked")
    if a.colours:
        out = out.quantize(colors=a.colours, method=Image.MEDIANCUT)
    out.save(a.dst, optimize=True)
    print("%s %dx%d  %d of %d rows kept" % (a.dst, out.size[0], out.size[1],
                                            kept, all_rows), file=sys.stderr)


if __name__ == "__main__":
    main()
