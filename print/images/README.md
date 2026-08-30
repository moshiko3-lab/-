# Photographs

Six places in the brochure are pictures. Right now every one of them is drawn
by [`../art.py`](../art.py) -- contour fields, lines of swell, the rack of
boards on the rental page -- because the machine this was built on cannot
reach a photograph, and a booklet with grey boxes in it is not a booklet.

Drawings are a decent default. They are not better than a photograph of this
beach, taken by the people who already sell photography here. Replacing them
is one file each and no layout work at all.

## Dropping one in

Put a file in this folder named after the slot. `cover.jpg` replaces the cover
drawing, `surf.jpg` the band on the lessons page, and so on. Then rebuild:

    python3 print/build_brochure.py

`.jpg`, `.jpeg`, `.png` and `.webp` are all read. The build prints which slots
found a photograph and which are still drawn. Nothing else changes -- a photo
and a drawing fill the same box the same way, so the type does not move.

## The six slots

| file       | where it goes                     | shape            | 300 dpi     |
|------------|-----------------------------------|------------------|-------------|
| `cover`    | the whole front cover             | 8.5 × 11 in      | 2550 × 3300 |
| `coast`    | the column down the right of p. 2 | 3.02 × 11 in     |  906 × 3300 |
| `surf`     | the band across the top of p. 3   | 8.5 × 3.92 in    | 2550 × 1176 |
| `beyond`   | the column down the left of p. 4  | 2.66 × 11 in     |  798 × 3300 |
| `boards`   | the band across the top of p. 5   | 8.5 × 2.125 in   | 2550 × 638  |
| `back`     | the whole back cover              | 8.5 × 11 in      | 2550 × 3300 |

300 dpi is what a print shop asks for. A phone photograph from the last few
years clears it easily at these sizes; a screenshot or something saved off
Instagram will not, and will look soft on paper in a way it never does on a
screen.

## Choosing them

* **Every picture is cropped to fill its box**, from the centre. `coast` and
  `beyond` are very tall and narrow, so a wide landscape shot loses both its
  sides in them -- give those two a vertical frame, or one with the subject
  dead centre. `surf` and `boards` are the opposite: wide and shallow.
* **The two covers are printed under a dark wash**, which is what the white
  type sits on. Pictures with one strong shape survive that; pictures with
  fine detail all over them turn to mud. A wave, a horizon, a single surfer.
* **`boards` currently draws the eight rental boards in the order the list
  under it names them**, so it reads as a key as well as a picture. A
  photograph of the actual rack, in that order, does the same job better --
  anything else loses that, which is fine, but is worth knowing.
* Keep them warm. The whole booklet is cream, deep ink and one pink; cold
  blue-grey photographs will sit outside it. If a shot is cold, warm it
  slightly before dropping it in.

## Rights

Only put photographs here that the school owns or has permission to print.
This booklet goes in guest rooms and to a print shop, which is commercial use;
an image found on the internet is not cleared for that just because it is easy
to download.
