# On screen

## Stay in step with the app

`app/app_template.html` and `app/minisite_template.html` already define this
system in CSS custom properties, and `brand.css` uses the same names for the
same values on purpose. When you build a page, take the tokens from
`brand.css`; when you restyle the app, change the value in the template and
mirror it here. Two files drifting apart is how a booking page starts looking
like a different business from the flyer that sent someone to it.

The one deliberate difference: the app and booking page set type in the system
font stack, not Figtree. That is a load-time decision, not a brand one — they
are single self-contained files a guest opens on hotel wifi. Keep it. Use
Figtree on marketing pages, covers and print, where one extra request buys the
brand's voice; if a marketing page must also be self-contained, run
`fonts.py --embed` and inline it.

## Dark mode

Screens have it, paper does not. The tokens flip under
`:root[data-theme="dark"]` and under `prefers-color-scheme: dark` guarded by
`:root:not([data-theme="light"])`, exactly as the two templates do it — a
`data-theme` attribute must be able to win in both directions, or a viewer's
explicit choice gets overridden by their OS.

Two things change on dark that are easy to miss: the accent moves from
`--pink-ui #e04b78` to `--pink-500 #f46e95`, because the darker pink dies on a
dark ground; and shadows deepen rather than lighten. Never define a colour only
inside a dark block — define the light value on bare `:root` first, or a page
in an unexpected context renders with nothing.

## Components the booking page already established

Reuse these rather than inventing parallel ones:

* **Header** — pink band, white logo chip on the left, wordmark with the
  location as a small second line, actions on the right. This is the piece that
  makes a page recognisably SHOKOGI in the first half-second.
* **Product card** — a three-column grid of picture, description, price and
  button, with the name in `--pink-700` and the price in mono. It handles a
  lesson, a rental and a camp without variation.
* **Chip** — uppercase, tracked, pill-shaped, `--pink-100` on `--pink-700`, for
  categories and states.
* **Button** — uppercase, tracked `.09em`, weight 800, `--r-sm` radius. Primary
  is `--pink-700` with white; on a dark ground it can be `--pink-500` with ink.

## Landing pages and covers

A marketing page is the flyer's layout unrolled: a dark or photographic hero
with the display headline and one sentence, a band of three or four offers, a
pink call-to-action strip, a footer with the location. Keep the same bands in
the same order across pieces and the set reads as a campaign.

For a link preview, render the `og` preset (1200 × 630) from the same HTML as
the hero and reference it with `og:image`. Keep type off the outer 10 % of any
cover or banner: Facebook, YouTube and LinkedIn all crop differently, and on a
phone they crop hardest.

## Before publishing

Render the page at `og` or `ig-post` and look at it, check it at 375 px wide,
and check it once in each theme. The three faults that actually ship are a
headline that wraps badly on a phone, white type left sitting on pink, and a
dark-mode page that inherited a light-only colour and vanished.
