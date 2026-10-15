"""Turn relief/index.html into the body of a Shopify page on shokogi.com.

The standalone page is the source. This reshapes it for life inside the
store's theme: every CSS rule is scoped under #rv so it neither leaks into
the theme nor loses to it, the page's own top bar goes (the site has one),
the language buttons move into the hero, images point at the store's CDN,
language direction is set on the page's root rather than on <html> (which
would flip the whole site), and the buttons go to Shopify checkout.

    python3 relief/shopify/build_page.py > /tmp/page.html        # whole page
    python3 relief/shopify/build_page.py --js > rebuild-venao.js # for the CDN
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "index.html")
STORE = json.load(open(os.path.join(HERE, "store.json")))

def scope_selector(sel):
    sel = sel.strip()
    if not sel:
        return sel
    if sel in ("html", "body", ":root") or sel.startswith(":root"):
        return "#rv" + sel[len(":root"):] if sel.startswith(":root") else "#rv"
    if sel == "*":
        return "#rv *"
    if sel.startswith("[dir="):
        return "#rv" + sel
    return "#rv " + sel

def scope_css(css):
    out, i = [], 0
    while i < len(css):
        j = css.find("{", i)
        if j < 0:
            out.append(css[i:]); break
        head = css[i:j]
        # find the matching brace
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0); k += 1
        inner = css[j + 1:k - 1]
        h = head.strip()
        if h.startswith("@media") or h.startswith("@supports"):
            out.append(head + "{" + scope_css(inner) + "}")
        elif h.startswith("@"):
            out.append(head + "{" + inner + "}")
        else:
            # keep comments that precede the selector
            m = re.match(r"(\s*(?:/\*.*?\*/\s*)*)(.*)", head, re.S)
            sels = [scope_selector(s) for s in m.group(2).split(",")]
            sels = [s for s in sels if s]
            if m.group(2).strip() == "html":
                out.append(m.group(1)); i = k; continue
            out.append(m.group(1) + ",".join(sels) + "{" + inner + "}")
        i = k
    return "".join(out)

html = open(SRC, encoding="utf-8").read()
css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
body = re.search(r"<body>(.*)</body>", html, re.S).group(1)

# the site has its own header: drop ours, keep the language buttons in the hero
langs = re.search(r'<div class="langs".*?</div>', body, re.S).group(0)
body = re.sub(r'<header class="top">.*?</header>\s*', "", body, flags=re.S)
HERO = '<div class="hero" id="hero">\n'
assert body.count(HERO) == 1, "hero markup changed"
body = body.replace(HERO, HERO + '  ' + langs.replace('class="langs"', 'class="langs rv-langs"') + '\n', 1)

for name, url in STORE["images"].items():
    body = body.replace('"img/%s"' % name, '"%s"' % url)

js_swaps = [
    ('document.documentElement.lang = lang;', 'ROOT.lang = lang;'),
    ('document.documentElement.dir = lang === "he" ? "rtl" : "ltr";', 'ROOT.dir = lang === "he" ? "rtl" : "ltr";'),
    ('document.querySelectorAll("[data-i18n]")', 'ROOT.querySelectorAll("[data-i18n]")'),
    ('  checkout: null,', '  checkout: ' + json.dumps(STORE["checkout"]) + ','),
    ('var lang = "en";', 'var lang = "en";\nvar ROOT = document.getElementById("rv");\n'
                         '(function(){ var t = document.querySelector(".main-page-title");'
                         ' var h = t && t.closest(".page-header"); if (h) h.style.display = "none"; })();'),
]
for a, b in js_swaps:
    assert body.count(a) == 1, a
    body = body.replace(a, b)
assert "img/" not in body.replace("cdn.shopify.com", ""), "an image is not on the store's CDN"

extra = """
/* inside the store's page template */
.page-header:has(+ .rte #rv),.section-header:has(+ .rte #rv){display:none}
.rte:has(> #rv){max-width:none;margin:0;padding:0}
/* the store's plain page template wraps content in a narrow theme grid column; let the page use the full width */
.page-width:has(#rv){max-width:none!important;padding-inline:0!important;margin-inline:0!important}
.page-width:has(#rv) .grid:has(#rv){display:block!important;margin:0!important;padding:0!important}
.page-width:has(#rv) .grid__item:has(#rv){width:100%!important;max-width:none!important;padding:0!important;margin:0!important;left:auto!important;right:auto!important;float:none!important}
#rv{font:17px/1.6 var(--f-body);color:var(--text);background:var(--bg);text-align:start}
#rv .hero,#rv .band,#rv footer{width:100vw;margin-left:calc(50% - 50vw);margin-right:calc(50% - 50vw)}
#rv .hero{margin-top:0}
#rv .rv-langs{position:absolute;top:16px;inset-inline-end:20px;z-index:2}
#rv footer{background:var(--sand);color:var(--text-2)}
#rv footer h4,#rv footer a{color:var(--text)}
#rv p,#rv ul,#rv ol,#rv h1,#rv h2,#rv h3{margin-top:0}
#rv ul{list-style:none;padding-left:0}
#rv img{max-width:100%;height:auto}
"""
page = '<style>' + scope_css(css) + extra + '</style>\n' + body.strip()

if "--js" not in sys.argv:
    sys.stdout.write('<div id="rv" class="rv">\n' + page + '\n</div>\n')
    sys.exit()

# --js: one file for the store's CDN. The page body on Shopify is then only
#   <div id="rv" class="rv"></div><script src="...rebuild-venao.js"></script>
# The markup goes in first, then the page's own script runs inside a closure
# so none of its names (t, pay, CONFIG...) can collide with the theme's.
markup, code = re.match(r"(.*)<script>(.*)</script>\s*$", page, re.S).groups()
sys.stdout.write("(function(){\n"
                 "var rv = document.getElementById('rv');\n"
                 "if (!rv) return;\n"
                 # Lift the page out of whatever narrow column the page template wraps it in,
                 # and hide that template's own title, so the theme's layout CSS can't squeeze it.
                 "var main = document.getElementById('MainContent'), box = main && rv.parentNode;\n"
                 "while (box && box.parentNode !== main) box = box.parentNode;\n"
                 "if (box && box !== rv) { main.insertBefore(rv, box); box.style.display = 'none'; }\n"
                 "rv.innerHTML = " + json.dumps(markup) + ";\n"
                 + code + "\n})();\n")
