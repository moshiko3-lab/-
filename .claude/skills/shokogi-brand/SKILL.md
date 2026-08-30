---
name: shokogi-brand
description: >-
  The SHOKOGI visual identity — palette, typography, logo rules, artboard sizes and a Chromium
  render pipeline — for every piece the surf school puts in front of a person. Use this skill
  whenever you are making anything SHOKOGI that will be looked at: a flyer, poster, price
  list, sign, menu, business card, sticker, book or brochure cover, Instagram or Facebook or
  WhatsApp graphic, link-preview image, landing page, booking page, email header, slide deck,
  or a restyle of app_template.html or minisite_template.html. Use it even when the request
  never says "design" or "brand" — "make a flyer for the five-day camp", "a cover image for
  the booking page", "something to print for the hostel wall" all need it, in English or in
  Hebrew. Not for code, data or copy that nobody sees rendered.
---

# SHOKOGI

A surf school on Playa Venao, Panama, teaching since 2009. Everything it prints
or publishes should look like it came from the same place as the booking page:
one pink, one slate, very heavy uppercase Latin, and a lot of air.

The identity is not invented here. It is read off what already ships —
`app/app_template.html`, `app/minisite_template.html` and `app/logo.png` — and
extended only where paper needs something a screen did not. When those files
change, `references/tokens.md` is the place to reconcile.

## Start here

```bash
SKILL=.claude/skills/shokogi-brand
mkdir -p work
cp $SKILL/assets/{brand.css,logo.png,flyer.html,cover.html} work/
python3 $SKILL/scripts/fonts.py --out work/fonts.css        # once per machine
# edit work/flyer.html, then:
python3 $SKILL/scripts/render.py work/flyer.html --preset a4 --out work/flyer.pdf
python3 $SKILL/scripts/render.py work/flyer.html --preset a4 --out work/flyer.png --dpi 300
```

The four files travel together: `flyer.html` reaches `brand.css`, `fonts.css`
and `logo.png` as siblings, so copy them into the same folder and render from
wherever you like.

`fonts.py` matters more than it looks. This container has no Figtree and no
Hebrew font at all, so a page that merely names them renders in DejaVu and the
piece stops being SHOKOGI. Run it before the first render; it caches into
`assets/fonts/` and is instant afterwards. Use `--embed` for any file that
leaves this machine.

`render.py --preset` lists every size it knows (run it bare). It writes a PDF
for print and a PNG for screens, checks the PDF really came out one page at the
size you asked for, and crops the PNG to the exact box — headless Chromium
quietly loses the bottom 87 px of a screenshot otherwise.

## The five things that make it look right

**One pink, used sparingly.** `--pink-500 #f46e95` is the school. A piece that
is 40 % pink swallows the badge and reads as a cosmetics ad; the pink should be
the loudest small thing on the page — a footer band, a rule, a price, a wash
behind a photo — against slate, near-black or paper.

**Ink on pink, never white on pink.** White on `#f46e95` measures 2.8:1, which
fails even the large-text bar, and on a printed flyer in daylight it is worse
than the number suggests. Put `--ink #121011` on pink (6.8:1). If a piece truly
needs white type on pink, deepen the field to `--pink-700 #9c465f` (6.1:1).

**Latin shouts, Hebrew does not.** Display Latin is Figtree 800–900, uppercase,
tracked `.10em`; it is the voice off the hexagon badge. Hebrew has no uppercase
and comes apart when tracked, so it carries the same weight in Heebo at normal
tracking. `brand.css` does this switch on `[lang="he"]` and `[dir="rtl"]` by
itself — set the attribute and leave the type alone. See `references/hebrew.md`
before laying out anything Hebrew; the traps are in the mixed lines, not the
Hebrew ones.

**The badge needs white under it.** The logo is pink line-art with no knockout
version, so it vanishes on pink and muddies on slate. On anything that is not
near-white, use the white chip (`.logo-chip`) the booking page header already
uses. Keep clear space of a third of its width, and never set it below 14 mm on
paper or 40 px on screen — the "PANAMA PLAYA VENAO" ring closes up.

**Air is the house style.** The booking page breathes: 16 mm margins on A4,
generous gaps, one idea per band. Crowding is the fastest way to make this brand
look like a template.

## Choosing the piece

| Asked for | Preset | Notes |
|---|---|---|
| Flyer, price list, hostel wall | `a4`, `a5`, `dl` | Start from `assets/flyer.html` |
| Poster | `a3`, `poster-50x70` | Scale the type, not the margins |
| Instagram, WhatsApp status | `ig-post`, `ig-story` | PNG, 96 dpi is enough |
| Facebook / YouTube / LinkedIn cover | `fb-cover`, `yt-banner`, `li-banner` | Keep type off the outer 10 % |
| Link preview for the booking page | `og` | 1200×630 |
| Card, sticker | `business-card` | Bleed matters, see print.md |
| Landing or booking page | — | `references/web.md`, not a fixed size |

## Where the detail lives

- `references/tokens.md` — the full palette with measured contrast, the type
  scale, spacing and radii. Read it when you need a value that is not in
  `brand.css`, or before adding a colour.
- `references/print.md` — bleed, safe area, dpi, what to hand a print shop,
  and the CMYK conversation. Read before anything that gets physically printed.
- `references/web.md` — how a page stays in step with the app's own tokens,
  dark mode, and the components the booking page already established.
- `references/hebrew.md` — RTL layout and Hebrew typography, including the bidi
  traps in prices and mixed English lines. Read before any Hebrew piece.

## Working habits

Render and look at what you made before you show it. `render.py` gives you a
PNG in a second; open it. Half the faults in a layout — a clipped footer, type
that collapsed to a fallback font, a headline that broke on the wrong word — are
invisible in the HTML and obvious in the image.

Keep the copy short. This is a surf school, not a prospectus: a headline of
three or four words, one sentence under it, prices as figures. If a flyer needs
a paragraph, the flyer is the wrong format.

When you invent something the system does not have — a second accent, a new
card shape — say so plainly rather than quietly adding it, and if it earns its
place, write it into `brand.css` and `references/tokens.md` so the next piece
inherits it instead of reinventing it.
