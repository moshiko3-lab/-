#!/usr/bin/env python3
"""The public booking site, and the pricing rule both pages share.

Two things are checked that nothing else can catch:

  * a rental whose top tier is priced by a different unit must not be quoted
    at that tier -- the imported catalogue has six of them, where 60 hours
    would otherwise come out cheaper than 3;
  * a booking made on the site must land in the same store the manager reads,
    in the shape the manager expects.
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


def low(pg, sel):
    """Lowercased text. The stylesheet uppercases headings and buttons, so a
    case-sensitive assertion measures the CSS rather than the page."""
    return (pg.inner_text(sel) or "").lower()


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def build(minisite=False):
    out = os.path.join(tempfile.mkdtemp(), "page.html")
    cmd = [sys.executable, os.path.join(HERE, "build.py"), "--out", out]
    if minisite:
        cmd.append("--minisite")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or r.stdout.strip())
        sys.exit(1)
    return out


def pricing_checks():
    """Run the shared pricing file under node, against the real catalogue."""
    cat = os.path.join(HERE, "catalog.json")
    if not os.path.exists(cat):
        print("  --   no catalog.json, pricing rule not checked against real data")
        return
    src = open(os.path.join(HERE, "pricing.js"), encoding="utf-8").read()
    harness = src + """
function money(n,d){return (Number(n)||0).toFixed(d==null?2:d);}
const cat = JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));
const out = {mixed: [], monotonic: true, worst: null};
for (const p of cat.products) {
  const units = new Set((p.prices||[]).map(x => x.unit||''));
  if (units.size > 1) {
    const odd = oddTiers(p);
    // the ladder must never quote less than a shorter hire on the same ladder
    let prev = 0, ok = true;
    const hs = ladderTiers(p).filter(x => x.hours).sort((a,b) => a.hours-b.hours);
    for (const t of hs) { if (t.price < prev - 0.001) ok = false; prev = t.price; }
    const longest = hs.length ? hs[hs.length-1] : null;
    const quoted = longest ? priceFor(p, 1, longest.hours * 4) : 0;
    out.mixed.push({name: p.name, odd: odd.length, ladder: hs.length,
                    ladderMonotonic: ok,
                    longestHours: longest ? longest.hours : 0,
                    longestPrice: longest ? longest.price : 0,
                    quotedWayPast: quoted});
  }
}
console.log(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(harness)
        path = f.name
    try:
        r = subprocess.run(["node", path, cat], capture_output=True, text=True)
    except FileNotFoundError:
        print("  --   node not available, pricing rule not checked")
        return
    finally:
        os.unlink(path)
    if r.returncode != 0:
        check("pricing harness runs", False, (r.stderr or "")[:200])
        return
    out = json.loads(r.stdout)
    check("the catalogue really does mix pricing units", len(out["mixed"]) > 0,
          "nothing to check")
    for m in out["mixed"]:
        check(f"{m['name']}: ladder never gets cheaper as it gets longer",
              m["ladderMonotonic"], json.dumps(m))
        check(f"{m['name']}: a long hire is not quoted at the odd tier",
              abs(m["quotedWayPast"] - m["longestPrice"]) < 0.005,
              f"quoted {m['quotedWayPast']}, ladder tops out at {m['longestPrice']}")


def main():
    print("shared pricing rule")
    pricing_checks()

    print("\nbooking site")
    manager = build()
    site = build(minisite=True)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME, args=["--no-sandbox"])
        # one context, so both pages share an origin and therefore a store
        ctx = b.new_context(viewport={"width": 1200, "height": 950})
        errs = []

        # seed the store by opening the manager first
        m = ctx.new_page()
        m.on("pageerror", lambda e: errs.append("manager: " + str(e)[:160]))
        m.goto("file://" + manager)
        m.wait_for_timeout(1800)
        before = m.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}').bookings.length")

        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append("site: " + str(e)[:160]))
        pg.goto("file://" + site)
        pg.wait_for_timeout(1200)

        txt = low(pg, "#wrap")
        check("the catalogue is offered", "book now" in txt)
        # their export puts num_nights=1 on plenty of day products; a camp may
        # legitimately show nights, a board hire may not
        pg.click('.filters button:has-text("Rental")')
        pg.wait_for_timeout(400)
        check("a board hire is not sold as a night stay",
              "night" not in low(pg, "#wrap"), low(pg, "#wrap")[:300])
        pg.click('.filters button:has-text("Home")')
        pg.wait_for_timeout(400)

        pg.click(".card button")
        pg.wait_for_timeout(600)
        check("the product dialog quotes a price", "$" in low(pg, ".modal"))
        pg.click('.modal button:has-text("Add to cart")')
        pg.wait_for_timeout(500)
        check("the cart counts it", pg.inner_text("#cart-n").strip() == "1",
              pg.inner_text("#cart-n"))

        pg.click("#btn-cart")
        pg.wait_for_timeout(500)
        check("the cart lists the line", "order summary" in low(pg, "#wrap"))
        # "Continue shopping" also contains "Continue"; take the exact one
        pg.get_by_role("button", name="Continue", exact=True).click()
        pg.wait_for_timeout(600)
        check("checkout asks for details", "your details" in low(pg, "#wrap"))
        check("no card is asked for", "card number" not in low(pg, "#wrap"))

        # a booking needs a name, a way to reach them, and the terms ticked
        pg.click('button:has-text("Book & pay later")')
        pg.wait_for_timeout(400)
        check("a nameless booking is refused",
              "need a name" in pg.inner_text("#toast").lower(), pg.inner_text("#toast"))
        pg.fill('#wrap input[type=text] >> nth=0', "Marta Ruiz")
        pg.click('button:has-text("Book & pay later")')
        pg.wait_for_timeout(400)
        check("a booking with no way to reply is refused",
              "email or a phone" in pg.inner_text("#toast").lower(), pg.inner_text("#toast"))
        pg.fill('#wrap input[type=email]', "marta@example.com")
        pg.click('button:has-text("Book & pay later")')
        pg.wait_for_timeout(400)
        check("the terms must be agreed",
              "terms of sale" in pg.inner_text("#toast").lower(), pg.inner_text("#toast"))
        pg.check('#wrap input[type=checkbox]')
        pg.click('button:has-text("Book & pay later")')
        pg.wait_for_timeout(800)

        done = low(pg, "#wrap")
        check("confirmation is shown", "confirmation" in done, done[:200])
        check("it gives an order number", "order number" in done, done[:300])
        check("it says who settles the payment", "settle" in done, done[:400])

        # and the manager sees it
        stored = pg.evaluate(
            "() => JSON.parse(localStorage.getItem('shokogi.manager.v1')||'{}')")
        check("the booking reached the shared store",
              len(stored.get("bookings", [])) == before + 1,
              f"{before} before, {len(stored.get('bookings', []))} after")
        bk = (stored.get("bookings") or [{}])[-1]
        check("the booking carries a client", bool(bk.get("clientId")))
        check("the booking has priced lines",
              bool(bk.get("lines")) and bk["lines"][0].get("price") is not None,
              json.dumps(bk.get("lines"))[:200])
        check("the booking is marked as coming from online", bk.get("source") == "online")
        client = [c for c in stored.get("clients", []) if c["id"] == bk.get("clientId")]
        check("the client was created with their email",
              bool(client) and client[0].get("email") == "marta@example.com",
              json.dumps(client)[:200])

        m.reload()
        m.wait_for_timeout(1800)
        m.click('#tabs button[data-id="bookings"]')
        m.wait_for_timeout(600)
        check("the manager lists it", "marta ruiz" in low(m, "#p-bookings"),
              m.inner_text("#p-bookings")[:300])

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
