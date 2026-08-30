# The room brochure

`shokogi-brochure.pdf` is the four-page sheet that goes in guest rooms. It is
in English and Spanish throughout, on US Letter, and every page carries a QR
code pointing at the booking page.

    Cover          the mark, what the school does, and a code to scan
    In the water   lessons, packs, video analysis, Young Guns, surf trips
    More than surf SUP, foil tow-in, yoga and pilates, ice bath, photo, the crew
    Take one out   board rental, what is worth knowing, and the code again

## Building it

    python3 print/build_brochure.py                  # -> print/shokogi-brochure.pdf
    python3 print/build_brochure.py --size a4        # 210x297 for a European printer
    python3 print/build_brochure.py --html out.html  # the page itself, to open in a browser

It needs `segno` for the code and a Chromium to print with; Playwright's copy,
the one the rest of this repository is tested against, is found automatically.

    pip install segno

The PDF is committed rather than only built, because the person who walks it to
a print shop is not going to have Python. Rebuild it and commit the result
whenever the wording changes.

## Checking it

    pip install pypdfium2 opencv-python-headless
    python3 print/test_brochure.py

Four pages, the right paper size, no type inside the trim, and every QR code
read back off the rendered page and compared against the booking URL. The last
one is the whole point of the sheet, and it is the one thing that cannot be
proof-read by looking at it.

## Printing it

* **100%, no scaling.** "Fit to page" shrinks everything and puts a white frame
  around the pink -- the design already holds its own margins.
* **Borderless if the printer offers it.** The pink field runs to the paper's
  edge. A printer that cannot go borderless trims about an eighth of an inch;
  no type sits there, so it costs colour and nothing else.
* **Coated or silk paper**, at least 150 gsm, if a shop is doing it. The pink
  covers most of the cover and thin uncoated stock will show through from the
  back.
* Print a single copy and scan the code off it before ordering a hundred.

## Changing what it says

All of the wording lives in [`content.py`](content.py), in English and Spanish
side by side; `build_brochure.py` only decides how it looks. Nothing in there
quotes a price, on purpose -- a printed sheet cannot follow a price list, so
the code carries a reader to the booking page where today's prices are.

The brand -- the pink, Figtree, the tracked uppercase labels, the hexagon --
is the storefront's, matching `bloowatch/site_template.html`. The logo is read
straight out of `app/logo.png`, so the mark on paper cannot drift from the mark
on screen. The fonts are already base64'd into `fonts.css` so a build makes the
same sheet on any machine, with or without a network.
