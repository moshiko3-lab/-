"""Build the page body on shokogi.com, with the anonymous wall of supporters.

Input is the JSON of an Admin API orders query (a list of order nodes, or
{"data":{"orders":{"nodes":[...]}}}) with, per order: createdAt, test,
cancelledAt, displayFinancialStatus, billingAddress{countryCodeV2},
shippingAddress{countryCodeV2}, lineItems{nodes{quantity product{id}}}.
Only the order date, the country and what was bought go on the wall:
no names, emails, cities or order numbers.

    python3 relief/shopify/supporters.py orders.json JS_URL > body.html
"""
import datetime, html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS = json.load(open(os.path.join(HERE, "store.json")))["products"]
PAID = {"PAID", "AUTHORIZED", "PARTIALLY_PAID", "PARTIALLY_REFUNDED"}

def entries(orders):
    out = []
    for o in orders:
        if o.get("test") or o.get("cancelledAt") or o.get("displayFinancialStatus") not in PAID:
            continue
        cc = ((o.get("billingAddress") or o.get("shippingAddress") or {}).get("countryCodeV2") or "")
        items = []
        for li in o["lineItems"]["nodes"]:
            item = PRODUCTS.get(((li.get("product") or {}).get("id") or "").rsplit("/", 1)[-1])
            if item:
                items.append({"i": item, "q": li.get("quantity") or 1})
        if items:
            out.append({"d": o["createdAt"][:10], "c": cc, "items": items})
    return sorted(out, key=lambda e: e["d"], reverse=True)

def body(orders, js_url):
    data = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "list": entries(orders)}
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    return ('<div id="rv" class="rv"></div>'
            '<script type="application/json" id="rv-supporters">' + blob + '</script>'
            '<script src="' + html.escape(js_url) + '"></script>')

if __name__ == "__main__":
    raw = json.load(open(sys.argv[1]))
    if isinstance(raw, dict):
        raw = raw["data"]["orders"]["nodes"]
    sys.stdout.write(body(raw, sys.argv[2]))
