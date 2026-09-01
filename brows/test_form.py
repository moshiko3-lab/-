#!/usr/bin/env python3
"""The release and waiver: what it refuses, and what it produces.

The point of the document is that it can be shown afterwards. So the test
does not stop at "it submitted" -- it reads the signed copy the page draws
and checks that every clause, every answer and the signature are in it.
"""
import sys
from playwright.sync_api import sync_playwright
from harness import browser, phone, open_page, db_of, ok, done


def book():
    return {
        "v": 1,
        "settings": {"name": "Test Studio", "phone": "61234567",
                     "hours": {str(d): [{"from": "09:00", "to": "17:00"}] for d in range(7)},
                     "step": 30, "buffer": 0, "leadHours": 2, "horizon": 30,
                     "cancelHours": 24, "autoConfirm": True},
        "services": [], "clients": [], "appointments": [], "blocks": [], "forms": []
    }


def watch_open(pg):
    pg.add_init_script("window.__opened = []; window.open = function(u){ "
                       "window.__opened.push(u); return null; };")


def sign(pg):
    """Draw on the signature pad the way a finger does."""
    box = pg.query_selector("#sig").bounding_box()
    pg.mouse.move(box["x"] + 40, box["y"] + 110)
    pg.mouse.down()
    for dx, dy in [(30, -40), (60, 20), (95, -30), (130, 10)]:
        pg.mouse.move(box["x"] + 40 + dx, box["y"] + 110 + dy)
    pg.mouse.up()
    pg.wait_for_timeout(120)


def answer_all(pg, yes_ids=()):
    """Tick every visible question; the ones named get a yes."""
    ids = pg.eval_on_selector_all("#q-box .q", "els => els.map(e => e.dataset.q)")
    for qid in ids:
        which = 1 if qid in yes_ids else 2      # 1 = yes, 2 = no
        pg.click('[data-q="%s"] .yn label:nth-child(%d)' % (qid, which))
    return ids


def main():
    with sync_playwright() as p:
        b = browser(p)

        # ------------------------------------------------ what it refuses
        pg = phone(b, seed=book(), lang="en")
        watch_open(pg)
        open_page(pg, "form.html")

        ok(len(pg.query_selector_all("#q-box .q")) == 18,
           "with no treatment chosen yet, every question is on show")

        pg.click("#send")
        pg.wait_for_timeout(300)
        msg = pg.inner_text("#sendmsg")
        for part in ["name", "phone", "treatment", "health questions",
                     "confirmations", "signature"]:
            ok(part in msg, "an empty form names what is missing: " + part)
        ok(db_of(pg) is None or not db_of(pg)["forms"],
           "and nothing at all is recorded")

        # ------------------------------------- the questions follow the treatment
        pg.check('#t-box input[data-t="lift"]')
        pg.wait_for_timeout(250)
        ids = pg.eval_on_selector_all("#q-box .q", "els => els.map(e => e.dataset.q)")
        ok("eyesurg" in ids, "a lash lift asks about eye surgery")
        ok("pmu" not in ids, "and does not ask about brow tattooing")

        pg.check('#t-box input[data-t="wax"]')
        pg.wait_for_timeout(250)
        ids = pg.eval_on_selector_all("#q-box .q", "els => els.map(e => e.dataset.q)")
        ok("pmu" in ids and "eyesurg" in ids,
           "adding brow waxing brings the brow questions back alongside them")

        # ------------------------------------------------ a full, signed form
        pg = phone(b, seed=book(), lang="en")
        watch_open(pg)
        open_page(pg, "form.html", "?lang=en&t=lift&n=Ana%20Perez&p=61234567")

        ok(pg.input_value("#p-name") == "Ana Perez" and pg.input_value("#p-phone") == "61234567",
           "the link from the booking page fills in what it already knows")
        ok(pg.is_checked('#t-box input[data-t="lift"]'), "and ticks the treatment")

        answered = answer_all(pg, yes_ids=("preg", "lens"))
        ok("minor" in answered, "the under-18 question is always asked")

        pg.fill('[data-note="preg"] input', "week 22")
        pg.check("#c-risk"); pg.check("#c-after"); pg.check("#c-dec")
        pg.check("#c-photo")
        pg.fill("#p-id", "PA-99887")
        pg.fill("#p-notes", "sensitive eyes")

        pg.click("#send")
        pg.wait_for_timeout(200)
        ok("signature" in pg.inner_text("#sendmsg"),
           "everything filled but unsigned is still refused")

        sign(pg)
        pg.click("#send")
        pg.wait_for_timeout(500)

        # ---------------------------------------------- the signed copy
        doc = pg.inner_text(".doc")
        ok("Health declaration, informed consent and release" in doc,
           "the signed copy is a document, not a receipt")
        ok("Ana Perez" in doc and "6123-4567" in doc and "PA-99887" in doc,
           "it carries who signed it")
        ok("Lash lift" in doc, "and what it covers")
        ok("Are you pregnant or breastfeeding?" in doc and "week 22" in doc,
           "every answer is in it, with what she added")
        ok(doc.count("Yes") >= 2, "including the ones she answered yes to")
        ok("negligence or wilful misconduct" in doc,
           "the clause that limits the waiver is in the signed copy, not only on screen")
        ok("release the therapist from liability" in doc,
           "and so is the release itself")
        ok("agreed" in doc, "the photo permission is recorded either way")
        sig = pg.get_attribute(".doc img", "src")
        ok(sig.startswith("data:image/png") and len(sig) > 2000,
           "the signature travels with it as an image")

        saved = db_of(pg)["forms"][0]
        ok(saved["phone"] == "50761234567", "the record is keyed by a whole phone number")
        ok(saved["consent"] == {"risks": True, "aftercare": True, "declaration": True},
           "the three confirmations are recorded separately")
        ok(len(saved["answers"]) == len(answered),
           "and every question that was shown is stored, not only the yeses")
        ok(sum(1 for a in saved["answers"] if a["yes"]) == 2, "two of them are yes")

        opened = pg.evaluate("window.__opened")
        ok(len(opened) == 1 and "wa.me/50761234567" in opened[0],
           "the studio gets a WhatsApp summary")
        ok("pregnant" in opened[0].lower() or "pregnant" in opened[0],
           "and it leads with what she answered yes to")
        ok("data%3Aimage" not in opened[0],
           "the signature image does not go through WhatsApp")

        # ------------------------------------------------ the same in Hebrew
        pg = phone(b, seed=book())
        watch_open(pg)
        open_page(pg, "form.html", "?lang=he&t=lam")
        ok(pg.evaluate("document.documentElement.dir") == "rtl", "Hebrew flips the page")
        stage = pg.inner_text("#stage")
        ok("כתב שחרור, פטור מאחריות והסכמה מדעת" in stage, "the release has its Hebrew title")
        ok("אין באמור במסמך זה כדי לפטור את המטפלת מאחריות לנזק שנגרם ברשלנותה" in stage,
           "and the limiting clause is in the Hebrew text too")

        done("test_form", pg)
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
