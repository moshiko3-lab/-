#!/usr/bin/env python3
"""Check the built pieces the way the room they end up in will.

    python3 print/test_brochure.py          # the booklet, then the tri-fold
    python3 print/test_brochure.py a4       # the booklet on A4

Four things are worth failing a build over, and every one of them has been
shipped wrong by somebody:

  * the paper size, because a PDF a millimetre off gets scaled by the print
    dialog and every margin in the design moves with it;
  * the page count, because an overflowing block silently adds a seventh sheet
    and nobody notices until it is printed;
  * the QR code, which is the only part of this booklet with a job to do -- so
    it is decoded out of the rendered page, at the resolution a phone camera
    actually sees, and compared against the URL it is supposed to hold;
  * the safe margin, because a printer that cannot go borderless trims the
    outermost eighth of an inch and takes any type sitting there with it.

The margin check reads the laid-out page rather than its pixels. Two pages are
deep ink from edge to edge, so "dark pixels near the edge" says nothing at all
about them; what matters is whether a box holding words overlaps the trim, and
the browser can be asked that directly.

Needs `pypdfium2` to rasterise and `opencv-python-headless` to decode. Without
either, the check that needs it says so and is skipped rather than passing
quietly.
"""

import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_brochure as B  # noqa: E402
import build_trifold as T  # noqa: E402
import content as C  # noqa: E402
import quiver  # noqa: E402

PAGES = 8
QR_ON = {5, 7, 8}               # the shop's code: beside the services,
                                # on the shop page, and filling the back
PT = {"letter": (612.0, 792.0), "a4": (595.276, 841.89)}
SAFE_IN = 0.30                  # type may not come closer to the edge than this
fails = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    if not ok:
        fails.append(name)


def margins(html, size):
    """Ask the browser for every box that holds words, and hand back the ones
    that reach into the trim."""
    probe = """
<script>window.addEventListener('load',function(){
  var sel = document.querySelector('.page') ? '.page' : '.sheet';
  var W = document.querySelector(sel).getBoundingClientRect().width;
  var H = document.querySelector(sel).getBoundingClientRect().height;
  var safe = %f * 96, out = [];
  document.querySelectorAll(sel).forEach(function(pg, i){
    var pr = pg.getBoundingClientRect();
    pg.querySelectorAll('*').forEach(function(el){
      if (el.children.length) return;                 /* leaves only */
      var t = (el.textContent || '').trim();
      if (!t) return;
      var r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      var l = r.left - pr.left, tp = r.top - pr.top;
      if (l < safe || tp < safe || l + r.width > W - safe || tp + r.height > H - safe)
        out.push({page: i + 1, text: t.slice(0, 42),
                  box: [Math.round(l), Math.round(tp),
                        Math.round(r.width), Math.round(r.height)]});
    });
  });
  var n = document.createElement('div');
  n.id = 'probe'; n.textContent = JSON.stringify(out);
  document.body.appendChild(n);
});</script>""" % SAFE_IN

    tmp = tempfile.mkdtemp(prefix="shokogi-probe-")
    path = os.path.join(tmp, "probe.html")
    with open(path, "w") as f:
        f.write(html.replace("</body>", probe + "</body>"))
    res = subprocess.run(
        [B.chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
         "--virtual-time-budget=12000", "--window-size=1000,1400",
         "--dump-dom", "file://" + path],
        capture_output=True, text=True)
    m = re.search(r'id="probe">(.*?)</div>', res.stdout, re.S)
    return json.loads(m.group(1)) if m else None


def main():
    size = sys.argv[1] if len(sys.argv) > 1 else "letter"
    pdf = os.path.join(HERE, "shokogi-brochure%s.pdf"
                       % ("" if size == "letter" else "-" + size))

    print("building %s" % os.path.basename(pdf))
    html = B.build(size)
    B.render(html, pdf)

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

    print("the pictures")
    have = B.photos()
    for slot in sorted(B.SLOTS):
        check("slot %s" % slot, True,
              "photograph %s" % os.path.basename(have[slot]) if slot in have else "drawn")

    # Page five prints numbers counted off app/catalog.json rather than typed
    # into content.py, so the way it fails is silent: a changed export shape
    # gives zeroes and a page that reads as if the school owned no boards.
    print("the quiver")
    q = quiver.read()
    check("boards counted", q["total"] > 0, "%d boards" % q["total"])
    check("lengths parsed", bool(q["rows"]) and all(a + b for _, a, b in q["rows"]),
          "%s to %s" % (q["shortest"], q["longest"]))
    check("shapers found", len(q["shapers"]) > 3, ", ".join(q["shapers"][:4]) + " ...")
    check("the page prints them", str(q["total"]) in html and q["longest"] in html)

    print("the QR code")
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("  SKIP  opencv-python-headless is not installed, so the codes went "
              "unchecked -- install it before trusting this run")
        cv2 = None

    if cv2 is not None:
        det = cv2.QRCodeDetector()
        for i in range(len(doc)):
            # 200 dpi: a whole page in a camera frame, which is a harder look
            # than a phone held up to one code.
            img = np.array(doc[i].render(scale=200 / 72.0).to_pil().convert("RGB"))
            _, decoded, _, _ = det.detectAndDecodeMulti(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
            found = sorted({d for d in (decoded or []) if d})
            want = [C.BOOKING_URL] if (i + 1) in QR_ON else []
            check("page %d %s" % (i + 1, "points at the booking page"
                                  if (i + 1) in QR_ON else "carries no code"),
                  found == want, "read %s" % (found or "nothing"))

    print("the trim")
    bad = margins(html, size)
    if bad is None:
        check("the browser reported its boxes", False, "no probe output")
    else:
        for pg in range(1, PAGES + 1):
            here = [b for b in bad if b["page"] == pg]
            check("page %d keeps its type out of the trim" % pg, not here,
                  "; ".join("%r at %s" % (b["text"], b["box"]) for b in here[:3]))

    # The tri-fold is a different sheet with the same job, so it gets the same
    # three questions: right paper, code readable, nothing in the trim.
    if size == "letter":
        print()
        print("the tri-fold")
        tri = os.path.join(HERE, "shokogi-trifold.pdf")
        thtml = T.build()
        B.render(thtml, tri)
        tdoc = pdfium.PdfDocument(tri)
        check("2 sheets", len(tdoc) == 2, "got %d" % len(tdoc))
        for i in range(len(tdoc)):
            w, h = tdoc[i].get_size()
            check("sheet %d is 11 x 8.5" % (i + 1),
                  abs(w - 792) < 1 and abs(h - 612) < 1, "%.1f x %.1f pt" % (w, h))
        if cv2 is not None:
            det2 = cv2.QRCodeDetector()
            for i in range(len(tdoc)):
                img = np.array(tdoc[i].render(scale=200 / 72.0).to_pil().convert("RGB"))
                _, dec, _, _ = det2.detectAndDecodeMulti(
                    cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
                found = sorted({d for d in (dec or []) if d})
                want = [C.BOOKING_URL] if i == 0 else []
                check("sheet %d %s" % (i + 1, "points at the shop" if not i
                                       else "carries no code"),
                      found == want, "read %s" % (found or "nothing"))
        tbad = margins(thtml, "trifold")
        if tbad is None:
            check("the browser reported the tri-fold's boxes", False, "no probe output")
        else:
            for pg in (1, 2):
                here = [b for b in tbad if b["page"] == pg]
                check("sheet %d keeps its type out of the trim" % pg, not here,
                      "; ".join("%r at %s" % (b["text"], b["box"]) for b in here[:3]))

    print()
    if fails:
        print("%d check(s) failed: %s" % (len(fails), ", ".join(fails)))
        return 1
    print("all good -- %s (%.0f KB)" % (pdf, os.path.getsize(pdf) / 1024.0))
    if size == "letter":
        print("          -- %s (%.0f KB)"
              % (os.path.join(HERE, "shokogi-trifold.pdf"),
                 os.path.getsize(os.path.join(HERE, "shokogi-trifold.pdf")) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
