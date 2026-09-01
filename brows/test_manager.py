#!/usr/bin/env python3
"""The diary: what the therapist actually taps all day.

The things worth guarding here are the ones that cost money or trust --
a double booking that goes unmentioned, a second client card for a woman
who already has one, and a reminder that reaches an English speaker in
Hebrew.
"""
import datetime
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, db_of, ok, done

TOMORROW = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()


def book(**over):
    b = {
        "v": 1,
        "settings": {"name": "Test Studio", "phone": "61234567",
                     "hours": {str(d): [{"from": "09:00", "to": "17:00"}] for d in range(7)},
                     "step": 30, "buffer": 0, "leadHours": 0, "horizon": 30,
                     "cancelHours": 24, "autoConfirm": True, "owner": "", "address": ""},
        "services": [
            {"id": "s-a", "he": "עיצוב גבות", "en": "Brow shaping", "minutes": 30,
             "form": False, "active": True},
            {"id": "s-lift", "he": "הרמת ריסים", "en": "Lash lift", "minutes": 75,
             "form": True, "active": True}],
        "clients": [], "appointments": [], "blocks": [], "forms": []
    }
    b.update(over)
    return b


def watch_open(pg):
    pg.add_init_script("window.__opened = []; window.open = function(u){ "
                       "window.__opened.push(u); return null; };")


def main():
    with sync_playwright() as p:
        b = browser(p)

        # ------------------------------------------------- booking one in
        pg = phone(b, seed=book())
        watch_open(pg)
        open_page(pg, "diary.html")
        ok("אין תורים ביום הזה" in pg.inner_text("#d-list"), "an empty day says so")

        pg.click("#btn-new")
        pg.wait_for_timeout(300)
        pg.fill("#e-name", "Ana Perez")
        pg.fill("#e-phone", "61234567")
        pg.select_option("#e-svc", "s-lift")
        pg.fill("#e-date", TOMORROW)
        pg.fill("#e-time", "10:00")
        pg.select_option("#e-lang", "en")
        pg.wait_for_timeout(150)
        ok(pg.input_value("#e-min") == "75",
           "choosing a treatment fills in how long it takes")
        pg.click("#e-save")
        pg.wait_for_timeout(400)

        saved = db_of(pg)
        ok(len(saved["appointments"]) == 1, "the appointment is in the book")
        ok(saved["appointments"][0]["phone"] == "50761234567",
           "with the number normalised once")
        ok(len(saved["clients"]) == 1 and saved["clients"][0]["lang"] == "en",
           "and a client card, remembering which language she reads")
        ok("Ana Perez" in pg.inner_text("#d-list") and "10:00 AM" in pg.inner_text("#d-list"),
           "the day it lands on is the day now shown")

        # ------------------------------------------------- the clash warning
        pg.click("#btn-new")
        pg.wait_for_timeout(300)
        pg.fill("#e-date", TOMORROW)
        pg.fill("#e-time", "10:30")
        pg.fill("#e-min", "30")
        pg.wait_for_timeout(250)
        ok("חופף" in pg.inner_text("#e-clash"),
           "an overlapping time is called out before it is saved")
        pg.fill("#e-time", "11:30")
        pg.wait_for_timeout(250)
        ok(pg.inner_text("#e-clash").strip() == "", "and the warning goes when it clears")

        # the same woman again must not become a second card
        pg.fill("#e-name", "Ana Perez")
        pg.fill("#e-phone", "6123-4567")
        pg.click("#e-save")
        pg.wait_for_timeout(400)
        saved = db_of(pg)
        ok(len(saved["clients"]) == 1,
           "the same number written differently is still the same client")
        ok(len(saved["appointments"]) == 2, "and she now has two appointments")

        # ------------------------------------------- the messages she sends
        pg.click('[data-appt="%s"]' % saved["appointments"][0]["id"])
        pg.wait_for_timeout(300)
        hrefs = pg.eval_on_selector_all("#modal a.btn", "els => els.map(e => e.href)")
        wa = [h for h in hrefs if "wa.me" in h]
        ok(len(wa) == 3, "call, confirm, remind and send-the-form are all one tap away")
        ok("Your%20appointment%20at" in wa[0],
           "a client who booked in English is written to in English")
        ok("form.html%3Flang%3Den" in wa[2] or "form.html?lang=en" in wa[2],
           "and the release link she gets is the English one")

        # ------------------------------------------------ cancelling
        pg.on("dialog", lambda d: d.accept())    # cancelling asks first
        pg.click("#m-cancel")
        pg.wait_for_timeout(400)
        saved = db_of(pg)
        ok(saved["appointments"][0]["status"] == "cancelled",
           "a cancelled appointment stays in the book, marked")

        # ------------------------------------------ a request from the site
        seeded = book()
        seeded["appointments"] = [{
            "id": "p1", "clientName": "Rita", "phone": "50762222222",
            "serviceId": "s-a", "serviceName": "Brow shaping", "date": TOMORROW,
            "time": "14:00", "minutes": 30, "status": "pending",
            "source": "online", "lang": "he"}]
        pg = phone(b, seed=seeded)
        watch_open(pg)
        open_page(pg, "diary.html")
        ok("ממתינות לאישור (1)" in pg.inner_text("#pending-box"),
           "a request from the site is waiting at the top of the day")
        pg.click("[data-ok='p1']")
        pg.wait_for_timeout(400)
        ok(db_of(pg)["appointments"][0]["status"] == "confirmed", "approving it confirms it")
        opened = pg.evaluate("window.__opened")
        ok(len(opened) == 1 and "%D7%94%D7%99%D7%99" in opened[0],
           "and the confirmation goes out in Hebrew, because that is how she booked")

        # ---------------------------------------- a signed release, in the diary
        seeded = book()
        seeded["forms"] = [{
            "id": "f1", "name": "Rita", "phone": "50762222222",
            "treatments": ["Lash lift"], "signedAt": "2026-08-30T10:00:00.000Z",
            "answers": [{"id": "preg", "q": "Pregnant?", "yes": True, "note": "week 22",
                         "flag": True},
                        {"id": "lens", "q": "Lenses?", "yes": False, "note": "", "flag": False}],
            "photos": True, "signature": "data:image/png;base64,iVBORw0KGgo=", "notes": ""}]
        pg = phone(b, seed=seeded)
        open_page(pg, "diary.html")
        pg.click('#tabs button[data-tab="forms"]')
        pg.wait_for_timeout(300)
        ok("לשים לב" in pg.inner_text("#f-list"),
           "a release with a contraindication is flagged in the list")
        pg.click("[data-f='f1']")
        pg.wait_for_timeout(300)
        sheet = pg.inner_text("#modal")
        ok("Pregnant?" in sheet and "week 22" in sheet,
           "opening it shows exactly what she declared")

        # ---------------------------------------------------- settings stick
        pg.click("[data-close]")
        pg.click('#tabs button[data-tab="settings"]')
        pg.wait_for_timeout(300)
        pg.fill("#st-name", "Nuevo Studio")
        pg.dispatch_event("#st-name", "change")
        pg.fill("#st-cancel", "48")
        pg.dispatch_event("#st-cancel", "change")
        pg.wait_for_timeout(300)
        saved = db_of(pg)
        ok(saved["settings"]["name"] == "Nuevo Studio" and saved["settings"]["cancelHours"] == 48,
           "settings are written down as they are typed")
        ok(pg.inner_text("#bizname") == "Nuevo Studio", "and the header follows")

        done("test_manager", pg)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
