# Bloowatch daily closings

Pulls SHOKOGI's day closing straight from Bloowatch instead of relying on a
file downloaded by hand into Google Drive.

## Why this exists

The old flow depended on someone exporting `payments-*.csv` from Bloowatch into
a Drive folder. That export is a snapshot of the moment it is taken, so a file
pulled at midday silently misses every payment that comes in afterwards. On
2026-08-28 the hand-exported file showed **160** while the day actually closed
at **1800**.

This reads Bloowatch's own report endpoint, the same one behind the dashboard's
"export report" button, so the figures are the company's own and are always the
complete day.

## Usage

```
BLOOWATCH_URL=https://shokogi.bloowatch.com \
BLOOWATCH_EMAIL=... BLOOWATCH_PASSWORD=... \
python3 daily_report.py 2026-08-27 2026-08-28
python3 daily_report.py --json 2026-08-28
```

Credentials are read from the environment only. They are never written to disk,
never logged, and must not be committed. Set them as environment variables on
the Claude Code environment so they survive a container restart.

## Output columns

`Date, Day, Transactions, Total, Credit, Cash, Web, OtherPay, Packages, Lessons,
Rentals, Photography, Other, Refunds, Check, Notes`

`Check` is `OK` only when the payment methods add up to the total, the
categories add up to the total, each method's own breakdown adds back up to that
method, *and* every method's takings are a whole number of dollars. Otherwise it
is `CHECK!` and `Notes` says what disagreed. A category Bloowatch reports that
has no column of its own (for example `VIDEO ANALYSIS`) is added into `Other`
and named in `Notes`, so nothing is ever dropped silently.

## The cash-up

```
python3 daily_report.py --cash-up 2026-08-29
```

```
2026-08-29
  web                  15
  credit lesson       513
  cash lesson          25
  total               553
```

Three figures, written the way the office writes them by hand at the end of the
day. They are the day's payments added up by how they were paid, which is what
the report's `Methods` block already states and what `Web` / `Credit` / `Cash`
hold. Verified against the raw ledger: the twelve payments recorded on
2026-08-29 are each a whole number and group to exactly 513 / 25 / 15.

**Whole numbers are the check.** Every price the school charges is a whole
number of dollars, so every method's daily takings are whole too. A total with
cents in it means the report did arithmetic of its own, and is called out rather
than presented as takings.

The category columns are whole dollars for the same reason. They arrive from the
report with four decimal places, and those decimals are not money -- an order
covering a lesson and a board hire is divided between the two by proportion, and
the shares even drift between one reading of a finished day and the next, which
is how a summary ends up announcing that a closed day changed when nothing about
it did. `whole_split` states them in dollars and hands the odd dollar to the
largest remaining fraction, so the parts still add to the day's takings exactly.

**Do not use Bloowatch's cross-tab as cash-up figures.** The report also cuts
each method across lessons and board hire, in `Account = <method>` blocks, and
those arrive with four decimal places because a mixed order is split between its
categories by proportion. They are shares of a payment, not money anybody took.
`parse_report` reads them and checks them against the method totals -- a second
route to the same number is worth having -- and that is all they are for.

**No shop.** The `credit shop` / `cash shop` figures written alongside come from
a different till in a different system, are not whole numbers, and appear nowhere
in this report. They are never derived or guessed.

## The activity split: `ledger.py`

```
python3 ledger.py --verify 2026-08-30
```

```
2026-08-30   11 payments
  web                   0
  credit lesson       661
  cash lesson          60
  total               721

  lessons             429
  rentals             292
  note: 87 on order YESCX filed as rentals — that tab holds lessons and rentals
```

The report's own category block says board hire took 312.9375 that day. Nobody
took 312.9375. An order in Bloowatch is a running tab -- seven board hires on
one order, paid off in parts -- and the report divides each payment across the
tab's lines by their value, which is where the decimals come from.

The office does it the other way: read the payment list, see what the order was
for, file the whole payment under that heading. That gives whole dollars, and it
is what gets written down at the end of the day. `ledger.py` does the same thing
from the same rows, and reproduces those figures exactly.

**Where the judgement is.** Two of the nine tabs settled on 30/08 held more than
one kind of thing, so a payment against them is not attributable on its own: 87
paid against a tab holding 198 of board hire, 54 of lesson and 100 of yoga. The
rule is the first thing on the tab. That is a convention, not a fact, so every
payment where the rule actually had to decide is listed as a `note:` and carried
into the closing rather than buried.

`--verify` reads the official report as well and checks the two agree on the
day's takings and on every payment method. They are independent routes to the
same day; a disagreement means one is wrong and neither should be quoted.

Bloowatch's API accepts and then ignores every filter, so the orders behind a
day's payments are found by binary search over the school's own order list --
about forty small requests for a day, with probes shared between orders and
between days. Roughly twenty seconds per day.

## Tests

```
python3 test_split.py
python3 test_ledger.py
```

Runs on handwritten rows rather than a real workbook, so a day that does not add
up can be tested and no real takings live in the repository.

## The daily run

`CLOSING.md` holds the full procedure the 19:30 routine follows. The routine
itself carries only the credentials and points at that file, so the procedure
can be changed without ever reprinting them.

## Things that will bite you

* **`date_start` / `date_end` do not work.** On `/api/schools/<id>/payments/`
  and `/orders/` those parameters are accepted and then ignored: you get the
  most recent rows across all dates, not the range you asked for. Filter client
  side. This module sidesteps it by using the report endpoint, which takes
  `from_date=YYYY/MM/DD` and does honour it.
* **Refunds come through as `(50.0000)`** — accounting parentheses for a
  negative — anywhere you read raw payment amounts.
* **There is no fetch-one-order endpoint.** `/api/schools/<id>/orders/<id>/`
  returns 404, and `search=` matches nothing, so reaching an old order means
  paging through the list.
* **Chromium cannot reach the host over TLS 1.3** from the sandbox: the relay
  drops its oversized ClientHello and the tab shows `ERR_CONNECTION_RESET`,
  which looks exactly like bot blocking but is not. Launch with
  `--ssl-version-max=tls1.2` if you need a browser. This module uses plain HTTP
  requests and is unaffected.

## Field names that are not what they look like

Four of these were exported wrong, or not at all, until someone opened the page
next to the JSON and compared them column by column.

* **`is_public` on a product is the SOLD ONLINE column**, not "visible to
  staff". Two of Shokogi's thirty-five products carry it. A booking page built
  without reading it offers board hire and staff-only lines to the public.
* **A product has two categories.** `category_name` is the ACTIVITY CALENDAR
  the sessions land on (`SURF PACK`); `product_categories` is the shop's own
  grouping (`PACKAGES`, `LESSONS`) and is what their public site tabs by.
  `order` is the POS column.
* **A session's instructor is `assigned`**, a list of `{id, first_name,
  last_name}`. Nothing in the session record is called `staff` or `instructor`.
* **A staff member's `categories` are the activities they may teach.** Their
  own staff page states the rule: only staff carrying the activity are proposed
  when the session is built. `languages` are two-letter codes, `order` is the
  hand position in the list, `show_in_agenda` keeps someone off the board
  without deleting them, and `hours_worked_this_month` arrives as `"27:30:00"`.

Half the app also lives under `/_new/en/…` — Resources → Staff is
`/_new/en/resources/staff`, not `/manager/staff/list`. A guessed route returns
a white page rather than a 404, so a crawl of invented routes looks like a
crawl of empty screens. Read the routes off their own navigation.

## Reference

`/api/payments/daily-report?from_date=YYYY/MM/DD` returns a BIFF8 `.xls`
workbook (`application/vnd.ms-excel`). `biff.py` reads just enough of that
format to recover the cell grid. Beyond the summary used here, the workbook
also carries a category-by-payment-method cross tab and the day's refunds and
cancellations.
