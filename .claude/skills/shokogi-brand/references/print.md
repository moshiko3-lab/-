# Print

## Sizes the school actually uses

| Preset | Size | What it is for |
|---|---|---|
| `a4` | 210 × 297 mm | The main flyer, price list, wall sheet |
| `a5` | 148 × 210 mm | Handout at the hostel desk, table card |
| `a6` | 105 × 148 mm | Postcard, insert |
| `dl` | 99 × 210 mm | Rack card — fits a tourist-info rack |
| `a3` | 297 × 420 mm | Notice board |
| `poster-50x70` | 500 × 700 mm | Bar or shopfront poster |
| `square-print` | 210 × 210 mm | Menu or lookbook page |
| `business-card` | 85 × 55 mm | Card, sticker |

## Bleed and safe area

A trimmed sheet is never cut exactly where you drew it. Two rules keep that
from mattering:

* **Anything that must be seen** — type, prices, the logo, the URL — stays
  inside 12 mm from every edge. That is what `.safe` is.
* **Anything that must reach the edge** — a pink band, a photo, a dark ground —
  runs 3 mm past it. That is what `.bleed` is. A background that stops exactly
  at 0 mm shows a white hairline on half the copies.

If the printer asks for a bleed PDF, give them a page 6 mm larger in each
dimension with the artwork centred, or say plainly that the file is trim-size
with 3 mm of internal bleed and let them impose it. Do not fake crop marks.

## Resolution

`render.py` writes PDFs with live vector text, which is what a print shop wants
and what stays crisp at any size. Use PDF for anything printed.

PNG is for screens and for the odd shop that only accepts images. When you must
send a PNG to print, `--dpi 300`; at A4 that is 2480 × 3508 px. `--dpi 150` is
for proofing on screen — fine to look at, too soft to print. Never send a 96 dpi
export to a printer.

`logo.png` is 256 × 250 px. At 28 mm wide that is about 230 dpi — acceptable at
flyer size, visibly soft on an A3 or a poster. For anything A3 or larger, set
the logo in the white chip at 28–35 mm and no bigger, or ask for a vector
version of the badge before going large.

## Colour

Everything here is sRGB. A print shop converting to CMYK will shift the pink
slightly duller — `#f46e95` is at the edge of what four-inks can hold. That is
normal and not worth fighting, but it is worth saying to whoever prints it, and
worth checking on a proof before a long run. Deep slate `#101418` prints as a
rich near-black; ask for it as a rich black rather than 100 % K if the piece is
mostly dark, or it will look grey against the paper.

## Handing it over

Send the PDF, not the HTML, and say the trim size and whether bleed is included.
Keep the source HTML in the repo next to the piece so the next season's prices
are a two-minute edit rather than a redraw.
