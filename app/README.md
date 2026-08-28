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
| Schedule | Day-by-day sessions, instructor, spot, capacity, participants |
| Bookings | Items, prices, payments, outstanding balance per booking |
| Clients | Contact details, booking count, lifetime spend |
| Catalog | Lessons, courses, rentals, photography, with prices |
| Crew | Instructors and assistants, role, session count |
| Day closing | Takings by payment method and by activity |
| Back office | Business details, spots, activity types, payment methods, roles, custom fields |

Sessions can be pinned to the tide rather than the clock — "2h before high
tide" — which is why a spot carries coordinates.

The day closing splits a payment across activities in proportion to what the
booking's items cost, the same rule Bloowatch's own report uses.

## Scope

`spec/BLOOWATCH.md` is the checklist: all 97 routes walked in a signed-in browser
plus 1,575 interface strings from the app bundle. Most of it is not built yet.
The table above is what works today.
