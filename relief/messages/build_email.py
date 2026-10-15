"""Write the Keep Venao Surfing email in English, Spanish and Hebrew.

    python3 relief/messages/build_email.py   # writes email-en.html, email-es.html, email-he.html

Table layout with inline styles, so it renders the same in Gmail, Apple Mail
and Outlook. Paste the HTML into Shopify Email (Custom HTML) or any mail tool.
"""
import html, os

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = "https://www.shokogi.com/pages/keep-venao-surfing"
CDN = "https://cdn.shopify.com/s/files/1/0116/5364/4354/files/"
IMG_HERO = CDN + "rebuild-venao-surf.webp?v=1792043775&format=pjpg&width=1200"
IMG_LYCRA = CDN + "lycra-pink-onmodel.jpg?v=1792045678&width=600&height=405&crop=top"
IMG_FOIL = CDN + "rebuild-venao-foil.webp?v=1792043775&format=pjpg&width=400&height=270&crop=center"

C = {
"en": dict(
  subject="Keep Venao Surfing 🌊",
  pre="The earthquake hit Venao. Here is how you can help us through this season, and surf it later.",
  eyebrow="After the 7.7 earthquake · 9 October 2026",
  title="Venao is still here.",
  p1="On 9 October a 7.7 earthquake hit Panama's Azuero coast, a few kilometres from our beach. It hit all of Venao, us included. The good news: the waves are as good as ever, and Venao is recovering.",
  open="We hope and expect to soft-open in early November, with the full opening in early to mid December.",
  p2="Until then, you can help Shokogi through this season, and surf it when you come. Everything is on one page:",
  items=[("Surf lesson · valid 24 months", "$60"), ("3-lesson course · valid 24 months", "$180"), ("Support & treat a local kid: 5 surf sessions · valid 24 months", "$150"),
         ("Foil session, 3 hours, jet-ski tow-in · valid 24 months", "$450"), ("The Shokogi lycra · kids", "$45 · $40")],
  note="Lessons and sessions are valid for 24 months from purchase, and you can give them as a gift. Lycras are shipped or collected at the school.",
  cta="See how you can help",
  share="Can't buy right now? Forwarding this email or sharing the page helps too.",
  sign="See you in the water,", team="Shokogi Surf School · Playa Venao, since 2009", lang="en", dir="ltr"),
"es": dict(
  subject="Keep Venao Surfing 🌊",
  pre="El terremoto golpeó a Venao. Así puedes ayudarnos a pasar esta temporada y surfear después.",
  eyebrow="Tras el terremoto de 7.7 · 9 de octubre de 2026",
  title="Venao sigue aquí.",
  p1="El 9 de octubre un terremoto de 7.7 sacudió la costa de Azuero, a pocos kilómetros de nuestra playa. Golpeó a todo Venao, también a nosotros. La buena noticia: las olas siguen tan buenas como siempre y Venao se está recuperando.",
  open="Esperamos una apertura suave a principios de noviembre y la apertura completa entre principios y mediados de diciembre.",
  p2="Mientras tanto, puedes ayudar a Shokogi a pasar esta temporada y surfear cuando vengas. Todo está en una página:",
  items=[("Clase de surf", "$60"), ("Curso de 3 clases", "$180"), ("Apoya y consiente a un niño local: 5 sesiones de surf", "$150"),
         ("Sesión de foil, 3 horas, con remolque de moto de agua", "$450"), ("La licra Shokogi · niños", "$45 · $40")],
  note="Las clases y sesiones son válidas por 24 meses desde la compra y puedes regalarlas.",
  cta="Mira cómo ayudar",
  share="¿No puedes comprar ahora? Reenviar este correo o compartir la página también ayuda.",
  sign="Nos vemos en el agua,", team="Shokogi Surf School · Playa Venao, desde 2009", lang="es", dir="ltr"),
"he": dict(
  subject="Keep Venao Surfing 🌊",
  pre="רעידת האדמה פגעה בוונאו. ככה אפשר לעזור לנו לעבור את התקופה, ולגלוש אחר כך.",
  eyebrow="אחרי רעידת האדמה בעוצמה 7.7 · 9 באוקטובר 2026",
  title="ונאו עדיין כאן.",
  p1="ב-9 באוקטובר רעידת אדמה בעוצמה 7.7 פגעה בחוף אסוארו בפנמה, כמה קילומטרים מהחוף שלנו. היא פגעה בכל ונאו, גם בנו. החדשות הטובות: הגלים טובים כמו תמיד, וונאו מתאוששת.",
  open="אנחנו מקווים ומצפים לפתיחה רכה בתחילת נובמבר, ולפתיחה מלאה בתחילת עד אמצע דצמבר.",
  p2="עד אז, אפשר לעזור לשוקוגי לעבור את התקופה הזאת, ולגלוש מתי שתגיעו. הכל בדף אחד:",
  items=[("שיעור גלישה", "$60"), ("קורס של 3 שיעורים", "$180"), ("לתמוך ולפנק ילד מקומי: 5 מפגשי גלישה", "$150"),
         ("סשן פויל של 3 שעות בגרירת אופנוע ים", "$450"), ("הלייקרה של שוקוגי · ילדים", "$45 · $40")],
  note="השיעורים והסשנים בתוקף 24 חודשים מיום הרכישה, ואפשר לתת אותם במתנה.",
  cta="איך אפשר לעזור",
  share="לא מתאים לקנות עכשיו? גם העברה של המייל הזה או שיתוף של הדף עוזרים.",
  sign="נתראה במים,", team="בית הספר לגלישה שוקוגי · פלאיה ונאו, מאז 2009", lang="he", dir="rtl"),
}

def e(s): return html.escape(s, quote=True)

def build(c):
    link = PAGE + ("" if c["lang"] == "en" else "?lang=" + c["lang"])
    al = "right" if c["dir"] == "rtl" else "left"
    font = "Helvetica,Arial,sans-serif"
    head = "'Barlow Condensed','Arial Narrow',Helvetica,Arial,sans-serif"
    rows = "" and "".join(
        f'<tr><td style="padding:12px 0;border-top:1px solid #eae5df;font:16px/1.4 {font};color:#1a1719;text-align:{al}">{e(n)}</td>'
        f'<td style="padding:12px 0;border-top:1px solid #eae5df;font:600 18px/1.4 {head};color:#b24d6a;white-space:nowrap;text-align:{"left" if al=="right" else "right"}" dir="ltr">{e(p)}</td></tr>'
        for n, p in c["items"])
    btn = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"><tr>'
           f'<td bgcolor="#f46e95" style="border-radius:3px"><a class="cta" href="{link}" target="_blank" '
           f'style="display:inline-block;padding:16px 22px;font:600 17px/1 {head};letter-spacing:1px;white-space:nowrap;text-transform:uppercase;color:#1e1419;text-decoration:none">{e(c["cta"])}</a></td></tr></table>')
    return f'''<!doctype html>
<html lang="{c["lang"]}" dir="{c["dir"]}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>{e(c["subject"])}</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&display=swap" rel="stylesheet">
<style>@media (max-width:620px){{.px{{padding-left:22px!important;padding-right:22px!important}} .h1{{font-size:40px!important}}}} @media (max-width:360px){{.cta{{font-size:15px!important;padding:14px 14px!important}}}}</style>
</head>
<body style="margin:0;padding:0;background:#f3f0eb">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(c["pre"])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f3f0eb"><tr><td align="center" style="padding:24px 10px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff" dir="{c["dir"]}">
  <tr><td align="center" style="padding:22px 0;font:600 22px/1 {head};letter-spacing:7px;color:#1a1719" dir="ltr">SHOK<span style="color:#f46e95">O</span>GI</td></tr>
  <tr><td><a href="{link}" target="_blank"><img src="{IMG_HERO}" width="600" alt="Shokogi, Playa Venao" style="display:block;width:100%;height:auto;border:0"></a></td></tr>
  <tr><td class="px" style="padding:34px 44px 8px;text-align:{al}">
    <div style="font:600 14px/1.3 {head};letter-spacing:{"0" if c["dir"]=="rtl" else "2px"};text-transform:uppercase;color:#b24d6a">{e(c["eyebrow"])}</div>
    <div class="h1" style="font:600 48px/1.02 {head};text-transform:uppercase;color:#1a1719;margin:10px 0 18px">{e(c["title"])}</div>
    <p style="font:17px/1.6 {font};color:#5a5254;margin:0 0 18px">{e(c["p1"])}</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="background:#fdeaf0;border-{"right" if c["dir"]=="rtl" else "left"}:3px solid #f46e95;padding:14px 16px;font:700 16px/1.5 {font};color:#1a1719;text-align:{al}">{e(c["open"])}</td>
    </tr></table>
    <p style="font:17px/1.6 {font};color:#5a5254;margin:22px 0 6px">{e(c["p2"])}</p>
  </td></tr>
  <tr><td class="px" style="padding:0 44px">
    <div style="height:14px;line-height:14px">&nbsp;</div>
    {btn}
  </td></tr>
  <tr><td class="px" style="padding:22px 44px 36px;text-align:{al}">
    <p style="font:16px/1.6 {font};color:#5a5254;margin:0 0 18px">{e(c["share"])}</p>
    <p style="font:17px/1.6 {font};color:#1a1719;margin:0">{e(c["sign"])}<br><b>{e(c["team"])}</b></p>
  </td></tr>
  <tr><td align="center" style="background:#1a1719;padding:20px;font:13px/1.6 {font};color:#d9e8ec" dir="ltr">
    <a href="https://www.shokogi.com" style="color:#ffffff;text-decoration:none">shokogi.com</a> ·
    <a href="https://instagram.com/shokogi_venao" style="color:#ffffff;text-decoration:none">@shokogi_venao</a> ·
    <a href="https://wa.me/50762596666" style="color:#ffffff;text-decoration:none">WhatsApp</a> ·
    <a href="mailto:shokogipanama@gmail.com" style="color:#ffffff;text-decoration:none">shokogipanama@gmail.com</a>
  </td></tr>
</table>
</td></tr></table>
</body>
</html>
'''

for k, c in C.items():
    open(os.path.join(HERE, "email-%s.html" % k), "w", encoding="utf-8").write(build(c))
print("ok")
