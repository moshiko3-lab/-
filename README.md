# SHOKOGI

The school's own manager, and the booking page it sends to customers. Two
self-contained HTML files: no server, no build step to run before opening one,
nothing to install. What each screen does is written up in
[`app/README.md`](app/README.md); what it is a replacement for is written up in
[`bloowatch/README.md`](bloowatch/README.md).

```
python3 app/build.py --out index.html            # the manager
python3 app/build.py --minisite --out book.html  # the booking page
```

Two things here are not web pages: `print/shokogi-trifold.pdf`, one sheet
folded in three for the rack by the door, and `print/shokogi-brochure.pdf`, the
bilingual eight-page booklet that goes in guest rooms. Both carry the shop's QR
code. Its offer is read off the school's Shopify store and its
board figures off `app/catalog.json`, so both are counted rather than typed.
How to rebuild it, how to print it, and how to put real photographs into it is
in [`print/README.md`](print/README.md).

## Putting it online

Every push to `main` or to the working branch rebuilds both pages and publishes
them, so the platform can be worked on while it is live:

* the manager at `https://moshiko3-lab.github.io/-/`
* the booking page at `https://moshiko3-lab.github.io/-/book.html`

GitHub's own address, `https://moshiko3-lab.github.io/-/`, keeps working and
redirects there.

The domain `shokogimanager.com` is bought and its A records already point at
GitHub, but it is not attached yet: one of the registrar's two nameservers was
still serving the old record, so the name answered correctly about half the
time and wrongly the rest. Attaching it also makes GitHub redirect the
github.io address to it, which turns a half-working domain into no working
address at all -- so the domain waits until both nameservers agree. To attach
it: put `shokogimanager.com` in a `CNAME` file here and in the repository's
Pages settings, which must say the same thing.

This needs GitHub Pages switched on once, by the repository's owner:
**Settings → Pages → Build and deployment → Source: GitHub Actions**. Until
that is done the build runs and the deploy step stops with "Ensure GitHub Pages
has been enabled".

Two things worth being clear about before sending anyone the link:

* **The data does not travel with the page.** Everything a browser records —
  clients, bookings, payments, the day's board — is kept in that browser, on
  that device. Two people opening the same address get the same app and their
  own separate books. One shared book needs a database behind it, and that is a
  different piece of work, not a setting.
* **There is no login.** Anyone with the address can open the manager. What
  they see is their own empty copy, not the school's, but the screens are
  public.

The client list is never published. `app/clients.json` holds real names, phone
numbers and email addresses; it is not in the repository, so a build made by CI
cannot contain it, and [`.github/no_pii.py`](.github/no_pii.py) reads the built
pages and fails the publish rather than trusting that.

## Tests

Sixteen of them, each driving the built page in a real browser rather than
testing the source:

```
python3 app/test_prices.py     # every tier of every product
python3 app/test_boardclick.py # an empty hour on the board opens a session
...                            # app/test_*.py
```
