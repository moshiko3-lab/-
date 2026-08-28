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

`Date, Day, Transactions, Total, Credit, Cash, Web, Packages, Lessons, Rentals,
Photography, Other, Refunds, Check, Notes`

`Check` is `OK` only when the payment methods add up to the total *and* the
categories add up to the total. Otherwise it is `CHECK!` and `Notes` says what
disagreed. A category Bloowatch reports that has no column of its own (for
example `VIDEO ANALYSIS`) is added into `Other` and named in `Notes`, so nothing
is ever dropped silently.

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

## Reference

`/api/payments/daily-report?from_date=YYYY/MM/DD` returns a BIFF8 `.xls`
workbook (`application/vnd.ms-excel`). `biff.py` reads just enough of that
format to recover the cell grid. Beyond the summary used here, the workbook
also carries a category-by-payment-method cross tab and the day's refunds and
cancellations.
