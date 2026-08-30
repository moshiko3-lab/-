#!/usr/bin/env python3
"""The way in: nothing opens until somebody signs in.

A school's book is not something a passer-by opens by knowing the address. The
app does not draw at all until a sign-in has happened -- and once a device has
signed in, the session is kept, so it is asked once and then never again. That
last part matters more here than anywhere: a device that has already signed in
opens with no network, because a till cannot wait for the wifi.

The network is stubbed, as in test_cloud: what is being checked is what the
page does, not that a request went out.
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


# Supabase, stood in for: sign-in works only for one password, and everything
# else answers empty so the app has nothing to merge.
STUB = """() => {
  window.fetch = function(url, opts) {
    opts = opts || {};
    const body = opts.body ? JSON.parse(opts.body) : null;
    if (String(url).indexOf("/auth/v1/token") >= 0) {
      if (!body || body.password !== "right") {
        return Promise.resolve(new Response(JSON.stringify({
          error_description: "Invalid login credentials"}), {status: 400,
          headers: {"Content-Type": "application/json"}}));
      }
      return Promise.resolve(new Response(JSON.stringify({
        access_token: "tok", refresh_token: "ref", expires_in: 3600,
        user: {email: body.email}}), {status: 200,
        headers: {"Content-Type": "application/json"}}));
    }
    if (opts.method === "POST") return Promise.resolve(new Response(null, {status: 204}));
    return Promise.resolve(new Response("[]", {status: 200,
      headers: {"Content-Type": "application/json"}}));
  };
  return true;
}"""

# no network at all: every call fails the way a dead wifi fails
DEAD = """() => {
  window.fetch = function() { return Promise.reject(new TypeError("Failed to fetch")); };
  return true;
}"""


def visible(pg, sel):
    return pg.evaluate("""(s) => {
      const n = document.querySelector(s);
      if (!n) return false;
      const r = n.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }""", sel)


def main():
    page = build()
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, executable_path=CHROME,
                               args=["--no-sandbox"])
        pg = br.new_context(viewport={"width": 1280, "height": 900}).new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        # the stub has to be in place before the page's own script runs
        pg.add_init_script(STUB.strip()[len("() => {"):-1].strip())
        pg.goto("file://" + page)
        pg.wait_for_timeout(2600)

        # --- locked --------------------------------------------------------
        check("the way in is shown first", visible(pg, "#gate"))
        check("and the app is not drawn behind it",
              not visible(pg, ".wrap") and not visible(pg, "header.top"),
              "wrap=%s header=%s" % (visible(pg, ".wrap"), visible(pg, "header.top")))
        check("the school is named on it",
              "shokogi" in (pg.inner_text("#gate") or "").lower())

        # --- a wrong password says so, and stays shut ----------------------
        pg.fill("#gate-email", "moshe@shokogi.com")
        pg.fill("#gate-pass", "wrong")
        pg.click("#gate-go")
        pg.wait_for_timeout(900)
        check("a wrong password is refused", visible(pg, "#gate"))
        err = (pg.inner_text("#gate-err") or "").lower()
        check("in words a person reads", "do not match" in err, err)
        check("and it can be tried again",
              pg.evaluate("() => !document.getElementById('gate-go').disabled"))

        # --- the right one opens it ----------------------------------------
        pg.fill("#gate-pass", "right")
        pg.click("#gate-go")
        pg.wait_for_timeout(1600)
        check("the right password opens the app", not visible(pg, "#gate"))
        check("and the app is there", visible(pg, ".wrap") and visible(pg, "header.top"))
        check("signed in as the person who signed in",
              "moshe@shokogi.com" in pg.evaluate(
                  "() => localStorage.getItem('shokogi.cloud.session') || ''"))
        check("the password is not kept anywhere",
              "right" not in pg.evaluate(
                  "() => localStorage.getItem('shokogi.cloud.session') || ''"))

        # --- it is asked once, not every time -------------------------------
        pg.reload()
        pg.wait_for_timeout(2400)
        check("a reload does not ask again", not visible(pg, "#gate"))

        # --- and it opens with the wifi down --------------------------------
        pg.evaluate(DEAD)
        pg.reload()
        pg.wait_for_timeout(2400)
        check("a device that has signed in opens with no network",
              not visible(pg, "#gate") and visible(pg, ".wrap"))

        # --- signing out puts it back ---------------------------------------
        pg.evaluate(STUB)
        pg.click("#btn-cloud")
        pg.wait_for_timeout(600)
        pg.locator('.modal-f button:has-text("Sign out")').first.click()
        pg.wait_for_timeout(900)
        check("signing out shuts it again", visible(pg, "#gate"))
        check("and the app is hidden again", not visible(pg, ".wrap"))

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
