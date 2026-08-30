# Photographs

Eight places in the brochure are pictures. Right now every one of them is drawn
by [`../art.py`](../art.py) -- a wave with somebody in the barrel, the line-up
seen from the water, swell coming in, the rack of rental boards -- because the
machine this was built on cannot reach a photograph, and a booklet with grey
boxes in it is not a booklet.

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

## The eight slots

| file     | where it goes                      | shape           | 300 dpi     |
|----------|------------------------------------|-----------------|-------------|
| `cover`  | across the bottom of the cover     | 8.5 × 4.35 in   | 2550 × 1305 |
| `place`  | across the lower half of p. 2      | 8.5 × 3.42 in   | 2550 × 1026 |
| `surf`   | across the top of p. 3             | 8.5 × 3.36 in   | 2550 × 1008 |
| `camps`  | across the top of p. 4             | 8.5 × 2.82 in   | 2550 × 846  |
| `beyond` | across the top of p. 5             | 8.5 × 2.72 in   | 2550 × 816  |
| `boards` | across the top of p. 6             | 8.5 × 1.78 in   | 2550 × 534  |
| `shop`   | across the top of p. 7             | 8.5 × 1.82 in   | 2550 × 546  |
| `back`   | across the bottom of the back      | 8.5 × 4.0 in    | 2550 × 1200 |

`camps` wants people in it -- a group, not a wave. `shop` wants the racks or
the counter.

Every one of them is a wide band, which is the shape a phone takes a photograph
in when it is held the way people hold it at a beach. No slot wants a portrait
crop.

300 dpi is what a print shop asks for. A phone photograph from the last few
years clears it easily at these sizes; a screenshot or something saved off
Instagram will not, and will look soft on paper in a way it never does on a
screen.

## Choosing them

* **Every picture is cropped to fill its box**, from the centre, and the boxes
  are shallow -- `boards` is four times as wide as it is tall. Put the subject
  on the horizontal centre line and expect the top and bottom to go.
* **`cover` and `back` sit on the deep ink pages**, with the type above them
  rather than over them, so a photograph there does not have to survive a wash
  -- but it does have to sit next to that colour. Something with water in it,
  shot late, works; a bright midday shot will fight the page.
* **The cover's drawing has no background of its own**, because the striped sun
  is behind it and shows through everywhere the water is not. A photograph does
  have a background, so dropping one into `cover` covers the lower half of that
  sun. That is fine -- a real wave beats a drawn one -- but it is a different
  cover, and worth looking at before printing a hundred.
* **`boards` currently draws the eight rental boards in the order the list
  under it names them**, so it reads as a key as well as a picture. A
  photograph of the actual rack, in that order, does the same job better --
  anything else loses that, which is fine, but is worth knowing.
* The booklet is deep sea, sand and bone with pink on top of it, so cold
  photographs belong here and over-saturated ones do not. If a shot is very
  blue, warm it a little; if it is very orange, pull it back.

## Rights

Only put photographs here that the school owns or has permission to print.
This booklet goes in guest rooms and to a print shop, which is commercial use;
an image found on the internet is not cleared for that just because it is easy
to download.
