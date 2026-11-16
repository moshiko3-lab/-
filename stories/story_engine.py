"""SHOKOGI story renderer: one photo or video in, one 9:16 story out, laid out
like the mobile home page of shokogi.com.

    photo (top, full width)  with the SHOKOGI wordmark over it
    PLAYA VENAO · PANAMA     pink, letter-spaced            (the site's eyebrow)
    SPANISH LINE             Barlow Condensed, uppercase    (the site's H1)
    English line             Figtree, warm grey             (the site's subtitle)
    ( SHOKOGI.COM )          pink pill                      (the site's button)

A photo becomes a still picture with a song under it: Instagram's API cannot
attach music to a photo story, so it goes up as a video whose every frame is
the same picture. Nothing moves. A video stays a video in the photo area.

Runs in the Composio workbench sandbox; STORY_BRAND_DIR points elsewhere for
local previews. make_story() returns the catalog entry of the track it used.
"""
import json, os, random, re, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
B = os.environ.get("STORY_BRAND_DIR", "/mnt/files/brand")
W, H = 1080, 1920
PINK = (244, 110, 149); DARK = (26, 23, 25); BODY = (76, 75, 71); WHITE = (255, 255, 255)
PHOTO_SECS = 10                     # how long a photo story plays
MIN_SECS, MAX_SECS = 3, 60          # Instagram's limits for a story video
SAFE_TOP, SAFE_BOTTOM = 230, H - 280    # clear of the story header and the reply bar
SIDE = 72
EYEBROW = "PLAYA VENAO · PANAMA"
BUTTON = "SHOKOGI.COM"


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

def _text_block(d, es, en):
    """The lines under the photo and the height they need."""
    h1 = barlow(96)
    sub = figtree(42, 400)
    es_lines = balanced(d, es.upper(), h1, W - 2 * SIDE)
    if len(es_lines) > 2:                       # a long line steps down a size
        h1 = barlow(80)
        es_lines = balanced(d, es.upper(), h1, W - 2 * SIDE)
    en_lines = balanced(d, en, sub, W - 2 * SIDE - 40)
    h1_lh, sub_lh = int(h1.size * 1.06), 66
    height = 34 + 52 + len(es_lines) * h1_lh + 34 + len(en_lines) * sub_lh + 64 + 124
    return h1, sub, es_lines, en_lines, h1_lh, sub_lh, height


def layout(es, en):
    """Where the photo ends, and an RGBA layer with everything except the photo."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    h1, sub, es_lines, en_lines, h1_lh, sub_lh, block = _text_block(d, es, en)
    pad = 72
    photo_h = min(1040, SAFE_BOTTOM - block - 2 * pad)
    d.rectangle((0, photo_h, W, H), fill=WHITE)

    # the text block, centred in the white area above the reply bar
    y = photo_h + (SAFE_BOTTOM - photo_h - block) // 2 + 34
    draw_spaced(d, W / 2, y + 18, EYEBROW, figtree(31, 700), 9.5, PINK)
    y += 52 + 34
    for l in es_lines:
        d.text((W / 2, y + h1_lh / 2), l, font=h1, fill=DARK, anchor="mm"); y += h1_lh
    y += 34
    for l in en_lines:
        d.text((W / 2, y + sub_lh / 2), l, font=sub, fill=BODY, anchor="mm"); y += sub_lh
    y += 64
    bf = figtree(34, 700)
    bw = spaced_width(BUTTON, bf, 8.5) + 2 * 96
    d.rounded_rectangle(((W - bw) / 2, y, (W + bw) / 2, y + 124), radius=62, fill=PINK)
    draw_spaced(d, W / 2, y + 62, BUTTON, bf, 8.5, WHITE)
    return photo_h, layer


MARK_Y = SAFE_TOP + 20


def wordmark(base, dark=False):
    """The site's SHOKOGI wordmark (pink O) over the top of the photo: white with a
    light shade, as on the site, or dark where the photo is too bright behind it."""
    if not dark:
        g = Image.new("L", (1, 420))
        for y in range(420):
            g.putpixel((0, y), int(70 * (1 - y / 420) ** 1.6))
        shade = Image.new("RGBA", (W, 420), (*DARK, 0)); shade.putalpha(g.resize((W, 420)))
        base.alpha_composite(shade)
    mark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_spaced(ImageDraw.Draw(mark), W / 2, MARK_Y, "SHOKOGI", barlow(64, "Bold"), 19,
                DARK if dark else WHITE, colors={4: PINK})
    halo = Image.new("RGBA", (W, H), WHITE + (0,) if dark else (0, 0, 0, 0))
    halo.putalpha(mark.split()[3].point(lambda a: a // 2 if dark else a // 3))
    base.alpha_composite(halo.filter(ImageFilter.GaussianBlur(6)))
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


def render_frame(src, es, en):
    """The finished picture for a photo."""
    photo_h, layer = layout(es, en)
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    frame = Image.new("RGBA", (W, H), WHITE + (255,))
    frame.paste(smart_fit(im, (W, photo_h)), (0, 0))
    behind = frame.crop((W // 2 - 260, MARK_Y - 50, W // 2 + 260, MARK_Y + 50)).convert("L")
    bright = sum(behind.getdata()) / (behind.width * behind.height) > 165
    wordmark(frame, dark=bright)
    frame.alpha_composite(layer)
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


ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "3500k", "-bufsize", "7000k",
       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart"]


def make_story(src, out, text_es, text_en, seed=None, track=None, photo_secs=PHOTO_SECS):
    trk = track or pick_track(seed)
    is_img = src.lower().split(".")[-1] in ("jpg", "jpeg", "png", "webp", "heic", "heif")
    tmp = out + ".png"
    small = out + ".small.mp4"
    try:
        if is_img:
            render_frame(src, text_es, text_en).save(tmp)
            dur = photo_secs
            run([FF, "-y", "-loop", "1", "-framerate", "30", "-t", str(dur), "-i", tmp, "-i", trk["file"],
                 "-filter_complex", f"[1:a]afade=t=in:d=0.6,afade=t=out:st={dur-1.5}:d=1.5,volume=0.85[a]",
                 "-map", "0:v", "-map", "[a]", "-t", str(dur), "-tune", "stillimage", "-r", "30", *ENC, out])
            return trk

        photo_h, layer = layout(text_es, text_en)
        wordmark(layer)                 # a video's brightness is unknown: white with its shade
        layer.save(tmp)
        real = probe_duration(src) or 15
        dur = min(max(real, MIN_SECS), MAX_SECS)
        frame = (f"scale={W}:{photo_h}:force_original_aspect_ratio=increase,crop={W}:{photo_h},setsar=1"
                 + tonemap(src))

        def video_cmd(source, frame_filters):
            # a clip shorter than Instagram's minimum holds its last frame
            hold = f",tpad=stop_mode=clone:stop_duration={MIN_SECS - real:.2f}" if real < MIN_SECS else ""
            vf = (f"[0:v]{frame_filters},fps=30{hold},pad={W}:{H}:0:0:white[b];"
                  f"[b][1:v]overlay=0:0,format=yuv420p[v]")
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
