"""SHOKOGI story renderer: one photo or video in, one branded 9:16 story video out.

Runs in the Composio workbench sandbox, where the brand assets and music live
under /mnt/files. make_story() returns the catalog entry of the track it used.
"""
import subprocess, json, random, os, re
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
B = "/mnt/files/brand"
W, H = 1080, 1920
PINK = (244, 110, 149); DARK = (26, 23, 25); CREAM = (243, 240, 235)
MIN_SECS, MAX_SECS = 3, 60          # Instagram's limits for a story video


def font(sz, wght=700):
    f = ImageFont.truetype(f"{B}/Figtree.ttf", sz)
    try: f.set_variation_by_axes([wght])
    except Exception: pass
    return f


def white_logo(width):
    lg = Image.open(f"{B}/logo.png").convert("RGBA")
    a = lg.split()[3]
    wl = Image.new("RGBA", lg.size, (255, 255, 255, 0)); wl.putalpha(a)
    r = width / lg.width
    return wl.resize((width, int(lg.height * r)), Image.LANCZOS)


def wrap(draw, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def overlay(text_es, text_en):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = Image.new("L", (1, H))
    for y in range(H):
        top = max(0, 1 - y / 520) * 130
        bot = max(0, (y - (H - 950)) / 950) * 225
        g.putpixel((0, y), int(max(top, bot)))
    shade = Image.new("RGBA", (W, H), (*DARK, 0)); shade.putalpha(g.resize((W, H)))
    ov = Image.alpha_composite(ov, shade)
    lg = white_logo(250)
    ov.alpha_composite(lg, ((W - lg.width) // 2, 290))      # below Instagram's top bar
    d = ImageDraw.Draw(ov)
    fes, fen, fsite = font(68, 800), font(44, 500), font(40, 700)
    y = H - 430                                              # above the reply box
    site = "shokogi.com  ·  link in bio"
    sw = d.textlength(site, font=fsite); pad = 34
    d.rounded_rectangle(((W - sw) / 2 - pad, y - 18, (W + sw) / 2 + pad, y + 62), radius=40, fill=PINK)
    d.text((W / 2, y + 22), site, font=fsite, fill="white", anchor="mm")
    en_lines = wrap(d, text_en, fen, W - 160)
    es_lines = wrap(d, text_es, fes, W - 160)
    yy = y - 50 - len(en_lines) * 56
    for l in en_lines:
        d.text((W / 2, yy), l, font=fen, fill=CREAM, anchor="mm"); yy += 56
    yy = y - 80 - len(en_lines) * 56 - len(es_lines) * 82
    for l in es_lines:
        d.text((W / 2, yy), l, font=fes, fill="white", anchor="mm"); yy += 82
    return ov


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
    return (f",zscale=tin={m[1]}:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=100,format=gbrpf32le,"
            f"zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def make_story(src, out, text_es, text_en, seed=None, photo_secs=7, track=None):
    tmp = out + ".ov.png"
    overlay(text_es, text_en).save(tmp)
    trk = track or pick_track(seed)
    is_img = src.lower().split(".")[-1] in ("jpg", "jpeg", "png", "webp", "heic")
    fill = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if is_img:
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        base = out + ".base.jpg"
        bg = ImageOps.fit(im, (W, H)).filter(ImageFilter.GaussianBlur(40))
        fg = ImageOps.contain(im, (W, H)) if im.width > im.height * 0.75 else ImageOps.fit(im, (W, H))
        bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2)); bg.save(base, quality=95)
        dur = photo_secs
        vf = (f"[0:v]scale=1188:2112,zoompan=z='min(zoom+0.0007,1.08)':d={dur*30}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30[b];"
              f"[b][1:v]overlay=0:0,format=yuv420p[v]")
        cmd = [FF, "-y", "-loop", "1", "-t", str(dur), "-i", base, "-i", tmp, "-i", trk["file"],
               "-filter_complex", vf + f";[2:a]afade=t=in:d=0.5,afade=t=out:st={dur-1}:d=1,volume=0.8[a]",
               "-map", "[v]", "-map", "[a]", "-t", str(dur)]
    else:
        real = probe_duration(src) or 15
        dur = min(max(real, MIN_SECS), MAX_SECS)
        frame = fill + tonemap(src)

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
                    "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}"]
        cmd = video_cmd(src, frame)
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-maxrate", "3500k", "-bufsize", "7000k",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", out]
    small = out + ".small.mp4"
    try:
        try:
            run(cmd + enc)
        except RuntimeError:
            if is_img:
                raise
            # The sandbox has little memory and a large source (4K, HDR) can get the
            # one-pass render killed. Shrink the source on its own first, then render.
            run([FF, "-y", "-threads", "1", "-i", src, "-t", f"{dur:.2f}", "-vf", frame + ",format=yuv420p",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", small])
            run(video_cmd(small, "setsar=1") + enc)
    finally:
        for f in (tmp, out + ".base.jpg", small):
            if os.path.exists(f): os.remove(f)
    return trk
