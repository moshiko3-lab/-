#!/usr/bin/env python3
"""Phone numbers, which are the identity of a client here.

Two things ride on this. A number that normalises wrong produces a
wa.me link that goes nowhere, and the client simply never hears back.
A number that normalises inconsistently produces a second client card
for a woman who already has one, and her history splits in half.

The studio is in Panama and its clients are local and Israeli in roughly
equal measure, so both shapes have to survive being typed by hand, badly.
"""
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, ok, done

# what a person types                 what it has to become
SAME_ISRAELI = ["+972 54-690-2515", "054-690-2515", "0546902515",
                "972546902515", "00972546902515", "+972546902515"]
SAME_PANAMA = ["61234567", "6123-4567", "+507 6123-4567", "00507 6123 4567",
               "507 6123 4567"]


def main():
    with sync_playwright() as p:
        b = browser(p)
        pg = open_page(phone(b), "index.html")

        def norm(x):
            return pg.evaluate("s => normPhone(s)", x)

        got = {norm(x) for x in SAME_ISRAELI}
        ok(got == {"972546902515"},
           "one Israeli number typed six ways is one client, not six: " + str(got))
        got = {norm(x) for x in SAME_PANAMA}
        ok(got == {"50761234567"},
           "and the same for a Panama number: " + str(got))

        ok(norm("2691234") == "5072691234",
           "a seven-digit Panama landline gets the country code it was missing")
        ok(norm("+1 415 555 2671") == "14155552671",
           "a number given with a + is left exactly as it was given")
        ok(norm("03-1234567") == "97231234567",
           "a leading zero means a national format, and here that is Israel")
        ok(norm("") == "" and norm("hello") == "",
           "nothing in, nothing out -- never a country code on its own")

        ok(pg.evaluate("waLink('054-690-2515','hi')").startswith(
               "https://wa.me/972546902515?"),
           "the link a client is written on goes to a number WhatsApp can dial")
        ok(pg.evaluate("waLink('61234567','hi')").startswith(
               "https://wa.me/50761234567?"),
           "from either country")

        ok(pg.evaluate("showPhone('972546902515')") == "+972 54-690-2515",
           "twelve digits in a row is not a phone number anyone can read")
        ok(pg.evaluate("showPhone('50761234567')") == "6123-4567",
           "and a Panama number reads the way it is written there")

        bad = pg.evaluate("['12','abc','0'].map(validPhone)")
        ok(bad == [False, False, False], "and something that is not a number is refused")

        # the number the studio is actually reachable on
        dest = pg.evaluate("db.settings.phone")
        ok(pg.evaluate("s => !!s && validPhone(s)", dest),
           "the published page carries a WhatsApp number to send requests to")

        done("test_phone", pg)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
