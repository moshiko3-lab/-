#!/usr/bin/env python3
"""Check the built brochure the way the room it ends up in will.

    python3 print/test_brochure.py

Four things are worth failing a build over, and they are all things that have
been shipped wrong before by somebody:

  * the paper size, because a PDF that is a millimetre off gets scaled by the
    print dialog and every margin in the design moves with it;
  * the page count, because an overflowing block silently adds a fifth sheet
    and nobody notices until it is printed;
  * the QR code, which is the only part of this sheet that has a job to do --
    so it is decoded out of the rendered page, at the resolution a phone
    camera actually sees, and compared against the URL it is supposed to hold;
  * the safe margin, because a printer that cannot go borderless trims the
    outermost eighth of an inch and takes any type sitting there with it.

Needs `pypdfium2` to rasterise and `opencv-python-headless` to decode. Without
opencv the QR check says so and is skipped rather than quietly passing.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import content as C  # noqa: E402

PAGES = 4
PT = {"letter": (612.0, 792.0), "a4": (595.276, 841.89)}
SAFE_IN = 0.32          # nothing but colour may sit closer to the edge than this
fails = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def main():
    size = sys.argv[1] if len(sys.argv) > 1 else "letter"
    pdf = os.path.join(HERE, "shokogi-brochure%s.pdf" % ("" if size == "letter" else "-" + size))

    print("building %s" % os.path.basename(pdf))
    subprocess.run([sys.executable, os.path.join(HERE, "build_brochure.py"),
                    "--size", size, "--out", pdf], check=True)

    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)

    print("the paper")
    check("%d pages" % PAGES, len(doc) == PAGES, "got %d" % len(doc))
    want_w, want_h = PT[size]
    for i in range(len(doc)):
        w, h = doc[i].get_size()
        check("page %d is %s" % (i + 1, size),
              abs(w - want_w) < 1 and abs(h - want_h) < 1,
              "%.1f x %.1f pt" % (w, h))

    print("the QR code")
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("  SKIP  opencv-python-headless is not installed, so the code went "
              "unchecked -- install it before trusting this run")
        cv2 = None

    if cv2 is not None:
        det = cv2.QRCodeDetector()
        for i in range(len(doc)):
            # 200 dpi: a page held at arm's length in a 12 MP camera frame, which
            # is a harder look than a phone held up to one code.
            img = np.array(doc[i].render(scale=200 / 72.0).to_pil().convert("RGB"))
            grey = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            _, decoded, _, _ = det.detectAndDecodeMulti(grey)
            found = sorted({d for d in (decoded or []) if d})
            check("page %d points at the booking page" % (i + 1),
                  found == [C.BOOKING_URL], "read %s" % (found or "nothing"))

    print("the trim")
    if cv2 is not None:
        margin = int(SAFE_IN * 150)
        for i in range(len(doc)):
            img = np.array(doc[i].render(scale=150 / 72.0).to_pil().convert("RGB"))
            h, w = img.shape[:2]
            # Ink is anything appreciably darker than the page or the pink field.
            # A colour field reaching the edge is the design; dark type there is
            # not, so only near-black pixels count as a trim risk.
            dark = (img.max(axis=2).astype(int) < 110)
            band = dark.copy()
            band[margin:h - margin, margin:w - margin] = False
            check("page %d keeps its type off the trim" % (i + 1),
                  band.sum() == 0, "%d dark pixels in the margin" % band.sum())

    print()
    if fails:
        print("%d check(s) failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all good -- %s" % pdf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
