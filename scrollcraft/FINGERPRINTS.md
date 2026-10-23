# Fingerprints

Every site you build with **scroll-craft** gets one row here, appended after it
ships. The registry exists so your next build can prove it is a different page
rather than a re-skin of one you already made.

This file is **yours**. It starts empty on purpose: the gate is about not
repeating *yourself*, so it has nothing to say until you have built something.

The rules and the gate live in the skill's
`references/uniqueness.md`. Short version:

**A new build must differ from EVERY row below on at least 4 of the 6
dimensions.** Four against each row individually, not four on average across the
table. If a planned build fails, change the plan. Never edit a row to make room
for it.

The six dimensions are: **grammar**, **nav treatment**, **hero device**,
**act-sequence shape**, **close pattern**, **signature move**.

Dimension 6 is free, because a signature move is unique by definition. So the
gate really asks for three more out of the remaining five, and a build that
changes only grammar and world will fail it.

---

## The registry

| Build | Grammar | Nav treatment | Hero device | Act-sequence shape | Close pattern | Signature move | World | Port |
|---|---|---|---|---|---|---|---|---|

*(empty: your first build has nothing to clear, so build whatever the interview
points at. From the second onwards, this table is the constraint.)*

---

## What is taken

Add a bullet here whenever a build claims something a later build should avoid
reusing: a grammar, a nav treatment, a close pattern, a signature move, an
act-count-and-length band. The shared columns are what the next build inherits
as a constraint, so writing them down is the whole point.

Nothing is taken yet.

---

## Appending a row

After shipping, add one line to the table and one bullet to **What is taken** if
the build claimed something new. Fill every column. Say what the build shares
with existing rows.

Rows are append-only. A build that has been superseded stays in the table,
because the space it occupies is still occupied.

---

## Worked example

The skill's author kept a registry of twelve builds across eight page grammars.
If you want to see what a filled-in table looks like, and which shapes tend to
collide, read `EXAMPLES.md` in the scroll-craft repository. Treat it as
illustration only: those rows are somebody else's builds and they do **not**
constrain yours.
| shokogi-day | Chaptered scenes under one continuous sky | Persistent slim bar: brand + single "Book Now", top scrim | Pinned layered hero, parallax foreground over a fixed sky/sea/horizon, greet headline | pin → flow → pan → pin → reveal → resolve; quiet reveal set before a short held close | Full-height resolve that holds as the last screen with a pointer spotlight (not pinned) | The page IS a day: global scroll drives a dawn→sunset sky and a sun that travels its own arc as the only progress indicator | CSS/SVG illustrated sky-sea-sun-headland (demo); real hero video + photos on the live port | Shopify section (planned) |
| shokogi-scrollcraft | Premium-minimal light editorial, distinct scenes (no single sky), white + pink + a touch of black | Fixed bar: brand + single "Book Now"; a small pink wash sweeps the logo | Pinned dimensional hero: pale CSS dawn-water planes + a foam tide line, kinetic greet headline, pointer drift | pin → flow(reveal) → pan → flow(quiet) → pin(PEAK) → pin(close) | Near-black pinned room, pointer-reactive pink glow + magnet CTA, footer inside the stage | The tide: a water sheet that follows the cursor on the hero and, at the peak, washes up the frame to lift "Glide above the waves" out of the water | CSS/SVG world in brand palette (no gen key, CDN blocked) | Standalone page (engine too large to upload to Shopify) |
