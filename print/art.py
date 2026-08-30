"""The artwork the brochure is built on, drawn rather than photographed.

Every picture in the brochure is a slot. If there is a photograph in
`print/images/` for that slot it wins; when there is not, one of these routines
fills it, and the page is still finished rather than a grey box with a cross
through it.

The drawings are all line work on a flat field -- contours read off a smooth
scalar field, swell lines, a wave with somebody in it -- because flat colour
and clean line on paper are what an expensive brochure looks like and what a cheap printer can
still hold. Everything is seeded, so the same page draws the same picture every
time and a reprint matches the copy already in the rooms.
"""

import math


# --------------------------------------------------------------------------
# A smooth scalar field: a handful of sinusoids at different scales and angles,
# which is enough to look like ground without the machinery of real noise.
# --------------------------------------------------------------------------
def _waves(seed, octaves=5):
    rnd = _rng(seed)
    out = []
    for k in range(octaves):
        freq = 0.85 * (1.7 ** k)
        ang = rnd() * math.tau
        out.append((freq * math.cos(ang), freq * math.sin(ang),
                    rnd() * math.tau, 1.0 / (1.35 ** k)))
    return out


def _rng(seed):
    """A small deterministic generator, so artwork never depends on the
    platform's random module changing under it."""
    state = [seed & 0xFFFFFFFF or 1]

    def nxt():
        x = state[0]
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        state[0] = x
        return x / 0xFFFFFFFF
    return nxt


def _sample(wv, x, y):
    v = 0.0
    for wx, wy, ph, amp in wv:
        v += amp * math.sin(wx * x + wy * y + ph)
    return v


# --------------------------------------------------------------------------
# Marching squares: pull iso-lines out of the field, join the loose segments
# into runs, and round the corners off. Drawing the segments unjoined is much
# less code and looks it -- every line ends in a visible stub.
# --------------------------------------------------------------------------
def _isolines(wv, level, nx, ny, w, h):
    gx, gy = w / (nx - 1.0), h / (ny - 1.0)
    val = [[_sample(wv, i * gx / w * 3.0, j * gy / h * 3.0) - level
            for j in range(ny)] for i in range(nx)]

    def cut(a, b, pa, pb):                     # where the level crosses an edge
        t = 0.5 if a == b else a / (a - b)
        return (pa[0] + (pb[0] - pa[0]) * t, pa[1] + (pb[1] - pa[1]) * t)

    segs = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            a, b = val[i][j], val[i + 1][j]
            c, d = val[i + 1][j + 1], val[i][j + 1]
            idx = (a > 0) | ((b > 0) << 1) | ((c > 0) << 2) | ((d > 0) << 3)
            if idx in (0, 15):
                continue
            p = [(i * gx, j * gy), ((i + 1) * gx, j * gy),
                 ((i + 1) * gx, (j + 1) * gy), (i * gx, (j + 1) * gy)]
            e = {0: cut(a, b, p[0], p[1]), 1: cut(b, c, p[1], p[2]),
                 2: cut(c, d, p[2], p[3]), 3: cut(d, a, p[3], p[0])}
            for u, v in _CASES[idx]:
                segs.append((e[u], e[v]))
    return _join(segs)


# Which edges the line runs between, per corner-sign case. The two saddles (5
# and 10) get both crossings; picking one at random is what makes contour art
# look like it has holes punched in it.
_CASES = {
    1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)],
    5: [(3, 0), (1, 2)], 6: [(0, 2)], 7: [(3, 2)], 8: [(2, 3)],
    9: [(2, 0)], 10: [(0, 1), (2, 3)], 11: [(2, 1)], 12: [(1, 3)],
    13: [(1, 0)], 14: [(0, 3)],
}


def _join(segs, tol=3):
    ends = {}
    for s in segs:
        for k, pt in ((0, s[0]), (1, s[1])):
            ends.setdefault((round(pt[0], tol), round(pt[1], tol)), []).append((s, k))

    used, runs = set(), []
    for s in segs:
        if id(s) in used:
            continue
        used.add(id(s))
        run = [s[0], s[1]]
        for end in (1, 0):                                  # grow both ways
            while True:
                tip = run[-1] if end else run[0]
                nxt = None
                for cand, k in ends.get((round(tip[0], tol), round(tip[1], tol)), ()):
                    if id(cand) not in used:
                        nxt = (cand, k)
                        break
                if not nxt:
                    break
                cand, k = nxt
                used.add(id(cand))
                far = cand[1 - k]
                run.append(far) if end else run.insert(0, far)
        if len(run) > 3:
            runs.append(run)
    return runs


def _chaikin(pts, rounds=2):
    for _ in range(rounds):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            out.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            out.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        out.append(pts[-1])
        pts = out
    return pts


def _path(pts):
    return "M" + "L".join("%.1f %.1f" % p for p in pts)


# --------------------------------------------------------------------------
# The pieces
# --------------------------------------------------------------------------
def contours(w, h, seed=7, lines=26, stroke="#F46E95", ground=None,
             width=0.9, opacity=1.0, grid=(120, 150)):
    """Ground read as contour lines -- the reef under the break, more or less.
    Fine, even hairlines with a lot of paper showing through."""
    wv = _waves(seed)
    nx, ny = grid
    d = []
    for k in range(lines):
        level = -1.55 + 3.1 * (k + 0.5) / lines
        for run in _isolines(wv, level, nx, ny, w, h):
            d.append(_path(_chaikin(run)))
    body = ('<g fill="none" stroke="%s" stroke-width="%s" stroke-opacity="%s" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="%s"/></g>'
            % (stroke, width, opacity, "".join(d)))
    return _svg(w, h, body, ground)


def swell(w, h, seed=3, lines=16, stroke="#F46E95", ground=None,
          width=1.0, opacity=1.0):
    """Lines of swell marching in: the same wave sampled again and again as it
    moves up the page, so the spacing tightens the way real sets do."""
    rnd = _rng(seed)
    ph = [rnd() * math.tau for _ in range(4)]
    d = []
    for i in range(lines):
        t = i / (lines - 1.0)
        y = h * (0.06 + 0.88 * t * t)                      # crowding downward
        amp = h * (0.012 + 0.055 * t)
        pts = []
        for s in range(0, 81):
            x = -w * 0.05 + w * 1.1 * s / 80.0
            u = x / w * math.tau
            pts.append((x, y + amp * (math.sin(u * 1.1 + ph[0] + i * .28)
                                      + .45 * math.sin(u * 2.3 + ph[1] - i * .17)
                                      + .22 * math.sin(u * 3.9 + ph[2]))))
        d.append(_path(pts))
    body = ('<g fill="none" stroke="%s" stroke-width="%s" stroke-opacity="%s" '
            'stroke-linecap="round"><path d="%s"/></g>'
            % (stroke, width, opacity, "".join(d)))
    return _svg(w, h, body, ground)


def tide(w, h, stroke="#F46E95", ground=None, width=1.0, hours=13):
    """The day's tide, the curve the school plans its sessions against. Drawn
    with its hour ticks, because a chart without them is just a squiggle."""
    d, base = [], h * 0.52
    pts = [(w * i / 240.0, base - h * 0.26 * math.sin(i / 240.0 * math.tau * 1.6 - 0.7))
           for i in range(241)]
    d.append(_path(pts))
    for i in range(hours):
        x = w * i / (hours - 1.0)
        d.append("M%.1f %.1fv%.1f" % (x, h * 0.80, h * 0.045))
    d.append("M0 %.1fH%.1f" % (h * 0.80, w))
    body = ('<g fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round">'
            '<path d="%s"/></g>' % (stroke, width, "".join(d)))
    return _svg(w, h, body, ground)


def _svg(w, h, body, ground, box=None, fit="slice"):
    """`box` lets a drawing keep its own coordinate space -- the wave is drawn
    once at 1000x640 and then cropped to whatever shape the page gives it.

    `fit` is "slice" for pictures, which should fill their box and lose their
    edges the way a photograph would, and "meet" for the chart, which must not:
    cropping a chart eats its axis labels, which is exactly what happened the
    first time this shipped."""
    bw, bh = box or (w, h)
    bg = '<rect width="%s" height="%s" fill="%s"/>' % (bw, bh, ground) if ground else ""
    return ('<svg class="art" viewBox="0 0 %s %s" preserveAspectRatio="xMidYMid %s" '
            'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">%s%s</svg>'
            % (bw, bh, fit, bg, body))


# --------------------------------------------------------------------------
# The boards, drawn as outlines and stood on their tails in the order the
# rental list names them. It is a picture and a key at the same time: the eye
# matches shape to word without either being labelled twice.
# --------------------------------------------------------------------------
#          length  width  nose  tail  peak  draw  foil
BOARDS = [(0.84,   0.320, 0.46, 0.66, 0.52, 0.80, False),   # soft-boards
          (0.77,   0.280, 0.36, 0.58, 0.52, 0.92, False),   # fun-boards
          (0.60,   0.212, 0.12, 0.46, 0.50, 1.45, False),   # short-boards
          (0.63,   0.194, 0.08, 0.38, 0.48, 1.70, False),   # high performance
          (1.00,   0.276, 0.52, 0.62, 0.56, 0.74, False),   # longboards
          (0.98,   0.354, 0.49, 0.70, 0.55, 0.70, False),   # sup
          (0.40,   0.344, 0.82, 0.90, 0.55, 0.90, False),   # bodyboards
          (0.62,   0.228, 0.22, 0.50, 0.50, 1.28, True)]    # foil


def _profile(t, nose, tail, peak, draw):
    """How wide the board is, a fraction of its widest point, at t from nose to
    tail. `draw` is how hard the curve is pulled in: low is the forgiving foam
    a beginner stands up on, high the narrow blade that will not forgive."""
    if t <= peak:
        u = t / peak
        return nose + (1 - nose) * math.sin(u * math.pi / 2) ** draw
    u = (1 - t) / (1 - peak)
    return tail + (1 - tail) * math.sin(u * math.pi / 2) ** draw


def _outline(cx, top, length, half, nose, tail, peak, draw, n=44):
    right = []
    for i in range(n + 1):
        t = i / float(n)
        right.append((cx + half * _profile(t, nose, tail, peak, draw),
                      top + t * length))
    left = [(2 * cx - x, y) for x, y in reversed(right)]
    wn, wt = half * nose, half * tail
    # Rounded off at both ends rather than closed flat: a board has no corners.
    return ("M%.1f %.1f" % right[0]
            + "L" + "L".join("%.1f %.1f" % p for p in right[1:])
            + "Q%.1f %.1f %.1f %.1f" % (cx, top + length + wt * 0.95,
                                        left[0][0], left[0][1])
            + "L" + "L".join("%.1f %.1f" % p for p in left[1:])
            + "Q%.1f %.1f %.1f %.1f" % (cx, top - wn * 0.95, right[0][0], right[0][1])
            + "Z")


def boards_row(w, h, stroke="#C9436B", ground=None, width=0.85, pad=0.15):
    """The rack. Everything is proportional to the longest board, so the
    longboard and the bodyboard come out the right sizes relative to each
    other instead of each being drawn to fill its own slot."""
    slot = w / float(len(BOARDS))
    tall = h * (1 - 2 * pad)
    floor = h * (1 - pad)
    d = []
    for i, (ln, wd, nose, tail, peak, draw, foil) in enumerate(BOARDS):
        cx = slot * (i + 0.5)
        length = tall * ln
        half = slot * 0.98 * wd / 2.0
        top = floor - length
        d.append(_outline(cx, top, length, half, nose, tail, peak, draw))
        d.append("M%.1f %.1fV%.1f" % (cx, top + length * 0.05,
                                      top + length * 0.95))     # the stringer
        if foil:
            my = top + length * 0.58
            d.append("M%.1f %.1fV%.1f" % (cx, my, floor + h * 0.055))
            d.append("M%.1f %.1fq%.1f %.1f %.1f 0"
                     % (cx - half * 1.5, floor + h * 0.055, half * 1.5,
                        -h * 0.05, half * 3.0))
    body = ('<g fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="%s"/></g>'
            % (stroke, width, "".join(d)))
    return _svg(w, h, body, ground)


# --------------------------------------------------------------------------
# The wave
#
# A brochure for a surf school has to open with a wave, and there is no
# photograph to open it with, so this one is built the way a screen printer
# would build it: three or four flat tones, no gradients, every edge a curve
# somebody chose. The figure is small on purpose. A wave with a person on it
# reads as surfing; the same wave without one reads as weather.
# --------------------------------------------------------------------------
def wave(w, h, deep="#0A222A", body="#17515E", foam="#F5F0E6", spray=None,
         rider=True, ground=None):
    # No rider, no spray: the back cover wants the shape of a wave behind the
    # type, and loose dots up in the air read as dirt on the page rather than
    # as water once there is nobody throwing them.
    spray = spray or foam
    p = []

    # the mass of water: trough at the left, rising to the crest at the right
    p.append('<path fill="%s" d="M0 640V560C140 540 260 490 360 415'
             'C460 340 540 235 630 172C712 114 800 96 868 116'
             'C936 136 984 190 1000 250V640Z"/>' % body)

    # two long runs up the open face, the way water draws off before it stands
    for x0, y0, x1, y1, x2, y2 in ((152, 528, 306, 474, 436, 402),
                                   (188, 578, 348, 520, 480, 446)):
        p.append('<path fill="none" stroke="%s" stroke-opacity=".13" stroke-width="7" '
                 'stroke-linecap="round" d="M%d %dQ%d %d %d %d"/>'
                 % (foam, x0, y0, x1, y1, x2, y2))

    # the tube: an almond, not a wedge -- it is an opening, and there is
    # daylight at the far end of it
    p.append('<path fill="%s" d="M452 352C505 270 592 216 690 205'
             'C768 196 822 218 848 254C800 292 730 330 660 352'
             'C590 374 512 372 452 352Z"/>' % deep)

    if rider:
        # In the barrel, in foam against the dark, because that is the only
        # place on a wave where a figure this small still reads. Built from
        # round-capped strokes rather than one filled outline: at 8mm on paper
        # a limb of even weight reads and a clever silhouette does not.
        p.append('<g transform="translate(578 236) rotate(10) scale(0.80)" '
                 'stroke="%s" stroke-linecap="round" fill="none">'
                 '<path fill="%s" stroke="none" d="M0 92C30 82 108 79 132 86'
                 'C104 96 28 100 0 92Z"/>'
                 '<circle cx="62" cy="18" r="7.5" fill="%s" stroke="none"/>'
                 '<path stroke-width="11" d="M62 27L71 53"/>'
                 '<path stroke-width="7" d="M60 33C46 36 30 41 18 45"/>'
                 '<path stroke-width="7" d="M67 32C80 28 92 23 104 20"/>'
                 '<path stroke-width="8" d="M71 53C64 64 54 76 45 86"/>'
                 '<path stroke-width="8" d="M71 53C80 63 88 74 94 85"/>'
                 '</g>' % (foam, foam, foam))

    # the lip, thrown forward and already coming apart at the tip
    p.append('<path fill="%s" d="M868 118C776 92 678 116 598 176'
             'C520 234 460 306 430 352C470 300 520 262 592 232'
             'C668 200 772 190 846 226C868 212 876 168 868 118Z"/>' % foam)

    # spray off the back of it, thinning as it goes
    if rider:
        for i, (x, y, r) in enumerate(((884, 98, 15), (920, 116, 11), (856, 76, 9),
                                       (948, 142, 8), (904, 64, 6), (968, 112, 5))):
            p.append('<circle cx="%d" cy="%d" r="%d" fill="%s" fill-opacity="%.2f"/>'
                     % (x, y, r, spray, 0.92 - i * 0.11))

    # whitewater along the trough
    p.append('<path fill="%s" fill-opacity=".95" d="M0 640V556C92 538 172 543 240 566'
             'C308 589 376 595 444 585C524 573 600 580 672 607'
             'C720 625 764 631 804 629V640Z"/>' % foam)

    return _svg(w, h, "".join(p), ground, box=(1000, 640))


# --------------------------------------------------------------------------
# The line-up
#
# The other half of surfing, and the half a brochure never shows: three people
# sitting on their boards, out past the break, waiting. It is the view from the
# water rather than of it, and at this size a seated figure reads instantly --
# a head, a torso, a board on the line.
# --------------------------------------------------------------------------
def _sitter(x, y, scale, ink):
    """Someone sitting their board, seen side-on, cut off at the waterline.
    Same build as the rider in the barrel -- round-capped strokes of even
    weight -- so the two figures in this booklet are recognisably one hand."""
    return ('<g transform="translate(%.1f %.1f) scale(%.3f)" stroke="%s" '
            'stroke-linecap="round" fill="none">'
            '<path fill="%s" stroke="none" d="M-34-1C-19-9 14-11 34-6'
            'L35 0C19 5-16 7-34-1Z"/>'
            '<path stroke-width="9" d="M0-4L6-26"/>'
            '<circle cx="8" cy="-35" r="6.2" fill="%s" stroke="none"/>'
            '<path stroke-width="6" d="M4-23C-2-19-9-13-13-7"/>'
            '</g>' % (x, y, scale, ink, ink, ink))


def lineup(w, h, ink="#14262C", line="#D24870", ground=None, sun_at=0.76):
    hz = h * 0.30
    d = ['<path fill="none" stroke="%s" stroke-width="1.6" stroke-opacity=".55" '
         'd="M0 %.1fH%.1f"/>' % (line, hz, w)]

    # the sun, half in the water, where the light in a photograph would be
    d.append('<clipPath id="lz"><rect x="0" y="0" width="%.0f" height="%.1f"/></clipPath>'
             % (w, hz))
    d.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
             'stroke-width="1.6" clip-path="url(#lz)"/>'
             % (w * sun_at, hz, h * 0.135, line))

    # swell coming in, opening out as it nears
    for i in range(9):
        t = (i + 1) / 9.0
        y = hz + (h - hz) * (t ** 1.7)
        amp = h * 0.012 * (0.4 + t)
        pts = ["%.1f %.1f" % (x, y + amp * math.sin(x / w * 7.4 + i))
               for x in range(-20, int(w) + 21, 24)]
        d.append('<path fill="none" stroke="%s" stroke-width="%.2f" '
                 'stroke-opacity="%.2f" stroke-linecap="round" d="M%s"/>'
                 % (line, 1.2 + 1.3 * t, 0.30 + 0.42 * t, "L".join(pts)))

    for x, y, sc in ((0.20, 0.60, 1.00), (0.45, 0.75, 1.28), (0.66, 0.545, 0.84)):
        d.append(_sitter(w * x, hz + (h - hz) * y, sc * h / 300.0, ink))

    return _svg(w, h, "".join(d), ground)


# --------------------------------------------------------------------------
# The quiver, counted
#
# One bar per foot of board, hard and soft stacked, in length order rather than
# in size order -- the rack is read from short to long and so is this. It is
# the one place in the booklet with real numbers in it, and they say something
# a sentence cannot: the eights are almost all foam and the fives are none of
# it, which is the school's whole progression drawn without a word.
#
# Two series, so a legend is present and every bar is labelled; the two colours
# were checked against the panel they sit on rather than chosen by eye.
# --------------------------------------------------------------------------
def quiver_chart(w, h, rows, hard_c="#0A8AA1", soft_c="#C93F68",
                 ink="#14262C", muted="#8A9AA0", surface="#F6F1E7",
                 labels=("HARD", "SOFT")):
    pad_l, pad_r, top = 52, 62, 40
    rowh = (h - top) / float(len(rows))
    barh = min(21.0, rowh * 0.52)
    scale = (w - pad_l - pad_r) / float(max(a + b for _, a, b in rows))
    mono = 'font-family="IBM Plex Mono, monospace"'
    d = []

    # legend first: two series never rely on colour alone
    x = pad_l
    for i, (c, lab) in enumerate(zip((hard_c, soft_c), labels)):
        d.append('<rect x="%.1f" y="6" width="11" height="11" rx="2.5" fill="%s"/>'
                 % (x, c))
        d.append('<text x="%.1f" y="15.5" %s font-size="10.5" letter-spacing="1.5" '
                 'fill="%s">%s</text>' % (x + 17, mono, ink, lab))
        x += 17 + len(lab) * 8.2 + 26

    for i, (name, a, b) in enumerate(rows):
        y = top + i * rowh + (rowh - barh) / 2.0
        d.append('<text x="0" y="%.1f" %s font-size="12" letter-spacing="1" '
                 'fill="%s">%s</text>' % (y + barh * 0.78, mono, ink, name))

        wa, wb = a * scale, b * scale
        gap = 2.0 if a and b else 0.0
        if a:
            d.append(_bar(pad_l, y, max(wa - gap, 1), barh, hard_c,
                          round_right=not b))
        if b:
            d.append(_bar(pad_l + wa, y, max(wb, 1), barh, soft_c, round_right=True))
        for val, x0, seg in ((a, pad_l, wa - gap), (b, pad_l + wa, wb)):
            if val and seg > 30:
                d.append('<text x="%.1f" y="%.1f" %s font-size="10.5" fill="%s" '
                         'text-anchor="middle">%d</text>'
                         % (x0 + seg / 2.0, y + barh * 0.72, mono, surface, val))
        d.append('<text x="%.1f" y="%.1f" %s font-size="12" fill="%s">%d</text>'
                 % (pad_l + wa + wb + 9, y + barh * 0.76, mono, ink, a + b))

    # one recessive baseline, no grid: the numbers are already on the bars
    d.append('<path d="M%.1f %.1fV%.1f" stroke="%s" stroke-width="1" '
             'stroke-opacity=".45"/>' % (pad_l - 0.5, top - 4, h, muted))
    return _svg(w, h, "".join(d), surface, fit="meet")


def _bar(x, y, w, h, fill, round_right=True, r=4.0):
    r = min(r, h / 2.0, w)
    if not round_right:
        return '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>' % (
            x, y, w, h, fill)
    return ('<path fill="%s" d="M%.1f %.1fH%.1fa%.1f %.1f 0 0 1 %.1f %.1f'
            'V%.1fa%.1f %.1f 0 0 1 %.1f %.1fH%.1fZ"/>'
            % (fill, x, y, x + w - r, r, r, r, r, y + h - r, r, r, -r, r, x))


# --------------------------------------------------------------------------
# Screen-print furniture
#
# What was missing was not another drawing, it was the grit around them. Surf
# print is a screen-printed medium and always has been: flat inks, halftone
# where a photograph would be, stripes, and a patch stitched on somewhere. All
# three of the pieces below exist to be layered over and under everything else.
# --------------------------------------------------------------------------
def halftone(w, h, cell=12.0, r=1.85, colour="#F5F0E6", opacity=0.15, angle=22.0):
    """A dot screen. Laid over a flat colour it gives the field the tooth a
    solid fill never has, and it survives a printer that a gradient would band
    all over.

    The dots are drawn, not tiled from an SVG <pattern>: Chromium rasterises a
    pattern fill on its way into a PDF, and at print size the screen came out
    as soft grey squares instead of dots. Some thousands of circles in one path
    is more markup and compresses to nothing, and it stays vector all the way
    to the plate."""
    rad = math.radians(angle)
    ca, sa = math.cos(rad), math.sin(rad)
    diag = math.hypot(w, h)
    d, j = [], 0
    y = -diag
    while y < diag:
        x = -diag
        # every other row offset, which is what makes it a screen and not a grid
        off = (cell / 2.0) if (j % 2) else 0.0
        while x < diag:
            px = (x + off) * ca - y * sa + w / 2.0
            py = (x + off) * sa + y * ca + h / 2.0
            if -cell < px < w + cell and -cell < py < h + cell:
                d.append("M%.1f %.1fm%.2f 0a%.2f %.2f 0 1 0 %.2f 0a%.2f %.2f 0 1 0 %.2f 0"
                         % (px, py, -r, r, r, r * 2, r, r, -r * 2))
            x += cell
        y += cell * 0.866
        j += 1
    return ('<svg class="screen" viewBox="0 0 %.0f %.0f" preserveAspectRatio="none" '
            'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
            '<path d="%s" fill="%s" fill-opacity="%s"/></svg>'
            % (w, h, "".join(d), colour, opacity))


def sunset(w, h, bands=22, cy=0.60, r=0.46, colours=("#F2A03D", "#F4894C",
                                                     "#F4735C", "#F4557F", "#E23F73"),
           ground=None, id_="sun"):
    """The striped disc every surf shop has had on a wall since about 1972:
    solid at the crown and coming apart into bands on the way down. Bands sit
    on an even pitch and lose thickness as they fall, so the gaps open by
    themselves -- an evenly striped circle is a beach ball."""
    cx, cyy, rr = w / 2.0, h * cy, min(w, h) * r
    top, pitch = cyy - rr, (2.0 * rr) / bands
    out = ['<defs><clipPath id="%s"><circle cx="%.1f" cy="%.1f" r="%.1f"/>'
           '</clipPath></defs>' % (id_, cx, cyy, rr)]
    out.append('<g clip-path="url(#%s)">' % id_)
    for i in range(bands):
        t = i / float(bands - 1)
        th = pitch * (1.0 - 0.88 * t ** 0.85)
        col = colours[min(int(t * len(colours)), len(colours) - 1)]
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"/>'
                   % (cx - rr - 2, top + i * pitch, rr * 2 + 4, max(th, 0.6), col))
    out.append('</g>')
    return _svg(w, h, "".join(out), ground)


def stamp(r, top_text, bottom_text, fg, mark=None, size=None, id_="st",
          track=0.16):
    """A patch. Type set round a ring is the most surf-looking thing a page can
    carry that is not a photograph, and it is the school's own words going
    round it rather than decoration.

    Both arcs run left to right -- the top one clockwise over the crown, the
    bottom one anticlockwise under the foot -- which is what keeps the lower
    words the right way up. Sweeping both the same way is the classic mistake
    and prints the bottom half upside down."""
    size = size or r * 0.14
    ring = r * 0.775
    mid = ('<g transform="translate(%.1f %.1f)">%s</g>' % (r, r, mark)) if mark else ""
    dot = ('<circle cx="%.1f" cy="%.1f" r="%.2f" fill="%s"/>'
           '<circle cx="%.1f" cy="%.1f" r="%.2f" fill="%s"/>'
           % (r - ring, r, r * 0.022, fg, r + ring, r, r * 0.022, fg))

    def ring_text(path_id, text):
        return ('<text font-family="IBM Plex Mono, monospace" font-size="%.2f" '
                'font-weight="500" letter-spacing="%.2f" fill="%s">'
                '<textPath href="#%s" startOffset="50%%" text-anchor="middle">%s'
                '</textPath></text>' % (size, size * track, fg, path_id, text))

    return (
        '<svg class="stamp" viewBox="0 0 %.1f %.1f" xmlns="http://www.w3.org/2000/svg">'
        '<defs>'
        '<path id="%s-t" fill="none" d="M%.1f %.1fA%.1f %.1f 0 0 1 %.1f %.1f"/>'
        '<path id="%s-b" fill="none" d="M%.1f %.1fA%.1f %.1f 0 0 0 %.1f %.1f"/>'
        '</defs>'
        '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.2f"/>'
        '<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" stroke-width="%.2f"/>'
        '%s%s%s%s</svg>'
    ) % (r * 2, r * 2,
         id_, r - ring, r, ring, ring, r + ring, r,
         id_, r - ring, r, ring, ring, r + ring, r,
         r, r, r * 0.965, fg, r * 0.042,
         r, r, r * 0.60, fg, r * 0.026,
         ring_text(id_ + "-t", top_text), ring_text(id_ + "-b", bottom_text),
         dot, mid)


def stripes(w, h, colours=("#F2A03D", "#F4894C", "#F4735C", "#F4557F"),
            ground=None, n=11, lean=1.25):
    """A band of them on an even pitch, losing thickness as they fall so the
    ground opens up underneath. The other half of the same 1972 idea as the
    disc, and the thing that turns a rule between two sections into a piece of
    surf furniture rather than a line."""
    out, pitch = [], h / float(n)
    for i in range(n):
        t = i / float(n - 1)
        th = pitch * (0.62 - 0.56 * t ** lean)
        out.append('<rect x="0" y="%.2f" width="%.1f" height="%.2f" fill="%s"/>'
                   % (i * pitch, w, max(th, 0.6),
                      colours[min(int(t * len(colours)), len(colours) - 1)]))
    return _svg(w, h, "".join(out), ground)


def _walker(x, y, scale, ink, board=1.0, flip=False):
    """Somebody carrying a board down to the water, seen side-on. Built from
    the same round-capped strokes as the rider and the sitter, so all the
    people in this booklet came off one hand."""
    f = -1 if flip else 1
    return ('<g transform="translate(%.1f %.1f) scale(%.3f %.3f)" stroke="%s" '
            'stroke-linecap="round" fill="none">'
            # the board, carried under the arm and tipped nose-up
            '<path fill="%s" stroke="none" transform="rotate(-9)" '
            'd="M-%.0f -34C-%.0f -44 %.0f -47 %.0f -40L%.0f -33C%.0f -26 -%.0f -24 -%.0f -34Z"/>'
            '<circle cx="0" cy="-96" r="9" fill="%s" stroke="none"/>'
            '<path stroke-width="12" d="M0-86V-46"/>'
            '<path stroke-width="8" d="M0-46 -13-24 -18 0"/>'
            '<path stroke-width="8" d="M0-46 12-26 10 0"/>'
            '<path stroke-width="7" d="M-1-78C-13-72-19-58-19-44"/>'
            '</g>' % (x, y, scale * f, scale, ink, ink,
                      44., 26., 42., 50., 52., 40., 20., 44., ink))


def walkers(w, h, ink="#14262C", line="#D24870", ground=None):
    """The walk down. Every surf trip is mostly this, and it is the one picture
    a camp page can carry that is about the people rather than the wave: the
    sea behind them, the sand under them, and five of them going in."""
    sea, sand = h * 0.26, h * 0.86
    d = ['<path fill="none" stroke="%s" stroke-width="1.7" stroke-opacity=".55" '
         'd="M0 %.1fH%.1f"/>' % (line, sea, w)]
    for i in range(6):                                    # swell behind them
        t = (i + 1) / 6.0
        y = sea + (sand - sea) * (t ** 1.6) * 0.78
        d.append('<path fill="none" stroke="%s" stroke-width="%.1f" '
                 'stroke-opacity="%.2f" stroke-linecap="round" '
                 'd="M-20 %.1fQ%.0f %.1f %.0f %.1f"/>'
                 % (line, 1.0 + t * 1.4, 0.22 + 0.30 * t, y,
                    w * 0.5, y - h * 0.016, w + 20, y))
    for x, sc, fl in ((0.10, 1.00, False), (0.29, 0.70, False),
                      (0.47, 0.95, False), (0.645, 0.62, True),
                      (0.85, 1.06, False)):
        d.append(_walker(w * x, sand, sc * h / 275.0, ink, flip=fl))
    return _svg(w, h, "".join(d), ground)


def foil(w, h, deep="#0A2129", body="#17515E", foam="#F5F0E6", ground=None):
    """A rider up on the foil: the board a clear stretch of air above the water
    and the wing still down in it. It is the one thing in surfing that looks
    wrong in a photograph and right in a drawing."""
    sea = h * 0.60
    p = ['<path fill="%s" d="M0 %.1fC%.0f %.1f %.0f %.1f %.0f %.1f'
         'C%.0f %.1f %.0f %.1f %.0f %.1fV%.0fH0Z"/>'
         % (body, sea, w * .2, sea - h * .03, w * .4, sea + h * .026, w * .58, sea,
            w * .72, sea - h * .026, w * .88, sea + h * .018, w, sea - h * .01, h)]

    bx, by = w * 0.54, sea - h * 0.235
    p.append('<g transform="rotate(-7 %.1f %.1f)">' % (bx, by))
    p.append('<path fill="%s" d="M%.1f %.1fC%.1f %.1f %.1f %.1f %.1f %.1f'
             'C%.1f %.1f %.1f %.1f %.1f %.1fZ"/>'
             % (foam,
                bx - w * .135, by, bx - w * .095, by - h * .026,
                bx + w * .105, by - h * .028, bx + w * .145, by - h * .004,
                bx + w * .105, by + h * .020, bx - w * .075, by + h * .024,
                bx - w * .135, by))
    p.append('</g>')

    # the mast, and the wing hanging off the bottom of it
    tip = sea + h * 0.155
    p.append('<path stroke="%s" stroke-width="%.1f" stroke-linecap="round" '
             'd="M%.1f %.1fV%.1f"/>' % (foam, w * .0075, bx, by + h * .04, tip))
    p.append('<path fill="%s" d="M%.1f %.1fC%.1f %.1f %.1f %.1f %.1f %.1f'
             'C%.1f %.1f %.1f %.1f %.1f %.1fZ"/>'
             % (deep,
                bx - w * .105, tip + h * .012, bx - w * .055, tip - h * .012,
                bx + w * .055, tip - h * .012, bx + w * .105, tip + h * .012,
                bx + w * .05, tip + h * .002, bx - w * .05, tip + h * .002,
                bx - w * .105, tip + h * .012))
    p.append('<path stroke="%s" stroke-width="%.1f" stroke-linecap="round" '
             'd="M%.1f %.1fh%.1f"/>'
             % (deep, w * .006, bx - w * .028, tip - h * .052, w * .056))

    # the rider, low and over the front foot
    p.append('<g transform="translate(%.1f %.1f) scale(%.3f) rotate(-7)" stroke="%s" '
             'stroke-linecap="round" fill="none">'
             '<circle cx="4" cy="-92" r="9" fill="%s" stroke="none"/>'
             '<path stroke-width="12" d="M2-83 -4-50"/>'
             '<path stroke-width="8" d="M-4-50 -22-28 -28-4"/>'
             '<path stroke-width="8" d="M-4-50 12-30 18-4"/>'
             '<path stroke-width="7" d="M-1-76C-17-71-30-61-37-49"/>'
             '<path stroke-width="7" d="M4-77C18-81 31-80 42-75"/>'
             '</g>' % (bx - w * .010, by - h * .016, h / 300.0 * 0.86, foam, foam))

    # the line the mast is drawing behind it
    p.append('<path fill="none" stroke="%s" stroke-opacity=".5" stroke-width="%.1f" '
             'stroke-linecap="round" d="M%.1f %.1fq%.1f %.1f %.1f %.1f"/>'
             % (foam, w * .005, bx - w * .015, sea + h * .012,
                -w * .15, h * .016, -w * .32, h * .004))
    return _svg(w, h, "".join(p), ground)
