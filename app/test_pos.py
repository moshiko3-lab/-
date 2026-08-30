#!/usr/bin/env python3
"""Drive the register through the UI: open it, move cash, take a payment, and
check the ticket that comes out of it.

The build check only opens dialogs. It cannot tell whether the till actually
refuses cash before it is opened, or whether a payment leaves a ticket.
"""
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))


def build():
    """Render the page the way a release does, into a throwaway file."""
    out = os.path.join(tempfile.mkdtemp(), "app.html")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def tab(pg, label):
    pg.click(f'#tabs button[data-id="{label}"]')
    pg.wait_for_timeout(400)


def modal_button(pg, text):
    pg.click(f'#modal button:has-text("{text}")')
    pg.wait_for_timeout(500)


def toast(pg):
    return (pg.inner_text("#toast") or "").strip()


def txt_of(pg, sel):
    """Lowercased text. The stylesheet uppercases chips and headings, so a
    case-sensitive assertion measures the CSS, not the app."""
    return (pg.inner_text(sel) or "").lower()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1500, "height": 1000}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(1500)

        # --- the till refuses to move cash before it is opened -----------
        tab(pg, "register")
        check("register starts unopened", "not opened" in txt_of(pg, "#p-register"))
        pg.click('#p-register button:has-text("Cash in / out")')
        pg.wait_for_timeout(500)
        check("cash refused while closed", "POS is closed" in toast(pg), toast(pg))
        check("no dialog opened", pg.get_attribute("#scrim", "hidden") is not None)

        # --- open it with a float ---------------------------------------
        pg.click('#p-register button:has-text("Open register")')
        pg.wait_for_timeout(500)
        pg.fill('#modal input[type=number]', "200")
        modal_button(pg, "Open register")
        txt = txt_of(pg, "#p-register")
        check("register reads open", "not opened" not in txt and "register" in txt)
        check("starting cash shown", "200.00" in txt, txt[:200])

        # --- now cash moves, with an operation type ---------------------
        pg.click('#p-register button:has-text("Cash in / out")')
        pg.wait_for_timeout(500)
        opts = pg.eval_on_selector_all('#modal select option', "els => els.map(e => e.textContent)")
        for want in ("Pay-In", "Pay-Out", "Bank → Cash", "Cash → Bank"):
            check(f"operation type {want}", want in opts)
        pg.select_option('#modal select >> nth=0', label="Pay-Out")
        pg.fill('#modal input[type=number]', "35")
        pg.fill('#modal input[type=text]', "Petrol for the boat")
        modal_button(pg, "Save")
        check("operation registered", "registered successfully" in toast(pg), toast(pg))
        txt = txt_of(pg, "#p-register")
        check("pay-out on the drawer", "pay-out" in txt and "petrol" in txt)
        check("expected drops by the pay-out", "165.00" in txt, txt[:400])

        # --- a booking with a payment leaves a ticket -------------------
        tab(pg, "catalog")
        pg.click('#p-catalog button:has-text("New product")')
        pg.wait_for_timeout(600)
        pg.fill('#modal input[type=text] >> nth=0', "Group lesson")
        # the price lives on the Price tab, not the first number field on screen
        pg.click('#modal button:has-text("Price")')
        pg.wait_for_timeout(300)
        pg.fill('#modal input[type=number]:visible >> nth=0', "60")
        modal_button(pg, "Save")
        check("product saved", "Group lesson" in pg.inner_text("#p-catalog"))

        tab(pg, "clients")
        pg.click('#p-clients button:has-text("New client")')
        pg.wait_for_timeout(600)
        pg.fill('#modal input[type=text] >> nth=0', "Ana Torres")
        modal_button(pg, "Save")
        check("client saved", "Ana Torres" in pg.inner_text("#p-clients"))

        # a booking is taken at the till now, not in a dialog
        tab(pg, "bookings")
        pg.click('#p-bookings button:has-text("New booking")')
        pg.wait_for_timeout(1200)
        tiles = pg.locator(".pos-tile")
        check("the till lists the product", tiles.count() > 0, str(tiles.count()) + " tiles")
        picked = False
        for i in range(tiles.count()):
            if "Group lesson" in (tiles.nth(i).inner_text() or ""):
                tiles.nth(i).click()
                picked = True
                break
        check("the product is on the booking", picked and
              "group lesson" in (pg.inner_text(".pos-lines") or "").lower(),
              pg.inner_text(".pos-lines")[:160])
        pg.wait_for_timeout(400)
        pg.click(".pos-cust")
        pg.wait_for_timeout(700)
        # pick the client made a moment ago rather than filling in a new one.
        # A build carrying the school's own clients has a hundred of them, so
        # search for her rather than trusting whoever sorts first.
        pg.fill('#modal input[type=search]', "Ana Torres")
        pg.wait_for_timeout(500)
        pg.locator('#modal .pick-row').filter(has_text="Ana Torres").first.click()
        pg.wait_for_timeout(700)
        pg.locator('.pos-foot button:has-text("Confirm")').click()
        pg.wait_for_timeout(1100)
        pg.click('#modal button:has-text("Record payment")')
        pg.wait_for_timeout(900)
        check("booking saved", "Ana Torres" in pg.inner_text("#p-bookings"), toast(pg))

        tab(pg, "register")
        txt = txt_of(pg, "#p-register")
        check("tickets table drawn", "seq. nb." in txt, txt[-400:])
        check("ticket issued for the payment", "#1" in txt, txt[-800:])
        check("ticket typed as a sale", "sale" in txt.split("tickets")[-1], txt[-400:])

        # --- integrity: clean, then after a hand edit --------------------
        pg.click('#p-register button:has-text("Check integrity")')
        pg.wait_for_timeout(500)
        check("integrity validates", "validated" in txt_of(pg, "#modal"), pg.inner_text("#modal")[:200])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)

        # Tamper with the stored journal the way a person with the console
        # would. It has to be a ticket the register is actually showing: a
        # build carrying the school's own book mints a ticket for every
        # payment it ever took, so tickets[0] is somebody's payment from
        # weeks ago and the day being looked at would never show it.
        tampered = pg.evaluate("""() => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          const mine = (d.tickets||[]).slice().sort((a,b) => b.seq - a.seq)[0];
          if (!mine) return null;
          mine.total = 999;
          localStorage.setItem(k, JSON.stringify(d));
          return {seq: mine.seq, date: mine.date};
        }""")
        check("there is a ticket to tamper with", tampered is not None)
        pg.reload()
        pg.wait_for_timeout(1200)
        tab(pg, "register")
        txt = txt_of(pg, "#p-register")
        check("edited ticket flagged broken", "broken" in txt, txt[-600:])
        pg.click('#p-register button:has-text("Check integrity")')
        pg.wait_for_timeout(500)
        check("integrity check fails on a tampered row",
              "failed" in txt_of(pg, "#modal"), pg.inner_text("#modal")[:250])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)

        # --- closing the register counts against the books ---------------
        pg.click('#p-register button:has-text("Close register")')
        pg.wait_for_timeout(500)
        body = pg.inner_text("#modal")
        m = re.search(r"expected in the till\s*\$([\d,]+\.\d\d)", body.lower())
        check("closing shows what is expected", bool(m), body[:200])
        pg.fill('#modal input[type=number]', "100")
        pg.wait_for_timeout(300)
        check("difference computed live", "−" in pg.inner_text("#modal") or "-" in pg.inner_text("#modal"))
        modal_button(pg, "Close register")
        txt = txt_of(pg, "#p-register")
        check("register closed", "closed" in txt)
        check("difference kept", "difference" in txt, txt[:300])

        # --- the archive seals what is there ----------------------------
        tab(pg, "settings")
        pg.click('#p-settings button:has-text("Export archive file")')
        pg.wait_for_timeout(500)
        # a year is the app's limit, so ask for a month of it
        dates = pg.query_selector_all('#modal input[type=date]')
        dates[0].fill((dt.date.today() - dt.timedelta(days=30)).isoformat())
        modal_button(pg, "Export file")
        mod = pg.inner_text("#modal")
        check("archive made", "fingerprint" in mod.lower(),
              repr(toast(pg)) + " | " + mod[:300].replace("\n", " / "))
        modal_button(pg, "Check integrity")
        check("archive validates", "validated" in txt_of(pg, "#modal"),
              pg.inner_text("#modal")[:200])

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
