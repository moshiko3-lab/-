# Daily Instagram stories

Put a photo or a video in the Drive folder **SHOKOGI Stories → 1 - להעלאה**.
Once a day it becomes a branded 9:16 story on `shokogi_venao` and the file
moves to **2 - פורסם**. Nothing else to do.

## What a story looks like

* 1080×1920. Photos (HEIC from an iPhone too) become a 7-second clip with a
  slow zoom over a blurred fill; videos are cropped to fill the frame and cut
  at 60 seconds (Instagram's limit; anything under 3 seconds holds its last
  frame).
* HDR video, which is what an iPhone records by default, is tone-mapped to
  ordinary colour; without it the story comes out grey and washed out.
* The white SHOKOGI logo at the top and a line in Spanish with English below,
  over a pink `shokogi.com · link in bio` pill — all placed clear of the parts
  Instagram covers.
* Music from Mixkit (Stock Music Free License: commercial and social use, no
  credit needed), never one of the last twelve used. A video's own sound stays
  on top.
* The line comes from a rotating list of thirty (every claim in it is on
  shokogi.com). If the file has a real name — "first wave for the kids", not
  `IMG_4411` — that name is turned into the line instead, in both languages.

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
| `/mnt/files/brand/`, `/mnt/files/music/` | logo, Figtree font, 30 tracks and their catalog |

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
  needs a Business account; Instagram accepted and processed a story container
  from this account on 2026-11-16, and the first real publish is the final test.
  If it is refused, switch the account to Business in the Instagram app
  (Settings → Account type and tools) — nothing here needs to change.
