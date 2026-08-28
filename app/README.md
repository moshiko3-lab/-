# Shokogi Manager

A management system for the surf school that starts completely empty. Nothing is
imported from anywhere; every client, product, session and booking is one you
entered.

## Running it

`index.html` is the whole application — open it, or drop it on any static host.
There is no server, no build step and no account.

    python3 build.py --out index.html

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
| Planning | The day's table: hour, activity calendar, instructors, title, note, duration, participants, with counts for sessions, rental, accommodation and bookings. Filter by activity, instructor, level or how full a session is; choose which columns show |
| Board | Sessions as blocks on an hourly timeline, grouped by activity or by instructor; drag one to another row or another hour. A side rail lists everyone booked that day who is not yet in a session — drag a name onto a block to seat them. Tide times sit above the grid |
| Trips | A boat or van going out: departure, skipper, seats, and a manifest that flags who has no waiver on file |
| Bookings | Products chosen from the catalogue rather than a dropdown, priced by tier, with discounts that keep the original price visible. Named participants with age, level and wetsuit size. Payments, deposits, balance, cancellation and refunds; search and filter by status or date |
| Clients | Contact details, booking count, lifetime spend, documents and when they expire |
| Catalog | Every product setting Bloowatch has, across four tabs: information, price, calendar, online sale. Eight product types, tiered pricing, deposits, tax, stock, weekdays and start hours, availability window, meeting spot. Search, filter and archive |
| Gear | Each board and suit by name, with service dates, what is out and until when |
| Crew | Instructors and assistants, role, session count, time off |
| Day closing | Takings by payment method and by activity, plus the cash drawer: float in, suppliers out, what should be in the till |
| Invoices | A frozen copy of a booking, numbered and printable |
| Reports | Monthly and yearly takings, by method, activity, product and day |
| Back office | Business details, spots, activity types, payment methods, roles, custom fields, instructor fee groups, promo codes, partners, accommodation |

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

Sessions can be pinned to the tide rather than the clock — "2h before high
tide" — which is why a spot carries coordinates. Tide times are entered per
day; a day without them says so rather than drawing a curve that would be
invented. A session can carry several instructors, as they do in practice.

The day closing splits a payment across activities in proportion to what the
booking's items cost, the same rule Bloowatch's own report uses.

## Scope

Two files hold the target. `spec/BLOOWATCH.md` is what a crawl of all 97 routes
could see rendered. `spec/TRANSLATIONS.md` is far more complete: all 2,544
labels, fields, options and messages, taken from the locale compiled into
Bloowatch's own bundle — including everything that only appears behind a
button, which no crawl was ever going to reach.

Most of it is still not built. The table above is what works today.
