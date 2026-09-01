#!/usr/bin/env python3
"""The client's side of it, driven the way a thumb drives it.

Without a shared book the page cannot promise a time, so what is checked
here is that it does not pretend to: it says "request", it hands the details
to WhatsApp, and it never tells the client she is booked.
"""
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, db_of, ok, done


def book():
    hours = {str(d): [{"from": "09:00", "to": "17:00"}] for d in range(7)}
    return {
        "v": 1,
        "settings": {"name": "Test Studio", "phone": "61234567", "hours": hours,
                     "step": 30, "buffer": 0, "leadHours": 2, "horizon": 30,
                     "cancelHours": 24, "autoConfirm": True,
                     "noteHe": "שלום", "noteEn": "Hello there"},
        "services": [
            {"id": "s-a", "he": "עיצוב גבות", "en": "Brow shaping", "minutes": 30,
             "price": 25, "form": False, "active": True},
            {"id": "s-lift", "he": "הרמת ריסים", "en": "Lash lift", "minutes": 75,
             "price": 80, "form": True, "active": True},
            {"id": "s-off", "he": "מוסתר", "en": "Hidden", "minutes": 30,
             "price": 10, "form": False, "active": False}],
        "clients": [], "appointments": [], "blocks": [], "forms": []
    }


def watch_open(pg):
    """window.open is where the WhatsApp message goes; keep it here instead."""
    pg.add_init_script("window.__opened = []; window.open = function(u){ "
                       "window.__opened.push(u); return null; };")


def main():
    with sync_playwright() as p:
        b = browser(p)

        pg = phone(b, seed=book(), lang="en")
        watch_open(pg)
        open_page(pg, "book.html")

        names = pg.eval_on_selector_all(".pick b", "els => els.map(e => e.textContent)")
        ok(names == ["Brow shaping", "Lash lift"],
           "only the treatments switched on are offered")
        ok(pg.inner_text("#note-box").strip() == "Hello there",
           "the studio's own note reaches the client")
        ok("consent form required" in pg.inner_text(".pick:nth-of-type(2)"),
           "a treatment that needs a signed release says so before booking")

        pg.click(".pick:nth-of-type(1)")
        pg.wait_for_timeout(300)
        ok(pg.query_selector(".slot") is not None, "times are offered")

        # the day strip must not offer a day with nothing free
        pg.click(".slot")
        pg.wait_for_timeout(300)
        ok("Your details" in pg.inner_text("#stage"), "picking a time asks who you are")

        # nothing filled in: it must refuse, and quietly, without moving on
        pg.click("#b-go")
        pg.wait_for_timeout(200)
        ok(pg.query_selector("#b-name") is not None, "an empty form does not submit")

        pg.fill("#b-name", "Ana Perez")
        pg.fill("#b-phone", "123")
        pg.click("#b-go")
        pg.wait_for_timeout(200)
        ok("err" in (pg.get_attribute("#b-phone", "class") or "") or
           pg.eval_on_selector("#b-phone", "e => e.closest('.field').className").find("err") >= 0,
           "a phone number that is too short is refused")

        pg.fill("#b-phone", "6123-4567")
        pg.click("#b-go")
        pg.wait_for_timeout(200)
        ok(pg.query_selector("#b-go") is not None,
           "and it still refuses until the cancellation terms are ticked")

        pg.check("#b-ok")
        pg.click("#b-go")
        pg.wait_for_timeout(400)

        opened = pg.evaluate("window.__opened")
        ok(len(opened) == 1 and opened[0].startswith("https://wa.me/50761234567"),
           "the request goes to the studio's own WhatsApp number")
        ok("Ana%20Perez" in opened[0], "and carries the client's name")

        stage = pg.inner_text("#stage")
        ok("Request sent" in stage, "with no shared book it says request, not booked")
        ok("Ana Perez" in stage and "6123-4567" in stage,
           "the client sees back what she just gave")

        saved = db_of(pg)
        appts = saved["appointments"]
        ok(len(appts) == 1 and appts[0]["status"] == "pending",
           "on the studio's own phone it lands in the book as pending")
        ok(appts[0]["phone"] == "50761234567",
           "the number is stored with its country code, once, in one shape")
        ok(saved["clients"][0]["name"] == "Ana Perez", "and the client card is created")

        # a treatment that needs the release offers the link straight after
        pg = phone(b, seed=book(), lang="en")
        watch_open(pg)
        open_page(pg, "book.html")
        pg.click(".pick:nth-of-type(2)")
        pg.wait_for_timeout(300)
        pg.click(".slot")
        pg.wait_for_timeout(200)
        pg.fill("#b-name", "Rita")
        pg.fill("#b-phone", "61234567")
        pg.check("#b-ok")
        pg.click("#b-go")
        pg.wait_for_timeout(400)
        href = pg.get_attribute("#stage a.btn", "href")
        ok(href.startswith("form.html?lang=en") and "t=lift" in href,
           "and the release link opens with the lash questions already chosen")

        # the same page in Hebrew
        pg = phone(b, seed=book())
        watch_open(pg)
        open_page(pg, "book.html", "?lang=he")
        ok(pg.evaluate("document.documentElement.dir") == "rtl", "Hebrew flips the page")
        ok("מה עושים היום?" in pg.inner_text("#stage"), "and speaks Hebrew")
        ok(pg.eval_on_selector_all(".pick b", "els => els.map(e => e.textContent)")
           == ["עיצוב גבות", "הרמת ריסים"], "with the Hebrew names of the treatments")

        done("test_booking", pg)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
