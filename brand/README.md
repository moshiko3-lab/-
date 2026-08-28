# the bee — brand assets

Everything here is drawn from one shared geometry in `generate.py`. Edit the
geometry once and run `python3 generate.py` to redraw every file.

## The mark

A bee sitting in a single comb cell. The hexagon is the idea: it tiles, so the
mark extends into patterns, containers and crops without the bee ever being
redrawn. It sits point-up, always.

## Files

| File | Use |
| --- | --- |
| `logo-horizontal.svg` | Primary lockup, light grounds |
| `logo-horizontal-reversed.svg` | Primary lockup, dark grounds |
| `logo-stacked.svg` | Narrow and square placements |
| `logo-mono-ink.svg` / `logo-mono-cream.svg` | Single-colour print, foil, etch |
| `mark-hex.svg` / `mark-hex-reversed.svg` | Mark alone, both grounds |
| `mark-monoline.svg` / `mark-monoline-dark.svg` | Direction 02, light and dark |
| `mark-stripe.svg` | Direction 03 |
| `icon-app.svg` | 512 px app icon |
| `favicon.svg` | 16–32 px, antennae removed |
| `identity.html` | The full identity presentation |

## Palette

| Name | Hex | Use |
| --- | --- | --- |
| Honey | `#E8A33D` | Primary. The cell, the accent. |
| Deep Honey | `#B8701A` | Links, hover, small type on cream. |
| Ink | `#17130F` | The bee, headlines. Warm, never blue-black. |
| Wax | `#FAF3E6` | Wings, stripes, paper ground. |
| Meadow | `#4F6B4A` | Secondary only. Never inside the mark. |

## Type

- **Fraunces 600** — wordmark and headlines.
- **Archivo 400/500/600** — body, UI, small print.

## Clear space and minimum size

One unit `x` = half the cell height. Keep `x` clear on all four sides.
Minimums: lockup 96 px wide, mark 24 px, favicon 16 px (use `favicon.svg`).

## Don't

- Stretch the cell to fill a space — use the stacked lockup.
- Rotate the cell. It is point-up so it tiles.
- Put the honey cell on a mid-tone colour. Ink, wax or a dark photo area only.

## Before final release

The wordmark in the SVGs is live text in Fraunces. Convert it to outlines so
the files no longer depend on the font being installed.
