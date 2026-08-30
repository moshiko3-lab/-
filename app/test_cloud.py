#!/usr/bin/env python3
"""The shared book: what this browser changed, handed over, and what came back.

There is no network in here, and there should not be: this stubs fetch and
watches what the page actually does. What matters is the behaviour a school
depends on, not that a request was made.

  * nothing is asked of the book before somebody signs in;
  * a write made with the wifi down goes into the outbox, whatever screen
    made it;
  * the outbox survives a reload -- a change made with no signal is not lost;
  * the connection coming back is what hands it over;
  * a push sends only what changed, carries the school, and marks a deleted
    record deleted rather than dropping it silently;
  * a pull merges somebody else's row into this browser and shows it;
  * a row this browser has pending is not overwritten by the pull.
"""
import datetime as dt
import json
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


# Stand in for Supabase: remember every call, answer sign-in, and hand back
# whatever rows the test has planted for the next pull. __down is the wifi,
# for the half of the morning the counter does not have any.
STUB_BODY = """
  window.__calls = [];
  window.__inbox = {};          // table -> rows the next pull returns
  window.__down = false;        // the connection, when the test takes it away
  window.__slow = 0;            // and how long it takes when it is there
  window.fetch = function(url, opts) {
    opts = opts || {};
    const body = opts.body ? JSON.parse(opts.body) : null;
    window.__calls.push({url: String(url), method: opts.method || "GET",
                         body: body, headers: opts.headers || {}});
    if (window.__down) return Promise.reject(new TypeError("Failed to fetch"));
    if (window.__slow) {
      const inner = window.__answer(url, opts, body);
      return new Promise(function(res) {
        setTimeout(function() { res(inner); }, window.__slow);
      });
    }
    return window.__answer(url, opts, body);
  };
  window.__answer = function(url, opts, body) {
    if (String(url).indexOf("/auth/v1/token") >= 0) {
      return Promise.resolve(new Response(JSON.stringify({
        access_token: "tok", refresh_token: "ref", expires_in: 3600,
        user: {email: (body && body.email) || "x@y.z"}
      }), {status: 200, headers: {"Content-Type": "application/json"}}));
    }
    if (opts.method === "POST") {
      return Promise.resolve(new Response(null, {status: 204}));
    }
    const m = String(url).match(/\\/rest\\/v1\\/([a-z]+)/);
    const rows = (m && window.__inbox[m[1]]) || [];
    if (m) window.__inbox[m[1]] = [];
    return Promise.resolve(new Response(JSON.stringify(rows),
      {status: 200, headers: {"Content-Type": "application/json"}}));
  };

  // The other end of the live connection, held by the test. It opens, answers
  // the join the way the server does, and then sits there until the test says
  // a row changed.
  window.__ws = null;
  window.WebSocket = function(url) {
    const self = this;
    this.url = String(url);
    this.readyState = 0;
    this.sent = [];
    this.send = function(m) { self.sent.push(JSON.parse(m)); };
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

# the same thing to hand to evaluate(), for after a reload
STUB = "() => {" + STUB_BODY + "return true; }"


def new_client(pg, name):
    pg.click('#tabs button[data-id="clients"]')
    pg.wait_for_timeout(500)
    pg.click('#p-clients button:has-text("New client")')
    pg.wait_for_timeout(500)
    pg.fill('#modal input[type=text] >> nth=0', name)
    pg.locator('.modal-f button:has-text("Save")').first.click()
    pg.wait_for_timeout(400)


def main():
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        # the door itself calls out, so the stub has to be in place before the
        # page's own script runs -- installing it after the load is too late
        pg.add_init_script(STUB_BODY)
        pg.goto("file://" + build())
        pg.wait_for_timeout(2600)

        check("nothing is asked of the book before somebody signs in",
              pg.evaluate("() => window.__calls.filter("
                          "c => c.url.indexOf('/rest/') >= 0).length") == 0)

        # --- in through the door -------------------------------------------
        pg.fill("#gate-email", "moshe@shokogi.com")
        pg.fill("#gate-pass", "whatever")
        pg.click("#gate-go")
        pg.wait_for_timeout(1800)
        check("the page knows where its book lives",
              pg.evaluate("() => !!document.getElementById('btn-cloud')"))
        label = (pg.inner_text("#btn-cloud") or "").lower()
        check("and no longer asks to be signed in", "sign in" not in label, label)

        # --- the live connection ------------------------------------------
        join = pg.evaluate("""() => {
          const w = window.__ws;
          if (!w) return null;
          const j = w.sent.filter(m => m.event === "phx_join")[0];
          return j ? {topic: j.topic,
                      tables: (j.payload.config.postgres_changes || [])
                                .map(c => c.table),
                      filters: (j.payload.config.postgres_changes || [])
                                .map(c => c.filter),
                      token: j.payload.access_token} : null;
        }""")
        check("signing in opens a live connection", join is not None)
        if join:
            check("it listens for every collection", len(join["tables"]) == 15,
                  str(len(join["tables"])))
            check("for this school only",
                  all(f == "school=eq.shokogi" for f in join["filters"]),
                  str(join["filters"][:2]))
            check("and signs the request, so the policies still apply",
                  bool(join["token"]))
        check("and the corner says it is live",
              "live" in (pg.inner_text("#btn-cloud") or "").lower(),
              pg.inner_text("#btn-cloud"))

        # --- the first hand-over, which nobody had to know to ask for -------
        # A school's book starts inside one browser. Signing in is what puts it
        # on the server; there is no button to remember, and a second device
        # signing in tomorrow finds it there rather than finding nothing.
        up = {}
        for c in pg.evaluate("() => window.__calls"):
            if c["method"] == "POST" and "/rest/v1/" in c["url"]:
                t = c["url"].split("/rest/v1/")[1].split("?")[0]
                up[t] = up.get(t, 0) + len(c["body"] or [])
        check("signing in puts the book up there without being asked",
              up.get("products", 0) > 0 and up.get("gear", 0) > 0, str(up))

        # and a table the server already holds is left alone: taking what is
        # there is the normal path, and this must never run over it
        pg.evaluate("""() => {
          window.__calls = [];
          window.__seenBefore = JSON.parse(
            localStorage.getItem("shokogi.cloud.seeded") || "{}");
        }""")
        check("every collection is accounted for after the first sync",
              len(pg.evaluate("() => window.__seenBefore")) == 15,
              str(len(pg.evaluate("() => window.__seenBefore"))))

        # --- a write with the wifi down goes into the outbox ---------------
        # which is the state a counter in Playa Venao spends half the morning in
        pg.evaluate("() => { window.__down = true; }")
        new_client(pg, "Nuria Cloud")
        pg.wait_for_timeout(800)

        box = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.cloud.outbox')||'{}')")
        check("the new client is in the outbox",
              len(box.get("clients", {})) >= 1, json.dumps(box)[:200])
        check("and the corner does not claim it is safe",
              "synced" not in (pg.inner_text("#btn-cloud") or "").lower(),
              pg.inner_text("#btn-cloud"))

        # the outbox is not a variable, it is a place
        pg.reload()
        pg.wait_for_timeout(2200)
        box2 = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.cloud.outbox')||'{}')")
        check("it survives a reload", box2 == box, json.dumps(box2)[:200])
        check("and the door does not ask again",
              not pg.evaluate("""() => {
                const n = document.getElementById("gate");
                if (!n) return false;
                const r = n.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
              }"""))

        # --- the connection comes back ------------------------------------
        pg.evaluate("() => { window.__calls = []; }")
        pg.click("#btn-cloud")
        pg.wait_for_timeout(600)
        pg.locator('.modal-f button:has-text("Sync now")').first.click()
        pg.wait_for_timeout(1800)

        calls = pg.evaluate("() => window.__calls")
        posts = [c for c in calls if c["method"] == "POST" and "/rest/v1/" in c["url"]]
        check("what was waiting goes over", bool(posts),
              str(len(calls)) + " calls")
        if posts:
            rows = [r for c in posts for r in (c["body"] or [])]
            check("every row carries the school",
                  all(r.get("school") == "shokogi" for r in rows),
                  str(len(rows)) + " rows")
            check("the client goes over as a whole record, not just an id",
                  any((r.get("data") or {}).get("name") == "Nuria Cloud"
                      for r in rows), str(len(rows)) + " rows")
            check("upserting, so a second device does not make a duplicate",
                  all("on_conflict=id" in c["url"] for c in posts),
                  posts[0]["url"])
        pg.wait_for_timeout(1200)
        check("the outbox is empty once it is sent",
              pg.evaluate("() => JSON.parse("
                          "localStorage.getItem('shokogi.cloud.outbox')||'{}')") == {})
        corner = (pg.inner_text("#btn-cloud") or "").lower()
        check("the button says so", "sync" in corner or "live" in corner, corner)

        # --- a change typed while a sync is in the air ---------------------
        # This was the reason somebody had to press the button. A save landing
        # during a sync was dropped and left to wait for the next poll, and at
        # a counter taking bookings that is the normal case, not the rare one.
        pg.evaluate("() => { window.__calls = []; window.__slow = 1200; }")
        new_client(pg, "During One")     # starts a sync a moment from now
        new_client(pg, "During Two")     # saved while that sync is in flight
        pg.wait_for_timeout(8000)
        pg.evaluate("() => { window.__slow = 0; }")
        rows = [r for c in pg.evaluate("() => window.__calls")
                if c["method"] == "POST" and "/rest/v1/clients" in c["url"]
                for r in (c["body"] or [])]
        names = [(r.get("data") or {}).get("name") for r in rows]
        check("the one saved during the sync is not dropped",
              "During Two" in names, str(names))
        check("and nothing is left waiting",
              pg.evaluate("() => JSON.parse("
                          "localStorage.getItem('shokogi.cloud.outbox')||'{}')") == {},
              pg.evaluate("() => localStorage.getItem('shokogi.cloud.outbox')"))

        # --- somebody else's work arrives, with nobody pressing anything ----
        # The poll deliberately does nothing while the tab is in the background.
        # Putting the page there is what makes this a test of the socket rather
        # than a test of waiting long enough: with the poll provably switched
        # off, anything that lands here arrived because the socket said so.
        pg.evaluate("""() => {
          Object.defineProperty(document, "hidden",
            {get: () => true, configurable: true});
        }""")
        pg.evaluate("""() => {
          window.__inbox.sessions = [{
            id: "seFromPhone", school: "shokogi", deleted: false,
            updated_at: new Date().toISOString(),
            data: {id:"seFromPhone", date: "%s", time:"07:00", duration: 60,
                   title:"FROM THE PHONE", capacity: 4, minCapacity: 0,
                   category:"", note:"", staffIds: [], participants: [],
                   spot:"", level:"", ageFrom:"", ageTo:"", allDay:false,
                   isPublic:true}}];
          window.__calls = [];
        }""" % today)
        pg.wait_for_timeout(1500)
        check("nothing arrives while nothing has changed",
              pg.evaluate("() => window.__calls.length") == 0,
              str(pg.evaluate("() => window.__calls.length")) + " calls")

        # the server says a row changed, which is all it says
        pg.evaluate("""() => {
          window.__ws.onmessage({data: JSON.stringify({
            topic: "realtime:shokogi", event: "postgres_changes",
            payload: {data: {table: "sessions", type: "UPDATE"}}})});
        }""")
        pg.wait_for_timeout(1600)
        pg.evaluate("""() => {
          Object.defineProperty(document, "hidden",
            {get: () => false, configurable: true});
        }""")

        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        got = [s for s in stored["sessions"] if s["id"] == "seFromPhone"]
        check("a session made on another device arrives on its own",
              len(got) == 1, str(len(stored["sessions"])) + " sessions")
        pg.click('#tabs button[data-id="board"]')
        pg.wait_for_timeout(1400)
        check("and shows on the board",
              "from the phone" in (pg.inner_text("#p-board") or "").lower(),
              (pg.inner_text("#p-board") or "")[:200])

        # --- a pending local change is not run over ------------------------
        pg.evaluate("""() => {
          const k = "shokogi.manager.v1";
          const d = JSON.parse(localStorage.getItem(k));
          const s = d.sessions.find(x => x.id === "seFromPhone");
          s.title = "MINE, NOT SENT YET";
          localStorage.setItem(k, JSON.stringify(d));
          const o = JSON.parse(localStorage.getItem("shokogi.cloud.outbox")||"{}");
          (o.sessions = o.sessions || {})["seFromPhone"] = 1;
          localStorage.setItem("shokogi.cloud.outbox", JSON.stringify(o));
          window.__inbox.sessions = [{
            id: "seFromPhone", school: "shokogi", deleted: false,
            updated_at: new Date().toISOString(),
            data: {id:"seFromPhone", title:"THEIRS", date: "1970-01-01",
                   time:"07:00", duration: 60, capacity: 4, minCapacity: 0,
                   category:"", note:"", staffIds: [], participants: [],
                   spot:"", level:"", ageFrom:"", ageTo:"", allDay:false,
                   isPublic:true}}];
        }""")
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.evaluate(STUB)
        pg.evaluate("""() => {
          window.__inbox.sessions = [{
            id: "seFromPhone", school: "shokogi", deleted: false,
            updated_at: new Date().toISOString(),
            data: {id:"seFromPhone", title:"THEIRS", date:"1970-01-01",
                   time:"07:00", duration: 60, capacity: 4, minCapacity: 0,
                   category:"", note:"", staffIds: [], participants: [],
                   spot:"", level:"", ageFrom:"", ageTo:"", allDay:false,
                   isPublic:true}}];
        }""")
        pg.click("#btn-cloud")
        pg.wait_for_timeout(500)
        pg.locator('.modal-f button:has-text("Sync now")').first.click()
        pg.wait_for_timeout(1600)
        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        mine = [s for s in stored["sessions"] if s["id"] == "seFromPhone"]
        check("a change of ours that is still waiting is not overwritten",
              mine and mine[0]["title"] == "MINE, NOT SENT YET",
              mine[0]["title"] if mine else "gone")

        # --- deleting says deleted, and nobody presses anything -------------
        # through the app, so the page's own copy loses it too: writing to
        # localStorage under a running page changes nothing it is holding
        pg.evaluate("() => { window.__calls = []; }")
        pg.locator('[data-session-id="seFromPhone"]').first.click()
        pg.wait_for_timeout(500)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Delete session")').first.click()
        pg.wait_for_timeout(500)
        pg.locator('.modal-f button:has-text("Delete")').first.click()
        # no Sync now: a change made in the app hands itself over. This is the
        # whole of what the school asked for -- nothing to remember to press.
        pg.wait_for_timeout(2500)
        calls = pg.evaluate("() => window.__calls")
        sent = [c for c in calls
                if c["method"] == "POST" and "/rest/v1/sessions" in c["url"]]
        check("a removed record goes over by itself, as deleted",
              bool(sent) and sent[0]["body"][0].get("deleted") is True,
              json.dumps(sent[0]["body"][0])[:160] if sent else "nothing sent")
        check("and the outbox is empty after it",
              pg.evaluate("() => JSON.parse("
                          "localStorage.getItem('shokogi.cloud.outbox')||'{}')") == {})

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
