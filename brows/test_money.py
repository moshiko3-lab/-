#!/usr/bin/env python3
"""There is no money in this system, and there is no way to make some appear.

It manages appointments. It is not a till and it is not a price list: no
figure beside a treatment, no total for the day, no takings on a client
card, no price to fill in when booking, and nothing on the client's page.

The awkward case is a backup made by an older build, which still carries
price fields in its data. Loading one must not bring money back to the
screen -- old data is data, not a setting.
"""
import datetime
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, ok, done

TODAY = datetime.date.today().isoformat()


def legacy_book():
    """A book from before, prices and all."""
    return {
        "v": 1,
        "settings": {"name": "Romy", "phone": "972546902515",
                     "hours": {str(d): [{"from": "09:00", "to": "18:00"}] for d in range(7)},
                     "step": 30, "buffer": 0, "leadHours": 0, "horizon": 30,
                     "cancelHours": 24, "autoConfirm": True,
                     "showPrices": True},              # and it was even switched on
        "services": [{"id": "s-a", "he": "הרמת ריסים", "en": "Lash lift",
                      "minutes": 60, "price": 70, "form": True, "active": True}],
        "clients": [{"id": "c1", "name": "Ana", "phone": "50761111111", "lang": "en"}],
        "appointments": [{"id": "a1", "clientId": "c1", "clientName": "Ana",
                          "phone": "50761111111", "serviceId": "s-a", "date": TODAY,
                          "time": "10:00", "minutes": 60, "price": 70,
                          "status": "confirmed", "lang": "en"}],
        "blocks": [], "forms": []
    }


def main():
    with sync_playwright() as p:
        b = browser(p)

        # ------------------------------------------------------- the diary
        pg = open_page(phone(b, seed=legacy_book()), "diary.html")
        ok("$" not in pg.inner_text("#d-list"), "no figure beside the appointment")
        ok("$" not in pg.inner_text("#d-sum"),
           "the day is counted in appointments and hours")
        ok("שעות" in pg.inner_text("#d-sum"), "and the hours are still counted")

        pg.click('[data-appt="a1"]')
        pg.wait_for_timeout(300)
        ok("$" not in pg.inner_text("#modal"), "nor on the appointment itself")
        pg.click("#m-edit")
        pg.wait_for_timeout(300)
        ok(pg.query_selector("#e-price") is None, "the editor does not ask for one")
        ok(pg.query_selector("#e-min") is not None, "it asks how long, which is the point")
        ok("$" not in pg.inner_text("#modal"),
           "and the treatment list in it is minutes only")
        pg.click("#e-save")
        pg.wait_for_timeout(300)
        ok(pg.evaluate("apptById('a1') !== null"), "and it still saves")

        pg.click('#tabs button[data-tab="clients"]')
        pg.wait_for_timeout(250)
        pg.click("[data-cl='c1']")
        pg.wait_for_timeout(300)
        ok("$" not in pg.inner_text("#modal"),
           "the client card counts visits, never takings")
        pg.click("[data-close]")

        pg.click('#tabs button[data-tab="settings"]')
        pg.wait_for_timeout(350)
        ok("$" not in pg.inner_text("#tab-settings"),
           "the treatment editor has a name and a length and no third number")
        ok(pg.query_selector("#st-prices") is None,
           "and there is no switch to turn money on")
        ok(pg.eval_on_selector_all("#st-svc input", "els => els.length") == 5,
           "five fields per treatment: two names, a length, a form tick, active")

        # -------------------------------------------------- the client's page
        for lang in ("en", "he"):
            pg2 = open_page(phone(b, seed=legacy_book(), lang=lang), "index.html")
            ok("$" not in pg2.inner_text("body"),
               "nothing on the client's treatment list either (%s)" % lang)
            pg2.click(".pick")
            pg2.wait_for_timeout(350)
            ok("$" not in pg2.inner_text("body"), "nor when picking a time (%s)" % lang)
            slot = pg2.query_selector(".slot")
            if slot:
                slot.click()
                pg2.wait_for_timeout(300)
                ok("$" not in pg2.inner_text("body"),
                   "nor on the details she fills in (%s)" % lang)

        # -------------------------------------------- and none in the code
        ok(pg.evaluate("typeof window.money") == "undefined",
           "the page does not even carry a way to format a sum")

        done("test_money", pg)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
