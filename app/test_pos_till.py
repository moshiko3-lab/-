#!/usr/bin/env python3
"""Drive the till: press tiles, add a customer, confirm, take the money.

Their new booking is a whole screen laid out like a till, not a dialog, and
this is the flow the school is in all day. The build check only proves the
screen renders; it cannot tell whether pressing a tile twice makes a quantity
of two, or whether confirming actually leaves a booking behind.
"""
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))

fails = []


def build():
    out = os.path.join(tempfile.mkdtemp(), "app.html")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def low(pg, sel):
    """Lowercased text: the stylesheet uppercases buttons and headings, so a
    case-sensitive assertion measures the CSS rather than the app."""
    return (pg.inner_text(sel) or "").lower()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2200)

        before = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}').bookings.length")

        pg.click("#btn-newbooking")
        pg.wait_for_timeout(1400)
        check("the till opens on + Booking", pg.locator(".pos-tile").count() > 0,
              str(pg.locator(".pos-tile").count()) + " tiles")
        check("it starts empty", "select a product" in low(pg, ".pos-lines"))
        check("confirm is refused while empty",
              pg.locator('.pos-foot button:has-text("Confirm")').is_disabled())

        # the price a tile shows must be the price pressing it charges
        tile_price = pg.locator(".pos-tile .px").first.inner_text().strip()
        pg.locator(".pos-tile").first.click()
        pg.wait_for_timeout(600)
        line_price = pg.locator(".pos-line .amt").first.inner_text().strip()
        check("the tile quotes what it charges",
              tile_price.rstrip("$€£") == line_price.rstrip("$€£"),
              f"tile {tile_price}, line {line_price}")

        # a second press of the same tile is a quantity of two, as a till behaves
        pg.locator(".pos-tile").first.click()
        pg.wait_for_timeout(600)
        check("pressing the same tile again makes it two",
              pg.locator(".pos-line").count() == 1 and
              pg.locator(".pos-line .qty span").first.inner_text().strip() == "2",
              pg.inner_text(".pos-lines")[:160].replace("\n", " / "))

        # a different tile is a second line
        pg.locator(".pos-tile").nth(2).click()
        pg.wait_for_timeout(600)
        check("a different tile is a second line", pg.locator(".pos-line").count() == 2)

        # the stepper and the remove button
        pg.locator('.pos-line .qty button:has-text("−")').first.click()
        pg.wait_for_timeout(500)
        check("the stepper comes back down",
              pg.locator(".pos-line .qty span").first.inner_text().strip() == "1")
        pg.locator(".pos-line .del").nth(1).click()
        pg.wait_for_timeout(500)
        check("a line can be removed", pg.locator(".pos-line").count() == 1)

        totals = low(pg, ".pos-foot")
        check("it totals up", "subtotal" in totals and "tax" in totals and "total" in totals)

        # confirming without a customer asks for one rather than saving a stray
        pg.locator('.pos-foot button:has-text("Confirm")').click()
        pg.wait_for_timeout(700)
        check("a booking with no customer is refused",
              "customer" in (pg.inner_text("#toast") or "").lower(),
              pg.inner_text("#toast"))
        check("and it opens the customer dialog",
              "customer info" in low(pg, "#modal"), low(pg, "#modal")[:120])

        pg.fill('#modal input[type=text] >> nth=1', "Nuria")
        pg.fill('#modal input[type=text] >> nth=2', "Campos")
        pg.fill('#modal input[type=email]', "nuria@example.com")
        pg.click('#modal button:has-text("Confirm")')
        pg.wait_for_timeout(900)
        check("the customer lands on the booking",
              "nuria" in low(pg, ".pos-cust"), pg.inner_text(".pos-cust"))

        pg.locator('.pos-foot button:has-text("Confirm")').click()
        pg.wait_for_timeout(1100)
        check("the payment dialog follows the confirm",
              "payment" in low(pg, "#modal"), low(pg, "#modal")[:150])
        pg.click('#modal button:has-text("Record payment")')
        pg.wait_for_timeout(900)

        after = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}')")
        check("the booking was saved", len(after.get("bookings", [])) == before + 1,
              f"{before} before, {len(after.get('bookings', []))} after")
        bk = (after.get("bookings") or [{}])[-1]
        check("it carries the line", len(bk.get("lines") or []) == 1,
              str(bk.get("lines")))
        check("it carries the payment", len(bk.get("payments") or []) == 1)
        check("the payment left a ticket", len(after.get("tickets") or []) >= 1)
        check("back on the bookings list",
              "campos" in low(pg, "#p-bookings") or "nuria" in low(pg, "#p-bookings"),
              pg.inner_text("#p-bookings")[:200])

        check("no uncaught errors", not errs, "; ".join(errs[:3]))
        b.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
