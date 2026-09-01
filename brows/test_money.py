#!/usr/bin/env python3
"""A studio that does not keep prices should not be shown any.

"$0" beside every appointment is worse than nothing at all -- it reads as
a treatment nobody paid for. So money is absent from the interface until
one real price exists, and then it appears everywhere on its own. There is
no setting to find and nothing to explain: type a price, money wakes up.
"""
import datetime
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, ok, done

TODAY = datetime.date.today().isoformat()


def book(priced):
    return {
        "v": 1,
        "settings": {"name": "Romy", "phone": "972546902515",
                     "hours": {str(d): [{"from": "09:00", "to": "18:00"}] for d in range(7)},
                     "step": 30, "buffer": 0, "leadHours": 0, "horizon": 30,
                     "cancelHours": 24, "autoConfirm": True, "showPrices": True},
        "services": [{"id": "s-a", "he": "הרמת ריסים", "en": "Lash lift",
                      "minutes": 60, "price": 70 if priced else 0,
                      "form": True, "active": True}],
        "clients": [{"id": "c1", "name": "Ana", "phone": "50761111111", "lang": "en"}],
        "appointments": [{"id": "a1", "clientId": "c1", "clientName": "Ana",
                          "phone": "50761111111", "serviceId": "s-a", "date": TODAY,
                          "time": "10:00", "minutes": 60,
                          "price": 70 if priced else 0,
                          "status": "confirmed", "lang": "en"}],
        "blocks": [], "forms": []
    }


def main():
    with sync_playwright() as p:
        b = browser(p)

        # ---------------------------------------------- a studio without prices
        pg = open_page(phone(b, seed=book(False)), "index.html")
        ok("$" not in pg.inner_text("#d-list"), "no price beside the appointment")
        ok("$" not in pg.inner_text("#d-sum"),
           "the day is counted in appointments and hours, not in money")
        ok("שעות" in pg.inner_text("#d-sum"), "and the hours are still there")

        pg.click('[data-appt="a1"]')
        pg.wait_for_timeout(300)
        ok("$" not in pg.inner_text("#modal"), "nor on the appointment itself")
        pg.click("#m-edit")
        pg.wait_for_timeout(300)
        ok(pg.query_selector("#e-price") is None,
           "and the editor does not ask for one")
        ok(pg.query_selector("#e-min") is not None, "though it still asks how long")
        pg.click("#e-save")
        pg.wait_for_timeout(300)
        ok(pg.evaluate("apptById('a1') !== null"),
           "saving without a price field still saves the appointment")

        pg.click('#tabs button[data-tab="clients"]')
        pg.wait_for_timeout(250)
        pg.click("[data-cl='c1']")
        pg.wait_for_timeout(300)
        ok("$" not in pg.inner_text("#modal"), "the client card counts visits, not takings")
        pg.click("[data-close]")

        pg.click('#tabs button[data-tab="settings"]')
        pg.wait_for_timeout(300)
        ok(pg.query_selector("#st-prices") is None,
           "and the switch for showing clients prices is not offered when there are none")

        # the client's own page, even with the setting left on
        pg2 = open_page(phone(b, seed=book(False), lang="en"), "book.html")
        ok("$" not in pg2.inner_text("#stage"),
           "a price the studio never set is not shown to a client either")

        # ---------------------------------------------- and once one price exists
        pg3 = open_page(phone(b, seed=book(True)), "index.html")
        ok("$70" in pg3.inner_text("#d-list"), "one real price and money is back")
        ok("$70" in pg3.inner_text("#d-sum"), "the day totals again")
        pg3.click('#tabs button[data-tab="settings"]')
        pg3.wait_for_timeout(300)
        ok(pg3.query_selector("#st-prices") is not None,
           "and the switch for the client's page reappears with it")

        pg4 = open_page(phone(b, seed=book(True), lang="en"), "book.html")
        ok("$70" in pg4.inner_text("#stage"),
           "which is what puts it on the client's page")

        done("test_money", pg3)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
