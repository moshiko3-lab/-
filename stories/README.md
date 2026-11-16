# Daily Instagram stories

**Now:** every morning, after the owner's yes on WhatsApp, four photos from the Drive
folder **SHOKOGI Instagram Stories → תמונות מהאתר** (its eight topic folders,
photos taken from shokogi.com: surf camps, kids camp, lessons, foil, Ocean
Monkey, rentals, shop, general) go up as stories on `shokogi_venao` in the
full-screen design below, and move to **פורסם**. One of each topic before the
second of any. The settings are `inbox_folders`, `per_day` (4), `stream` and
`as_is_9x16` (false: every one of these photos gets the design) in
`stories_config.json`.

**Where WhatsApp runs.** The Green-API credentials live only in the Bloowatch
environment. So the daily task (in the session that holds the Instagram
connector) starts one helper session on Bloowatch each morning, which runs
`stories/wa.py send-url` (Green-API fetches the preview image by its one-hour
link) and later `wa.py check` / `wa.py text` when asked. No credential is
copied anywhere.

**Approval on WhatsApp.** At 6:10 Panama time the day's four are prepared
and one image of them goes to the owner's WhatsApp (+507 6259 6666) through
Green-API (`stories/wa.py`, credentials GREENAPI_ID / GREENAPI_TOKEN /
GREENAPI_URL in this environment, as in Bloowatch). At 6:28, and then hourly
until 11:28, the answer is read (approved by 6:28, they are up at about 6:30): a yes (אישור, כן, סבבה, 👍...) publishes exactly the
stories in that image; a no (לא, עצור...) or silence by the last check
publishes nothing that day. `require_approval` in the config enforces it in
the code: without `approved_day` = today, a run publishes nothing.

Earlier the source was the main folder itself, which holds stories the school
designed (1080×1920): those go up untouched with a song when `as_is_9x16` is
true. A file not to post goes in the **לא לפרסום** subfolder.

## What a story looks like

**A picture that is already 9:16** (1080×1920: a story the school designed) goes
up exactly as it is, with only a song added: no wordmark, no line, no crop.
Everything below is for an ordinary photo.

The photo fills the screen. Over it, quietly, in the site's type: the
`SHOK`**`O`**`GI` wordmark small and white at the top (over a faint shade that
deepens where the photo is bright behind it), and at the foot, on a soft shade that deepens only for a
bright photo, the eyebrow `PLAYA VENAO · PANAMA`, the story's one line in
Figtree Light, and `shokogi.com` on a small pink pill (the site's button colour). One language per story: `language` in
`stories_config.json` (`en` or `es`).

**Every story is laid out afresh**, so the day's stories do not look alike
(`render_look` in `story_engine.py`). By default (`"look_mode": "balanced"`) the
hand is mostly the clean one described above, Figtree Light, and now and then the
wordmark's condensed capitals, plain white or dark boxes, or the card: never the
same playful one twice in three stories, never three clean ones in a row, nothing
tilted, no emoji. The places change too: where the words sit (top, middle or foot;
left or centre; with or without the eyebrow). shokogi.com is on about one story in
three (never when one of the last two had it), under the words or alone at the
other end of the screen. `"look_mode": "clean"` keeps the clean hand and the pill on
every story; `"look_mode": "mixed"` uses every hand:

* **Where the words go**: the quietest stretch of the photo, top, middle or foot,
  left, centre or right. "Quiet" is measured: edges (people, boards, splash) and,
  heavily, skin colour, so the words stay off faces and bodies.
* **Their hand**: light (Figtree Light, as above), bold (the wordmark's condensed
  capitals, large), boxed (each line on a white, pink or dark box, as the app's text
  background, slightly tilted), script (Caveat, a handwriting face, tilted), neon
  (white with a pink glow), or card (the whole photo, uncropped, as a rounded card
  on a blurred copy of itself; photos only). Sometimes one emoji of the topic
  (Noto Color Emoji).
* **shokogi.com** on its pink (or white) pill: under the words, alone at the other
  end of the screen on its quietest side, or as a tilted sticker on a corner of the
  words.

The hand differs from the last three stories, the place and the pill from the last
one. What was drawn is recorded in the log (`look`). `"looks": false` in
`stories_config.json` goes back to fixed designs taken in turn (`STYLES`:
classic, editorial, headline, tag, frame, card; `"styles"` narrows them).
The wordmark always stays: white, small, at the top.

Details:

* 1080×1920, everything clear of the parts Instagram covers.
* A photo (HEIC from an iPhone too) is a still picture for 10 seconds with a
  song under it. Nothing moves. It goes up as a video only because Instagram's
  API cannot attach music to a photo story.
* A photo is cropped to fill the screen: sideways it keeps the busiest part of
  the picture, up and down it keeps the upper part, where heads are.
* A video fills the screen too, cut at 60 seconds (Instagram's limit;
  anything under 3 seconds holds its last frame). HDR video, which is what an
  iPhone records by default, is tone-mapped to ordinary colour; without it the
  story comes out grey and washed out.
* Music from Mixkit (Stock Music Free License: commercial and social use, no
  credit needed), only tracks marked `"upbeat": true` in `music/catalog.json`
  (34 of 52, chosen by measured beat strength and tempo, then by title and genre for the
  mood: no Christmas, children's or slow tracks), never one of the last twelve
  used, and each from its `"start"`: the liveliest ten seconds of the track,
  measured, rather than a quiet intro. A video's own sound stays on top.
* The line comes from a rotating list of thirty (every claim in it is on
  shokogi.com). If the file has a real name — "first wave for the kids", not
  `IMG_4411` — that name is turned into the line instead, in both languages,
  unless the same topic was among the last three stories.

There is no clickable link: Instagram's publishing API does not allow link,
poll or location stickers on stories, so the story says "link in bio".

## Where it runs

Everything runs in the Composio workbench sandbox (the `instgram` connector),
which holds the Google Drive and Instagram connections:

| path | what |
|---|---|
| `/mnt/files/story_engine.py` | the renderer (copy of `story_engine.py` here) |
| `/mnt/files/run_daily.py` | the daily run (copy of `run_daily.py` here) |
| `/mnt/files/stories_config.json` | Drive folder ids and the Instagram account id |
| `/mnt/files/stories_log.json` | one entry per Drive file: what was published, when, with what |
| `/mnt/files/stories_run_status.json` | the last run's progress and result |
| `/mnt/files/brand/`, `/mnt/files/music/` | Figtree and Barlow Condensed (the site's fonts), Caveat (handwriting, OFL), Noto Color Emoji (the CBDT build, v2.047: Pillow cannot draw the COLRv1 one), 30 tracks and their catalog |

A workbench cell is cut off after 180 seconds, and the MCP client gives up on a
call after about 60, so the run works in a
background thread:

```python
exec(open('/mnt/files/run_daily.py').read()); start()   # begin
wait(40)                                                 # repeat until state is not "running"
```

`start(dry_run=True, limit=1)` renders and creates the Instagram container but
publishes nothing, moves nothing and writes no log. `"paused": true` in
`stories_config.json` stops every real run before it touches anything.

The sandbox has one CPU and about 1 GB of memory, and it loses installed
packages when it restarts (the files under `/mnt/files` stay). The run
reinstalls what it needs, renders one file at a time, and if a large source
gets a render killed it shrinks the source first and tries again. Never start
two renders at once there.

Each file's progress is written to the log as it goes, so a run that dies
halfway is simply started again; a story already published is recognised from
Instagram's own record and never goes out twice. A file that fails three times
is left in the inbox and reported.

## Limits

* Instagram allows 100 API publishes per 24 hours on this account (checked at
  the start of every run); a run publishes at most 25.
* The account is a Creator account. Meta's documentation says story publishing
  needs a Business account, but it works on this one: the first story went out
  on 2026-11-16 (`01-family-surf-camps-1.jpg`, media 17956520385289414).
