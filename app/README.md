# Shokogi Manager

A management system for the surf school that starts completely empty. Nothing is
imported from anywhere; every client, product, session and booking is one you
entered.

## Running it

`index.html` is the whole application — open it, or drop it on any static host.
There is no server, no build step and no account.

    python3 build.py --out index.html
    python3 build.py --minisite --out booking.html

The second page is the public booking site. Put both on the **same domain**:
they share one browser store, which is how an online booking reaches the
manager. Served from two different domains they are two different stores, and
the booking site would be taking orders nobody ever sees.

Three test suites drive the built pages in a real browser:

    python3 test_pos.py       # register, tickets, integrity, archive
    python3 test_agenda.py    # the planning's four views and the fortnight
    python3 test_booking.py   # the shared pricing rule, and the booking site

## Where the data lives

In the browser, under `localStorage`. That has two consequences worth being
plain about: the data does not follow you to another device or another person,
and clearing site data erases it. The Backup button in the header exports and
restores the whole database as text, and is the only safety net until this sits
on a server.

Swapping to a server means rewriting `load()` and `save()` and nothing else —
the rest of the app never touches storage directly.

## What is in it

| Screen | Covers |
| --- | --- |
| Today | Takings so far, sessions on the water, outstanding balances |
| Planning | The day's table at four densities — compact, simple, details, accommodation — split at one o'clock into morning and afternoon, for one day or a fortnight. Hour, activity calendar, instructors, title, note, duration, participants, with counts for sessions, rental, accommodation and bookings. Filter by activity, instructor, level or how full a session is; choose which columns show |
| Board | Sessions as blocks on an hourly timeline, in lanes so overlapping ones never hide each other. Drag a block to another lane or hour, or drag a name from the side rail onto a block to seat them. The tide is drawn as a curve across the hours |
| Crew pay | What each instructor is owed for a period, worked out from the sessions taught and their fee group, with a breakdown per session. Partner commissions on the same period: what each hotel or agency earned on what they sent |
| Trips | A boat or van going out: departure, skipper, seats, and a manifest that flags who has no waiver on file |
| Bookings | Sessions assigned from the booking, so a three-lesson course is three seats and the list says how many are still owed. Products chosen from the catalogue rather than a dropdown, priced by tier, with discounts that keep the original price visible. Named participants with age, level and wetsuit size. Payments, deposits, balance, cancellation and refunds; search and filter by status or date |
| Clients | Contact details, booking count, lifetime spend, documents and when they expire |
| WhatsApp | The school's own number: every message in and out in one thread per person, with the reply box closed when WhatsApp would refuse a free-form message. Reminders before a session, a brief on the day's board each morning to whoever is working, and a bot that answers what it recognises and hands over what it does not. Nothing is on until it is switched on; the setup is in `supabase/WHATSAPP.md` |
| Catalog | Every product setting Bloowatch has, across four tabs: information, price, calendar, online sale. Eight product types, tiered pricing, deposits, tax, stock, weekdays and start hours, availability window, meeting spot. Search, filter and archive |
| Gear | Each board and suit by name, with service dates, what is out and until when |
| Crew | Instructors and assistants, role, session count, time off |
| Day closing | The register: opened with a float, closed against a count, with the difference recorded. Takings by payment method and by activity. Cash movements typed the way their POS does — pay-in, pay-out, cash to bank, bank to cash — and refused entirely on a day the register was never opened. The day's tickets, with duplicate and integrity checks |
| Invoices | A frozen copy of a booking, numbered and printable |
| Reports | Monthly and yearly takings, by method, activity, product and day |
| Booking site | A separate public page: catalogue by type, tier prices, cart, participant names, confirmation. Books and leaves settling to the school — no card is taken |
| Back office | Business details, spots, activity types, payment methods, roles, custom fields, instructor fee groups, promo codes, partners, commission groups, calendar feeds, accommodation, and the fiscal archive |

Everything except clients comes across from Bloowatch and loads by itself the
first time the app is opened: 35 products with prices and session counts, 21
crew, 12 activity calendars with their colours, 267 individually named boards
and suits across 8 gear types, both spots, and the schedule from a week back to
a month ahead.

Three things stay behind on purpose. Clients, bookings and payment history,
which is what "start from zero" meant. Session participants, because they point
at those clients. And crew phone numbers and email addresses, because the built
page inlines this data and can be shared by URL.

A wipe in the back office clears the records and does not invite the catalog
back in. It is
offered, never forced: the app still starts empty, the import skips anything
already there by name, and no clients, bookings or history come across.

Assigning an instructor who is booked off that day says so in the form.

A seat in a session holds either a saved client or somebody named on a booking
who was never a client — the seating dialog, the board's rail, the trip
manifests and the day's client list all resolve both, and say which a person
came from.

The board's client list is a list of people, not of bookings: one card per
client, with everything they bought inside it under its own product heading and
the day it was bought beside it, so two of the same product do not read as one
purchase. A booking with nobody on it keeps a card of its own. Where a card
carries several bookings the ⋮ names each one rather than offering a "delete
booking" that could mean any of them, and offers to merge the ones sharing a
day.

A slot only goes in a session of its own activity. A product names the activity
calendar it runs under, so a foil tow cannot be dropped on a surf lesson: while
a slot is in the air the board dashes every session that would refuse it, the
drop is turned away with a line saying which activity each side is, the
participants list refuses the tick, and neither session picker — the till's nor
the booking form's — offers a session of the wrong activity in the first place.
A product with no calendar set is not being fussy and goes anywhere.

Sessions can be pinned to the tide rather than the clock — "2h before high
tide" — which is why a spot carries coordinates. Tide times are entered per
day; a day without them says so rather than drawing a curve that would be
invented. A session can carry several instructors, as they do in practice.

The day closing splits a payment across activities in proportion to what the
booking's items cost, the same rule Bloowatch's own report uses.

Every payment and refund leaves a numbered ticket, and the tickets are chained
by fingerprint: edit or remove one afterwards and the integrity check names it.
Editing a payment voids its ticket and issues a new one rather than rewriting
the old one. This is tamper-evident bookkeeping and nothing more — **if your tax
authority requires certified fiscal software, this is not that**, and the screen
says so.

A product's price comes from a tier matrix, not a number, and `price_unit`
decides what a tier means. Nine of the imported products mix units: six rentals
carry a `from_pickup` tier on top of a `by_closing_time` ladder — 60h at $10
where 30h is $285. Only tiers sharing the ladder's unit are compared, so a long
hire is never quoted at the odd one; the rest are left for the school to price
deliberately, and the product form shows the unit rather than hiding it.

## Scope

Two files hold the target. `spec/BLOOWATCH.md` is what a crawl of all 97 routes
could see rendered. `spec/TRANSLATIONS.md` is far more complete: all 2,544
labels, fields, options and messages, taken from the locale compiled into
Bloowatch's own bundle — including everything that only appears behind a
button, which no crawl was ever going to reach.

Most of it is still not built. The table above is what works today. Still
missing, in rough order of how much of their locale each accounts for:
iCalendar feeds answer nothing until this sits on a server (the URLs are
generated, the feed is not served), the fiscal archive exports and verifies but
is not a certified format, and there is no e-commerce settings screen, no email
or SMS sending, and no POS receipt printing. WhatsApp is the one message
channel that is built, and it needs the Edge Function deployed before it does
anything.
