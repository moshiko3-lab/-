# The flyers

Two service flyers — board rentals and surf lessons — built in the house style
set by the private-surf-photo-session poster: a light 2:3 sheet, a condensed
pink headline over a washed photograph, a text column on the left, feature rows
parted by pink hairlines, one solid pink call to action, and the wordmark twice.

    python3 build_flyers.py           # HTML + PNG + JPG into out/
    python3 build_flyers.py --html    # HTML only, if there is no browser here

`out/*.jpg` are the ones to post; the PNGs are lossless masters and the HTML is
what the browser actually renders, so a change is made in `build_flyers.py`, not
in the pictures.

## Where the measurements come from

Every number in `build_flyers.py` was read off the photo-session flyer at
1024x1536 — the margin at 71px, the wordmark 241px wide with its cap 32px tall,
the headline's 121.5px line pitch, the 77px call to action, the footer wordmark
at 301px. Type is Oswald 700 for display and Montserrat for everything else,
both under the SIL Open Font License and committed in `fonts/`.

The two flyers carry a two-word headline where the photo-session poster carries
three, so the gaps between blocks are flex weights rather than fixed pixels:
the slack from the missing line spreads across every gap in the same
proportions the original had, and the foot of the column still lands where it
lands on the third poster.

## The photographs

`photos/` holds the two surf shots cut out of the first versions of these
flyers — the left column of each old flyer was cropped away, so what remains
starts at the first pixel that carried no type. That crop is why each
photograph is only around 630-700px wide: it is placed at its natural scale
against the 1536px height, hung on the right edge, and dissolved into the page
on its left by a mask plus a veil tuned per flyer.

The lessons shot needs the gentler hand of the two: the surfer's head sits
right on the crop's left edge, so its veil clears early and its mask fades over
70px rather than 20 — enough to lose the edge without losing his face. If a
full-frame original of either photograph turns up, drop it into `photos/` and
the veils can be pulled back a long way.

## Adding a third flyer

Append a dict to `FLYERS`: the slug, the photo, the headline (two lines,
`<br>`-separated), the lede, four icon-and-text rows, and the call to action.
Icons are single-stroke paths on a 24-grid in `ICONS`, with `INK_LEFT` saying
how far each drawing sits from the left of its grid so every icon still starts
hard on the column edge.
