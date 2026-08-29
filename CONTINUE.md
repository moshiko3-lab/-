# Picking this up again

## What survives, and what does not

Everything in this repository is safe: it is committed and pushed to
`claude/new-session-d0r3xc` on GitHub. That includes the app, the Bloowatch
scripts, the catalog export and the crawl of Bloowatch's own pages.

The container this was built in does not survive. When the session ends its
disk is reclaimed. One thing lives only there, and it is the one thing that
cannot be committed: the Bloowatch login. It sits encrypted at
`scratchpad/secrets/creds.enc`, and it will be gone.

## Keeping the Bloowatch access

Set these three as environment variables on the Claude Code environment, in the
Anthropic Console. They then exist for every future session, and every script
here reads them without any further setup:

    BLOOWATCH_URL       https://shokogi.bloowatch.com
    BLOOWATCH_EMAIL     shokogipanama@gmail.com
    BLOOWATCH_PASSWORD  (the account password)

Never put them in a file in this repository. Anything committed here is
permanent and visible to anyone with repository access; `.gitignore` already
refuses `.env`, `secrets/`, `*.enc` and `*.key`, but the real safeguard is not
writing them down in the first place.

## Getting going in a new session

    git fetch origin claude/new-session-d0r3xc
    git checkout claude/new-session-d0r3xc

Then, with the three variables set:

    cd app && python3 build.py --out index.html            # the management app
    cd app && python3 build.py --minisite --out booking.html  # the public site
    cd bloowatch && python3 export_catalog.py        # refresh from Bloowatch
    cd bloowatch && python3 daily_report.py 2026-08-28

Both pages must be hosted on the **same domain**. They share one browser store,
which is how a booking taken on the public site reaches the manager; on two
domains they are two stores and the bookings go nowhere.

`build.py` refuses to write a page whose script does not parse, then opens it in
a browser, clicks every screen and opens some thirty dialogs. Two silent
breakages got through before that existed. Beyond it there are three suites that
drive the built pages the way a person would:

    cd app && python3 test_pos.py       # register, tickets, integrity, archive
    cd app && python3 test_agenda.py    # the planning's views and fortnight
    cd app && python3 test_booking.py   # pricing rule, and the booking site

`test_booking.py` is the one to keep. It checks the shared pricing file against
the real exported catalogue: nine products mix `price_unit` values, and the
earlier rule would have hired a surfboard for a fortnight for ten dollars.

One trap when writing more of these: the stylesheet uppercases chips, headings
and buttons, and `inner_text` returns the transformed text. Compare
case-insensitively or the test measures the CSS instead of the app.

## One thing the sandbox gets wrong

Chromium cannot reach Bloowatch over TLS 1.3 from here: the relay drops its
oversized ClientHello and the tab reports `ERR_CONNECTION_RESET`, which reads
exactly like bot blocking and is not. Launch with `--ssl-version-max=tls1.2`.
Weeks were lost to that misreading; `bloowatch/README.md` has the detail.

## Where the app's own data lives

In the browser, not here. The management app keeps what you enter in
`localStorage` on whichever browser you opened it in — it does not follow you
to a phone or to a colleague. The Backup button in its header exports and
restores the whole database as text, and is the only safety net until it sits
on a server.
