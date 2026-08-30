#!/usr/bin/env python3
"""An empty answer is the normal answer, not a failure.

The push asks the server for the shortest reply it can give -- it does not want
the rows back, it only wants to know they landed. PostgREST obliges with 201
Created and an empty body. Handing that to JSON.parse throws "Unexpected end of
JSON input", which is what the school saw in the corner: every table failing,
every time, while the writes themselves were landing perfectly well.

That is the worst shape a bug can take here. The rows were never cleared from
the outbox, so they were sent again on the next run, landed again, and were
counted as refused again -- a sync that looked broken while quietly working,
and a book that never stopped having a backlog.

So: an empty body means it worked. A body with something unreadable in it is a
real problem and still says so.
"""
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


# A server that answers a push exactly the way PostgREST does with
# Prefer: return=minimal -- 201 Created, and nothing in the body.
STUB = """
  try {
    localStorage.setItem("shokogi.cloud.session", JSON.stringify({
      access_token: "test", refresh_token: "test", email: "test@shokogi",
      expires_at: Date.now() + 36e5}));
  } catch (e) {}
  window.__posts = [];
  window.__garbage = false;     // when the reply is unreadable rather than empty
  window.fetch = function(url, opts) {
    opts = opts || {};
    if ((opts.method || "GET") === "POST" &&
        String(url).indexOf("/rest/v1/") >= 0) {
      window.__posts.push({url: String(url),
                           rows: opts.body ? JSON.parse(opts.body) : null});
      if (window.__garbage)
        return Promise.resolve(new Response("<html>gateway</html>",
          {status: 201, headers: {"Content-Type": "text/html"}}));
      // 201 and an empty body: the case that was breaking
      return Promise.resolve(new Response("", {status: 201}));
    }
    return Promise.resolve(new Response("[]", {status: 200,
      headers: {"Content-Type": "application/json"}}));
  };
  window.WebSocket = function() {
    this.send = function() {}; this.close = function() {};
  };
"""


def outbox(pg):
    return pg.evaluate("""() => {
      const o = JSON.parse(localStorage.getItem("shokogi.cloud.outbox") || "{}");
      let n = 0;
      Object.keys(o).forEach(k => { n += Object.keys(o[k] || {}).length; });
      return n;
    }""")


def corner(pg):
    pg.click("#btn-cloud")
    pg.wait_for_timeout(700)
    txt = pg.inner_text("#modal") or ""
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(400)
    return txt


def new_client(pg, name):
    pg.click('#tabs button[data-id="clients"]')
    pg.wait_for_timeout(600)
    pg.click('#p-clients button:has-text("New client")')
    pg.wait_for_timeout(600)
    pg.fill('#modal input[type=text] >> nth=0', name)
    pg.locator('.modal-f button:has-text("Save")').first.click()
    pg.wait_for_timeout(700)


def main():
    page = build()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 1280, "height": 900})

        pg = ctx.new_page()
        pg.add_init_script(STUB)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + page)
        pg.wait_for_timeout(2800)

        new_client(pg, "Empty Reply Test")
        pg.wait_for_timeout(2600)

        check("the write was sent to the server",
              any("clients" in c["url"] for c in pg.evaluate("() => window.__posts")),
              str([c["url"][-30:] for c in pg.evaluate("() => window.__posts")][:4]))
        check("an empty reply counts as sent, so the outbox drains",
              outbox(pg) == 0, str(outbox(pg)) + " still waiting")

        txt = corner(pg)
        check("and nothing is reported as trouble",
              "none" in txt.lower().split("trouble")[-1][:40],
              txt[txt.lower().find("trouble"):][:120] if "trouble" in txt.lower()
              else txt[:160])
        check("in particular not the JSON complaint",
              "json" not in txt.lower(), txt[:200])

        # sending again must not re-send what already landed
        before = len(pg.evaluate("() => window.__posts"))
        pg.wait_for_timeout(2500)
        check("and it is not sent over and over",
              len(pg.evaluate("() => window.__posts")) == before,
              "%d then %d" % (before, len(pg.evaluate("() => window.__posts"))))

        # --- an unreadable reply is still a real problem --------------------
        # its own context: pages in one context share localStorage, and the
        # first page is still draining the very outbox this one is about
        ctx2 = br.new_context(viewport={"width": 1280, "height": 900})
        pg2 = ctx2.new_page()
        pg2.add_init_script(STUB)
        pg2.add_init_script("window.__garbage = true;")
        errs2 = []
        pg2.on("pageerror", lambda e: errs2.append(str(e)[:200]))
        pg2.goto("file://" + page)
        pg2.wait_for_timeout(2800)
        new_client(pg2, "Garbage Reply Test")
        pg2.wait_for_timeout(2600)

        check("and that work is kept to be sent again", outbox(pg2) > 0,
              str(outbox(pg2)))
        txt2 = corner(pg2)
        check("an answer that is not empty but not readable does say so",
              "not readable" in txt2.lower(), txt2[:220])

        check("no uncaught errors", not errs and not errs2,
              "; ".join((errs + errs2)[:3]))
        br.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
