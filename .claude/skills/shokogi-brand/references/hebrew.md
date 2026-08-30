# Hebrew and RTL

Hebrew pieces are not translated flyers. The eye enters at the top right, so
the layout mirrors: logo top right, headline right-aligned, cards filling right
to left. `dir="rtl"` on `<html>` does most of that for free — put it on the
document, not on a wrapper, or the bidi algorithm and the font switch apply to
only part of the page.

```html
<html lang="he" dir="rtl">
```

`brand.css` keys off `[lang="he"]` and `[dir="rtl"]`: it switches to Heebo,
drops the Latin tracking, removes the uppercase transform and opens the display
line-height. Set the attributes and then leave the typography alone.

## Typography

* **No uppercase.** Hebrew has no case. `text-transform:uppercase` does nothing
  to Hebrew and mangles any Latin caught in the same line.
* **No tracking.** Letter-spacing that flatters Figtree pulls Hebrew words
  apart; the letters are meant to sit close. Keep it at 0, `.02em` at most on a
  small label.
* **More leading.** Hebrew has no ascenders and descenders to separate lines
  optically. Display goes to `line-height:1.15`, body to 1.6 — tighter than
  Latin looks cramped in Hebrew, not tight.
* **Real weights.** Heebo ships 400 through 900; use them. A browser faking
  bold on a Hebrew face is immediately visible.
* **Weight instead of size.** Where a Latin piece shouts with tracked caps, a
  Hebrew piece shouts with Heebo 900. It is the same volume by other means.

## The name stays Latin

SHOKOGI is a wordmark, not a word. Never transliterate it, and never set it in
Heebo — it stays Figtree 900 uppercase, tracked, even mid-sentence in Hebrew.
The same goes for the badge, which contains Latin and is never mirrored or
redrawn: a flipped logo is a different logo.

## The bidi traps

These are the faults that actually appear, and they all live in mixed lines.

**A whole English block inside an RTL page** — an English product description,
an address, a testimonial — needs its own `dir="ltr"`, or its final full stop
jumps to the left of the paragraph and the block reads as broken English.

```html
<p dir="ltr">Soft-tops and performance shortboards, by the day.</p>
```

**Number runs with a space, a hyphen or a plus in them** reverse. This was
measured, not assumed: in a Hebrew line, `$45` on its own comes out right
wherever it sits, and so does `$45 / לאדם`. But `$45-$90` renders as `$90-$45`,
and `+507 6000 0000` renders as `0000 6000 507+`. The rule that covers both
without having to think about it: a Latin run of more than one part gets its
own direction.

```html
<div class="price figure" dir="ltr">$45</div>          <!-- safe either way -->
<span dir="ltr">$45-$90</span>                          <!-- reverses without this -->
<span dir="ltr">+507 6000 0000</span>                   <!-- reverses without this -->
```

A price range and a phone number on a flyer are exactly the two places this
bites, and a reversed price is the kind of mistake that gets printed a thousand
times before anyone notices.

**A URL at the end of a Hebrew sentence** wants `dir="ltr"` too, or the trailing
slash or dot detaches and lands at the wrong end.

**What is not a bug:** in Hebrew a sentence ends on the left, so its final
period sits at the far left of the last line, visually before the last word.
That is correct. Do not "fix" it by moving punctuation or adding marks — you
will only break the copy for a Hebrew reader.

## Layout notes

Mirror the structure, not the meaning. Columns, cards, nav and icon-plus-label
pairs all flip; a photograph does not, a chart's time axis does not, and the
logo does not. Padding written as `inset` or with logical properties
(`padding-inline-start`) flips by itself; `left`/`right` values do not, which is
why the templates use `inset` where they can.

Numbers still run left to right inside a right-to-left line, so a price table
stays left-aligned in its column even when its label is right-aligned. Set
figures in IBM Plex Mono with tabular numerals and they line up regardless of
the surrounding direction.

## Before sending a Hebrew piece

Render it and read it as a Hebrew reader would — right to left, top right
first. Check every line that mixes an English word or a number, check that the
headline broke where a Hebrew speaker would break it rather than mid-phrase,
and check the Heebo actually loaded: if it fell back, the text is set in
DejaVu's Hebrew, which is thin, wide and unmistakably not this brand.
