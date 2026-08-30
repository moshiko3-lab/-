#!/usr/bin/env python3
"""Build the Shokogi service flyers in the house style.

The style is the one set by the private-surf-photo-session flyer: a light,
hazy 2:3 poster, Oswald display type in pink over a washed photograph, a
Montserrat text column on the left, hairline-separated feature rows, a solid
pink call to action, and the wordmark twice — once at the top, once at the
foot.

    python3 build_flyers.py            # writes the HTML and renders the PNGs
    python3 build_flyers.py --html     # HTML only, no browser needed

Every measurement below is taken off the photo-session flyer at 1024x1536, so
a flyer built here drops into the same set without looking like a cousin.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

W, H = 1024, 1536

# --- the palette, sampled from the photo-session flyer -----------------------
PINK = "#DA5A7A"
PINK_CTA = "#DC5E7E"
NAVY = "#1F2B4A"
BG = "#EFF0F4"
BG_FOOT = "#D3D7E1"
RULE = "rgba(218,90,122,.55)"

# --- the icons, drawn on a 24x24 grid in one thin pink stroke ----------------
ICONS = {
    "board": '<rect x="8.1" y="2.2" width="7.8" height="19.6" rx="3.9"/>'
             '<path d="M12 5.6v12.8"/>',
    "calendar": '<rect x="3.2" y="5.2" width="17.6" height="15.6" rx="2.6"/>'
                '<path d="M3.2 10.2h17.6M8.2 3.2v4M15.8 3.2v4"/>',
    "wave": '<path d="M2.6 7.4c2.3-2.4 4.7-2.4 7 0s4.7 2.4 7 0 4.7-2.4 4.8 0"/>'
            '<path d="M2.6 12.8c2.3-2.4 4.7-2.4 7 0s4.7 2.4 7 0 4.7-2.4 4.8 0"/>'
            '<path d="M2.6 18.2c2.3-2.4 4.7-2.4 7 0s4.7 2.4 7 0 4.7-2.4 4.8 0"/>',
    "star": '<path d="M12 2.6 14.9 8.8l6.6.8-4.9 4.7 1.3 6.7L12 17.6l-5.9 3.4 1.3-6.7-4.9-4.7 6.6-.8z"/>',
    "people": '<circle cx="9.2" cy="8.2" r="3.3"/><circle cx="16.8" cy="9.2" r="2.6"/>'
              '<path d="M2.9 19.4c0-3.5 2.8-5.7 6.3-5.7s6.3 2.2 6.3 5.7"/>'
              '<path d="M16.6 13.9c2.9 0 4.5 2 4.5 5.2"/>',
    "badge": '<circle cx="12" cy="9.4" r="6.6"/>'
             '<path d="M12 5.9 13.4 8.7l3.1.4-2.3 2.2.6 3.1L12 12.9l-2.8 1.5.6-3.1-2.3-2.2 3.1-.4z"/>'
             '<path d="M8.2 15.6 7.1 21.4 12 18.8l4.9 2.6-1.1-5.8"/>',
    "camera": '<rect x="2.6" y="6.6" width="18.8" height="13.6" rx="2.6"/>'
              '<path d="M8.4 6.6 9.9 3.6h4.2l1.5 3"/><circle cx="12" cy="13.4" r="3.7"/>',
    "pin": '<path d="M12 21.6c0 0 7-6.7 7-11.8A7 7 0 0 0 5 9.8c0 5.1 7 11.8 7 11.8Z"/>'
           '<circle cx="12" cy="9.8" r="2.7"/>',
}


# how far each drawing sits from the left of its 24-grid, so the viewBox can
# be nudged and every icon starts on the same line as the text column
INK_LEFT = {"board": 7.4, "calendar": 2.3, "wave": 1.7, "star": 1.6,
            "people": 2.0, "badge": 4.5, "camera": 1.7, "pin": 4.1}


def icon(name, size=44, stroke=1.8):
    return (
        f'<svg class="icon" width="{size}" height="{size}" '
        f'viewBox="{INK_LEFT[name]} 0 24 24" fill="none" '
        f'stroke="{PINK}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{ICONS[name]}</svg>"
    )


CSS = f"""
@font-face {{ font-family: 'Oswald'; src: url('../fonts/Oswald.ttf'); font-weight: 200 700; }}
@font-face {{ font-family: 'Montserrat'; src: url('../fonts/Montserrat.ttf'); font-weight: 100 900; }}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #888; }}

.canvas {{
  position: relative; width: {W}px; height: {H}px; overflow: hidden;
  background: linear-gradient(180deg, {BG} 0%, {BG} 44%, {BG_FOOT} 100%);
  font-family: 'Montserrat', sans-serif; -webkit-font-smoothing: antialiased;
}}

/* the photograph, twice: an out-of-focus copy carrying the shot's own light
   across the whole poster — without it the left half is a dead white field —
   and then the sharp one on the right, its left edge dissolved into that */
.haze {{ position: absolute; inset: 0; overflow: hidden; }}
.haze img {{ width: 100%; height: 100%; object-fit: cover; transform: scale(1.12); }}

.shot {{ position: absolute; top: 0; right: 0; height: 100%; }}
.shot img {{ height: 100%; display: block; }}

.veil {{ position: absolute; inset: 0; }}

.col {{
  position: absolute; left: 71px; top: 70px; width: 600px; height: {H - 70 - 57}px;
  display: flex; flex-direction: column; align-items: flex-start;
}}
.sp {{ width: 100%; }}

/* the wordmark, top */
.mark {{ width: 241px; text-align: center; }}
.mark .name {{
  font-weight: 700; font-size: 43px; line-height: 1; letter-spacing: .132em;
  color: {PINK}; text-indent: .132em; margin-left: -5.5px;
}}
.mark .sub {{
  margin-top: 14px; font-weight: 500; font-size: 16px; line-height: 1;
  letter-spacing: .298em; color: {PINK}; text-indent: .298em;
}}
.mark .dash {{ margin: 22px auto 0; width: 65px; height: 2px; background: {PINK}; }}

/* the headline */
.head {{
  font-family: 'Oswald', sans-serif; font-weight: 700; font-size: 151px;
  line-height: 1.047; letter-spacing: .05em; color: {PINK}; text-transform: uppercase;
  margin-left: -8px;
}}
.head-dash {{ width: 36px; height: 2px; background: {PINK}; }}

.lede {{
  font-weight: 600; font-size: 23px; line-height: 33px; letter-spacing: .04em;
  color: {NAVY}; text-transform: uppercase;
}}

/* the feature rows, hairline between each */
.rows {{ width: 100%; }}
.row {{ display: flex; align-items: center; gap: 34px; height: 92px; }}
.row .icon {{ flex: none; }}
.row .txt {{
  font-weight: 600; font-size: 17px; line-height: 25px; letter-spacing: .03em;
  color: {NAVY}; text-transform: uppercase;
}}
.rule {{ width: 285px; height: 1px; background: {RULE}; }}

.cta {{
  display: flex; align-items: center; justify-content: center;
  height: 77px; padding: 0 48px; background: {PINK_CTA};
  font-weight: 700; font-size: 23px; letter-spacing: .03em; color: #fff;
  text-transform: uppercase; text-indent: .03em;
}}

.where {{ display: flex; align-items: center; gap: 15px; }}
.where .txt {{
  font-weight: 600; font-size: 18.5px; letter-spacing: .04em; color: {NAVY};
  text-transform: uppercase;
}}
.where-dash {{ margin: 15px 0 0 58px; width: 30px; height: 2px; background: {PINK}; }}

/* the wordmark, foot: lighter, wider, quieter */
.foot {{ width: 301px; text-align: center; }}
.foot .name {{
  font-weight: 400; font-size: 38.5px; line-height: 1; letter-spacing: .527em;
  color: {PINK}; text-indent: .527em; margin-left: -23.5px;
}}
.foot .sub {{
  margin-top: 18px; font-weight: 500; font-size: 13px; line-height: 1;
  letter-spacing: .304em; color: rgba(218,90,122,.78); text-indent: .304em;
}}
.foot .dash {{ margin: 21px auto 0; width: 46px; height: 2px; background: {PINK}; }}
"""

# gaps between blocks on the photo-session flyer, in pixels; they are used as
# flex weights so a shorter headline spreads its slack over every gap instead
# of dumping it in one hole
GAPS = [70, 41, 33, 64, 91, 41, 62]


def spacer(weight):
    return f'<div class="sp" style="flex: {weight} 0 0"></div>'


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>{css}</style></head>
<body>
<div class="canvas">
  <div class="haze" style="opacity: {haze}"><img src="{photo}" alt=""
       style="filter: blur({blur}px) saturate(.32)"></div>
  <div class="shot" style="width: {shot_w}px"><img src="{photo}" alt="{alt}"
       style="width: {img_w}px; margin: {img_y}px 0 0 {img_x}px;
              -webkit-mask-image: linear-gradient(90deg, transparent 0, #000 {fade}%);"></div>
  <div class="veil" style="background: linear-gradient(180deg, rgba(255,255,255,.10) 0%, rgba(255,255,255,.02) 34%, rgba(255,255,255,.04) 100%)"></div>
  <div class="veil" style="background: {veil}"></div>
  <div class="col">
    <div class="mark">
      <div class="name">SHOKOGI</div>
      <div class="sub">SURF SCHOOL</div>
      <div class="dash"></div>
    </div>
    {sp0}
    <div class="head">{headline}</div>
    {sp1}
    <div class="head-dash"></div>
    {sp2}
    <div class="lede">{lede}</div>
    {sp3}
    <div class="rows">{rows}</div>
    {sp4}
    <div class="cta">{cta}</div>
    {sp5}
    <div>
      <div class="where">{pin}<div class="txt">PLAYA VENAO, PANAMA</div></div>
      <div class="where-dash"></div>
    </div>
    {sp6}
    <div class="foot">
      <div class="name">SHOKOGI</div>
      <div class="sub">SURF SCHOOL</div>
      <div class="dash"></div>
    </div>
  </div>
</div>
</body></html>
"""

FLYERS = [
    dict(
        slug="board_rentals",
        title="Shokogi — Board Rentals",
        photo="../photos/rentals.jpg",
        alt="A surfer trimming along a green wave on a soft-top longboard",
        # the crop is 625x1800, laid in at its own scale so it reaches from
        # x=400 to the right edge, hung 130px low to keep the dark headland
        # out of the top corner
        haze=.62, blur=58,
        shot_w=624, img_w=624, img_x=0, img_y=0, fade=22,
        # the wash is tilted: it reaches further across the dark headland at the
        # top, where the headline crosses the photograph, and clears at the
        # bottom where the surfer is
        veil=("linear-gradient(101deg, rgba(240,241,245,.81) 0%, rgba(240,241,245,.74) 26%,"
              " rgba(240,241,245,.52) 38%, rgba(240,241,245,.20) 48%,"
              " rgba(240,241,245,0) 58%)"),
        headline="Board<br>Rentals",
        lede="Ride any wave. Any level.<br>Any day.",
        cta="Rent your board",
        rows=[
            ("board", "Shortboards, funboards,<br>longboards &amp; softboards"),
            ("calendar", "Daily rentals<br>available"),
            ("wave", "Great for<br>all skill levels"),
            ("star", "Quality boards,<br>ready to surf"),
        ],
    ),
    dict(
        slug="surf_lessons",
        title="Shokogi — Surf Lessons",
        photo="../photos/lessons.jpg",
        alt="A surfer carving off the top of a breaking wave",
        # the crop is 694x1800; at 1536 tall it is 592 wide. the surfer's head
        # sits on its left edge, so the photograph keeps almost full strength
        # from the very first pixel and the veil alone does the dissolving
        haze=.62, blur=58,
        shot_w=592, img_w=592, img_x=0, img_y=0, fade=12,
        veil=("linear-gradient(97deg, rgba(240,241,245,.80) 0%, rgba(240,241,245,.72) 20%,"
              " rgba(240,241,245,.50) 32%, rgba(240,241,245,.16) 44%,"
              " rgba(240,241,245,0) 54%)"),
        headline="Surf<br>Lessons",
        lede="From your first wave to<br>your best wave.",
        cta="Book your lesson",
        rows=[
            ("people", "Private &amp; group<br>lessons available"),
            ("badge", "All levels,<br>beginner to advanced"),
            ("calendar", "Multi-lesson<br>surf courses"),
            ("star", "Expert local<br>instructors"),
        ],
    ),
]


def rows_html(rows):
    out = []
    for i, (name, text) in enumerate(rows):
        if i:
            out.append('<div class="rule"></div>')
        out.append(f'<div class="row">{icon(name)}<div class="txt">{text}</div></div>')
    return "".join(out)


def build(flyer):
    html = PAGE.format(
        css=CSS,
        title=flyer["title"],
        photo=flyer["photo"],
        alt=flyer["alt"],
        haze=flyer["haze"],
        blur=flyer["blur"],
        shot_w=flyer["shot_w"],
        img_w=flyer["img_w"],
        img_x=flyer["img_x"],
        img_y=flyer["img_y"],
        fade=flyer["fade"],
        veil=flyer["veil"],
        headline=flyer["headline"],
        lede=flyer["lede"],
        cta=flyer["cta"],
        rows=rows_html(flyer["rows"]),
        pin=icon("pin", size=44, stroke=1.8),
        **{f"sp{i}": spacer(g) for i, g in enumerate(GAPS)},
    )
    path = os.path.join(OUT, flyer["slug"] + ".html")
    with open(path, "w") as fh:
        fh.write(html)
    return path


def chromium():
    for candidate in ("/opt/pw-browsers/chromium", "chromium", "chromium-browser",
                      "google-chrome", "google-chrome-stable"):
        found = candidate if os.path.exists(candidate) else shutil.which(candidate)
        if found:
            return found
    return None


# headless chromium keeps 92px of its window for furniture that is never
# painted, so ask for a taller window and cut the dead strip off afterwards
CHROME_CHROME = 92


def render(path):
    browser = chromium()
    if not browser:
        print("no chromium found — HTML written, render it yourself", file=sys.stderr)
        return None
    png = path[:-5] + ".png"
    subprocess.run(
        [browser, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={W},{H + CHROME_CHROME}", "--force-device-scale-factor=1",
         "--virtual-time-budget=6000", f"--screenshot={png}", path],
        check=True, capture_output=True,
    )
    try:
        from PIL import Image
    except ImportError:
        print(f"install Pillow to trim {png} to {W}x{H}", file=sys.stderr)
        return png
    with Image.open(png) as shot:
        poster = shot.convert("RGB").crop((0, 0, W, H))
        poster.save(png)
        poster.save(png[:-4] + ".jpg", quality=92)  # the one to post
    return png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true", help="write the HTML, skip the render")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    for flyer in FLYERS:
        path = build(flyer)
        print("wrote", os.path.relpath(path, HERE))
        if not args.html:
            png = render(path)
            if png:
                print("wrote", os.path.relpath(png, HERE))


if __name__ == "__main__":
    main()
