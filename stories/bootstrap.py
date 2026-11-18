"""Bring the Composio sandbox back to working order, whatever is left of it.

The sandbox's /mnt/files has come back empty more than once (a new sandbox does not
always get the old storage). Everything the stories need can be fetched again:

* the code: story_engine.py and run_daily.py, from this branch on GitHub;
* the fonts: Figtree and Barlow Condensed (the site's), Caveat, Noto Color Emoji;
* the music: the upbeat Mixkit tracks below, each with where its liveliest ten
  seconds start;
* the state: stories_config.json, stories_log.json and stories_approval.json, from
  one file in Google Drive, shokogi_stories_state.json, which run_daily.py rewrites
  after every run and every approval step.

Every scheduled task starts with:

    import requests; exec(requests.get(BOOTSTRAP_URL, timeout=60).text); ensure()

ensure() fetches only what is missing (the code always, so the sandbox runs what is
on the branch) and prints one line saying what it restored.
"""
import json
import os

import requests

RAW = "https://raw.githubusercontent.com/moshiko3-lab/-/claude/shokogi-stories-instagram-vmh09p/stories/"
HOME = "/mnt/files"
STATE_NAME = "shokogi_stories_state.json"
STATE_FILES = {"config": "stories_config.json", "log": "stories_log.json", "approval": "stories_approval.json"}

_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {
    "Figtree.ttf": _GF + "figtree/Figtree%5Bwght%5D.ttf",
    "BarlowCondensed-Bold.ttf": _GF + "barlowcondensed/BarlowCondensed-Bold.ttf",
    "BarlowCondensed-ExtraBold.ttf": _GF + "barlowcondensed/BarlowCondensed-ExtraBold.ttf",
    "Caveat.ttf": _GF + "caveat/Caveat%5Bwght%5D.ttf",
    # the CBDT build: Pillow cannot draw the COLRv1 one that google/fonts carries
    "NotoColorEmoji.ttf": "https://github.com/googlefonts/noto-emoji/raw/v2.047/fonts/NotoColorEmoji.ttf",
}

# Mixkit (Stock Music Free License), chosen for a strong beat and tempo, then by title
# and genre (no Christmas, children's or slow tracks): id, title, liveliest start (s)
MUSIC = [
    ("157", "Infected Vibes", 58.0), ("1007", "Move Your Body", 31.7), ("813", "Magical moment", 70.2),
    ("961", "I Wanna Know 2", 35.1), ("1146", "I'm Not The Only One", 53.6), ("780", "Okay", 95.6),
    ("832", "I'm Going Home", 66.3), ("852", "Music and Life", 81.4), ("1077", "Sounds Good", 5.9),
    ("839", "Tears of Joy", 61.0), ("801", "Happy Home", 1.5), ("953", "Feel Alive", 18.5),
    ("851", "Me and You", 55.6), ("860", "Year 2001", 14.6), ("1116", "Pick it Up", 28.8),
    ("519", "Motivation Gets in the Way", 19.0), ("1001", "I Do!", 58.0), ("78", "Sports Rock", 16.6),
    ("284", "Mi Gente", 41.4), ("1084", "Let's Play Africa", 0.0), ("963", "Just Keep Walking", 61.4),
    ("1103", "K.O. Games", 32.2), ("1210", "Can't Get You Off My Mind", 41.4), ("695", "Pop 05", 30.7),
    ("989", "Dirty Thinkin'", 35.6), ("623", "Deep Urban", 43.9), ("872", "Gimme that Groove!", 39.5),
    ("130", "Tech House vibes", 37.1), ("400", "C.B.P.D", 54.1), ("371", "Cat Walk", 29.3),
    ("738", "Hip Hop 02", 0.0), ("466", "Games Worldbeat", 0.0), ("250", "Island Beat", 16.1),
    ("51", "Sports Highlights", 0.0),
]
import threading as _threading
_LOCK = _threading.Lock()
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _get(url, headers=None, timeout=90):
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers or {}, timeout=timeout)
            if r.status_code == 200:
                return r.content
        except Exception:
            pass
    raise RuntimeError(f"could not fetch {url}")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{_threading.get_ident()}.part"      # its own name: several threads write the catalog
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _drive(slug, args):
    r, err = run_composio_tool(slug, args)          # noqa: F821  (a workbench helper)
    if err:
        raise RuntimeError(f"{slug}: {err}")
    return r.get("data", r) if isinstance(r, dict) else r


def _count(cat_path):
    """How many Mixkit tracks the catalog lists (it is rewritten while tracks arrive)."""
    for p in (cat_path, cat_path + ".tmp"):
        try:
            return sum(1 for t in json.load(open(p)) if not t.get("own"))
        except Exception:
            pass
    return 0


def state_file():
    """The Drive file that holds the state, or None."""
    d = _drive("GOOGLEDRIVE_FIND_FILE", {"q": f"name = '{STATE_NAME}' and trashed = false", "pageSize": 10,
                                         "fields": "files(id,name,modifiedTime)"})
    files = sorted(d.get("files") or [], key=lambda f: f.get("modifiedTime", ""), reverse=True)
    return files[0] if files else None


def restore_state():
    f = state_file()
    if not f:
        return "no state file in Drive"
    d = _drive("GOOGLEDRIVE_DOWNLOAD_FILE", {"fileId": f["id"]})
    url = d.get("s3url") or (d.get("downloaded_file_content") or {}).get("s3url")
    state = json.loads(_get(url).decode("utf-8"))
    done = []
    for key, name in STATE_FILES.items():
        if state.get(key) is not None:
            _write(f"{HOME}/{name}", json.dumps(state[key], ensure_ascii=False, indent=1).encode("utf-8"))
            done.append(key)
    return "state from Drive (" + ", ".join(done) + f", saved {state.get('saved_at')})"


def ensure():
    did = []
    for fn in ("story_engine.py", "run_daily.py"):
        _write(f"{HOME}/{fn}", _get(RAW + fn, timeout=30))
    for fn, url in FONTS.items():
        if not os.path.exists(f"{HOME}/brand/{fn}"):
            _write(f"{HOME}/brand/{fn}", _get(url))
            did.append(fn)
    cat_path = f"{HOME}/music/catalog.json"
    if _count(cat_path) < len(MUSIC):
        # in the background (about a minute and a half for all of them): the catalog
        # lists each track as soon as it is there, so a render can start meanwhile
        import threading
        from concurrent.futures import ThreadPoolExecutor

        def fetch(t):
            p = f"{HOME}/music/{t[0]}.mp3"
            try:
                if not os.path.exists(p):
                    _write(p, _get(f"https://assets.mixkit.co/music/{t[0]}/{t[0]}.mp3", _UA))
            except Exception:
                return
            with _LOCK:
                have = {i for i, _, _ in MUSIC if os.path.exists(f"{HOME}/music/{i}.mp3")}
                own = []
                for q in (cat_path, cat_path + ".tmp"):       # the school's own tracks stay listed
                    try:
                        own = [t for t in json.load(open(q)) if t.get("own")]
                        break
                    except Exception:
                        pass
                cat = [{"id": i, "title": ti, "file": f"{HOME}/music/{i}.mp3", "upbeat": True, "start": st,
                        "source": "https://mixkit.co (Stock Music Free License)"} for i, ti, st in MUSIC if i in have]
                _write(cat_path, json.dumps(cat + own, ensure_ascii=False, indent=1).encode("utf-8"))

        def run():
            with ThreadPoolExecutor(8) as ex:
                list(ex.map(fetch, MUSIC))
        threading.Thread(target=run, daemon=True).start()
        did.append("music (downloading in the background)")
    if not os.path.exists(f"{HOME}/{STATE_FILES['config']}"):
        did.append(restore_state())
    os.makedirs(f"{HOME}/previews", exist_ok=True)
    print("bootstrap: code refreshed" + ("; restored " + "; ".join(did) if did else "; nothing else missing"))
