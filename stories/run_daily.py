"""SHOKOGI daily stories: every photo or video in the Drive inbox becomes a
branded Instagram story, is published, and moves to the "published" folder.

Runs inside the Composio workbench, which provides run_composio_tool,
upload_local_file and invoke_llm as globals. The work runs in a background
thread because a single workbench cell is cut off after 180 seconds:

    exec(open('/mnt/files/run_daily.py').read()); start()   # begin
    wait(40)                                                 # repeat until state != "running"

start(dry_run=True) renders and creates the Instagram containers but never
publishes, never moves a file and never writes the log.

start(prepare=True, limit=4) goes as far as a dry run but records the result:
the next real run publishes those very containers (same picture, line, song).
ignore_daily_cap=True lets one run go past per_day. only=["name.jpg", ...] (names
or Drive ids) runs just those files, whatever their place in the queue. Every rendered story leaves
a small preview in /mnt/files/previews/<drive file id>.jpg.

"require_approval": true publishes nothing on a day without "approved_day" = that
day (Panama date), which approve_today() sets after the owner's yes on WhatsApp.

stories_config.json: "inbox_folders" (several source folders) or "inbox" (one);
"stream" names the current source, and only its stories count toward per_day;
"as_is_9x16": false puts the design on every picture, even a story-shaped one.
"language" ("en" or "es") is the one language a story is
written in; "paused": true stops every real run before it touches anything.
Each story gets a freshly drawn look (story_engine.render_look): where the words
sit and where shokogi.com goes, unlike the story just before it. "look_mode":
"classic" (the default): the design as first approved, the same on every story,
with shokogi.com on about one story in three. "balanced": mostly the clean hand (Figtree Light), now and then the
wordmark's condensed capitals, plain boxes or the card, nothing tilted, no emoji,
and shokogi.com on about one story in three; "clean": always the clean hand with
the pill; "mixed": every hand (also script, neon), tilts, stickers, emoji.
"looks": false goes back to fixed designs taken in turn, "styles" (optional) listing
them from story_engine.STYLES (classic, editorial, headline, tag, frame, card).

Every step is recorded per Drive file id in stories_log.json, so a run that
dies halfway can simply be started again: a file is never published twice.
"""
import json, os, re, sys, time, random, shutil, subprocess, threading, traceback
import datetime as _dt

BASE = "/mnt/files"
CFG_PATH = f"{BASE}/stories_config.json"
LOG_PATH = f"{BASE}/stories_log.json"
STATUS_PATH = f"{BASE}/stories_run_status.json"
WORK = "/home/user/shokogi_work"          # scratch space; not kept between runs
MAX_PER_RUN = 25                          # a safety cap well under Instagram's quota
MAX_ATTEMPTS = 3                          # after this many failures a file is left alone
STALE_SECS = 600                          # a "running" status this old means the thread died

# Rotating story lines (Spanish first, English below). Every claim here is on
# shokogi.com: lessons for all levels, waves all year, 100+ boards, foil, kids
# camp, surf camps, custom trips, board rentals, "Keep Venao Surfing".
TEXTS = [
    ("¡Las olas te esperan en Playa Venao!", "The waves are waiting for you in Playa Venao"),
    ("Tu primera ola empieza aquí", "Your first wave starts here"),
    ("Clases de surf para todos los niveles", "Surf lessons for every level"),
    ("Olas todo el año en Playa Venao", "Waves all year round in Playa Venao"),
    ("Aprende a surfear con nosotros", "Learn to surf with us"),
    ("Otro día perfecto en Venao", "Another perfect day in Venao"),
    ("Vuela sobre el agua con foil surf", "Fly above the water: foil surfing in Venao"),
    ("Menos pantalla, más olas", "Less screen time, more wave time"),
    ("¿Listo para tu primera ola?", "Ready for your first wave?"),
    ("Más de 100 tablas para elegir", "100+ boards, every size on hand"),
    ("El océano es nuestra aula", "The ocean is our classroom"),
    ("Rema, ponte de pie, sonríe", "Paddle, pop up, smile"),
    ("Campamento de surf para niños", "Kids surf camp in Playa Venao"),
    ("Cada ola es una nueva lección", "Every wave is a new lesson"),
    ("Surf, sonrisas y buena energía", "Surf, smiles and good vibes"),
    ("Tu aventura en Panamá empieza en el agua", "Your Panama adventure starts in the water"),
    ("Hoy es un buen día para surfear", "Today is a good day to surf"),
    ("Donde los amigos se vuelven familia", "Where friends become family"),
    ("Ven a surfear con SHOKOGI", "Come surf with SHOKOGI"),
    ("De tu primera ola a nivel avanzado", "From your first wave to advanced"),
    ("Surf camps en Playa Venao", "Surf camps in Panama's top surf spot"),
    ("Viajes de surf a tu medida", "Custom surf trips, made for you"),
    ("Alquiler de tablas junto a las olas", "Board rentals steps from the waves"),
    ("Instructores expertos, olas perfectas", "Expert instructors, perfect waves"),
    ("El mar nos llama", "The ocean is calling"),
    ("Nunca es tarde para aprender a surfear", "It's never too late to learn to surf"),
    ("Una ola más y nos vamos", "One more wave, then we go"),
    ("Atardeceres y olas en Playa Venao", "Sunsets and waves in Playa Venao"),
    ("Sol, arena y buenas olas", "Sun, sand and good waves"),
    ("Keep Venao Surfing", "Keep Venao Surfing"),
]

# Lines per topic for the photos taken from the site, so a foil photo never says
# "surf lessons". The topic is the file name without its number (kids-camp-03.jpg
# -> "kids camp"). Every claim is on shokogi.com or in the school's own designs.
TOPIC_LINES = {
    "playa venao": [("¡Las olas te esperan en Playa Venao!", "The waves are waiting for you in Playa Venao"),
                    ("Otro día perfecto en Venao", "Another perfect day in Venao"),
                    ("Olas todo el año en Playa Venao", "Waves all year round in Playa Venao"),
                    ("El mar nos llama", "The ocean is calling"),
                    ("Hoy es un buen día para surfear", "Today is a good day to surf"),
                    ("Keep Venao Surfing", "Keep Venao Surfing")],
    "surf camp": [("Surf camps en Playa Venao", "Surf camps in Playa Venao"),
                  ("Campamentos de 7, 10 y 15 días", "7, 10 and 15 day surf camps"),
                  ("Tu aventura en Panamá empieza en el agua", "Your Panama adventure starts in the water"),
                  ("Donde los amigos se vuelven familia", "Where friends become family"),
                  ("Coaching diario para tu nivel", "Daily coaching for your level"),
                  ("Surf, sonrisas y buena energía", "Surf, smiles and good vibes")],
    "kids camp": [("Campamento de surf para niños", "Kids surf camp in Playa Venao"),
                  ("Surf camps seguros y divertidos", "Safe, fun surf camps for kids and teens"),
                  ("Su primera ola empieza aquí", "Their first wave starts here"),
                  ("Clases, juegos y educación oceánica", "Lessons, games and ocean education")],
    "surf lessons": [("Clases de surf para todos los niveles", "Surf lessons for every level"),
                     ("Tu primera ola empieza aquí", "Your first wave starts here"),
                     ("Rema, ponte de pie, sonríe", "Paddle, pop up, smile"),
                     ("De tu primera ola a nivel avanzado", "From your first wave to advanced"),
                     ("Cada ola es una nueva lección", "Every wave is a new lesson"),
                     ("Instructores expertos, olas perfectas", "Expert instructors, perfect waves")],
    "foil the bee": [("Vuela sobre el agua con foil surf", "Fly above the water: foil surfing in Venao"),
                     ("Tow-in foil con The Bee", "Tow-in foil with The Bee"),
                     ("Olas a las que no llegas remando", "Reach waves you can't paddle to"),
                     ("Desliza sobre las olas", "Glide above the waves")],
    "ocean monkey": [("Tablas soft-top Ocean Monkey", "Ocean Monkey soft-top boards"),
                     ("Seguras para aprender, divertidas para surfear", "Safe to learn, fun to ride"),
                     ("Hechas para tu primera ola", "Made for your first wave")],
    "board rentals": [("Alquiler de tablas junto a las olas", "Board rentals steps from the waves"),
                      ("Más de 100 tablas para elegir", "100+ boards, every size on hand"),
                      ("Cada forma y tamaño para cada ola", "Every shape & size for every wave")],
    "shop": [("Gorras y lycras SHOKOGI", "SHOKOGI hats and rash guards"),
             ("Representa a SHOKOGI donde surfees", "Represent SHOKOGI wherever you surf"),
             ("Keep Venao Surfing", "Keep Venao Surfing")],
}

# Emoji a story about each topic may carry (one, sometimes; never for a designed file).
TOPIC_EMOJI = {"playa venao": ["🌊", "☀️", "🌴"], "surf camp": ["🏄", "🤙", "🌊"], "kids camp": ["🤙", "☀️", "🏄"],
               "surf lessons": ["🏄", "🤙"], "foil the bee": ["🌊", "🤙"], "ocean monkey": ["🐒", "🏄"],
               "board rentals": ["🏄", "🌊"], "shop": ["🧢", "🤙"]}

# Stories that sell something carry the pill, with a call to action; the others (a
# beautiful day in Venao) carry none. The pill cannot be tapped: Instagram's API adds
# no link stickers, so it names the site.
SALES_CTA = {"surf camp": "Book now", "kids camp": "Book now", "surf lessons": "Book now",
             "foil the bee": "Book now", "board rentals": "Book now", "shop": "Shop now"}

# A title per topic, for the "headline" design: the topic's name, as the site uses it.
TOPIC_TITLES = {"playa venao": "Playa Venao", "surf camp": "Surf Camp", "kids camp": "Kids Camp",
                "surf lessons": "Surf Lessons", "foil the bee": "Foil", "ocean monkey": "Ocean Monkey",
                "board rentals": "Board Rentals", "shop": "The Shop"}

# Names cameras, phones and apps give files: these are not captions.
AUTO_NAME = re.compile(
    r"(?i)\b(img|vid|mov|dsc[nf]?|dji|gopr\w*|gopro|pxl|mvimg|screenshot|screen|recording|whatsapp|"
    r"image|video|photo|foto|movie|copy|copia|untitled|captura|pantalla|edited|final|at|"
    r"test|example|sample|demo|story|stories|reel|clip|new|draft|ejemplo|prueba|nuevo|shop|"
    r"צילום|מסך|תמונה|סרטון|וידאו|דוגמה|דוגמא|בדיקה|ניסיון|חדש|סטורי|טיוטה)\b")
SAFE_TEXT = re.compile(r"^[A-Za-zÀ-ÿ0-9 ,.!¡?¿'’&:+\-]+$")

IMAGE_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic",
             "image/heif": "heif", "image/gif": "gif"}


# ---------------------------------------------------------------- helpers

def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path, default):
    for p in (path, path + ".tmp"):       # an interrupted replace leaves only the temp copy
        try:
            return json.load(open(p, encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return default


def _save(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _tool(slug, args, retries=2):
    res, err = run_composio_tool(slug, args, retry_params={"max_retries": retries, "delay_ms": 3000},
                                 print_schema_for_tool=False)
    if err:
        raise RuntimeError(f"{slug}: {str(err)[:400]}")
    data = res.get("data", res)
    return data


STATE_NAME = "shokogi_stories_state.json"


def _backup_state():
    """One copy of the config, the log and today's approval record in Google Drive
    (a file in the main stories folder), rewritten after every run and approval step:
    the sandbox's storage has come back empty before, and bootstrap.py restores from
    this copy. Never stops a run: a failure is returned as text."""
    try:
        cfg = _load(CFG_PATH, None)
        if not cfg:
            return "no config to back up"
        text = json.dumps({"saved_at": _now(), "config": cfg, "log": _load(LOG_PATH, None),
                           "approval": _load(f"{BASE}/stories_approval.json", None)}, ensure_ascii=False)
        if cfg.get("state_file_id"):
            try:
                _tool("GOOGLEDRIVE_EDIT_FILE", {"file_id": cfg["state_file_id"], "content": text,
                                                "mime_type": "application/json"})
                return "backed up"
            except Exception:
                pass                          # deleted or unreachable: make a new one
        d = _tool("GOOGLEDRIVE_CREATE_FILE_FROM_TEXT", {"file_name": STATE_NAME, "text_content": text,
                                                        "parent_id": cfg.get("root") or cfg.get("inbox"),
                                                        "mime_type": "application/json"})
        cfg["state_file_id"] = d.get("id") or (d.get("file") or {}).get("id")
        _save(CFG_PATH, cfg)
        return "backed up (new file)"
    except Exception as e:
        return f"backup failed: {str(e)[:200]}"


def _ensure_deps():
    for mod, pkg in (("imageio_ffmpeg", "imageio-ffmpeg"), ("pillow_heif", "pillow-heif")):
        try:
            __import__(mod)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], check=True)
    if BASE not in sys.path:
        sys.path.insert(0, BASE)


# ---------------------------------------------------------------- text & music

def _filename_text(name):
    """A caption from a meaningful file name, in Spanish and English, or None."""
    stem = os.path.splitext(name)[0]
    left = AUTO_NAME.sub(" ", re.sub(r"[\d_\-\.\(\)\[\]]+", " ", stem))
    if len(re.sub(r"\W", "", left)) < 4:
        return None
    prompt = (
        "You write short Instagram Story overlay text for SHOKOGI, a surf school in Playa Venao, Panama.\n"
        f"A team member named the uploaded file: {json.dumps(stem, ensure_ascii=False)}\n"
        "Only treat it as meaningful if it says what is in the photo/video or carries a message for "
        "viewers, e.g. 'first wave for the kids', 'sunset session', 'שיעור גלישה לילדים'. NOT meaningful: "
        "camera/app auto-names, random characters, dates, a lone first name, or generic words such as "
        "example, test, video, photo, story, new, file. When in doubt, it is not meaningful.\n"
        "If meaningful, turn it into a short upbeat story line in Spanish and in English, keeping its "
        "meaning. Do not invent facts, prices, dates or offers. Spanish at most 45 characters, English "
        "at most 55. No emojis, no hashtags, no quotation marks.\n"
        'Reply with JSON only: {"meaningful": true or false, "es": "...", "en": "..."}')
    try:
        out, err = invoke_llm(prompt)
        if err:
            return None
        m = re.search(r"\{.*\}", out, re.S)
        j = json.loads(m.group(0)) if m else {}
        es, en = (j.get("es") or "").strip(), (j.get("en") or "").strip()
        if j.get("meaningful") is True and 0 < len(es) <= 50 and 0 < len(en) <= 60 \
                and SAFE_TEXT.match(es) and SAFE_TEXT.match(en):
            return es, en
    except Exception:
        pass
    return None


def _topic(name):
    """What a file is about, from its name: '01-family-surf-camps-2.jpg' -> 'family surf camps'."""
    stem = re.sub(r"[\d_\-\.\(\)\[\]]+", " ", os.path.splitext(name)[0])
    return re.sub(r"\s+", " ", stem).strip().lower()


def _panama_day(iso):
    """The calendar day in Playa Venao (UTC-5, no daylight saving) of a UTC timestamp."""
    t = _dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ") - _dt.timedelta(hours=5)
    return t.date().isoformat()


def _mixed_order(files, log=None, ranks=None):
    """Oldest first, but one of each topic before the second of any: three photos of
    the same thing do not go out on the same day. Topics already published count, so
    the second family photo waits until every other topic has had its first. Files from
    `priority_folders` come before all of these, in the order the config's "ranks" gives
    them (name -> place), else in the order they were shot (by name)."""
    seen, ranked = {}, []
    for it in (log or {}).get("items", {}).values():
        if it.get("status") == "published":
            t = _topic(it.get("name", ""))
            seen[t] = seen.get(t, 0) + 1
    for f in sorted(files, key=lambda f: f.get("createdTime", "")):
        t = _topic(f.get("name", ""))
        ranked.append((seen.get(t, 0), f.get("createdTime", ""), f))
        seen[t] = seen.get(t, 0) + 1
    ranks = ranks or {}
    first = sorted((f for f in files if f.get("_priority")),
                   key=lambda f: (f["_priority"], ranks.get(f.get("name"), 10 ** 6), f.get("name", "")))
    return first + [f for _, _, f in sorted(ranked, key=lambda r: (r[0], r[1])) if not f.get("_priority")]


def _liveliest(path, secs=10):
    """Where the liveliest `secs` seconds of a track start: steady beat and loudness,
    measured on the onset envelope (the same measure the Mixkit starts came from)."""
    import numpy as np
    import imageio_ffmpeg
    sr, hop = 11025, 256
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    n = len(x) // hop
    if n < 10:
        return 0.0
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-6
    env = np.convolve(np.maximum(0, np.diff(np.log(rms), prepend=np.log(rms[0]))), np.ones(3) / 3, "same")
    fps, win = sr / hop, int(sr / hop * secs)
    best, score = 0.0, -1.0
    for st in range(0, max(1, n - win), int(fps / 2)):
        sc = float(env[st:st + win].mean() * rms[st:st + win].mean())
        if sc > score:
            score, best = sc, st / fps
    return round(best, 1)


def _sync_music(cfg):
    """Tracks the school puts in its music folder in Drive (`music_folder`): fetched,
    measured for their liveliest ten seconds, and added to the catalog as "own". Once
    there are five or more, only they are used. The school picks them, and is
    responsible for having the right to use them (a music subscription, say)."""
    folder = cfg.get("music_folder")
    if not folder:
        return 0
    cat_path = f"{BASE}/music/catalog.json"
    cat = _load(cat_path, [])
    have = {t.get("drive_id") for t in cat if t.get("drive_id")}
    d = _tool("GOOGLEDRIVE_FIND_FILE", {"q": f"'{folder}' in parents and trashed = false and mimeType contains 'audio/'",
                                         "pageSize": 200, "fields": "files(id,name,mimeType)"})
    files = d.get("files") or []
    live = {f["id"] for f in files}
    added = 0
    for f in files:
        if f["id"] in have:
            continue
        ext = os.path.splitext(f["name"])[1].lower() or ".mp3"
        path = f"{BASE}/music/own_{f['id']}{ext}"
        try:                                    # one bad file does not keep the rest out
            _download(f, path)
            cat.append({"id": f["id"], "drive_id": f["id"], "title": os.path.splitext(f["name"])[0], "file": path,
                        "own": True, "upbeat": True, "start": _liveliest(path), "source": "the school's music folder in Drive"})
            added += 1
        except Exception:
            continue
    kept = [t for t in cat if not t.get("drive_id") or t["drive_id"] in live]     # removed from the folder: dropped
    if added or len(kept) != len(cat):
        tmp = f"{cat_path}.sync.part"           # not the bootstrap's temp name: both may write the catalog
        json.dump(kept, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, cat_path)
    return added


def _choose_track(log):
    """A track from the school's own music folder once it holds five or more, else an
    upbeat Mixkit one; not one of the last twelve used. Each catalog entry's "start" is
    where its liveliest ten seconds begin."""
    cat = json.load(open(f"{BASE}/music/catalog.json"))
    own = [t for t in cat if t.get("own") and os.path.exists(t["file"])]
    pool = own if len(own) >= 5 else ([t for t in cat if t.get("upbeat") and not t.get("own")] or cat)
    done = sorted((it for it in log["items"].values() if it.get("track")), key=lambda it: it.get("updated", ""))
    recent = {it["track"] for it in done[-12:]}
    return random.choice([t for t in pool if t["file"] not in recent] or pool)


# ---------------------------------------------------------------- the steps

def _choose_style(log, cfg, title, is_image):
    """The next design in turn (story_engine.STYLES, or "styles" in the config), so the
    day's stories do not all look alike. Skips "headline" without a title and "card"
    for a video (a card needs a still photo)."""
    import story_engine
    styles = [x for x in (cfg.get("styles") or story_engine.STYLES) if x in story_engine.STYLES] or ["classic"]
    i = log.get("style_idx", 0)
    for k in range(len(styles)):
        st = styles[(i + k) % len(styles)]
        if (st == "headline" and not title) or (st == "card" and not is_image):
            continue
        log["style_idx"] = i + k + 1                      # a dry run never saves it
        return st
    log["style_idx"] = i + 1
    return "classic"


def _list_inbox(cfg):
    """Every picture or video directly inside the source folder(s): `inbox_folders`
    when the config lists several, otherwise the single `inbox`; first those in
    `priority_folders` (new photos the school wants out before the rest), each with the
    folders directly inside it (one per day, say)."""
    files = []
    priority = list(cfg.get("priority_folders") or [])
    for top in list(priority):           # a photographer's folder may hold one folder per day
        d = _tool("GOOGLEDRIVE_FIND_FILE", {"q": f"'{top}' in parents and mimeType = 'application/vnd.google-apps.folder' "
                                                 "and trashed = false", "pageSize": 100, "fields": "files(id,name)"})
        for sub in sorted(d.get("files") or [], key=lambda f: f.get("name", "")):
            priority.insert(priority.index(top) + 1, sub["id"])
    for folder in priority + list(cfg.get("inbox_folders") or [cfg["inbox"]]):
        token = None
        while True:
            args = {"folder_id": folder, "orderBy": "createdTime", "pageSize": 100,
                    "q": "(mimeType contains 'image/' or mimeType contains 'video/') and trashed = false",
                    "fields": "nextPageToken,files(id,name,mimeType,size,createdTime)"}
            if token:
                args["pageToken"] = token
            d = _tool("GOOGLEDRIVE_FIND_FILE", args)
            for f in d.get("files") or []:
                if folder in priority:
                    f["_priority"] = priority.index(folder) + 1
                files.append(f)
            token = d.get("nextPageToken")
            if not token:
                break
    return files


def _download(f, dest):
    d = _tool("GOOGLEDRIVE_DOWNLOAD_FILE", {"fileId": f["id"]})
    url = (d.get("downloaded_file_content") or {}).get("s3url")
    if not url:
        raise RuntimeError("Drive download returned no file URL")
    for attempt in range(3):              # a large file over a flaky link: curl's own retry misses SSL errors
        r = subprocess.run(["curl", "-sSfL", "--retry", "3", "--retry-all-errors", "-o", dest, url],
                           capture_output=True, text=True)
        if not r.returncode and os.path.exists(dest) and os.path.getsize(dest):
            return
        time.sleep(5)
    raise RuntimeError(f"download failed: {r.stderr[-300:]}")


_TO_JPEG = r"""
import sys
from PIL import Image, ImageOps
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass
im = Image.open(sys.argv[1])
im.draft("RGB", (2600, 2600))          # a JPEG decodes straight at a reduced scale
im = ImageOps.exif_transpose(im).convert("RGB")
im.thumbnail((2600, 2600), Image.LANCZOS)
im.save(sys.argv[2], quality=93)
"""


def _to_jpeg(src, dest):
    """Upright (EXIF), RGB, at most 2600 px a side (plenty for a 1080x1920 story), in a
    child process: a 24-megapixel camera photo opened inside the workbench took the
    whole workbench down."""
    r = subprocess.run([sys.executable, "-c", _TO_JPEG, src, dest], capture_output=True, text=True)
    if r.returncode or not os.path.exists(dest):
        raise RuntimeError(f"could not read the picture: {r.stderr[-300:]}")


def _container_status(cid):
    return (_tool("INSTAGRAM_GET_POST_STATUS", {"creation_id": cid}) or {}).get("status_code")


def _wait_container(cid, beat, timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        sc = _container_status(cid)
        if sc in ("FINISHED", "PUBLISHED", "ERROR", "EXPIRED"):
            return sc
        beat()
        time.sleep(6)
    return "TIMEOUT"


# ---------------------------------------------------------------- the run

PREVIEWS = f"{BASE}/previews"


def _save_preview(engine, fid, src, out, line, is_image):
    """A small copy of what the story looks like, kept after the work files are gone.
    Taken from the finished video by ffmpeg, so nothing is drawn twice in this process."""
    os.makedirs(PREVIEWS, exist_ok=True)
    path = f"{PREVIEWS}/{fid}.jpg"
    subprocess.run([engine.FF, "-y", "-loglevel", "error", "-ss", "1", "-i", out, "-frames:v", "1",
                    "-vf", "scale=540:960", "-q:v", "3", path], check=True)
    return path


def _run(dry_run=False, limit=None, prepare=False, ignore_daily_cap=False, only=None):
    status = {"state": "running", "dry_run": dry_run, "started": _now(), "heartbeat": _now(),
              "results": [], "message": ""}

    def beat(msg=None):
        status["heartbeat"] = _now()
        if msg:
            status["message"] = msg
        _save(STATUS_PATH, status)

    try:
        beat("starting")
        _ensure_deps()
        try:
            status["music_added"] = _sync_music(json.load(open(CFG_PATH)))
        except Exception as e:              # the Mixkit tracks still serve
            status["music_error"] = str(e)[:200]
        import importlib, story_engine
        importlib.reload(story_engine)
        cfg = json.load(open(CFG_PATH))
        if cfg.get("paused") and not dry_run and not prepare:
            status["state"] = "done"
            status["paused"] = True
            status["finished"] = _now()
            beat("paused: stories_config.json has \"paused\": true, so nothing was published")
            return
        if cfg.get("require_approval") and not dry_run and not prepare \
                and cfg.get("approved_day") != _panama_day(_now()):
            # the owner approves each day's stories on WhatsApp; without today's yes, nothing goes up
            status["state"] = "done"
            status["awaiting_approval"] = True
            status["finished"] = _now()
            beat("waiting for today's approval on WhatsApp, so nothing was published")
            return
        ig = cfg["ig_user_id"]
        lang = cfg.get("language", "en")        # one language per story: "en" or "es"
        log = _load(LOG_PATH, {"items": {}, "text_idx": 0})
        os.makedirs(WORK, exist_ok=True)

        q = _tool("INSTAGRAM_GET_IG_USER_CONTENT_PUBLISHING_LIMIT", {"ig_user_id": ig})
        q = (q.get("data") or [{}])[0]
        total = (q.get("config") or {}).get("quota_total", 100)
        used = q.get("quota_usage", 0)
        status["quota"] = {"used": used, "total": total}
        room = max(0, total - used - 2)

        files = _mixed_order(_list_inbox(cfg), log, cfg.get("ranks"))
        run_looks = []                      # a dry run saves no log: its looks are kept here
        status["found"] = len(files)
        beat(f"{len(files)} file(s) in the inbox")

        per_day = int(cfg.get("per_day", MAX_PER_RUN))
        today = _panama_day(_now())
        stream = cfg.get("stream")
        done_today = sum(1 for it in log["items"].values()
                         if it.get("status") == "published" and it.get("published_at")
                         and _panama_day(it["published_at"]) == today and it.get("stream") == stream)
        status["today"] = {"per_day": per_day, "already_published": done_today}
        published_now = 0
        day_room = MAX_PER_RUN if ignore_daily_cap else per_day - done_today
        cap = max(0, min(MAX_PER_RUN, room, day_room, limit if limit else MAX_PER_RUN))
        for f in files:
            fid, name = f["id"], f.get("name", "")
            if only and name not in only and fid not in only:
                continue                    # a run for chosen files leaves the rest alone
            it = log["items"].get(fid) or {"name": name, "attempts": 0}
            it.setdefault("stream", cfg.get("stream"))
            row = {"name": name}
            status["results"].append(row)

            if it.get("status") == "failed":
                row["result"] = "skipped (failed before)"
                continue
            if it.get("status") != "published" and published_now >= cap:
                row["result"] = "waiting for the next run (daily cap or quota)"
                continue
            try:
                # A container from an earlier, interrupted run: find out whether it went out.
                if it.get("status") != "published" and it.get("container_id") and not dry_run:
                    sc = _container_status(it["container_id"])
                    if sc == "PUBLISHED":
                        it.update(status="published", published_at=it.get("published_at") or _now())
                    elif sc != "FINISHED":
                        it.pop("container_id", None)

                if it.get("status") != "published":
                    beat(f"preparing {name}")
                    if not it.get("container_id"):
                        mime = f.get("mimeType", "")
                        raw = os.path.join(WORK, fid + ".raw")
                        _download(f, raw)
                        if mime.startswith("image/"):
                            src = os.path.join(WORK, fid + ".jpg")
                            _to_jpeg(raw, src)
                        else:
                            src = os.path.join(WORK, fid + ".video")
                            os.replace(raw, src)

                        designed = (mime.startswith("image/") and cfg.get("as_is_9x16", True)
                                    and story_engine.is_finished_story(src))
                        caption = (cfg.get("captions") or {}).get(name)
                        if designed:
                            it["as_is"] = True              # already a designed story: only the song is added
                            it["line"] = ""
                        elif caption:
                            # a line written for this very photo (the config's "captions")
                            it["text_en"] = caption if isinstance(caption, str) else caption.get("en")
                            it["text_es"] = None if isinstance(caption, str) else caption.get("es")
                            it["line"] = (it["text_es"] if lang == "es" and it["text_es"] else it["text_en"])
                        elif TOPIC_LINES.get(_topic(name)):
                            # a photo from a topic folder: the topic's own lines, in turn
                            tp = _topic(name)
                            ti = log.setdefault("topic_idx", {})
                            texts = TOPIC_LINES[tp][ti.get(tp, 0) % len(TOPIC_LINES[tp])]
                            ti[tp] = ti.get(tp, 0) + 1                    # a dry run never saves it
                            it["text_es"], it["text_en"] = texts
                            it["line"] = it["text_es"] if lang == "es" else it["text_en"]
                        else:
                            recent = sorted((x for x in log["items"].values() if x.get("published_at")),
                                            key=lambda x: x["published_at"])[-3:]
                            texts = None
                            if _topic(name) not in {_topic(x.get("name", "")) for x in recent}:
                                texts = _filename_text(name)
                            if not texts:
                                texts = TEXTS[log.get("text_idx", 0) % len(TEXTS)]
                                log["text_idx"] = log.get("text_idx", 0) + 1   # a dry run never saves it
                            it["text_es"], it["text_en"] = texts
                            it["line"] = it["text_es"] if lang == "es" else it["text_en"]
                        trk = _choose_track(log)
                        title = TOPIC_TITLES.get(_topic(name))
                        look = None
                        pill = True
                        mode = cfg.get("look_mode", "classic")
                        if designed:
                            style = None
                        elif mode == "classic":
                            # the design as first approved, always the same; shokogi.com on about one
                            # story in three (not when either of the last two carried it)
                            style = "classic"
                            last = sorted((x for x in log["items"].values() if x.get("style")),
                                          key=lambda x: x.get("updated") or "")[-2:]
                            cta = SALES_CTA.get(_topic(name))
                            it["pill"] = bool(cta) and not any(x.get("pill") for x in last)
                            pill = f"{cta} · shokogi.com" if it["pill"] else False
                        elif cfg.get("looks", True):
                            # a freshly drawn story look, unlike the ones just before it
                            style = "look"
                            look = {"seed": random.randrange(1 << 30), "emoji": TOPIC_EMOJI.get(_topic(name), []),
                                    "mode": mode,
                                    "sales": bool(SALES_CTA.get(_topic(name))),
                                    "cta": (SALES_CTA[_topic(name)] + " · shokogi.com") if SALES_CTA.get(_topic(name)) else None,
                                    "recent": ([x["look"] for x in sorted(
                                        (x for x in log["items"].values() if x.get("look")),
                                        key=lambda x: x.get("updated") or "")]
                                        + (run_looks if dry_run else []))[-3:]}
                        else:
                            style = _choose_style(log, cfg, title, mime.startswith("image/"))
                        it["style"] = style

                        beat(f"rendering {name}")
                        out = os.path.join(WORK, fid + "_story.mp4")
                        story_engine.make_story(src, out, it["line"], track=trk, designed=designed,
                                                style=style if style in story_engine.STYLES else "classic",
                                                title=title, look=look, pill=pill)
                        if look is not None:
                            it["look"] = look.get("drawn")
                            run_looks.append(it["look"])
                        it["track"] = trk["file"]
                        it["track_title"] = trk.get("title")
                        it["preview"] = _save_preview(story_engine, fid, src, out, it["line"],
                                                      mime.startswith("image/"))

                        beat(f"uploading {name}")
                        up, err = upload_local_file(out)
                        if err:
                            raise RuntimeError(f"upload: {err}")
                        s3key = (up.get("data") or up).get("s3key")
                        c = _tool("INSTAGRAM_POST_IG_USER_MEDIA", {
                            "ig_user_id": ig, "media_type": "STORIES",
                            "video_file": {"name": f"shokogi_story_{fid}.mp4", "mimetype": "video/mp4", "s3key": s3key}})
                        it["container_id"] = c["id"]
                        it["updated"] = _now()
                        if not dry_run:
                            log["items"][fid] = it
                            _save(LOG_PATH, log)

                    beat(f"waiting for Instagram to process {name}")
                    sc = _wait_container(it["container_id"], beat)
                    if sc == "PUBLISHED":
                        it.update(status="published", published_at=_now())
                    elif sc != "FINISHED":
                        it.pop("container_id", None)
                        raise RuntimeError(f"Instagram could not process the video ({sc})")
                    elif dry_run:
                        published_now += 1
                        row.update(result="dry run: container ready, not published",
                                   container_id=it["container_id"], line=it.get("line") or "as designed, song only",
                                   track=it.get("track_title"), preview=it.get("preview"))
                        continue
                    elif prepare:
                        # everything but the publish: the next real run publishes exactly this
                        published_now += 1
                        it["prepared_at"] = it["updated"] = _now()
                        log["items"][fid] = it
                        _save(LOG_PATH, log)
                        row.update(result="prepared: container ready, not published",
                                   container_id=it["container_id"], line=it.get("line") or "as designed, song only",
                                   track=it.get("track_title"), preview=it.get("preview"))
                        continue
                    else:
                        beat(f"publishing {name}")
                        try:
                            p = _tool("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {
                                "ig_user_id": ig, "creation_id": it["container_id"], "max_wait_seconds": 60}, retries=0)
                            it["media_id"] = p.get("id")
                        except RuntimeError:
                            # The answer may have been lost on the way back: ask Instagram itself.
                            time.sleep(10)
                            if _container_status(it["container_id"]) != "PUBLISHED":
                                raise
                        it.update(status="published", published_at=_now())
                        published_now += 1
                        row["fresh"] = True
                    it["updated"] = _now()
                    log["items"][fid] = it
                    _save(LOG_PATH, log)

                if not dry_run:
                    beat(f"moving {name} to the published folder")
                    _tool("GOOGLEDRIVE_MOVE_FILE", {"file_id": fid, "add_parents": cfg["done"]})
                    it["moved_at"] = _now()
                    log["items"][fid] = it
                    _save(LOG_PATH, log)
                    row.update(result="published" if row.pop("fresh", False) else "published earlier, moved now",
                               line=it.get("line") or it.get("text_en") or "as designed, song only",
                               track=it.get("track_title"), media_id=it.get("media_id"))
            except Exception as e:
                it["attempts"] = it.get("attempts", 0) + 1
                it["error"] = str(e)[:500]
                it["updated"] = _now()
                if it["attempts"] >= MAX_ATTEMPTS and it.get("status") != "published":
                    it["status"] = "failed"
                if not dry_run:
                    log["items"][fid] = it
                    _save(LOG_PATH, log)
                row.update(result="error", error=str(e)[:300], attempts=it["attempts"])
            finally:
                for p in os.listdir(WORK):
                    if p.startswith(fid):
                        os.remove(os.path.join(WORK, p))

        status["state"] = "done"
        status["finished"] = _now()
        if not dry_run:
            status["backup"] = _backup_state()
        beat("finished")
    except Exception as e:
        status["state"] = "error"
        status["error"] = f"{e}\n{traceback.format_exc()[-1500:]}"
        status["finished"] = _now()
        status["backup"] = _backup_state()
        beat("stopped with an error")


# ---------------------------------------------------------------- WhatsApp approval
# The morning preview: prepare the day's stories, send one image of them to the
# owner (stories/wa.py, run where the Green-API credentials are), and publish only
# the stories in that image, only after a yes on the same day.

APPROVAL_PATH = f"{BASE}/stories_approval.json"


def approval_sheet():
    """After start(prepare=True): one image of the prepared stories, left to right,
    at a public link that lasts an hour, and today's approval record."""
    import requests
    from PIL import Image
    st = _load(STATUS_PATH, {})
    rows = [r for r in st.get("results", []) if str(r.get("result", "")).startswith("prepared") and r.get("preview")]
    if not rows:
        return {"error": "nothing prepared"}
    sheet = Image.new("RGB", (len(rows) * 540 + (len(rows) - 1) * 20, 960), (235, 235, 235))
    for i, r in enumerate(rows):
        sheet.paste(Image.open(r["preview"]).convert("RGB").resize((540, 960)), (i * 560, 0))
    path = f"{PREVIEWS}/approval_sheet.jpg"
    sheet.save(path, quality=86)
    up, err = upload_local_file(path)
    if err:
        return {"error": f"upload: {err}"}
    link = requests.get((up.get("data") or up).get("s3_url"), allow_redirects=False, timeout=30).headers.get("location")
    rec = {"day": _panama_day(_now()), "items": [{"name": r["name"], "line": r.get("line")} for r in rows],
           "sheet_url": link, "sent_at": None, "decision": None}
    _save(APPROVAL_PATH, rec)
    rec["backup"] = _backup_state()
    return rec


def approval_record():
    return _load(APPROVAL_PATH, {})


def approval_mark(**fields):
    rec = _load(APPROVAL_PATH, {})
    rec.update(fields)
    _save(APPROVAL_PATH, rec)
    _backup_state()
    return rec


def approve_today():
    """Record the owner's yes for today; returns the names of the stories it covers."""
    cfg = json.load(open(CFG_PATH))
    cfg["approved_day"] = _panama_day(_now())
    _save(CFG_PATH, cfg)
    _backup_state()
    return [i["name"] for i in approval_record().get("items", [])]


_THREAD = globals().get("_THREAD")    # survive a second exec() of this file


def start(dry_run=False, limit=None, prepare=False, ignore_daily_cap=False, only=None):
    """Begin a run in the background. Refuses if one is already going."""
    global _THREAD
    st = _load(STATUS_PATH, {})
    if _THREAD and _THREAD.is_alive():
        print("already running"); return
    if st.get("state") == "running":
        age = time.time() - _dt.datetime.strptime(st["heartbeat"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.timezone.utc).timestamp()
        if age < STALE_SECS:
            print(f"another run is active (heartbeat {int(age)}s ago)"); return
    # written before the thread starts, so a wait() straight after never reads the last run's result
    _save(STATUS_PATH, {"state": "running", "dry_run": dry_run, "started": _now(), "heartbeat": _now(),
                        "results": [], "message": "starting"})
    _THREAD = threading.Thread(target=_run, daemon=True, kwargs={
        "dry_run": dry_run, "limit": limit, "prepare": prepare, "ignore_daily_cap": ignore_daily_cap,
        "only": only})
    _THREAD.start()
    print("started")


def wait(seconds=40):
    """Block up to `seconds`, then print the status. Keep it well under the caller's
    tool timeout: the MCP client gives up on a workbench call after about 60 s."""
    t0 = time.time()
    st = {}
    while time.time() - t0 < seconds:
        st = _load(STATUS_PATH, {}) or st     # a read can miss while the file is replaced
        if st and st.get("state") != "running":
            break
        time.sleep(4)
    if st.get("state") == "running":
        age = time.time() - _dt.datetime.strptime(st["heartbeat"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=_dt.timezone.utc).timestamp()
        if age > STALE_SECS or (_THREAD is not None and not _THREAD.is_alive()):
            time.sleep(2)
            st = _load(STATUS_PATH, {}) or st      # the thread may have finished a moment ago
            if st.get("state") == "running":
                st["state"] = "stalled"
    print(json.dumps(st, ensure_ascii=False, indent=1))
    return st
