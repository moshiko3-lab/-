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

* the manager at `https://shokogimanager.com/`
* the booking page at `https://shokogimanager.com/book.html`

GitHub's own address, `https://moshiko3-lab.github.io/-/`, redirects there.

The domain `shokogimanager.com` is attached: `CNAME` here names it, and the
repository's Pages settings must say the same thing or the two disagree and the
site answers on neither. It was unhooked once before, when one of the
registrar's two nameservers was still serving the old record and the name
answered correctly about half the time; both agree now.

This needs GitHub Pages switched on once, by the repository's owner:
**Settings → Pages → Build and deployment → Source: GitHub Actions**. Until
that is done the build runs and the deploy step stops with "Ensure GitHub Pages
has been enabled".

Two things worth being clear about before sending anyone the link:

* **There is one book, and it is shared.** Bookings, clients, payments and the
  day's board live in Supabase, and every device that signs in sees the same
  day. Writes land in the browser first and drain to the shared book when there
  is a network, so the till does not stop when the wifi in Venao does — which it
  does. The header says `Synced`, `Syncing…` or `Offline`; nothing is lost while
  it says the last of those, it is only waiting.
* **There is a login.** The app draws nothing until somebody signs in, so the
  address alone opens no book. A device is asked once and the session is kept,
  which is why a signed-in iPad opens on a morning with no wifi.
* **The booking page is not on that book yet.** `book.html` has no sign-in and
  no Supabase in it: it writes into whatever browser it is opened in. A booking
  a customer makes on their own phone stays on their phone. It reaches the
  school only when the page is opened in the same browser storage as the
  manager — the iPad at the counter, in the same place the manager runs. A
  booking taken at the counter is taken in the manager itself.

## On the school's iPad

The manager belongs on the counter, and an iPad can keep it as an app rather
than a tab:

1. Open `https://shokogimanager.com` in **Safari** — Chrome and Firefox on iOS
   cannot add anything to the home screen.
2. **Share → Add to Home Screen**, name it *Shokogi*, **Add**.
3. Open it from that icon from now on. It launches with no address bar and no
   tabs, and sits in the app switcher as its own app.

The build puts `icon-180.png`, `icon-192.png`, `icon-512.png` and
`manifest.webmanifest` beside the pages, which is what the icon and the
chromeless window come from. They are made from the badge with
`.claude/skills/shokogi-brand`:

```
SKILL=.claude/skills/shokogi-brand
python3 $SKILL/scripts/render.py $SKILL/assets/icon.html \
    --preset icon-180 --out app/icon-180.png     # and icon-192, icon-512
```

Three things to know before switching a device over:

* **A home-screen copy has its own storage**, separate from the Safari tab it
  was installed from. That costs nothing here — it signs in and pulls the shared
  book — except for a write still sitting in the tab's outbox. Check the tab
  says `Synced`, not `Offline`, before you install.
* **The address is part of the identity.** `shokogimanager.com` and the
  github.io address are different origins with different local stores and
  different installed apps. Install from the domain and stay on it.
* **The installed app and the Safari tab are two stores**, which matters for
  `book.html`: opened in Safari it cannot reach a manager that is running as an
  installed app, and the installed app has no address bar to open it from. Take
  counter bookings in the manager, where they belong, and leave the booking page
  to the customers it was written for.

To hand the iPad to a customer without them wandering off into Safari, turn on
**Settings → Accessibility → Guided Access**, then triple-click the top button
inside the app to start and end a locked session.

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
