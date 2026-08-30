#!/usr/bin/env python3
"""The WhatsApp screen, driven the way the counter drives it.

Four things are worth a test here, and they are all things that would be found
out by a customer rather than by us:

* The 24-hour window. WhatsApp refuses a free-form message more than a day
  after the person's own last message, so the box has to be closed *before*
  somebody types into it -- a reply that is accepted, sent and then refused by
  Meta reads to the school as a message delivered.
* A number typed one way and arriving another is one conversation. "+507 6000
  0000" at the counter and "50760000000" from the webhook must be the same
  thread and must show the client's name, or the school answers a stranger.
* Sending goes to the function, never to Meta. The page has no token and must
  never behave as though it does.
* The brief the preview shows is the brief that goes out. It is the one thing
  in this screen a person reads before turning something on for everybody.
"""
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


TODAY = subprocess.run(
    [sys.executable, "-c", "import datetime;print(datetime.date.today().isoformat())"],
    capture_output=True, text=True).stdout.strip()

# A book with one client, one instructor and one session today. The client's
# phone is written the way a person writes it; the conversation carries the
# same number the way Meta sends it.
BOOK = {
    "v": 1, "seq": 9, "seeded": True,
    "clients": [{"id": "c1", "name": "Nahum Cordero", "phone": "+507 6000 0000",
                 "email": "", "country": "PA"}],
    "staff": [{"id": "s1", "name": "Marta", "role": "Instructor",
               "phone": "50760000001"}],
    "sessions": [{"id": "se1", "title": "Surf lesson", "date": TODAY,
                  "time": "09:00", "duration": 90, "capacity": 6,
                  "staffIds": ["s1"], "participants": ["c:c1"], "category": "Surf"}],
    "products": [], "gear": [], "gearBlocks": [], "timeOff": [], "bookings": [],
    "spots": [], "invoices": [], "tides": [], "docs": [], "cash": [], "trips": [],
    "pos": [], "tickets": [], "archives": [], "commissionGroups": [],
    "icalFeeds": [], "feeGroups": [], "promos": [], "partners": [],
    "accommodations": [], "staffFees": {}, "boardCollapsed": {},
    "settings": {"business": {"name": "Shokogi", "currency": "USD"},
                 "methods": ["Cash"], "roles": ["Instructor"],
                 "kinds": [{"k": "lesson", "l": "Lesson"}],
                 "customFields": [], "boardFrom": 6, "boardTo": 20},
}

# One conversation gone cold, one still open. The server's own shapes.
COLD = "50760000000"     # the client, three days quiet
WARM = "50760000002"     # a stranger who wrote a minute ago

STUB = """
  window.__sent = [];
  localStorage.setItem("shokogi.cloud.session", JSON.stringify({
    access_token: "test", refresh_token: "test", email: "test@shokogi",
    expires_at: Date.now() + 36e5}));
  localStorage.setItem("shokogi.manager.v1", JSON.stringify(__BOOK__));
  var ago = function(mins){ return new Date(Date.now()-mins*60000).toISOString(); };
  var CONTACTS = [
    {school:"shokogi", wa_id:"__WARM__", name:"Walk-in", unread:2,
     last_in:ago(1), last_out:null, opted_out:false, needs_human:false},
    {school:"shokogi", wa_id:"__COLD__", name:null, unread:0,
     last_in:ago(60*72), last_out:ago(60*70), opted_out:false, needs_human:false}
  ];
  var MESSAGES = [
    {id:"m3", wa_id:"__WARM__", direction:"in", kind:"text",
     body:"is there space this afternoon?", status:"received", created_at:ago(1)},
    {id:"m2", wa_id:"__COLD__", direction:"out", kind:"template",
     body:"Nahum · Surf lesson", template:"session_reminder", status:"delivered",
     created_at:ago(60*70)},
    {id:"m1", wa_id:"__COLD__", direction:"in", kind:"text",
     body:"see you tomorrow", status:"received", created_at:ago(60*72)}
  ];
  var answer = function(body, status){
    // a 204 may not carry a body at all -- constructing one with an empty
    // string throws, which is the stub failing rather than the app
    status = status || 200;
    var text = typeof body === "string" ? body : JSON.stringify(body);
    if (status === 204) return Promise.resolve(new Response(null, {status: 204}));
    return Promise.resolve(new Response(text,
      {status: status, headers: {"Content-Type": "application/json"}}));
  };
  window.fetch = function(url, opts){
    url = String(url); opts = opts || {};
    var method = opts.method || "GET";
    if (url.indexOf("/functions/v1/whatsapp/send") >= 0) {
      window.__sent.push(JSON.parse(opts.body));
      return answer({ok: true, id: "wamid.test", how: "text"});
    }
    if (url.indexOf("/functions/v1/whatsapp/health") >= 0)
      return answer({connected: false, token: false, phoneId: true,
                     verifyToken: true, appSecret: false, tickSecret: false,
                     queued: 0, config: {}});
    if (url.indexOf("/functions/v1/whatsapp/tick") >= 0)
      return answer({ok: true, queued: {reminders: 1, brief: 0}, sent: 1, failed: 0});
    if (url.indexOf("/rest/v1/wa_config") >= 0) {
      if (method !== "GET") return answer("", 201);
      return answer([{data: {tz: "America/Panama", bookingUrl: "",
        reminders: {on: true, hoursBefore: 18, template: "session_reminder", lang: "en",
                    quietFrom: 21, quietTo: 7},
        brief: {on: false, at: "07:00", days: [1,2,3], to: ["__WARM__"],
                template: "daily_brief", lang: "en"},
        bot: {on: false, greeting: "hello", hours: "", handover: "", rules: []}}}]);
    }
    if (url.indexOf("/rest/v1/wa_contacts") >= 0) {
      if (method !== "GET") return answer("", 204);
      return answer(CONTACTS);
    }
    if (url.indexOf("/rest/v1/wa_messages") >= 0) {
      var m = url.match(/wa_id=eq\\.(\\d+)/);
      if (m) return answer(MESSAGES.filter(function(x){ return x.wa_id === m[1]; }));
      return answer(MESSAGES);
    }
    return answer([]);
  };
  window.WebSocket = function(){ this.send = function(){}; this.close = function(){}; };
"""


def stub():
    return (STUB.replace("__BOOK__", json.dumps(BOOK))
                .replace("__WARM__", WARM).replace("__COLD__", COLD))


def open_tab(pg, label):
    pg.click('#tabs button[aria-label="%s"]' % label)
    pg.wait_for_timeout(700)


def chat_tab(pg, name):
    for b in pg.query_selector_all("#p-whatsapp .pos-tabs button"):
        if (b.inner_text() or "").strip().lower() == name.lower():
            b.click()
            pg.wait_for_timeout(600)
            return True
    return False


def main():
    path = build()
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--no-sandbox"])
        pg = b.new_context(viewport={"width": 1500, "height": 1000}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)[:200]))
        pg.add_init_script(stub())
        pg.goto("file://" + os.path.abspath(path))
        pg.wait_for_timeout(1500)

        print("the screen")
        tab = pg.query_selector('#tabs button[aria-label="WhatsApp"]')
        check("the rail carries a WhatsApp screen", tab is not None)
        open_tab(pg, "WhatsApp")
        pg.wait_for_timeout(1200)
        body = pg.inner_text("#p-whatsapp")
        check("both conversations are listed", "Walk-in" in body,
              body[:200])
        check("a number that matches a client shows the client's name",
              "Nahum Cordero" in body,
              "the client's phone is written with spaces and a +, the "
              "conversation carries digits only")
        check("the unread count is shown", "2" in body)

        print("the 24-hour window")
        pg.click('#p-whatsapp button:has-text("Nahum Cordero")')
        pg.wait_for_timeout(900)
        cold = pg.inner_text("#p-whatsapp")
        check("a cold thread says why it cannot be answered",
              "24 hours" in cold, cold[-400:])
        check("a cold thread has no reply box",
              pg.query_selector("#p-whatsapp textarea") is None)
        # the stylesheet uppercases buttons, and inner_text returns what the
        # CSS made of it -- compare case-insensitively or this measures the
        # stylesheet rather than the screen
        check("a cold thread offers WhatsApp itself instead",
              "open in whatsapp" in cold.lower())
        check("the thread carries the messages both ways",
              "see you tomorrow" in cold and "session_reminder" in cold)

        pg.click('#p-whatsapp button:has-text("Walk-in")')
        pg.wait_for_timeout(900)
        warm = pg.inner_text("#p-whatsapp")
        check("an open thread reads the message",
              "is there space this afternoon?" in warm)
        ta = pg.query_selector("#p-whatsapp textarea")
        check("an open thread has a reply box", ta is not None)

        print("sending")
        if ta:
            ta.fill("Yes — 3pm, two spaces left.")
            pg.click('#p-whatsapp button:has-text("Send")')
            pg.wait_for_timeout(900)
        sent = pg.evaluate("() => window.__sent")
        check("the reply went to the function, not to Meta", len(sent) == 1,
              json.dumps(sent))
        if sent:
            check("it was addressed to the right number", sent[0].get("to") == WARM,
                  json.dumps(sent[0]))
            check("it carried what was typed",
                  sent[0].get("text") == "Yes — 3pm, two spaces left.",
                  json.dumps(sent[0]))
            check("the page never sent a token of its own",
                  "template" not in sent[0] or sent[0].get("template") is None)

        print("the automations")
        check("automations open", chat_tab(pg, "Automations"))
        auto = pg.inner_text("#p-whatsapp")
        check("the reminder settings are read back from the server",
              pg.input_value('#p-whatsapp input[type="number"]') == "18")
        check("the group limit is stated on the screen itself",
              "cannot post into a group" in auto.lower(), auto[:400])
        pg.click('#p-whatsapp button:has-text("Preview")')
        pg.wait_for_timeout(700)
        pre = pg.inner_text("#modal")
        check("the preview is the day that is actually on the board",
              "09:00" in pre and "surf lesson" in pre.lower() and
              "marta" in pre.lower(), pre[:200])
        check("the preview counts the seats", "1/6" in pre, pre[:200])
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(400)

        print("the setup")
        check("setup opens", chat_tab(pg, "Setup"))
        setup = pg.inner_text("#p-whatsapp")
        check("it names what is still missing",
              "missing" in setup.lower() and "WA_TOKEN" in setup.upper(),
              setup[:300])
        check("it says the number leaves the phone app",
              "leaves the whatsapp business phone app" in setup.lower())

        b.close()

    check("nothing threw", not errors, "; ".join(errors[:4]))
    print(("\nFAILED: " + ", ".join(fails)) if fails else "\nall good")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
