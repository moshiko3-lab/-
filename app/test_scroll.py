#!/usr/bin/env python3
"""A screen redrawn under somebody's hands must not move.

Every save redraws the whole panel, and once the book is shared so does every
change arriving from another device. The panel is rebuilt from scratch, so
without care the scroll goes back to the top -- which at a counter, mid-morning,
means the board jumps away from the hour you were working in every time somebody
else's phone saves a hire.

The board is the case that matters: it is scrolled sideways far more than it is
scrolled down, and sideways is the scroll a rebuild loses most readily. So this
scrolls the board across, has the server say a row changed, and checks the view
did not move -- while checking the change really did land, because a redraw that
keeps the scroll by not redrawing would pass a weaker test than this.

And the other half of the rule: changing screens still starts at the top. That
one is wanted, and it would be easy to break while fixing the first.
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


# A device that has already signed in, and the other end of its live
# connection held by the test -- the same shape test_cloud uses.
SIGNED_IN = """
  try {
    localStorage.setItem("shokogi.cloud.session", JSON.stringify({
      access_token: "test", refresh_token: "test", email: "test@shokogi",
      expires_at: Date.now() + 36e5}));
  } catch (e) {}
  window.__inbox = {};
  window.fetch = function(url, opts) {
    opts = opts || {};
    if (opts.method === "POST")
      return Promise.resolve(new Response(null, {status: 204}));
    const m = String(url).match(/\\/rest\\/v1\\/([a-z]+)/);
    const rows = (m && window.__inbox[m[1]]) || [];
    if (m) window.__inbox[m[1]] = [];
    return Promise.resolve(new Response(JSON.stringify(rows),
      {status: 200, headers: {"Content-Type": "application/json"}}));
  };
  window.__ws = null;
  window.WebSocket = function(url) {
    const self = this;
    this.url = String(url);
    this.readyState = 0;
    this.send = function() {};
    this.close = function() { self.readyState = 3; };
    window.__ws = this;
    setTimeout(function() {
      self.readyState = 1;
      if (self.onopen) self.onopen({});
      if (self.onmessage) self.onmessage({data: JSON.stringify({
        topic: "realtime:shokogi", event: "phx_reply", ref: "1",
        payload: {status: "ok", response: {}}})});
    }, 20);
  };
"""

# the scroller the board lives in: the widest thing on the screen
SCROLLER = """() => {
  const sec = document.getElementById("p-board");
  if (!sec) return null;
  let best = null;
  sec.querySelectorAll("*").forEach(function(n) {
    if (n.scrollWidth - n.clientWidth > 60 &&
        (!best || n.scrollWidth > best.scrollWidth)) best = n;
  });
  if (!best) return null;
  window.__scroller = best;
  return best.scrollWidth - best.clientWidth;
}"""


def main():
    today = dt.date.today().isoformat()
    page = build()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        # deliberately short, so the board cannot fit and must scroll
        pg = br.new_context(viewport={"width": 1100, "height": 700}).new_page()
        pg.add_init_script(SIGNED_IN)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + page)
        pg.wait_for_timeout(2600)

        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1600)

        room = pg.evaluate(SCROLLER)
        check("the board is wider than the screen it is on",
              bool(room and room > 60), str(room))
        if not room:
            br.close()
            return 1

        # somebody working in the afternoon, scrolled across to it
        want = int(room * 0.6)
        pg.evaluate("(x) => { window.__scroller.scrollLeft = x; }", want)
        pg.wait_for_timeout(400)
        before = pg.evaluate("() => window.__scroller.scrollLeft")
        check("the board can be scrolled across to the afternoon",
              before > 60, str(before))

        # --- a change arrives from another device ---------------------------
        # the poll does nothing while the tab is in the background, so what
        # lands here arrived because the socket said so
        pg.evaluate("""() => {
          Object.defineProperty(document, "hidden",
            {get: () => true, configurable: true});
        }""")
        pg.evaluate("""(today) => {
          window.__inbox.sessions = [{
            id: "seScroll", school: "shokogi", deleted: false,
            updated_at: new Date().toISOString(),
            data: {id:"seScroll", date: today, time:"07:00", duration: 60,
                   title:"FROM ANOTHER DEVICE", capacity: 4, minCapacity: 0,
                   category:"", note:"", staffIds: [], participants: [],
                   spot:"", level:"", ageFrom:"", ageTo:"", allDay:false,
                   isPublic:true}}];
        }""", today)
        pg.evaluate("""() => {
          window.__ws.onmessage({data: JSON.stringify({
            topic: "realtime:shokogi", event: "postgres_changes",
            payload: {data: {table: "sessions", type: "INSERT"}}})});
        }""")
        pg.wait_for_timeout(1800)
        pg.evaluate("""() => {
          Object.defineProperty(document, "hidden",
            {get: () => false, configurable: true});
        }""")

        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        landed = [s for s in stored["sessions"] if s["id"] == "seScroll"]
        check("the change really did arrive", len(landed) == 1,
              str(len(stored["sessions"])) + " sessions")
        check("and the screen was redrawn to show it",
              "another device" in (pg.inner_text("#p-board") or "").lower(),
              (pg.inner_text("#p-board") or "")[:160])

        after = pg.evaluate(SCROLLER) is not None and pg.evaluate(
            "() => window.__scroller.scrollLeft")
        check("and the board did not jump back to the start of the day",
              abs(after - before) <= 4, "was %s, now %s" % (before, after))

        # --- a save on this device is the same story ------------------------
        pg.evaluate("(x) => { window.__scroller.scrollLeft = x; }", want)
        pg.wait_for_timeout(300)
        before = pg.evaluate("() => window.__scroller.scrollLeft")
        pg.evaluate("""() => {
          window.__inbox.sessions = [{
            id: "seScroll2", school: "shokogi", deleted: false,
            updated_at: new Date().toISOString(),
            data: {id:"seScroll2", date: "%s", time:"08:00", duration: 60,
                   title:"SECOND ONE", capacity: 4, minCapacity: 0,
                   category:"", note:"", staffIds: [], participants: [],
                   spot:"", level:"", ageFrom:"", ageTo:"", allDay:false,
                   isPublic:true}}];
          window.__ws.onmessage({data: JSON.stringify({
            topic: "realtime:shokogi", event: "postgres_changes",
            payload: {data: {table: "sessions", type: "INSERT"}}})});
        }""".replace("%s", today))
        pg.wait_for_timeout(1800)
        after = pg.evaluate(SCROLLER) is not None and pg.evaluate(
            "() => window.__scroller.scrollLeft")
        check("a second change does not move it either",
              abs(after - before) <= 4, "was %s, now %s" % (before, after))

        # --- but changing screens still starts at the top -------------------
        pg.click('#tabs button[data-id="clients"]')
        pg.wait_for_timeout(900)
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1400)
        pg.evaluate(SCROLLER)
        back = pg.evaluate("() => window.__scroller.scrollLeft")
        check("changing screens still starts at the beginning",
              back <= 4, str(back))

        check("no uncaught errors", not errs, "; ".join(errs[:3]))
        br.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
