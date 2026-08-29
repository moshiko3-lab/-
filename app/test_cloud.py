#!/usr/bin/env python3
"""The shared book: what this browser changed, handed over, and what came back.

There is no network in here, and there should not be: this stubs fetch and
watches what the page actually does. What matters is the behaviour a school
depends on, not that a request was made.

  * a write goes into the outbox, whatever screen made it;
  * the outbox survives a reload -- a change made with no signal is not lost;
  * signing in is what starts the traffic, and nothing is sent before;
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
# whatever rows the test has planted for the next pull.
STUB = """() => {
  window.__calls = [];
  window.__inbox = {};          // table -> rows the next pull returns
  const real = window.fetch;
  window.fetch = function(url, opts) {
    opts = opts || {};
    const body = opts.body ? JSON.parse(opts.body) : null;
    window.__calls.push({url: String(url), method: opts.method || "GET",
                         body: body, headers: opts.headers || {}});
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
  return true;
}"""


def main():
    today = dt.date.today().isoformat()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 1680, "height": 1050}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto("file://" + build())
        pg.wait_for_timeout(2600)
        pg.evaluate(STUB)

        check("the page knows where its book lives",
              pg.evaluate("() => !!document.getElementById('btn-cloud')"))
        label = (pg.inner_text("#btn-cloud") or "").lower()
        check("and says it is not signed in yet", "sign in" in label, label)

        # --- a write with nobody signed in still goes into the outbox ------
        pg.click('#tabs button[data-id="clients"]')
        pg.wait_for_timeout(900)
        pg.click('#p-clients button:has-text("New client")')
        pg.wait_for_timeout(600)
        pg.fill('#modal input[type=text] >> nth=0', "Nuria Cloud")
        pg.locator('.modal-f button:has-text("Save")').first.click()
        pg.wait_for_timeout(800)

        box = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.cloud.outbox')||'{}')")
        # the seeded catalogue is in there too, and rightly: this browser made
        # it, so it is this browser's to hand over
        check("the new client is in the outbox",
              len(box.get("clients", {})) >= 1, json.dumps(box)[:200])
        check("and nothing was sent before signing in",
              pg.evaluate("() => window.__calls.filter("
                          "c => c.url.indexOf('/rest/') >= 0).length") == 0)

        # the outbox is not a variable, it is a place
        pg.reload()
        pg.wait_for_timeout(2200)
        pg.evaluate(STUB)
        box2 = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.cloud.outbox')||'{}')")
        check("it survives a reload", box2 == box, json.dumps(box2)[:200])

        # --- signing in starts the traffic --------------------------------
        pg.click("#btn-cloud")
        pg.wait_for_timeout(600)
        pg.fill('#modal input[type=email]', "moshe@shokogi.com")
        pg.fill('#modal input[type=password]', "whatever")
        pg.locator('.modal-f button:has-text("Sign in")').first.click()
        pg.wait_for_timeout(1500)

        calls = pg.evaluate("() => window.__calls")
        posts = [c for c in calls if c["method"] == "POST" and "/rest/v1/" in c["url"]]
        check("signing in hands over what was waiting", bool(posts),
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
        check("the button says so", "sync" in (pg.inner_text("#btn-cloud") or "").lower()
              or "synced" in (pg.inner_text("#btn-cloud") or "").lower(),
              pg.inner_text("#btn-cloud"))

        # --- somebody else's work arrives ---------------------------------
        pg.evaluate("""() => {
          window.__inbox.sessions = [{
            id: "seFromPhone", school: "shokogi", deleted: false,
            updated_at: new Date().toISOString(),
            data: {id:"seFromPhone", date: "%s", time:"07:00", duration: 60,
                   title:"FROM THE PHONE", capacity: 4, minCapacity: 0,
                   category:"", note:"", staffIds: [], participants: [],
                   spot:"", level:"", ageFrom:"", ageTo:"", allDay:false,
                   isPublic:true}}];
        }""" % today)
        pg.click("#btn-cloud")
        pg.wait_for_timeout(500)
        pg.locator('.modal-f button:has-text("Sync now")').first.click()
        pg.wait_for_timeout(1600)

        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1'))")
        got = [s for s in stored["sessions"] if s["id"] == "seFromPhone"]
        check("a session made on another device lands here", len(got) == 1,
              str(len(stored["sessions"])) + " sessions")
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

        # --- deleting says deleted ----------------------------------------
        # through the app, so the page's own copy loses it too: writing to
        # localStorage under a running page changes nothing it is holding
        pg.locator('[data-session-id="seFromPhone"]').first.click()
        pg.wait_for_timeout(500)
        pg.locator(".sess-pop .kebab").first.click()
        pg.wait_for_timeout(400)
        pg.locator('.rowmenu button:has-text("Delete session")').first.click()
        pg.wait_for_timeout(500)
        pg.locator('.modal-f button:has-text("Delete")').first.click()
        pg.wait_for_timeout(900)
        pg.evaluate("() => { window.__calls = []; }")
        pg.click("#btn-cloud")
        pg.wait_for_timeout(500)
        pg.locator('.modal-f button:has-text("Sync now")').first.click()
        pg.wait_for_timeout(1600)
        calls = pg.evaluate("() => window.__calls")
        sent = [c for c in calls
                if c["method"] == "POST" and "/rest/v1/sessions" in c["url"]]
        check("a removed record is sent as deleted",
              bool(sent) and sent[0]["body"][0].get("deleted") is True,
              json.dumps(sent[0]["body"][0])[:160] if sent else "nothing sent")

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
