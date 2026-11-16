"""SHOKOGI story renderer: one photo or video in, one 9:16 story out.

The photo fills the screen. Over it, quietly: the site's SHOKOGI wordmark, white
with its pink O, small at the top, and at the foot, on a soft shade, the site's eyebrow
PLAYA VENAO · PANAMA, the story's one line in light type, and shokogi.com on a
small pink pill.

A picture that is already 9:16 (a story the school designed) is left exactly as it
is: no wordmark, no line, no crop, only the song.

A photo becomes a still picture with a song under it: Instagram's API cannot
attach music to a photo story, so it goes up as a video whose every frame is
the same picture. Nothing moves. A video stays a video, filling the screen.

Runs in the Composio workbench sandbox; STORY_BRAND_DIR points elsewhere for
local previews. make_story() returns the catalog entry of the track it used.
"""
import json, os, random, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
B = os.environ.get("STORY_BRAND_DIR", "/mnt/files/brand")
W, H = 1080, 1920
PINK = (244, 110, 149); DARK = (26, 23, 25); WHITE = (255, 255, 255)
PHOTO_SECS = 10                     # how long a photo story plays
MIN_SECS, MAX_SECS = 3, 60          # Instagram's limits for a story video
SAFE_TOP, SAFE_BOTTOM = 230, H - 280    # clear of the story header and the reply bar
EYEBROW = "PLAYA VENAO · PANAMA"


# ---------------------------------------------------------------- type

def figtree(size, weight):
    f = ImageFont.truetype(f"{B}/Figtree.ttf", size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f


def barlow(size, weight="ExtraBold"):
    return ImageFont.truetype(f"{B}/BarlowCondensed-{weight}.ttf", size)


def spaced_width(text, font, tracking):
    return sum(font.getlength(c) for c in text) + tracking * (len(text) - 1)


def draw_spaced(d, cx, cy, text, font, tracking, fill, colors=None):
    """Centred text with letter-spacing (PIL has none); `colors` overrides per index."""
    x = cx - spaced_width(text, font, tracking) / 2
    for i, c in enumerate(text):
        d.text((x, cy), c, font=font, fill=(colors or {}).get(i, fill), anchor="lm")
        x += font.getlength(c) + tracking


def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def balanced(d, text, font, maxw):
    """As few lines as fit, with the words spread evenly: no lone word on the last line."""
    import itertools
    words = text.split()
    n = len(wrap(d, text, font, maxw))
    if n <= 1:
        return [text]
    best, best_score = None, None
    for cuts in itertools.combinations(range(1, len(words)), n - 1):
        parts = [" ".join(words[a:b]) for a, b in zip((0,) + cuts, cuts + (len(words),))]
        widths = [d.textlength(p, font=font) for p in parts]
        if max(widths) <= maxw and (best_score is None or max(widths) - min(widths) < best_score):
            best, best_score = parts, max(widths) - min(widths)
    return best or wrap(d, text, font, maxw)


# ---------------------------------------------------------------- layout

LINE_FONT, LINE_SIZE, LINE_LH = 300, 56, 74        # Figtree Light: the one line of the story
MARK_Y = SAFE_TOP + 12
X0 = 92                             # left margin of the left-aligned styles

# Ways to set the same few things (wordmark, eyebrow, the line, shokogi.com), so a
# day's stories do not all look alike. Every one keeps the site's type and colours;
# all but "card" keep the photo full-screen. "card" shows the whole photo, uncropped,
# on a blurred copy of itself (for a wide photo). "headline" needs a title.
STYLES = ("classic", "editorial", "headline", "tag", "frame", "card")
LEFT_STYLES = ("editorial", "tag")

TEXT_ZONE = (0, 1300, W, 1660)      # where the words sit, for measuring the photo behind them


def _foot_shade(layer, shade, start=0.52):
    """Shade only where the text sits, so the photo stays the photo."""
    g = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * start) / (H * (1 - start)))
        g.putpixel((0, y), min(235, int(165 * shade * t ** 1.3)))
    s = Image.new("RGBA", (W, H), (*DARK, 0)); s.putalpha(g.resize((W, H)))
    layer.alpha_composite(s)


def _pill(d, x, y, align="center", fill=PINK, color=WHITE, h=64):
    """shokogi.com on a small pill, the site's button colour. x is its centre or its left edge."""
    pf = figtree(27, 600)
    pw = spaced_width("shokogi.com", pf, 3) + 2 * 38
    left = x - pw / 2 if align == "center" else x
    d.rounded_rectangle((left, y, left + pw, y + h), radius=h / 2, fill=fill)
    draw_spaced(d, left + pw / 2, y + h / 2, "shokogi.com", pf, 3, color)
    return pw


def _fit(d, line, size, maxw, weight=LINE_FONT, max_lines=3, smaller=None):
    lf = figtree(size, weight)
    lines = balanced(d, line, lf, maxw)
    if len(lines) > max_lines and smaller:
        lf = figtree(smaller, weight)
        lines = balanced(d, line, lf, maxw)
    return lf, lines


def _eyebrow(d, x, y, align="center"):
    ef = figtree(24, 600)
    cx = x if align == "center" else x + spaced_width(EYEBROW, ef, 7) / 2
    draw_spaced(d, cx, y, EYEBROW, ef, 7, WHITE + (215,))


def _classic(d, line):
    """Centred at the foot: eyebrow, the line in light type, the pink pill."""
    lf, lines = _fit(d, line, LINE_SIZE, W - 220, smaller=48)
    lh, pill_h = int(lf.size * 1.32), 64
    y = SAFE_BOTTOM - 20 - (30 + 44 + len(lines) * lh + 40 + pill_h)
    _eyebrow(d, W / 2, y + 15)
    y += 30 + 44
    for l in lines:
        d.text((W / 2, y + lh / 2), l, font=lf, fill=WHITE, anchor="mm"); y += lh
    _pill(d, W / 2, y + 40)


def _editorial(d, line):
    """Left-aligned, like a magazine page: a short pink rule, the eyebrow, the line
    larger, the pill under it."""
    lf, lines = _fit(d, line, 70, W - X0 - 150, smaller=60)
    lh, pill_h = int(lf.size * 1.22), 64
    y = SAFE_BOTTOM - 20 - (4 + 34 + 30 + 30 + len(lines) * lh + 44 + pill_h)
    d.rectangle((X0, y, X0 + 64, y + 4), fill=PINK)
    y += 4 + 34
    _eyebrow(d, X0, y + 15, align="left")
    y += 30 + 30
    for l in lines:
        d.text((X0, y + lh / 2), l, font=lf, fill=WHITE, anchor="lm"); y += lh
    _pill(d, X0, y + 44, align="left")


def _headline(d, line, title):
    """The topic in the wordmark's condensed type, large, the line small under it."""
    if not title:
        return _classic(d, line)
    title = title.upper()
    size = 200
    while size > 90 and spaced_width(title, barlow(size), 3) > W - 170:
        size -= 6
    tf = barlow(size)
    cap = -tf.getbbox("H", anchor="ls")[1]
    lf, lines = _fit(d, line, 42, W - 240, max_lines=2, smaller=38)
    lh, pill_h = int(lf.size * 1.35), 64
    y = SAFE_BOTTOM - 20 - (30 + 34 + cap + 38 + len(lines) * lh + 40 + pill_h)
    _eyebrow(d, W / 2, y + 15)
    y += 30 + 34
    x = W / 2 - spaced_width(title, tf, 3) / 2
    for c in title:
        d.text((x, y + cap), c, font=tf, fill=WHITE, anchor="ls"); x += tf.getlength(c) + 3
    y += cap + 38
    for l in lines:
        d.text((W / 2, y + lh / 2), l, font=lf, fill=WHITE, anchor="mm"); y += lh
    _pill(d, W / 2, y + 40)


def _tag(d, line):
    """Left-aligned, the line on pink labels, shokogi.com on a white pill."""
    lf, lines = _fit(d, line, 50, W - X0 - 220, weight=600, smaller=44)
    padx, pady, gap, pill_h = 24, 13, 10, 64
    lh = lf.size + 2 * pady
    y = SAFE_BOTTOM - 20 - (30 + 32 + len(lines) * (lh + gap) - gap + 40 + pill_h)
    _eyebrow(d, X0, y + 15, align="left")
    y += 30 + 32
    for l in lines:
        d.rectangle((X0, y, X0 + d.textlength(l, font=lf) + 2 * padx, y + lh), fill=PINK)
        d.text((X0 + padx, y + lh / 2), l, font=lf, fill=WHITE, anchor="lm")
        y += lh + gap
    _pill(d, X0, y - gap + 40, align="left", fill=WHITE, color=PINK)


def _frame(d, line):
    """The classic words inside a thin white frame: its top edge breaks for the
    wordmark, its bottom edge for shokogi.com."""
    m, t, col, pill_h = 56, 3, WHITE + (225,), 64
    pf = figtree(27, 600)
    pw = spaced_width("shokogi.com", pf, 3) + 2 * 38
    bottom = SAFE_BOTTOM - 20 - pill_h / 2
    top = MARK_Y
    half_mark = spaced_width("SHOKOGI", barlow(46, "Bold"), 14) / 2 + 34
    d.rectangle((m, top - t / 2, W / 2 - half_mark, top + t / 2), fill=col)
    d.rectangle((W / 2 + half_mark, top - t / 2, W - m, top + t / 2), fill=col)
    d.rectangle((m - t / 2, top - t / 2, m + t / 2, bottom + t / 2), fill=col)
    d.rectangle((W - m - t / 2, top - t / 2, W - m + t / 2, bottom + t / 2), fill=col)
    d.rectangle((m, bottom - t / 2, W / 2 - pw / 2 - 22, bottom + t / 2), fill=col)
    d.rectangle((W / 2 + pw / 2 + 22, bottom - t / 2, W - m, bottom + t / 2), fill=col)
    _pill(d, W / 2, bottom - pill_h / 2)
    lf, lines = _fit(d, line, LINE_SIZE, W - 2 * m - 150, smaller=48)
    lh = int(lf.size * 1.32)
    y = bottom - pill_h / 2 - 52 - len(lines) * lh
    _eyebrow(d, W / 2, y - 44)
    for l in lines:
        d.text((W / 2, y + lh / 2), l, font=lf, fill=WHITE, anchor="mm"); y += lh


def layout(line, shade=1.0, style="classic", title=None):
    """An RGBA layer over a full-screen photo: a soft shade at the foot and the words,
    set in one of STYLES. Quiet on purpose. `shade` deepens the shade for a bright
    photo, so light type still reads."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _foot_shade(layer, shade, start=0.44 if style == "headline" else 0.52)
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    if style == "editorial": _editorial(d, line)
    elif style == "headline": _headline(d, line, title)
    elif style == "tag": _tag(d, line)
    elif style == "frame": _frame(d, line)
    else: _classic(d, line)
    soft = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    soft.putalpha(txt.split()[3].point(lambda a: int(a * (0.22 if style == "tag" else 0.45))))
    layer.alpha_composite(soft.filter(ImageFilter.GaussianBlur(9)))
    layer.alpha_composite(txt)
    return layer


def _mark_x(align):
    return W / 2 if align == "center" else X0 + spaced_width("SHOKOGI", barlow(46, "Bold"), 14) / 2


def wordmark(base, shade=1.0, align="center"):
    """The site's SHOKOGI wordmark, small and white (pink O, as on the site), at the
    top over a faint shade; `shade` deepens it where the photo is bright behind it."""
    g = Image.new("L", (1, 420))
    for y in range(420):
        g.putpixel((0, y), min(200, int(60 * shade * (1 - y / 420) ** 1.4)))
    top = Image.new("RGBA", (W, 420), (*DARK, 0)); top.putalpha(g.resize((W, 420)))
    base.alpha_composite(top)
    mark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_spaced(ImageDraw.Draw(mark), _mark_x(align), MARK_Y, "SHOKOGI", barlow(46, "Bold"), 14,
                WHITE, colors={4: PINK})
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    halo.putalpha(mark.split()[3].point(lambda a: int(a * min(0.75, 0.35 * shade))))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(7)))
    base.alpha_composite(mark)


def smart_fit(im, size):
    """Crop to fill `size`. Sideways, keep the busiest part of the picture (edges and
    colour), pulled toward the centre so it moves only for a reason. Up and down, keep
    the upper part: that is where heads are, and the busiest part of a surf photo is
    usually the splash at the bottom."""
    import numpy as np
    tw, th = size
    wide = im.width / im.height > tw / th
    if not wide:
        return ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, 0.33))
    small = im.resize((240, max(1, int(240 * im.height / im.width))))
    e = np.asarray(small.convert("L").filter(ImageFilter.FIND_EDGES), float) \
        + 0.5 * np.asarray(small.convert("HSV").split()[1], float)
    prof = e.sum(0)
    span = small.height * tw / th
    win = max(1, min(len(prof), int(round(span))))
    sums = np.convolve(prof, np.ones(win), "valid")
    if len(sums) <= 1:
        return ImageOps.fit(im, size, Image.LANCZOS)
    pos = np.arange(len(sums)) / (len(sums) - 1)
    best = float(pos[int(np.argmax(sums * (1 - 0.4 * np.abs(pos - 0.5) ** 2 / 0.25)))])
    return ImageOps.fit(im, size, Image.LANCZOS, centering=(best, 0.5))


def is_finished_story(path):
    """True for a picture that is already a 9:16 story (one the school designed, or a
    phone's story-shaped shot): it goes up exactly as it is, with only the song added."""
    with Image.open(path) as im:
        w, h = im.size
        try:
            if im.getexif().get(274) in (5, 6, 7, 8):      # rotated by its EXIF tag
                w, h = h, w
        except Exception:
            pass
    return abs(w / h - W / H) < 0.01


def _card(im, line):
    """The whole photo, uncropped, as a card with rounded corners, on a blurred and
    darkened copy of itself; the words under it as in "classic"."""
    bg = ImageOps.fit(im, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    frame = Image.blend(bg, Image.new("RGB", (W, H), DARK), 0.38).convert("RGBA")
    box_top, box_w, box_h = 340, W - 2 * 72, 960
    card = ImageOps.contain(im, (box_w, box_h), Image.LANCZOS)
    x, y = (W - card.width) // 2, box_top + (box_h - card.height) // 2
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=26, fill=255)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x, y + 18, x + card.width, y + card.height + 18), radius=26,
                                         fill=(0, 0, 0, 130))
    frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))
    frame.paste(card, (x, y), mask)
    wordmark(frame, shade=1.0)
    frame.alpha_composite(layout(line, shade=0.85, style="classic"))
    return frame


def render_frame(src, line, style="classic", title=None):
    """The finished picture for a photo, in one of STYLES."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    if style == "card":
        return _card(im, line).convert("RGB")
    align = "left" if style in LEFT_STYLES else "center"
    frame = smart_fit(im, (W, H)).convert("RGBA")
    mx = _mark_x(align)
    behind = frame.crop((int(mx - 220), MARK_Y - 45, int(mx + 220), MARK_Y + 45)).convert("L")
    px = sorted(behind.getdata())
    top_lum = px[int(len(px) * 0.85)]     # the bright part decides: a white patch behind a letter is enough
    wordmark(frame, shade=min(2.6, max(1.0, 1.0 + (top_lum - 110) / 55)), align=align)
    zone = frame.crop((0, 1150, W, 1660) if style == "headline" else TEXT_ZONE).convert("L")
    lum = sum(zone.getdata()) / (zone.width * zone.height)
    frame.alpha_composite(layout(line, shade=min(1.6, max(0.85, 0.85 + (lum - 95) / 110)),
                                 style=style, title=title))
    return frame.convert("RGB")


# ---------------------------------------------------------------- story looks
# A story made the way a person makes one in the app. The words go where the photo
# is quiet (the top, the middle or the foot), in one of several hands, sometimes
# tilted, sometimes with an emoji; shokogi.com moves around: under the words, at the
# other end of the screen, or slapped on as a tilted sticker. Each story's look is
# drawn at random, but its hand, its place and its pill differ from the stories just
# before it. The wordmark stays where it is: white, small, at the top.

TREATMENTS = ("light", "bold", "boxed", "script", "neon", "card")
ZONES = {"top": (330, 820), "middle": (760, 1240), "bottom": (1180, SAFE_BOTTOM - 20)}
PILL_MODES = ("under", "opposite", "sticker")
PAD = 40                             # room around a block for its shadow or glow
PILL_H = 64


def caveat(size, weight=700):
    f = ImageFont.truetype(f"{B}/Caveat.ttf", size)
    try: f.set_variation_by_axes([weight])
    except Exception: pass
    return f


def emoji_img(ch, h):
    """One colour emoji, `h` pixels high (Noto Color Emoji draws only at 109)."""
    f = ImageFont.truetype(f"{B}/NotoColorEmoji.ttf", 109)
    im = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox())
    return im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)


def _measure():
    return ImageDraw.Draw(Image.new("L", (1, 1)))


def _shadowed(img, strength=0.45, blur=9):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.split()[3].point(lambda a: int(a * strength)))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    out.alpha_composite(img)
    return out


def _x_in(align, bw, w):
    return PAD + {"left": 0, "center": (bw - w) / 2, "right": bw - w}[align]


def _with_emoji(block, emo, h, align):
    """Put an emoji after the block's last line (or under it, centred, for a centred block)."""
    if not emo:
        return block
    try:
        e = emoji_img(emo, h)
    except Exception:
        return block
    # the letters' own edges, not their soft shadow
    bb = block.split()[3].point(lambda a: 255 if a > 140 else 0).getbbox() or (PAD, PAD, block.width - PAD, block.height - PAD)
    if align == "center":
        out = Image.new("RGBA", (max(block.width, e.width + 2 * PAD), bb[3] + 12 + e.height + PAD), (0, 0, 0, 0))
        out.alpha_composite(block, ((out.width - block.width) // 2, 0))
        out.alpha_composite(e, ((out.width - e.width) // 2, bb[3] + 12))
        return out
    out = Image.new("RGBA", (bb[2] + 14 + e.width + PAD, block.height), (0, 0, 0, 0))
    out.alpha_composite(block, (0, 0))
    out.alpha_composite(e, (bb[2] + 14, max(0, bb[3] - e.height - 2)))
    return out


def _b_light(line, align, maxw, eyebrow):
    d = _measure()
    lf, lines = _fit(d, line, 62, maxw, smaller=52)
    lh = int(lf.size * 1.28)
    ef = figtree(24, 600)
    top = 60 if eyebrow else 0
    ws = [d.textlength(l, font=lf) for l in lines]
    bw = int(max(ws + ([spaced_width(EYEBROW, ef, 7)] if eyebrow else [])))
    img = Image.new("RGBA", (bw + 2 * PAD, top + len(lines) * lh + 2 * PAD), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    if eyebrow:
        ew = spaced_width(EYEBROW, ef, 7)
        draw_spaced(dd, _x_in(align, bw, ew) + ew / 2, PAD + 15, EYEBROW, ef, 7, WHITE + (215,))
    y = PAD + top
    for l, w in zip(lines, ws):
        dd.text((_x_in(align, bw, w), y + lh / 2), l, font=lf, fill=WHITE, anchor="lm"); y += lh
    return _shadowed(img)


def _b_bold(line, align, maxw, eyebrow):
    d = _measure()
    text = line.upper()
    for size in range(132, 62, -6):
        tf = barlow(size)
        lines = balanced(d, text, tf, maxw)
        if len(lines) <= 3 and all(d.textlength(l, font=tf) <= maxw for l in lines):
            break
    cap = -tf.getbbox("H", anchor="ls")[1]
    gap = int(cap * 0.30)
    ef = figtree(24, 600)
    top = 56 if eyebrow else 0
    ws = [d.textlength(l, font=tf) for l in lines]
    bw = int(max(ws + ([spaced_width(EYEBROW, ef, 7)] if eyebrow else [])))
    img = Image.new("RGBA", (bw + 2 * PAD, top + len(lines) * (cap + gap) - gap + 2 * PAD), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    if eyebrow:
        ew = spaced_width(EYEBROW, ef, 7)
        draw_spaced(dd, _x_in(align, bw, ew) + ew / 2, PAD + 12, EYEBROW, ef, 7, WHITE + (215,))
    y = PAD + top
    for l, w in zip(lines, ws):
        dd.text((_x_in(align, bw, w), y + cap), l, font=tf, fill=WHITE, anchor="ls"); y += cap + gap
    return _shadowed(img, 0.5, 10)


BOX_SCHEMES = {"white": (WHITE, DARK), "pink": (PINK, WHITE), "dark": (DARK, WHITE)}


def _b_boxed(line, align, maxw, scheme):
    """Each line on its own rounded box, as the app's text background does it."""
    d = _measure()
    lf, lines = _fit(d, line, 54, maxw - 60, weight=650, smaller=46)
    padx, pady = 26, 14
    lh = lf.size + 2 * pady
    ws = [d.textlength(l, font=lf) + 2 * padx for l in lines]
    bw = int(max(ws))
    img = Image.new("RGBA", (bw + 2 * PAD, len(lines) * lh + 2 * PAD), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    bg, fg = BOX_SCHEMES[scheme]
    y = PAD
    for l, w in zip(lines, ws):
        x = _x_in(align, bw, w)
        dd.rounded_rectangle((x, y, x + w, y + lh + 1), radius=16, fill=bg)
        dd.text((x + padx, y + lh / 2), l, font=lf, fill=fg, anchor="lm"); y += lh
    return _shadowed(img, 0.25, 12)


def _b_script(line, align, maxw):
    d = _measure()
    lf = caveat(100)
    lines = balanced(d, line, lf, maxw)
    if len(lines) > 3:
        lf = caveat(86); lines = balanced(d, line, lf, maxw)
    lh = int(lf.size * 1.0)
    ws = [d.textlength(l, font=lf) for l in lines]
    bw = int(max(ws))
    img = Image.new("RGBA", (bw + 2 * PAD, len(lines) * lh + 2 * PAD + 20), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    y = PAD
    for l, w in zip(lines, ws):
        dd.text((_x_in(align, bw, w), y + lh / 2), l, font=lf, fill=WHITE, anchor="lm"); y += lh
    return _shadowed(img, 0.55, 8)


def _b_neon(line, align, maxw):
    """White letters with a pink glow, the site's pink."""
    d = _measure()
    lf, lines = _fit(d, line, 64, maxw, weight=600, smaller=54)
    lh = int(lf.size * 1.3)
    ws = [d.textlength(l, font=lf) for l in lines]
    bw = int(max(ws))
    size = (bw + 2 * PAD, len(lines) * lh + 2 * PAD)
    txt = Image.new("RGBA", size, (0, 0, 0, 0)); dd = ImageDraw.Draw(txt)
    y = PAD
    for l, w in zip(lines, ws):
        dd.text((_x_in(align, bw, w), y + lh / 2), l, font=lf, fill=WHITE, anchor="lm"); y += lh
    a = txt.split()[3]
    glow = Image.new("RGBA", size, PINK + (0,))
    glow.putalpha(a.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, v * 2)))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(glow); out.alpha_composite(glow); out.alpha_composite(txt)
    return out


def _pill_img(scheme):
    fill, color = (PINK, WHITE) if scheme == "pink" else (WHITE, PINK)
    pf = figtree(27, 600)
    pw = int(spaced_width("shokogi.com", pf, 3) + 2 * 38)
    img = Image.new("RGBA", (pw + 40, PILL_H + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((20, 26, 20 + pw, 26 + PILL_H), radius=PILL_H / 2, fill=(0, 0, 0, 70))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((20, 20, 20 + pw, 20 + PILL_H), radius=PILL_H / 2, fill=fill)
    draw_spaced(d, 20 + pw / 2, 20 + PILL_H / 2, "shokogi.com", pf, 3, color)
    return img


def _put(layer, img, x, y, angle=0, margin=0):
    """Paste, tilted by `angle` degrees about its centre, kept on the screen (`margin`
    clear of its edges). Returns the box."""
    if angle:
        cx, cy = x + img.width / 2, y + img.height / 2
        img = img.rotate(angle, resample=Image.BICUBIC, expand=True)
        x, y = cx - img.width / 2, cy - img.height / 2
    x = int(min(max(margin, x), W - img.width - margin)); y = int(min(max(0, y), H - img.height))
    layer.alpha_composite(img, (x, y))
    return (x, y, x + img.width, y + img.height)


def _band(layer, y0, y1, alpha):
    """A soft dark band behind words on a full-screen photo, strongest where they sit."""
    g = Image.new("L", (1, H), 0)
    for y in range(H):
        if y < y0: t = max(0.0, 1 - (y0 - y) / 260)
        elif y > y1: t = max(0.0, 1 - (y - y1) / 260)
        else: t = 1.0
        g.putpixel((0, y), int(alpha * t ** 1.6))
    s = Image.new("RGBA", (W, H), (*DARK, 0)); s.putalpha(g.resize((W, H)))
    layer.alpha_composite(s)


def cost_maps(frame):
    """Where words would hurt the photo, at a quarter of the size: edges (people,
    boards, splash) plus, heavily, anything skin-coloured (faces, arms). And brightness."""
    import numpy as np
    sm = frame.convert("RGB").resize((W // 4, H // 4), Image.BILINEAR)
    e = np.asarray(sm.convert("L").filter(ImageFilter.FIND_EDGES), float)
    ycc = np.asarray(sm.convert("YCbCr"), float)
    y, cb, cr = ycc[..., 0], ycc[..., 1], ycc[..., 2]
    skin = ((cr >= 138) & (cr <= 175) & (cb >= 85) & (cb <= 130) & (y > 60)).astype(float)
    return e + 260 * skin, y


def _zone_of(y, h):
    c = y + h / 2
    return "top" if c < 800 else ("middle" if c < 1200 else "bottom")


def plan_look(rnd, recent=(), is_image=True, emoji=()):
    """Draw a look: the hand, the pill and its place, tilt, emoji. Where the words go is
    decided afterwards, from the photo. `recent` (the looks just before) keeps it varied."""
    rt = [r.get("treatment") for r in recent][-3:]
    rp = [r.get("pill") for r in recent][-1:]
    ts = [t for t in TREATMENTS if is_image or t != "card"]
    t = rnd.choice([x for x in ts if x not in rt] or ts)
    look = {"treatment": t, "pill": rnd.choice([p for p in PILL_MODES if p not in rp]),
            "pill_scheme": rnd.choice(["pink", "pink", "white"]),
            "tilt": round(rnd.choice([-1, 1]) * rnd.uniform(2, 4.5), 1) if t in ("boxed", "script") else 0,
            "sticker_tilt": round(rnd.choice([-1, 1]) * rnd.uniform(4, 8), 1),
            "eyebrow": t in ("light", "bold", "card") and rnd.random() < 0.6,
            "box": rnd.choice(list(BOX_SCHEMES)),
            "emoji": rnd.choice(list(emoji)) if emoji and t in ("boxed", "script", "neon") and rnd.random() < 0.6 else ""}
    return look


def _aligns(t):
    return ["left", "center", "right"] if t in ("boxed", "script") else ["left", "center"]


def _box_x(align, bw):
    return {"left": X0, "center": (W - bw) / 2, "right": W - X0 - bw}[align]


def _block(look, line):
    t, align = look["treatment"], look["align"]
    maxw = W - 2 * X0 - (60 if align != "center" else 0)
    if t == "bold": b = _b_bold(line, align, maxw, look["eyebrow"])
    elif t == "boxed": b = _b_boxed(line, align, maxw - 80, look["box"])
    elif t == "script": b = _b_script(line, align, maxw - 60)
    elif t == "neon": b = _b_neon(line, align, maxw - 40)
    else: b = _b_light(line, align, maxw - 60, look["eyebrow"])
    eh = {"boxed": 62, "script": 84, "neon": 70}.get(t, 0)
    return _with_emoji(b, look.get("emoji"), eh, align)


def _room(look):
    """Space the pill needs next to the words: (above, below)."""
    return {"under": (0, PILL_H + 34), "sticker": (PILL_H + 10, 0)}.get(look["pill"], (0, 0))


def place(look, line, maps, rnd, recent_zone=None, fixed=None):
    """Choose alignment and height for the words: the quietest stretch of the photo
    (no faces, no busy splash), a different part of the screen from the last story if
    an almost-as-quiet one exists, and some chance. Returns (block, x, y, lum)."""
    up, down = _room(look)
    cands = []
    for al in ([look["align"]] if fixed else _aligns(look["treatment"])):
        blk = _block(dict(look, align=al), line)
        bw, bh = blk.width - 2 * PAD, blk.height - 2 * PAD
        x = _box_x(al, bw)
        if fixed:
            y0, y1 = fixed
            ys = [y0 + up] if look.get("at") == "top" else [y1 - bh - down]
        else:
            ys = range(330 + up, int(SAFE_BOTTOM - 20 - bh - down) + 1, 20)
        for y in ys:
            if maps is None:
                cands.append((0, y, al, blk, 110)); continue
            cost, lum = maps
            r0, r1 = int((y - up) / 4), int((y + bh + down) / 4)
            c0, c1 = int(max(0, x) / 4), int(min(W, x + bw) / 4)
            cands.append((float(cost[r0:r1, c0:c1].mean()), y, al, blk, float(lum[r0:r1, c0:c1].mean())))
    best = min(c[0] for c in cands)
    ok = [c for c in cands if c[0] <= best * 1.22 + 2]
    ok = [c for c in ok if _zone_of(c[1], c[3].height - 2 * PAD) != recent_zone] or ok
    c, y, al, blk, lum = rnd.choice(ok)
    look["align"], look["zone"] = al, _zone_of(y, blk.height - 2 * PAD)
    return blk, _box_x(al, blk.width - 2 * PAD) - PAD, y - PAD, lum


def compose(layer, look, block, x, y, lum, shade=True, maps=None):
    """Draw the words (already set, at x, y) and the pill on `layer`. `maps` (from
    cost_maps) lets a pill on its own find a quiet spot."""
    t, align = look["treatment"], look["align"]
    pill = _pill_img(look["pill_scheme"])
    pw = pill.width - 40
    up, down = _room(look)
    if shade and t in ("light", "bold", "neon", "script"):
        a = min(185, max(55, 70 + (lum - 90) * 1.1 + (30 if t == "neon" else 0)))
        _band(layer, y + PAD - up, y + block.height - PAD + down, a)
    bx = _put(layer, block, x, y, look.get("tilt", 0))
    inner = (bx[0] + PAD, bx[1] + PAD, bx[2] - PAD, bx[3] - PAD)
    side = {"left": X0 - 20, "center": W / 2 - pill.width / 2, "right": W - X0 - pw - 20}
    if look["pill"] == "under":
        _put(layer, pill, side[align], inner[3] + 26 - 20)
    elif look["pill"] == "opposite":
        # alone at the other end of the screen: under the wordmark, or near the foot,
        # on whichever side is quietest
        py = MARK_Y + 64 if look["zone"] == "bottom" else SAFE_BOTTOM - 20 - PILL_H - 20
        px = side[align]
        if maps is not None:
            cost = maps[0]
            r0, r1 = int((py + 20) / 4), int((py + 20 + PILL_H) / 4)
            px = min(side.values(), key=lambda v: float(cost[r0:r1, int(max(0, v + 20) / 4):int(min(W, v + 20 + pw) / 4)].mean()))
        _put(layer, pill, px, py, margin=24)
    else:   # a sticker on a corner of the words, tilted
        right = align != "right"
        px = (inner[2] - pw * 0.55) if right else (inner[0] - pw * 0.45)
        _put(layer, pill, px - 20, inner[1] - PILL_H - 24 - 20, look["sticker_tilt"] * (1 if right else -1), margin=24)
    return layer


def _card_back(im, look):
    """The whole photo, uncropped, as a card on a blurred copy of itself, away from the
    words (look["zone"]: where the words go)."""
    bg = ImageOps.fit(im, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    frame = Image.blend(bg, Image.new("RGB", (W, H), DARK), 0.38).convert("RGBA")
    top, bot = (330, 1130) if look["zone"] == "bottom" else (800, SAFE_BOTTOM - 10)
    card = ImageOps.contain(im, (W - 2 * 72, bot - top), Image.LANCZOS)
    x, y = (W - card.width) // 2, top + (bot - top - card.height) // 2
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=26, fill=255)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x, y + 18, x + card.width, y + card.height + 18), radius=26, fill=(0, 0, 0, 130))
    frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))
    frame.paste(card, (x, y), mask)
    return frame


def render_look(src, line, spec):
    """The finished picture for a photo in a freshly drawn look. spec: seed, recent
    (looks just before), emoji (the topic's). Returns (picture, look)."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    rnd = random.Random(spec.get("seed"))
    recent = spec.get("recent", [])
    look = plan_look(rnd, recent, True, spec.get("emoji", []))
    last_zone = (recent[-1].get("zone") if recent else None)
    if look["treatment"] == "card":
        look["at"] = rnd.choice(["top", "bottom"])
        look["zone"] = look["at"]
        frame = _card_back(im, dict(look, zone="bottom" if look["at"] == "bottom" else "top"))
        wordmark(frame, 1.0)
        if look["pill"] == "opposite":
            look["pill"] = "under"                  # alone, it would sit on the card
        words = dict(look, treatment="light", align="center")
        zone = (1140, SAFE_BOTTOM - 20) if look["at"] == "bottom" else (330, 790)
        blk, x, y, _ = place(words, line, None, rnd, fixed=zone)
        compose(frame, words, blk, x, y, 60)
        look["align"] = "center"
        return frame.convert("RGB"), look
    frame = smart_fit(im, (W, H)).convert("RGBA")
    behind = frame.crop((W // 2 - 220, MARK_Y - 45, W // 2 + 220, MARK_Y + 45)).convert("L")
    px = sorted(behind.getdata())
    top_lum = px[int(len(px) * 0.85)]
    look["align"] = "center"
    maps = cost_maps(frame)
    blk, x, y, lum = place(look, line, maps, rnd, last_zone)
    wordmark(frame, shade=min(2.6, max(1.0, 1.0 + (top_lum - 110) / 55)))
    compose(frame, look, blk, x, y, lum, maps=maps)
    return frame.convert("RGB"), look


def video_look_layer(line, spec):
    """A clear layer for a video: the words at the top or the foot (a video moves, so
    there is no quiet part to find), with a steady shade."""
    rnd = random.Random(spec.get("seed"))
    recent = spec.get("recent", [])
    look = plan_look(rnd, recent, False, spec.get("emoji", []))
    look["align"] = rnd.choice(_aligns(look["treatment"]))
    look["at"] = rnd.choice(["top", "bottom"])
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wordmark(layer, shade=1.6)
    zone = (330, 820) if look["at"] == "top" else (1180, SAFE_BOTTOM - 20)
    blk, x, y, _ = place(look, line, None, rnd, fixed=zone)
    look["zone"] = look["at"]
    compose(layer, look, blk, x, y, 120)
    return layer, look


# ---------------------------------------------------------------- media

def pick_track(seed=None):
    cat = json.load(open("/mnt/files/music/catalog.json"))
    return random.Random(seed).choice(cat)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-1500:])


def probe_duration(path):
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def has_audio(path):
    return "Audio:" in subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr


def tonemap(path):
    """Filters that bring an HDR phone video (HLG or PQ, BT.2020) down to ordinary
    SDR BT.709; without them it comes out grey and washed out. Empty for SDR."""
    info = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Video:.*?\b(arib-std-b67|smpte2084)\b", info)
    if not m:
        return ""
    # npl=203: phones put reference white at 203 nits (ITU-R BT.2408). Mobius keeps
    # everything up to that as it was and rolls off brighter highlights (sky, sun on
    # the water) instead of clipping them. Measured on a test card converted to HLG
    # and back: mean error 8 levels of 255, against 19 for hable at 100 nits and 21
    # for no tone mapping at all.
    return (f",zscale=tin={m[1]}:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=203,format=gbrpf32le,"
            f"zscale=p=bt709,tonemap=tonemap=mobius:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def _video_layer(line, style="classic", title=None):
    style = "classic" if style == "card" else style      # a card needs a still photo
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wordmark(layer, shade=1.6, align="left" if style in LEFT_STYLES else "center")   # a video changes under the wordmark
    layer.alpha_composite(layout(line, shade=1.2, style=style, title=title))      # and under the words
    return layer


def _render_apart(kind, src, line, out, style="classic", title=None, spec=None):
    """Draw in a separate, short-lived process. The sandbox has about 1 GB, and a big
    photo drawn inside the workbench's own process once took the whole workbench down;
    a child process gives its memory back when it ends, and if it dies it only fails
    this story."""
    r = subprocess.run([sys.executable, os.path.abspath(__file__), kind, src, line, out, style, title or "",
                        json.dumps(spec or {}, ensure_ascii=False)],
                       capture_output=True, text=True, env=dict(os.environ, STORY_BRAND_DIR=B))
    if r.returncode:
        raise RuntimeError(f"render ({kind}) failed: {r.stderr[-800:] or r.returncode}")
    last = (r.stdout.strip().splitlines() or [""])[-1]
    return json.loads(last) if last.startswith("{") else None


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "3500k", "-bufsize", "7000k",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart"]


def make_story(src, out, line, seed=None, track=None, photo_secs=PHOTO_SECS, designed=None,
               style="classic", title=None, look=None):
    """designed: True posts a picture untouched, False always draws the design,
    None decides by shape (a 9:16 picture counts as already designed).
    style: one of STYLES; title: the topic, for "headline".
    look: a spec dict (seed, recent, emoji) for a freshly drawn story look instead of
    a fixed style; the look drawn is written back into it as look["drawn"]."""
    trk = track or pick_track(seed)
    is_img = src.lower().split(".")[-1] in ("jpg", "jpeg", "png", "webp", "heic", "heif")
    tmp = out + ".png"
    small = out + ".small.mp4"
    try:
        if is_img:
            as_is = is_finished_story(src) if designed is None else designed
            if look is not None and not as_is:
                look["drawn"] = _render_apart("look", src, line or "-", tmp, style, title, look)
            else:
                _render_apart("asis" if as_is else "frame", src, line or "-", tmp, style, title)
            dur = photo_secs
            run([FF, "-y", "-loop", "1", "-framerate", "30", "-t", str(dur), "-i", tmp, "-i", trk["file"],
                 "-filter_complex", f"[1:a]afade=t=in:d=0.6,afade=t=out:st={dur-1.5}:d=1.5,volume=0.85[a]",
                 "-map", "0:v", "-map", "[a]", "-t", str(dur), "-tune", "stillimage", "-r", "30", *ENC,
                 "-crf", "18", out])
            return trk

        if look is not None:
            look["drawn"] = _render_apart("vlook", "-", line, tmp, style, title, look)
        else:
            _render_apart("layer", "-", line, tmp, style, title)
        real = probe_duration(src) or 15
        dur = min(max(real, MIN_SECS), MAX_SECS)
        frame = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
                 + tonemap(src))

        def video_cmd(source, frame_filters):
            # a clip shorter than Instagram's minimum holds its last frame
            hold = f",tpad=stop_mode=clone:stop_duration={MIN_SECS - real:.2f}" if real < MIN_SECS else ""
            vf = f"[0:v]{frame_filters},fps=30{hold}[b];[b][1:v]overlay=0:0,format=yuv420p[v]"
            if has_audio(source):
                af = (f"[0:a]volume=0.6,apad[o];[2:a]volume=0.35,afade=t=out:st={max(dur-1.5,0)}:d=1.5[m];"
                      f"[o][m]amix=inputs=2:duration=shortest[a]")
            else:
                af = f"[2:a]afade=t=in:d=0.5,afade=t=out:st={max(dur-1.5,0)}:d=1.5,volume=0.8[a]"
            return [FF, "-y", "-i", source, "-i", tmp, "-i", trk["file"],
                    "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", *ENC, out]

        try:
            run(video_cmd(src, frame))
        except RuntimeError:
            # The sandbox has little memory and a large source (4K, HDR) can get the
            # one-pass render killed. Shrink the source on its own first, then render.
            run([FF, "-y", "-threads", "1", "-i", src, "-t", f"{dur:.2f}", "-vf", frame + ",format=yuv420p",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", small])
            run(video_cmd(small, "setsar=1"))
        return trk
    finally:
        for f in (tmp, small):
            if os.path.exists(f): os.remove(f)


if __name__ == "__main__":
    # python story_engine.py frame <photo> <line> <out.png> [style] [title] | layer - <line> <out.png> [style] [title]
    kind, src, line, out = sys.argv[1:5]
    style = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] in STYLES else "classic"
    title = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else None
    spec = json.loads(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] else {}
    if kind in ("look", "vlook"):
        pic, drawn = render_look(src, line, spec) if kind == "look" else video_look_layer(line, spec)
        pic.save(out)
        print(json.dumps(drawn, ensure_ascii=False))
    elif kind == "asis":
        ImageOps.exif_transpose(Image.open(src)).convert("RGB").resize((W, H), Image.LANCZOS).save(out)
    else:
        (render_frame(src, line, style, title) if kind == "frame" else _video_layer(line, style, title)).save(out)
