# Daily Instagram stories

Put a photo or a video in the Drive folder **SHOKOGI Instagram Stories**
(owned by the school's account, shared with the one Composio uses). Every
evening up to three of them become branded 9:16 stories on `shokogi_venao`
and move to its **פורסם** subfolder. Nothing else to do.

Three a day is `per_day` in `stories_config.json`, counted by the calendar day
in Panama. Files waiting their turn go out one of each topic before the second
of any (the topic is the file name without its numbers), so three photos of
the same thing never go out together.

## What a story looks like

It is laid out like the mobile home page of shokogi.com, top to bottom:

* the photo, full width, with the site's `SHOK`**`O`**`GI` wordmark over it
  (white with a light shade, or dark where the photo is bright behind it);
* on white, the site's eyebrow `PLAYA VENAO · PANAMA` (Figtree bold, pink,
  letter-spaced), the Spanish line as the site's heading (Barlow Condensed
  ExtraBold, uppercase), the English line as its subtitle (Figtree, warm grey),
  and a pink pill button reading `SHOKOGI.COM`.

Details:

* 1080×1920, everything clear of the parts Instagram covers.
* A photo (HEIC from an iPhone too) is a still picture for 10 seconds with a
  song under it. Nothing moves. It goes up as a video only because Instagram's
  API cannot attach music to a photo story.
* A photo is cropped to the photo area: sideways it keeps the busiest part of
  the picture, up and down it keeps the upper part, where heads are.
* A video plays in the photo area, cut at 60 seconds (Instagram's limit;
  anything under 3 seconds holds its last frame). HDR video, which is what an
  iPhone records by default, is tone-mapped to ordinary colour; without it the
  story comes out grey and washed out.
* Music from Mixkit (Stock Music Free License: commercial and social use, no
  credit needed), never one of the last twelve used. A video's own sound stays
  on top.
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
| `/mnt/files/brand/`, `/mnt/files/music/` | Figtree and Barlow Condensed (the site's fonts), 30 tracks and their catalog |

A workbench cell is cut off after 180 seconds, and the MCP client gives up on a
call after about 60, so the run works in a
background thread:

```python
exec(open('/mnt/files/run_daily.py').read()); start()   # begin
wait(40)                                                 # repeat until state is not "running"
```

`start(dry_run=True, limit=1)` renders and creates the Instagram container but
publishes nothing, moves nothing and writes no log.

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
