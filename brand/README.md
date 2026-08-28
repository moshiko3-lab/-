# the bee — boat marks

Marks for the dinghy *the bee*. Everything is redrawn from one geometry by
`generate.py`; run `python3 generate.py` after any change.

Open `marks.html` for the full presentation.

## The mark

Two swept wings, a head, three tapering bands. It reads twice — a bee seen
from above, and the wake of something small moving fast.

It is built for one production method: single-colour cut vinyl at small size.

- **No holes.** Every piece is positive, so nothing has to be weeded out of an
  interior and nothing floats off the backing sheet.
- **No hairlines.** The thinnest element is a wing tip at 2.8 mm when the mark
  is cut 60 mm tall. That sets the minimum size.
- **No sharp points.** Every corner is rounded — sharp tips lift first.

## Files

| File | Use |
| --- | --- |
| `logo-bow-two-tone.svg` / `-navy` / `-foam` | Bow lockup, three colourways |
| `logo-transom-two-tone.svg` / `-navy` / `-foam` | Stacked lockup for the stern |
| `mark-two-tone.svg` / `-navy` / `-honey` / `-foam` | Mark alone |
| `wordmark-navy.svg` / `-foam` | Name alone, outlined |
| `roundel-navy.svg` / `-honey` | Sticker and badge version |
| `cut-mark.svg` / `cut-bow.svg` / `cut-transom.svg` | Single-colour cut files for the vinyl shop |
| `generate.py` | Redraws every file |
| `wordmark.path` / `outline_wordmark.py` | The outlined name, and how to regenerate it |
| `archive/` | The first round (hive cell / honey), kept for reference |

## Colour

| Name | Hex | Use |
| --- | --- | --- |
| Navy | `#12283F` | On white, grey or wood hulls. The default. |
| Honey | `#E8A33D` | The wings in two-colour. Alone only on navy. |
| Foam | `#F7F4EC` | On navy, black or dark grey hulls and tubes. |

Two-colour is a layered cut — a second sheet plus a registration step. One
colour is what to order for a quick turnaround.

## Sizes on the boat

| Placement | Size | File |
| --- | --- | --- |
| Hull side, forward | 120 mm wide | `cut-bow.svg` |
| Transom | 90 mm tall | `cut-transom.svg` |
| Oar blade, tube, tiller | 60 mm tall | `cut-mark.svg` |
| Gunwale, trailer | 35 mm cap height | `wordmark-navy.svg` |

Never below a 60 mm mark height. Ask for marine cast vinyl (not calendared) so
it follows a curved hull. Nothing here is antifoul-safe — topsides only.

## Type

The name is Fraunces Bold Italic, already converted to outlines in every
delivered file. No font is needed downstream.
