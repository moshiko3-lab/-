# The room brochure

`shokogi-brochure.pdf` is the six-page booklet that goes in guest rooms. It is
in English and Spanish throughout, on US Letter, and it carries the booking
page's QR code twice -- once beside the services on page four, once filling the
back cover.

    01  cover           the mark on deep ink, and nothing else
    02  the place       Playa Venao, and what a first lesson is
    03  in the water    private, shared, packs, video analysis
    04  the rest of     SUP, foil, yoga, ice bath, photo, kids, trips
        the day         -- and the code to book any of it
    05  take one out    the eight boards for rent, and what to know
    06  reserve         the code, the address, the way to reach us

## Building it

    python3 print/build_brochure.py                  # -> print/shokogi-brochure.pdf
    python3 print/build_brochure.py --size a4        # 210x297 for a European printer
    python3 print/build_brochure.py --html out.html  # the pages, to open in a browser

It needs `segno` for the code and a Chromium to print with; Playwright's copy,
the one the rest of this repository is tested against, is found automatically.

    pip install segno

The PDF is committed rather than only built, because the person who walks it to
a print shop is not going to have Python. Rebuild it and commit the result
whenever the wording or the pictures change.

## Checking it

    pip install pypdfium2 opencv-python-headless
    python3 print/test_brochure.py

Six pages, the right paper size, no type inside the trim, and both QR codes
read back off the rendered page and compared against the booking URL. That last
one is the only part of the booklet with a job to do, and the only part that
cannot be proof-read by looking at it.

## Printing it

* **100%, no scaling.** "Fit to page" shrinks everything and puts a white frame
  around the ink -- the design already holds its own margins.
* **Borderless if the printer offers it.** Two covers and three picture bands
  run to the paper's edge. A printer that cannot go borderless trims about an
  eighth of an inch; no type sits there, so it costs picture and nothing else.
* **Six pages is three sheets, printed both sides.** Folded and stapled it is a
  booklet; loose in a folder or a stand it still reads in order.
* **Matte or silk stock, 170 gsm or better**, if a shop is doing it. Pages one
  and six are solid deep ink, and thin paper will show them through from the
  back. Matte suits the hairline drawings; high gloss fights them.
* Print one copy and scan the code off it before ordering a hundred.

## Changing what it says

All of the wording is in [`content.py`](content.py), English and Spanish side
by side; `build_brochure.py` only decides how it looks. Nothing in there quotes
a price on purpose -- a printed booklet cannot follow a price list, so the code
carries a reader to the booking page where today's prices are.

## Where the look comes from

The brand is the storefront's, matching `bloowatch/site_template.html`, but
turned down: a sheet that is mostly pink reads as a flyer, so here the pink is
an accent on warm cream and deep ink instead of a field. Display type is
Cormorant Garamond, text is Figtree -- the storefront's own sans -- and labels
stay in IBM Plex Mono. The logo is read straight out of `app/logo.png`, so the
mark on paper cannot drift from the mark on screen, and its hexagon is reused
for the bullets and the middle of the QR code. The fonts are already base64'd
into `fonts.css` so a build makes the same booklet on any machine, with or
without a network.

Every picture is drawn by [`art.py`](art.py) rather than photographed, and
[`images/README.md`](images/README.md) says how to replace any of them with a
real photograph -- which is one file per slot and no layout work.
