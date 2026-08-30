#!/usr/bin/env python3
"""A refused subscription must cost less than the whole live connection.

Asking to be told about changes is one request naming every table. If the
server objects to any single part of it -- a table nobody remembered to
publish, a filter it will not accept -- it refuses the whole thing, and the
school is left on the fifteen-second fallback with no Live and no reason
given. That is what happened here in the real project.

So: refused once, ask again for less. The same tables without the school
filter, which is safe because the row policies decide what a device may be
told regardless of what was filtered on the way out. Only if that is refused
too does it stay on the poll -- and then it says why, in words, rather than
leaving somebody staring at a corner that will not say Live.
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


# A signed-in device whose socket refuses the first join the way Supabase does
# when a table is not published, and takes the second.
STUB = """
  try {
    localStorage.setItem("shokogi.cloud.session", JSON.stringify({
      access_token: "test", refresh_token: "test", email: "test@shokogi",
      expires_at: Date.now() + 36e5}));
  } catch (e) {}
  window.fetch = function(url, opts) {
    opts = opts || {};
    if (opts.method === "POST")
      return Promise.resolve(new Response(null, {status: 204}));
    return Promise.resolve(new Response("[]", {status: 200,
      headers: {"Content-Type": "application/json"}}));
  };
  window.__refuseAll = false;    // when the second ask should be refused too
  window.__ws = null;
  window.WebSocket = function(url) {
    const self = this;
    this.url = String(url);
    this.readyState = 0;
    this.sent = [];
    this.close = function() { self.readyState = 3; };
    this.send = function(raw) {
      const m = JSON.parse(raw);
      self.sent.push(m);
      if (m.event !== "phx_join") return;
      const asks = m.payload.config.postgres_changes || [];
      const filtered = asks.some(function(a) { return !!a.filter; });
      // Supabase refuses the whole subscription, not the offending part
      const refuse = filtered || window.__refuseAll;
      setTimeout(function() {
        if (!self.onmessage) return;
        self.onmessage({data: JSON.stringify(refuse ? {
          topic: "realtime:shokogi", event: "phx_reply", ref: m.ref,
          payload: {status: "error", response: {reason:
            "Unable to subscribe to changes with given parameters"}}
        } : {
          topic: "realtime:shokogi", event: "phx_reply", ref: m.ref,
          payload: {status: "ok", response: {}}})});
      }, 20);
    };
    window.__ws = this;
    setTimeout(function() {
      self.readyState = 1;
      if (self.onopen) self.onopen({});
    }, 20);
  };
"""


def joins(pg):
    return pg.evaluate(
        "() => (window.__ws ? window.__ws.sent : [])"
        ".filter(m => m.event === 'phx_join')"
        ".map(m => (m.payload.config.postgres_changes || [])"
        "  .some(a => !!a.filter) ? 'filtered' : 'plain')")


def corner(pg):
    pg.click("#btn-cloud")
    pg.wait_for_timeout(700)
    txt = pg.inner_text("#modal") or ""
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(400)
    return txt


def main():
    page = build()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 1280, "height": 900})

        # --- the narrow ask is refused, the plain one is taken --------------
        pg = ctx.new_page()
        pg.add_init_script(STUB)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + page)
        pg.wait_for_timeout(2800)

        asked = joins(pg)
        check("it asks for this school's rows first",
              len(asked) >= 1 and asked[0] == "filtered", str(asked))
        check("and when that is refused it asks again for less",
              len(asked) >= 2 and asked[1] == "plain", str(asked))
        check("it does not keep asking the same refused thing",
              len(asked) <= 2, str(len(asked)) + " asks")

        txt = corner(pg)
        check("the corner says the connection is open",
              "live connection" in txt.lower() and "open" in txt.lower(),
              txt[:200])
        check("and not that it is closed",
              "not open" not in txt.lower(), txt[:200])

        # --- refused both ways: the day still works, and it says why --------
        pg2 = ctx.new_page()
        pg2.add_init_script(STUB)
        pg2.add_init_script("window.__refuseAll = true;")
        errs2 = []
        pg2.on("pageerror", lambda e: errs2.append(str(e)[:200]))
        pg2.goto("file://" + page)
        pg2.wait_for_timeout(2800)

        asked2 = joins(pg2)
        check("it tries twice and then stops", len(asked2) == 2, str(asked2))
        txt2 = corner(pg2)
        check("the corner admits the connection is not open",
              "not open" in txt2.lower(), txt2[:200])
        check("says changes still arrive, so nobody thinks work is being lost",
              "15 seconds" in txt2.lower() or "fifteen" in txt2.lower(),
              txt2[:300])
        check("and repeats the server's own reason",
              "unable to subscribe" in txt2.lower(), txt2[:300])
        check("the app is usable regardless",
              pg2.is_visible("#tabs") and not pg2.is_visible("#gate"))

        # --- the socket will not take the publishable key -------------------
        # The REST side takes it and always has, so everything else works and
        # only Live is missing -- which is exactly how this looked in the real
        # project. A signed-in person has a token the socket does understand.
        pg3 = ctx.new_page()
        pg3.add_init_script(STUB)
        pg3.add_init_script("""
          window.__keys = [];
          const Real = window.WebSocket;
          window.WebSocket = function(url) {
            const key = decodeURIComponent(
              (String(url).match(/apikey=([^&]*)/) || [,""])[1]);
            window.__keys.push(key);
            const s = new Real(url);
            // the way a gateway refuses a credential: hang up, saying nothing
            if (key.indexOf("sb_publishable") === 0 || key === "PUBKEY") {
              setTimeout(function() {
                s.readyState = 3;
                if (s.onclose) s.onclose({code: 1006});
              }, 40);
            }
            return s;
          };
        """)
        errs3 = []
        pg3.on("pageerror", lambda e: errs3.append(str(e)[:200]))
        pg3.goto("file://" + page)
        pg3.wait_for_timeout(3200)

        keys = pg3.evaluate("() => window.__keys")
        check("it introduces itself with the publishable key first",
              len(keys) >= 1 and keys[0].startswith(("sb_publishable", "PUBKEY")),
              str([k[:18] for k in keys]))
        check("and when the socket hangs up, tries the sign-in token",
              len(keys) >= 2 and keys[1] == "test",
              str([k[:18] for k in keys]))
        txt3 = corner(pg3)
        check("which gets it open", "not open" not in txt3.lower(), txt3[:200])
        check("and it remembers what worked, so tomorrow starts there",
              pg3.evaluate(
                  "() => localStorage.getItem('shokogi.cloud.livekey')") == "1")

        check("no uncaught errors",
              not errs and not errs2 and not errs3,
              "; ".join((errs + errs2 + errs3)[:3]))
        br.close()

    print()
    if fails:
        print(f"{len(fails)} failed: " + ", ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
