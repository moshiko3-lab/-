# The room brochure

`shokogi-brochure.pdf` is the six-page booklet that goes in guest rooms. It is
in English and Spanish throughout, on US Letter, and it carries the booking
page's QR code twice -- once beside the services on page four, once filling the
back cover.

    01  cover           the name over a wave with somebody in it
    02  the place       Playa Venao, a first lesson, and the line-up
    03  in the water    where to start, then the four ways to have a lesson
    04  the rest of     SUP, foil, yoga, ice bath, photo, kids, camps,
        the day         trips -- and the code to book any of it
    05  the quiver      every board the school owns, counted
    06  reserve         what to bring, the code, and how to reach us

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

Six pages, the right paper size, no type inside the trim, both QR codes read
back off the rendered page and compared against the booking URL, and the board
figures on page five checked against the catalogue they were counted from.

The codes are the only part of the booklet with a job to do and the only part
that cannot be proof-read by looking at it. The quiver figures are the only
part that could go wrong silently: they are counted, not typed, so a changed
export shape would print zeroes rather than an error.

## Printing it

* **100%, no scaling.** "Fit to page" shrinks everything and puts a white frame
  around the ink -- the design already holds its own margins.
* **Borderless if the printer offers it.** Two covers and three picture bands
  run to the paper's edge. A printer that cannot go borderless trims about an
  eighth of an inch; no type sits there, so it costs picture and nothing else.
* **Six pages is three sheets, printed both sides.** Folded and stapled it is a
  booklet; loose in a folder or a stand it still reads in order.
* **The file is around 5 MB**, most of it the dot screen on the two poster
  pages. That is normal for print and small for a shop; it is only worth
  mentioning because emailing it may need a link rather than an attachment.
* **Matte or silk stock, 170 gsm or better**, if a shop is doing it. Pages one,
  three and six are solid deep ink edge to edge -- thin paper shows them
  through from the other side, and cheap paper drinks that much ink and goes
  soft. Ask for matte or silk rather than high gloss.
* Print one copy and scan the code off it before ordering a hundred.

## Changing what it says

All of the wording is in [`content.py`](content.py), English and Spanish side
by side; `build_brochure.py` only decides how it looks. Nothing in there quotes
a price on purpose -- a printed booklet cannot follow a price list, so the code
carries a reader to the booking page where today's prices are.

Page five is the exception, and deliberately so. Its numbers -- how many boards,
how short and how long, which shapers, how many of each length -- are not
written anywhere. [`quiver.py`](quiver.py) counts them off `app/catalog.json`,
the school's own inventory, so a rebuild after the next export prints what is
true then. That page is the closest thing here to a wetsuit brand's spec sheet,
and it is worth as much as it is accurate.

## Where the look comes from

It is meant to read as a surf school's booklet and not as a hotel's, and what
finally got it there was not another drawing -- it was the furniture around
them. Surf print is a screen-printed medium and has been since the sixties:
flat inks, a dot screen where a photograph would be, stripes, and a patch
sewn on somewhere. All four are in `art.py` and all four are on the cover.

The palette is the water rather than the brand sheet -- deep sea, sand and
bone, with the storefront's pink kept as the accent it is good at, and amber
and coral behind it for the hour worth surfing. A page that is mostly pink
reads as a flyer and a page that is mostly cream reads as a spa. The display
face is Archivo set wide and heavy, where a fine serif at the same size reads
as a boutique hotel however well it is set. Figtree, the storefront's own sans,
does the reading; IBM Plex Mono does the labels, the numbers and the type that
runs round the patches.

One thing about the dot screen is worth knowing before anyone tunes it. Its
dots are drawn, not tiled from an SVG `<pattern>`: Chromium rasterises a
pattern on its way into a PDF, and at print size the screen came out as soft
grey squares rather than dots. Some thousands of real circles stay vector all
the way to the plate -- and cost about three megabytes, which is why the screen
is on the two poster pages and not on the four with paragraphs on them.

The logo comes straight out of `app/logo.png`, so the mark on paper cannot
drift from the mark on screen, and its hexagon is reused for the bullets and
the middle of the QR code. The fonts are base64'd into `fonts.css` so a build
makes the same booklet on any machine, with or without a network.

Every picture is drawn by [`art.py`](art.py) rather than photographed: a wave
with somebody in the barrel, the line-up seen from the water, swell coming in,
the day's tide, and the eight rental boards at their real relative proportions
in the order the list beside them names them.
[`images/README.md`](images/README.md) says how to replace any of them with a
real photograph -- one file per slot, and no layout work.

The one chart in the booklet, on page five, uses two colours that were checked
rather than chosen: `#0A8AA1` and `#C93F68` pass lightness, chroma, colour-blind
separation and contrast against the panel they sit on. Both series are labelled
on every bar as well, so the chart never depends on colour alone. Anyone
changing them should re-check rather than eyeball it.
