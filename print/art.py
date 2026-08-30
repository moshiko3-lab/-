"""The artwork the brochure is built on, drawn rather than photographed.

Every picture in the brochure is a slot. If there is a photograph in
`print/images/` for that slot it wins; when there is not, one of these routines
fills it, and the page is still finished rather than a grey box with a cross
through it.

The drawings are all line work on a flat field -- contours read off a smooth
scalar field, swell lines, a sun over a banded horizon -- because hairlines on
paper are what an expensive brochure looks like and what a cheap printer can
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


def sun(w, h, stroke="#F46E95", ground=None, width=1.0, bands=30, opacity=1.0):
    """A disc low over a horizon, with the water between it and you drawn as
    lines that open out as they come nearer and lighten as they do. The
    spacing and the fade do all the work -- it reads as distance without
    anything being drawn in perspective."""
    cx, cy, r = w * 0.5, h * 0.375, min(w, h) * 0.25
    hz = h * 0.565
    lines = ['<circle cx="%.1f" cy="%.1f" r="%.1f" stroke-opacity="%s"/>'
             % (cx, cy, r, opacity),
             '<path d="M0 %.1fH%.1f" stroke-opacity="%s"/>' % (hz, w, opacity)]
    for i in range(1, bands + 1):
        t = i / float(bands)
        y = hz + (h - hz) * (t ** 1.9)
        lines.append('<path d="M0 %.1fH%.1f" stroke-opacity="%.3f"/>'
                     % (y, w, opacity * (1.0 - 0.62 * t)))
    body = ('<g fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round">'
            '%s</g>' % (stroke, width, "".join(lines)))
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


def _svg(w, h, body, ground):
    bg = '<rect width="%s" height="%s" fill="%s"/>' % (w, h, ground) if ground else ""
    return ('<svg class="art" viewBox="0 0 %s %s" preserveAspectRatio="xMidYMid slice" '
            'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">%s%s</svg>'
            % (w, h, bg, body))


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
