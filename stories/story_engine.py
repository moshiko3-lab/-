"""SHOKOGI story renderer: one photo or video in, one 9:16 story out.

The photo fills the screen. Over it, quietly: the site's SHOKOGI wordmark, white
with its pink O, small at the top, and at the foot, on a soft shade, the site's eyebrow
PLAYA VENAO · PANAMA, the story's one line in light type, and shokogi.com on a
small pink pill.

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


TEXT_ZONE = (0, 1300, W, 1660)      # where the words sit, for measuring the photo behind them


def layout(line, shade=1.0):
    """An RGBA layer over a full-screen photo: a soft shade at the foot, the site's
    eyebrow, the story's line in light type, and shokogi.com. Quiet on purpose.
    `shade` deepens the shade for a bright photo, so light type still reads."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # shade only where the text sits, so the photo stays the photo
    g = Image.new("L", (1, H))
    for y in range(H):
        t = max(0.0, (y - H * 0.52) / (H * 0.48))
        g.putpixel((0, y), min(235, int(165 * shade * t ** 1.3)))
    shade = Image.new("RGBA", (W, H), (*DARK, 0)); shade.putalpha(g.resize((W, H)))
    layer.alpha_composite(shade)

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    lf = figtree(LINE_SIZE, LINE_FONT)
    lines = balanced(d, line, lf, W - 2 * 110)
    if len(lines) > 3:
        lf = figtree(48, LINE_FONT)
        lines = balanced(d, line, lf, W - 2 * 110)
    lh = int(lf.size * 1.32)
    pill_h = 64
    block = 30 + 44 + len(lines) * lh + 40 + pill_h
    y = SAFE_BOTTOM - 20 - block
    draw_spaced(d, W / 2, y + 15, EYEBROW, figtree(24, 600), 7, WHITE + (215,))
    y += 30 + 44
    for l in lines:
        d.text((W / 2, y + lh / 2), l, font=lf, fill=WHITE, anchor="mm"); y += lh
    y += 40
    # shokogi.com on a small pink pill, the site's button colour
    pf = figtree(27, 600)
    pw = spaced_width("shokogi.com", pf, 3) + 2 * 38
    d.rounded_rectangle(((W - pw) / 2, y, (W + pw) / 2, y + pill_h), radius=pill_h / 2, fill=PINK)
    draw_spaced(d, W / 2, y + pill_h / 2, "shokogi.com", pf, 3, WHITE)

    soft = Image.new("RGBA", (W, H), (0, 0, 0, 0)); soft.putalpha(txt.split()[3].point(lambda a: int(a * 0.45)))
    layer.alpha_composite(soft.filter(ImageFilter.GaussianBlur(9)))
    layer.alpha_composite(txt)
    return layer


def wordmark(base, shade=1.0):
    """The site's SHOKOGI wordmark, small and white (pink O, as on the site), at the
    top over a faint shade; `shade` deepens it where the photo is bright behind it."""
    g = Image.new("L", (1, 420))
    for y in range(420):
        g.putpixel((0, y), min(200, int(60 * shade * (1 - y / 420) ** 1.4)))
    top = Image.new("RGBA", (W, 420), (*DARK, 0)); top.putalpha(g.resize((W, 420)))
    base.alpha_composite(top)
    mark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_spaced(ImageDraw.Draw(mark), W / 2, MARK_Y, "SHOKOGI", barlow(46, "Bold"), 14,
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


def render_frame(src, line):
    """The finished picture for a photo."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    frame = smart_fit(im, (W, H)).convert("RGBA")
    behind = frame.crop((W // 2 - 220, MARK_Y - 45, W // 2 + 220, MARK_Y + 45)).convert("L")
    px = sorted(behind.getdata())
    top_lum = px[int(len(px) * 0.85)]     # the bright part decides: a white patch behind a letter is enough
    wordmark(frame, shade=min(2.6, max(1.0, 1.0 + (top_lum - 110) / 55)))
    zone = frame.crop(TEXT_ZONE).convert("L")
    lum = sum(zone.getdata()) / (zone.width * zone.height)
    frame.alpha_composite(layout(line, shade=min(1.6, max(0.85, 0.85 + (lum - 95) / 110))))
    return frame.convert("RGB")


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


def _video_layer(line):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wordmark(layer, shade=1.6)      # a video changes under the wordmark: a little more shade
    layer.alpha_composite(layout(line, shade=1.2))     # and under the words
    return layer


def _render_apart(kind, src, line, out):
    """Draw in a separate, short-lived process. The sandbox has about 1 GB, and a big
    photo drawn inside the workbench's own process once took the whole workbench down;
    a child process gives its memory back when it ends, and if it dies it only fails
    this story."""
    r = subprocess.run([sys.executable, os.path.abspath(__file__), kind, src, line, out],
                       capture_output=True, text=True, env=dict(os.environ, STORY_BRAND_DIR=B))
    if r.returncode:
        raise RuntimeError(f"render ({kind}) failed: {r.stderr[-800:] or r.returncode}")


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "3500k", "-bufsize", "7000k",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart"]


def make_story(src, out, line, seed=None, track=None, photo_secs=PHOTO_SECS):
    trk = track or pick_track(seed)
    is_img = src.lower().split(".")[-1] in ("jpg", "jpeg", "png", "webp", "heic", "heif")
    tmp = out + ".png"
    small = out + ".small.mp4"
    try:
        if is_img:
            _render_apart("frame", src, line, tmp)
            dur = photo_secs
            run([FF, "-y", "-loop", "1", "-framerate", "30", "-t", str(dur), "-i", tmp, "-i", trk["file"],
                 "-filter_complex", f"[1:a]afade=t=in:d=0.6,afade=t=out:st={dur-1.5}:d=1.5,volume=0.85[a]",
                 "-map", "0:v", "-map", "[a]", "-t", str(dur), "-tune", "stillimage", "-r", "30", *ENC, out])
            return trk

        _render_apart("layer", "-", line, tmp)
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
    # python story_engine.py frame <photo> <line> <out.png> | layer - <line> <out.png>
    kind, src, line, out = sys.argv[1:5]
    (render_frame(src, line) if kind == "frame" else _video_layer(line)).save(out)
