#!/usr/bin/env python3
"""Nothing may scroll sideways.

These pages open on one kind of screen and one only. A page that is fifteen
pixels too wide does not look like a fifteen pixel problem on a phone -- it
looks like a broken app, and the settings screen was exactly that until this
test existed. So every screen, on the narrowest phone still in use and on a
normal one, in both languages, and with the dialogs open.
"""
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, site, ok, done

WIDTHS = [320, 390, 430]           # SE, 15, Pro Max


def overflow(pg):
    """Anything sticking out past either edge, named so it can be found."""
    return pg.evaluate("""() => {
      const vw = document.documentElement.clientWidth;
      const out = [];
      document.querySelectorAll("body *").forEach(el => {
        const st = getComputedStyle(el);
        if (st.display === "none" || st.visibility === "hidden") return;
        // a strip that is meant to be swiped sideways is not an overflow
        if (el.closest(".days")) return;
        const r = el.getBoundingClientRect();
        if (r.width === 0) return;
        if (r.right > vw + 1 || r.left < -1) {
          out.push((el.id ? "#" + el.id : el.tagName.toLowerCase()) +
            (typeof el.className === "string" && el.className.trim()
              ? "." + el.className.trim().split(/\\s+/).join(".") : "") +
            " [" + Math.round(r.left) + "," + Math.round(r.right) + "] of " + vw);
        }
      });
      return {scroll: document.documentElement.scrollWidth, vw: vw,
              bad: out.slice(0, 4)};
    }""")


def check(pg, where):
    o = overflow(pg)
    ok(o["scroll"] <= o["vw"] + 1 and not o["bad"],
       "%s stays inside the screen" % where +
       ("" if not o["bad"] else " -- " + "; ".join(o["bad"])))


def main():
    with sync_playwright() as p:
        b = browser(p)
        for w in WIDTHS:
            ctx = b.new_context(viewport={"width": w, "height": 780}, has_touch=True)
            pg = ctx.new_page()

            # ---- the diary, every screen and two of its dialogs
            open_page(pg, "diary.html")
            for tab in ["today", "agenda", "clients", "forms", "settings"]:
                pg.click('#tabs button[data-tab="%s"]' % tab)
                pg.wait_for_timeout(220)
                check(pg, "%dpx diary/%s" % (w, tab))
            pg.click("#btn-new")
            pg.wait_for_timeout(300)
            check(pg, "%dpx the new-appointment sheet" % w)
            pg.click("#modal [data-close]")
            pg.click('#tabs button[data-tab="today"]')
            pg.click("#d-block")
            pg.wait_for_timeout(300)
            check(pg, "%dpx the block-time sheet" % w)
            pg.click("#modal [data-close]")

            # ---- what the client sees, in both languages
            for lang in ["en", "he"]:
                open_page(pg, "index.html", "?lang=" + lang)
                check(pg, "%dpx booking/%s treatments" % (w, lang))
                pg.click(".pick")
                pg.wait_for_timeout(300)
                check(pg, "%dpx booking/%s times" % (w, lang))
                slot = pg.query_selector(".slot")
                if slot:
                    slot.click()
                    pg.wait_for_timeout(250)
                    check(pg, "%dpx booking/%s details" % (w, lang))

                open_page(pg, "form.html", "?lang=" + lang + "&t=lift,bodywax")
                check(pg, "%dpx the release/%s" % (w, lang))
            ctx.close()
        done("test_layout")
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
