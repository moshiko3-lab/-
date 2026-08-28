#!/usr/bin/env python3
"""Generates the full logo file set for "The Bee" from one shared geometry.

Everything is derived from a 100x100 mark grid so the bee stays identical
across the hex mark, the monoline mark, the icon and the lockups.
"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))

INK    = "#17130F"
HONEY  = "#E8A33D"
DEEP   = "#B8701A"
CREAM  = "#FAF3E6"

HEX  = "M50 2 L89.6 26 L89.6 74 L50 98 L10.4 74 L10.4 26 Z"
BODY = ("M50 38 C59 38 66 45 66 54 C66 66 58 78 50 84 "
        "C42 78 34 66 34 54 C34 45 41 38 50 38 Z")
ANT_L = "M45.5 24 C42 18 40 16 37.5 14.5"
ANT_R = "M54.5 24 C58 18 60 16 62.5 14.5"


def bee_solid(pfx, body, stripe, wing, wing_op="0.9"):
    """Top-down bee, filled. Wings sit behind the body."""
    return f'''<g>
    <ellipse cx="30" cy="40" rx="15" ry="8" transform="rotate(30 30 40)" fill="{wing}" opacity="{wing_op}"/>
    <ellipse cx="70" cy="40" rx="15" ry="8" transform="rotate(-30 70 40)" fill="{wing}" opacity="{wing_op}"/>
    <path d="{ANT_L}" fill="none" stroke="{body}" stroke-width="3.2" stroke-linecap="round"/>
    <path d="{ANT_R}" fill="none" stroke="{body}" stroke-width="3.2" stroke-linecap="round"/>
    <circle cx="50" cy="30" r="9" fill="{body}"/>
    <clipPath id="{pfx}-b"><path d="{BODY}"/></clipPath>
    <path d="{BODY}" fill="{body}"/>
    <g clip-path="url(#{pfx}-b)" fill="{stripe}">
      <rect x="30" y="44" width="40" height="6.5"/>
      <rect x="30" y="56" width="40" height="6.5"/>
      <rect x="30" y="68" width="40" height="5.5"/>
    </g>
  </g>'''


def bee_line(stroke, ground, w="3.4"):
    """Same bee as a single-weight outline. Each shape knocks out the one
    behind it with a ground-coloured fill, so no two lines ever cross."""
    return f'''<g stroke="{stroke}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">
    <g fill="none">
      <path d="{ANT_L}"/>
      <path d="{ANT_R}"/>
    </g>
    <ellipse cx="30" cy="40" rx="15" ry="8" transform="rotate(30 30 40)" fill="{ground}"/>
    <ellipse cx="70" cy="40" rx="15" ry="8" transform="rotate(-30 70 40)" fill="{ground}"/>
    <path d="{BODY}" fill="{ground}"/>
    <g fill="none">
      <path d="M41 47.5 H59"/>
      <path d="M39.5 60 H60.5"/>
      <path d="M44.5 71.5 H55.5"/>
    </g>
    <circle cx="50" cy="30" r="9" fill="{ground}"/>
  </g>'''


def stripe_mark(bar, wing):
    """Direction C: abstract bee - two swept wings over three tapering bars."""
    return f'''<g>
    <path d="M50 44 C34 48 18 42 11 29 C26 20 45 27 50 44 Z" fill="{wing}"/>
    <path d="M50 44 C66 48 82 42 89 29 C74 20 55 27 50 44 Z" fill="{wing}"/>
    <g fill="{bar}">
      <circle cx="50" cy="45" r="7"/>
      <rect x="26" y="55" width="48" height="10" rx="5"/>
      <rect x="32" y="69" width="36" height="10" rx="5"/>
      <rect x="39" y="83" width="22" height="10" rx="5"/>
    </g>
  </g>'''


def svg(view, inner, extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" '
            f'role="img"{extra}>\n  {inner}\n</svg>\n')


BEE_IN_HEX = 'transform="translate(50 52) scale(0.74) translate(-50 -49)"'


def hex_mark(pfx, hexfill, body, stripe, wing, wing_op="0.9"):
    return (f'<path d="{HEX}" fill="{hexfill}"/>\n  '
            f'<g {BEE_IN_HEX}>{bee_solid(pfx, body, stripe, wing, wing_op)}</g>')


def write(name, content):
    with open(os.path.join(OUT, name), "w") as f:
        f.write(content)
    print("wrote", name)


# ---------------------------------------------------------------- marks
write("mark-hex.svg", svg("0 0 100 100",
      hex_mark("mh", HONEY, INK, CREAM, CREAM),
      ' aria-label="The Bee mark"'))

write("mark-hex-reversed.svg", svg("0 0 100 100",
      hex_mark("mhr", INK, HONEY, INK, CREAM, "0.26"),
      ' aria-label="The Bee mark, reversed"'))

def monoline(stroke, ground):
    return svg("0 0 100 106",
        f'''<path d="M7 98 C24 103 41 94 46 81" fill="none" stroke="{HONEY}"
        stroke-width="3.4" stroke-linecap="round" stroke-dasharray="0.1 8"/>
  <g transform="translate(50 45) scale(0.88) translate(-50 -49)">{bee_line(stroke, ground)}</g>''',
        ' aria-label="The Bee monoline mark"')


write("mark-monoline.svg", monoline(INK, CREAM))
write("mark-monoline-dark.svg", monoline(CREAM, INK))

write("mark-stripe.svg", svg("0 0 100 100",
      stripe_mark(INK, HONEY),
      ' aria-label="The Bee stripe mark"'))

# ---------------------------------------------------------------- lockups
WORD = ("font-family=\"Fraunces, 'Fraunces 144', Georgia, 'Times New Roman', serif\" "
        "font-weight=\"600\"")


def horizontal(pfx, hexfill, body, stripe, wing, text):
    return svg("0 0 400 120",
        f'''<g transform="translate(8 12) scale(0.96)">{hex_mark(pfx, hexfill, body, stripe, wing)}</g>
  <text x="126" y="81" {WORD} font-size="62" letter-spacing="-1" fill="{text}">the bee</text>''',
        ' aria-label="The Bee logo"')


write("logo-horizontal.svg", horizontal("lh", HONEY, INK, CREAM, CREAM, INK))
write("logo-horizontal-reversed.svg", horizontal("lhr", HONEY, INK, CREAM, CREAM, CREAM))

write("logo-stacked.svg", svg("0 0 260 210",
      f'''<g transform="translate(80 8)">{hex_mark("ls", HONEY, INK, CREAM, CREAM)}</g>
  <text x="130" y="188" text-anchor="middle" {WORD} font-size="54" letter-spacing="-1" fill="{INK}">the bee</text>''',
      ' aria-label="The Bee logo, stacked"'))

# ---------------------------------------------------------------- one-colour
write("logo-mono-ink.svg", svg("0 0 400 120",
      f'''<g transform="translate(8 12) scale(0.96)">
    <path d="{HEX}" fill="{INK}"/>
    <g {BEE_IN_HEX}>{bee_solid("mi", "#ffffff", INK, "#ffffff", "1")}</g>
  </g>
  <text x="126" y="81" {WORD} font-size="62" letter-spacing="-1" fill="{INK}">the bee</text>''',
      ' aria-label="The Bee logo, single colour"'))

write("logo-mono-cream.svg", svg("0 0 400 120",
      f'''<g transform="translate(8 12) scale(0.96)">
    <path d="{HEX}" fill="{CREAM}"/>
    <g {BEE_IN_HEX}>{bee_solid("mc", INK, CREAM, INK, "1")}</g>
  </g>
  <text x="126" y="81" {WORD} font-size="62" letter-spacing="-1" fill="{CREAM}">the bee</text>''',
      ' aria-label="The Bee logo, reversed single colour"'))

# ---------------------------------------------------------------- icon + favicon
write("icon-app.svg", svg("0 0 512 512",
      f'''<rect width="512" height="512" rx="114" fill="{INK}"/>
  <g transform="translate(256 262) scale(4.5) translate(-50 -49)">{bee_solid("ic", HONEY, INK, CREAM, "0.26")}</g>''',
      ' aria-label="The Bee app icon"'))

# Favicon drops the antennae and thins the stripes - they disappear below 24px.
write("favicon.svg", svg("0 0 100 100",
      f'''<path d="{HEX}" fill="{HONEY}"/>
  <g transform="translate(50 52) scale(0.86) translate(-50 -49)">
    <ellipse cx="30" cy="40" rx="15" ry="8" transform="rotate(30 30 40)" fill="{CREAM}"/>
    <ellipse cx="70" cy="40" rx="15" ry="8" transform="rotate(-30 70 40)" fill="{CREAM}"/>
    <circle cx="50" cy="30" r="9" fill="{INK}"/>
    <clipPath id="fv-b"><path d="{BODY}"/></clipPath>
    <path d="{BODY}" fill="{INK}"/>
    <g clip-path="url(#fv-b)" fill="{CREAM}">
      <rect x="30" y="46" width="40" height="7"/>
      <rect x="30" y="60" width="40" height="7"/>
    </g>
  </g>''',
      ' aria-label="The Bee favicon"'))
