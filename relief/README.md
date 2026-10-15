# Rebuild Venao

The landing page for the earthquake of 9 October 2026: give to the rebuild and
get a surf lesson back. One static file, in English, Spanish and Hebrew
(`?lang=es`, `?lang=he`), published at `/relief/` next to the manager.

Everything the school fills in sits in `CONFIG` at the bottom of `index.html`:

* `payLinks` -- a payment link per reward (Stripe Payment Link, PayPal...).
  Empty, the button opens WhatsApp / email / Instagram with a ready message.
* `whatsapp` -- the number, digits only with the country code.
* `recipient` -- who receives the money, as donors should read it. If a
  registered foundation runs the campaign, its legal name goes here.
* `goal` / `raised` -- `raised: null` hides the bar. Only put real figures.
* `heroImage` -- a photo file placed next to `index.html`; empty keeps the gradient.
* `instagramPosts` -- the school's own posts shown in the gallery.
* `lycra` -- the Shokogi lycra: price (`null` hides it), sizes, colours with
  their front and back photos in `img/`, and
  whether it is collected at the school or shipped. `lycra.kids` adds a
  kids' version (own price, sizes and pictures) behind an Adults / Kids choice.
* `quakePhotos` -- the team's own photos from after the earthquake, with a
  caption per language. Empty hides the section.
* `preview` -- draws placeholders where those go; keep it `false` live.

Rewards are the regular catalogue prices: lesson $60, 3 lessons $180,
5 lessons $300, five Young Guns sessions $100. The $300 tier promises a video
analysis on top, which is the school's to confirm.

The facts on the page are sourced in its footer (USGS via AP, La Prensa,
mapadelterremoto.com) as of 15 October 2026.
