# Tokens

Every value here is either already in `app/app_template.html` /
`app/minisite_template.html`, or derived from one that is by mixing toward
white or black. Nothing is invented from scratch, which is why a flyer sits
next to the booking page without arguing with it.

## Pink

The school's colour. `--pink-500` is the interface accent; the printed badge is
a shade duller, and that is the one to match when the logo sits beside a pink
field.

| Token | Hex | Use |
|---|---|---|
| `--pink-50` | `#fef6f9` | Tinted paper, table stripes |
| `--pink-100` | `#fdebf0` | Chip and tag backgrounds (the app's `--accent-soft`) |
| `--pink-200` | `#fcd6e1` | Dividers on tinted ground |
| `--pink-300` | `#fab6ca` | Type on slate or near-black (11.1:1 on `--slate-900`) |
| `--pink-400` | `#f792b0` | Hover states, secondary fills |
| `--pink-500` | `#f46e95` | **The brand pink.** Bands, rules, washes, large fills |
| `--pink-600` | `#c85a7a` | Pressed states; white type at 4.0:1 (large only) |
| `--pink-700` | `#9c465f` | Headings on paper (6.1:1); white type on it (6.1:1) |
| `--pink-800` | `#6e3143` | Deep accents |
| `--pink-900` | `#441f2a` | Near-black with pink in it |
| `--pink-logo` | `#e37695` | The actual ink of the badge in `logo.png` |
| `--pink-ui` | `#e04b78` | Links and buttons on light screens (3.9:1) |

## Slate

The cool counterweight — the app's rail, the booking page's chrome, and the
ground for any piece that wants to look like evening rather than midday.

| Token | Hex | Use |
|---|---|---|
| `--slate-50` … `--slate-300` | `#f3f4f5` `#e3e5e7` `#c8cbcf` `#9ca2aa` | Borders, muted type on dark |
| `--slate-400` | `#6a747f` | Secondary type on paper |
| `--slate-500` | `#394654` | The app's `--slate`; 9.6:1 on white either way |
| `--slate-600/700` | `#2f3945` `#242d36` | Panels on dark pieces |
| `--slate-800/900` | `#1a1f26` `#101418` | Full-bleed dark grounds (18.5:1 with white) |

## Ground and ink

Warm, never neutral. A pure `#000` or `#fff` beside this pink looks cheap.

`--paper #f7f5f6` · `--paper-2 #faf7f8` · `--paper-3 #f2ecee` · `--white #fff`
`--ink #121011` (17.5:1 on paper) · `--ink-2 #5c5257` (6.9:1) · `--ink-3 #8d8288` (labels only)
`--line #e6dfe2` · `--line-soft #efe9eb`

Status colours carry over from the app unchanged: `--good #1f7a4d`,
`--warn #9a6a10`, `--crit #b23a2c`, each with a `-soft` tint. On dark grounds
they lighten to `#5ec98d` / `#e0ae4a` / `#f0705c`.

## Contrast, measured

Do not guess these; they were computed, and two of them are counter-intuitive.

| Pair | Ratio | Verdict |
|---|---|---|
| white on `--pink-500` | 2.80 | **Fails everything.** The one mistake to avoid |
| white on `--pink-ui` | 3.86 | Large type only (≥24 px or ≥19 px bold) |
| white on `--pink-700` | 6.08 | Fine anywhere |
| `--ink` on `--pink-500` | 6.78 | Fine anywhere — this is the house combination |
| `--pink-500` on `--slate-900` | 6.62 | Fine anywhere |
| `--pink-300` on `--slate-900` | 11.11 | Body copy on dark pieces |
| `--ink` on `--paper` | 17.46 | Default |

The booking page's own header puts white on `--accent-hot`, which is that 2.8:1
case. It survives there because it is 14 px bold uppercase on a screen the
reader chose to open. Do not carry it onto paper, and do not extend it to
anything smaller or longer.

## Type

Three families, no more. Figtree and IBM Plex Mono are what the app ships;
Heebo is the Hebrew companion, chosen because its weight and roundness match
Figtree closely enough that a bilingual flyer does not look assembled.

| Role | Family | Setting |
|---|---|---|
| Display | Figtree 900 | uppercase, `letter-spacing:.10em`, `line-height:1.02` |
| Eyebrow / label | Figtree 700 | uppercase, `.16em`, 11–12 px |
| Lede | Figtree 500 | sentence case, `line-height:1.45` |
| Body | Figtree 400 | `line-height:1.55`, never below 12 px in print |
| Figures, prices, codes | IBM Plex Mono 600 | `font-variant-numeric:tabular-nums` |
| All Hebrew | Heebo 400–900 | tracking 0, `line-height:1.15` display / 1.6 body |

Scale, in the `brand.css` classes: hero 76 · h1 48 · h2 32 · h3 22 · body 15 ·
small 13 · micro 11. Pick a step. Interpolating between them is how a set of
pieces stops looking like a set.

## Spacing, radii, shadow

Print margins are in millimetres and screen padding in pixels, because that is
how each medium is actually judged. A4 and A5 take a 12–16 mm margin; the safe
area is 12 mm and `brand.css` `.safe` is set to it. On screen the app's rhythm
is 4 / 8 / 12 / 16 / 24 / 32 px.

Radius is `--r 12px` for panels and `--r-sm 6px` for cards and buttons — the
booking page's own values. Shadows (`--shadow`, `--shadow-lg`) are screen-only:
on paper they print as grey smudge, so drop them from anything going to a
printer and use `--line` instead.
