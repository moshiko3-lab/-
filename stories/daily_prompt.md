# The daily scheduled task

**Name:** SHOKOGI – סטורי יומי לאינסטגרם
**When:** every day at 18:43, Panama time (`CRON_TZ=America/Panama 43 18 * * *`)
**Connector it needs:** `instgram` (Composio). Without it the session has no way to
reach the sandbox and the run does not happen; it says so in its report.
**Notifications:** push

The prompt, word for word:

```text
Daily run of SHOKOGI's automatic Instagram stories (surf school in Playa Venao, Panama; Instagram account shokogi_venao). Everything is already built and tested; your only job is to run it and report. Do not edit any file, do not publish anything by hand, do not create or remove connections, and do not commit or push anything.

Tools: the `instgram` MCP connector (Composio); if its tools are not loaded yet, find them with ToolSearch ("+instgram workbench"). Use its COMPOSIO_REMOTE_WORKBENCH tool (COMPOSIO_REMOTE_BASH_TOOL only to read /mnt/files/stories_run_status.json if the workbench misbehaves). Every workbench call must finish in under about 50 seconds: the MCP client gives up after 60.

1. Call COMPOSIO_REMOTE_WORKBENCH with exactly this code:
   exec(open('/mnt/files/run_daily.py').read()); start()
   It prints "started", "already running" or "another run is active"; all three are fine.

2. Then call COMPOSIO_REMOTE_WORKBENCH again and again with exactly this code:
   exec(open('/mnt/files/run_daily.py').read()); st = wait(40)
   Each call prints the run's status as JSON. Keep calling while "state" is "running". A run with several videos can take 20 to 40 minutes; after 70 calls stop and report it as still running.
   - "state": "stalled" means the background thread died (the sandbox restarted). Do step 1 once more (it resumes where it stopped; nothing is ever published twice) and keep polling. At most twice.
   - If a call times out or the sandbox reports a failed health check, just poll again.

3. When "state" is "done" or "error", end with a short report in Hebrew:
   - how many files were in the inbox ("found") and how many stories were published now, listing each file name with its Spanish and English line;
   - every item whose result is "error": file name, the error, and the attempt count (after 3 failed attempts a file is left in the inbox for good);
   - items marked "skipped (failed before)" only as a one-line reminder;
   - if "found" is 0, a single line: לא היו קבצים חדשים בתיקייה היום;
   - if "state" is "error", or an error mentions OAuth, code 190, an invalidated session or a missing connection: say plainly that the Instagram or Google Drive connection in Composio has to be reconnected, and quote the error.
   - if the `instgram` connector is not available in this session at all, say so plainly: the daily run did not happen.
```
