#!/usr/bin/env python3
"""The card that opens when you click a session on the board.

Bloowatch does not open a form when you click a block. It opens a small card
on the block: the hour, whether it is public, how full it is, the instructor
as a dropdown, and everyone in it with which lesson of their course this one
is -- "P1 roei s  2/2". The form is still there behind the title, for
everything the card does not carry.
"""
import datetime as dt
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
HERE = os.path.dirname(os.path.abspath(__file__))

fails = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def build():
    out = os.path.join(tempfile.mkdtemp(), "app.html")
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out


def low(pg, sel):
    return (pg.inner_text(sel) or "").lower()


SEED = """(today) => {
  const k = "shokogi.manager.v1";
  const d = JSON.parse(localStorage.getItem(k));
  const course = d.products.find(p => (p.sessions||1) >= 2
                   && p.ptype !== "rental" && !p.gearId);
  if (!course) return null;
  const staff = d.staff.slice(0, 2);
  if (staff.length < 2) return null;

  d.bookings = [];
  d.sessions = [];
  d.clients.push({id:"cPop", name:"Roei Sasson", phone:"+507 9", custom:{}});
  d.bookings.push({id:"bPop", date: today, clientId:"cPop",
    payments: [], refunds: [], custom:{}, notes:"",
    participants: [{pid:"pp1", name:"P1 roei s", custom:{}}],
    lines: [{lid:"lPop", productId: course.id, qty:1, pax:1, hours:null,
             price: 120, wanted: today, pids:["pp1"], sessionIds: []}]});

  // two sessions of that course, the second one seated
  ["09:00","13:00"].forEach((t, i) => {
    d.sessions.push({id:"sePop"+i, date: today, time: t, duration: 60,
      title:"SURF PACK", capacity: 6, minCapacity: 0, category: course.category || "",
      note:"", staffIds: i === 1 ? [staff[0].id] : [], participants: [],
      spot:"", level:"", ageFrom:"", ageTo:"", allDay:false, isPublic:true,
      fromLines: ["lPop"]});
  });
  d.sessions.forEach(s => { s.participants = ["p:bPop:pp1"]; });
  localStorage.setItem(k, JSON.stringify(d));
  return {course: course.name, sessions: course.sessions || 1,
          staff: staff.map(s => s.name)};
}"""


def main():
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2600)

        seeded = pg.evaluate(SEED, today)
        check("a course with two sessions was seeded", seeded is not None)
        if seeded is None:
            b.close()
            return 1
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)

        blocks = pg.locator('[data-session-id]')
        check("the sessions are on the board", blocks.count() >= 2,
              str(blocks.count()))

        # clicking a block opens the card, not the form
        blocks.first.click()
        pg.wait_for_timeout(700)
        check("a click opens the card", pg.locator(".sess-pop").count() == 1)
        # The modal element is always in the document; the scrim's hidden
        # attribute is what says whether a form is actually up, so counting
        # ".modal" would pass whether or not one opened.
        check("and not the form", pg.locator("#scrim").is_hidden())

        card = low(pg, ".sess-pop")
        check("the card names the session", "surf pack" in card, card[:200])
        check("it shows the hour", "09:00" in card or "13:00" in card, card[:200])
        # Theirs shows the headcount alone -- "1", not "1/6". The capacity is
        # a setting, and it lives in the tooltip.
        check("it shows the headcount", "1" in card, card[:200])
        check("and not the capacity", "/6" not in card, card[:200])
        check("which the tooltip spells out",
              "of 6" in (pg.get_attribute(".sess-pop .sp-cap", "title") or ""),
              pg.get_attribute(".sess-pop .sp-cap", "title") or "")
        check("it names who is in it", "roei" in card, card[:200])
        check("with which lesson of their course this is",
              ("1/" + str(seeded["sessions"])) in card or
              ("2/" + str(seeded["sessions"])) in card, card[:200])
        # the day is the day you are looking at, so theirs leaves it out
        check("and no date repeating the day you are on",
              dt.date.today().strftime("%d/%m") not in card, card[:200])

        # the instructor changes from the card
        sel = pg.locator(".sess-pop select.sp-who")
        check("the instructor is a dropdown on the card", sel.count() == 1)
        sel.select_option(label=seeded["staff"][1])
        pg.wait_for_timeout(800)
        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        names = {s["id"]: s["name"] for s in stored["staff"]}
        who = [names.get(i) for se in stored["sessions"]
               for i in (se.get("staffIds") or [])]
        check("choosing one puts them on the session",
              seeded["staff"][1] in who, str(who))

        # the eye toggles public without leaving
        blocks.first.click()
        pg.wait_for_timeout(600)
        pg.click(".sess-pop .sp-eye")
        pg.wait_for_timeout(700)
        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        check("the eye takes a session off the public site",
              any(s.get("isPublic") is False for s in stored["sessions"]),
              str([s.get("isPublic") for s in stored["sessions"]]))

        # and the card closes the way a card should
        blocks.first.click()
        pg.wait_for_timeout(500)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)
        check("Escape closes it", pg.locator(".sess-pop").count() == 0)

        blocks.first.click()
        pg.wait_for_timeout(500)
        pg.mouse.click(900, 980)
        pg.wait_for_timeout(400)
        check("so does clicking away", pg.locator(".sess-pop").count() == 0)

        # the title still reaches the full form
        blocks.first.click()
        pg.wait_for_timeout(500)
        pg.click(".sess-pop .sp-title")
        pg.wait_for_timeout(800)
        check("the title opens the full session", pg.locator("#scrim").is_visible())
        check("which is the edit form", "edit session" in low(pg, "#modal"),
              low(pg, "#modal")[:120])
        check("and the card stepped out of the way",
              pg.locator(".sess-pop").count() == 0)

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
