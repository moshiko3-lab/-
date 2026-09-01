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

## Putting it online

Every push to `main` or to the working branch rebuilds both pages and publishes
them, so the platform can be worked on while it is live:

* the manager at `https://moshiko3-lab.github.io/-/`
* the booking page at `https://moshiko3-lab.github.io/-/book.html`

GitHub's own address, `https://moshiko3-lab.github.io/-/`, keeps working and
redirects there.

The domain `shokogimanager.com` no longer answers half wrongly. The reason it
waited -- one of the registrar's two nameservers still serving an old record --
is gone: the apex and `www` both resolve to all four of GitHub's Pages
addresses, consistently. The `CNAME` file here carries the name and the build
copies it into the published site, which is what attaches it; the repository's
Pages settings must say the same thing. Once attached, GitHub redirects the
github.io address to the domain, so the two are one site and not two.

A repository gets **one** custom domain. That matters now that a second
business publishes from here: the studio under `/studio/` can only ever live
on this domain, and if it is to have a name of its own it needs a repository
of its own.

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

## The brow and lash studio

It used to be published from here, under `/studio/`. It is not any more: it
has its own repository and its own name.

* code -- [moshiko3-lab/Romyhovav](https://github.com/moshiko3-lab/Romyhovav)
* live -- <https://romyhovav.com>

The reason is not tidiness. GitHub Pages gives a repository one custom
domain, and this one was already `shokogimanager.com` -- so a studio wanting
a name of its own needed a repository of its own. Two businesses also have
no reason to rebuild each other's site on every push, and the release form
handles health information, which does not belong beside a surf school's
till.

## Tests

Sixteen of them, each driving the built page in a real browser rather than
testing the source:

```
python3 app/test_prices.py     # every tier of every product
python3 app/test_boardclick.py # an empty hour on the board opens a session
...                            # app/test_*.py
```
