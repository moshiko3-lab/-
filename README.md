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

## The school's WhatsApp

The manager can hold the school's WhatsApp conversation: every message in and
out on one screen, a reminder before each session, a brief on the day's board
each morning to whoever is working, and a bot that answers the questions that
get asked forty times a week.

It is off until somebody sets it up, and setting it up is mostly Meta's
paperwork rather than ours. `bash supabase/setup_whatsapp.sh` does every part
a script can do and prints what is left;
[`supabase/WHATSAPP.md`](supabase/WHATSAPP.md) is the whole of it, in order. Three things are worth knowing before starting:

* **A number on the API leaves the WhatsApp Business phone app.** It cannot be
  in both. Use a second number unless the school is ready to give the first one
  up.
* **There is no group.** WhatsApp's own API cannot post into one, so the
  evening brief — tomorrow's board, with the hours, the instructors and who is
  on each session — is the same message to each person on a list, sent
  individually. Where it has to be the real group, a link opens WhatsApp with
  the day already written and somebody taps send.

The brief the crew gets is one message in their own group, every evening.
`Evening brief` in Actions reads tomorrow out of Bloowatch at eight in the
evening Panama time, folds the day into the lines a person would write, and
posts it as a comment on the repository's **Evening brief** issue — which is
what puts it on a phone. The link in the comment opens WhatsApp with the whole
message written; you pick the group and send. That last tap is a person's
because the Cloud API has no way to post into a group at all.
* **A free-form message only goes within 24 hours of the customer's own last
  message.** Outside that, only a template Meta approved beforehand — which is
  why the reply box closes itself rather than accepting something that would be
  refused after the fact.

The token that can message the world as the school lives on a Supabase Edge
Function ([`supabase/functions/whatsapp`](supabase/functions/whatsapp)) and
nowhere else. The page asks it to send; the page can never send.

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
