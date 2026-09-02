#!/usr/bin/env python3
"""Put a message on WhatsApp, through whichever gateway is configured.

    python3 send.py --to staff --text rota.txt --file board.png
    python3 send.py --to +50762596666 --text hello.txt
    python3 send.py --to staff --text rota.txt --dry-run

Runs on the machine that can reach the gateway, which is not the machine
that builds the message; both gateways are unreachable from the container
Bloowatch is read from. So this file is fetched from the repository by the
sandbox, and the message is handed to it as files.

Two gateways, one shape. TimelinesAI is what the school uses today and it
meters automated messages -- fifty a month on the plan it is on, against a
need nearer five hundred. Green-API charges for the connection rather than
the message. Nothing above the gateway changes: the rota, the board and
the forecast are built the same way either side of the move, and which one
is in use is decided by which credentials are in the environment.

    GREENAPI_ID / GREENAPI_TOKEN   -> Green-API
      (and GREENAPI_URL, the instance's own host from the console)
    TIMELINESAI_TOKEN              -> TimelinesAI

Never put a token in a file, a log, or an argument: they come from the
environment so they do not end up in shell history or a transcript.
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, "whatsapp.json")

TL = "https://app.timelines.ai/integrations/api"
# Green-API gives each instance its own host -- the console shows it as
# apiUrl, e.g. https://7107.api.greenapi.com -- so it is read from the
# environment rather than guessed. mediaUrl is usually the same host.
GREEN = os.environ.get("GREENAPI_URL") or "https://api.green-api.com"
GREEN_MEDIA = (os.environ.get("GREENAPI_MEDIA") or os.environ.get("GREENAPI_URL")
               or "https://media.green-api.com")

CAPTION_MAX = 1024          # both gateways cut a caption here, as WhatsApp does


def book(path=BOOK):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def target(name, groups):
    """Where a message is going, as both gateways want it spelled.

    A group is addressed by its WhatsApp id everywhere; TimelinesAI wants
    its own chat number instead, which is why both are written down.
    """
    g = groups.get(name)
    if g:
        return {"jid": g["jid"], "chat_id": str(g["chat_id"]), "name": name}
    n = "".join(ch for ch in name if ch.isdigit())
    if not n:
        raise SystemExit("unknown destination %r -- a group name or a phone" % name)
    return {"jid": n + "@c.us", "chat_id": None, "name": "+" + n}


def _multipart(fields, files):
    """Build a form-data body without pulling in a dependency."""
    line = b"\r\n"
    edge = "----shokogi" + uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        if v is None:
            continue
        out.append(("--" + edge).encode())
        out.append(('Content-Disposition: form-data; name="%s"' % k).encode())
        out.append(b"")
        out.append(str(v).encode("utf-8"))
    for k, path in files.items():
        if not path:
            continue
        kind = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            blob = f.read()
        out.append(("--" + edge).encode())
        out.append(('Content-Disposition: form-data; name="%s"; filename="%s"'
                    % (k, os.path.basename(path))).encode())
        out.append(("Content-Type: " + kind).encode())
        out.append(b"")
        out.append(blob)
    out.append(("--" + edge + "--").encode())
    out.append(b"")
    return line.join(out), "multipart/form-data; boundary=" + edge


def _post(url, body, ctype, headers=None, timeout=180):
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", ctype)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def already_said(where, text, ident, token, minutes=720):
    """True when this exact message has already gone to this chat today.

    A reminder is short, fixed, and sent by a schedule, which makes it the
    one message a machine can plausibly send twice: a container restarts, a
    routine is re-run by hand, two schedules overlap for a day while one is
    being moved. The instructor cannot tell a duplicate from a correction,
    and stops reading either. Green-API's own outgoing journal is the right
    place to check, because it survives everything on this side dying.

    Failing to reach the journal is not a reason to hold the message: a
    reminder that never arrives is the worse of the two mistakes, so an
    unreachable journal answers "no".

    Measured limit: the journal takes a few seconds to show a message that
    has just gone out. Sending the same text twice within about a minute
    gets through; a minute later the same call skips. That is the right
    trade for what this guards against -- two schedules half an hour apart,
    a container that restarted, a routine re-run by hand -- and no help at
    all against a loop that sends twice in the same breath.
    """
    url = "%s/waInstance%s/lastOutgoingMessages/%s?minutes=%d" % (
        GREEN, ident, token, minutes)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            sent = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return False
    want = " ".join(text.split())
    for m in sent if isinstance(sent, list) else []:
        if m.get("chatId") != where["jid"]:
            continue
        had = m.get("textMessage") or m.get("extendedTextMessage") or ""
        if isinstance(had, dict):
            had = had.get("text") or ""
        if " ".join(str(had).split()) == want:
            return True
    return False


def via_timelines(where, text, path, token):
    if where["chat_id"] is None:
        body = json.dumps({"phone": where["name"],
                           "whatsapp_account_phone": book()["account"]["phone"],
                           "text": text}).encode("utf-8")
        return _post(TL + "/messages/", body, "application/json",
                     {"Authorization": "Bearer " + token})
    url = "%s/chats/%s/messages" % (TL, where["chat_id"])   # no trailing slash
    if path:
        body, ctype = _multipart({"text": text}, {"file": path})
    else:
        body, ctype = _multipart({"text": text}, {})
    return _post(url, body, ctype, {"Authorization": "Bearer " + token})


def via_green_url(where, text, url, ident, token, name="file.mp4"):
    """Send something Green-API is already holding, by its own link.

    Nothing is uploaded and nothing is downloaded first, which is why the
    day-off animations live here: the file went over once and every night
    after that is one call.
    """
    body = json.dumps({"chatId": where["jid"], "urlFile": url,
                       "fileName": name,
                       "caption": text[:CAPTION_MAX]}).encode("utf-8")
    return _post("%s/waInstance%s/sendFileByUrl/%s" % (GREEN, ident, token),
                 body, "application/json")


def via_green(where, text, path, ident, token):
    """Green-API: a text goes to sendMessage, a file to sendFileByUpload.

    The file call carries the text as its caption, so the picture and the
    rota arrive as one message rather than two -- the same shape we have
    today, and the reason the office reads it as one thing.
    """
    if path:
        url = "%s/waInstance%s/sendFileByUpload/%s" % (GREEN_MEDIA, ident, token)
        body, ctype = _multipart(
            {"chatId": where["jid"], "caption": text[:CAPTION_MAX],
             "fileName": os.path.basename(path)}, {"file": path})
        return _post(url, body, ctype)
    url = "%s/waInstance%s/sendMessage/%s" % (GREEN, ident, token)
    body = json.dumps({"chatId": where["jid"], "message": text}).encode("utf-8")
    return _post(url, body, "application/json")


def run_batch(path, gateway, ident, token, dry_run, once_today):
    """Send a whole plan in one run, and keep going when one of them fails.

    The alternative -- a message written out by hand, checked, and sent, once
    per person -- is what a busy morning actually costs: twelve instructors
    on one lesson slot is twelve chances to mistype a number or lose the
    invisible marks that keep Hebrew the right way round. Here the text goes
    from the file that built it to the gateway untouched.

    One failure does not stop the rest. Eleven reminders that arrived beat
    twelve that were abandoned halfway, and the ones that failed are named at
    the end so nobody has to read back through the output to find them.
    """
    with open(path, encoding="utf-8") as f:
        sends = json.load(f)
    if not gateway:
        print("error: no gateway configured. Set GREENAPI_ID and "
              "GREENAPI_TOKEN, or TIMELINESAI_TOKEN.", file=sys.stderr)
        return 1

    failed = []
    for i, s in enumerate(sends):
        where = target(s["phone"], {})
        line = {"name": s["name"], "to": where["name"],
                "chatId": where["jid"], "chars": len(s["text"])}
        if dry_run:
            print(json.dumps(line, ensure_ascii=False))
            continue
        if once_today and gateway == "green" and already_said(
                where, s["text"], ident, token):
            line["skipped"] = "already sent today"
            print(json.dumps(line, ensure_ascii=False))
            continue
        if gateway == "green":
            code, said = via_green(where, s["text"], "", ident, token)
        else:
            code, said = via_timelines(where, s["text"], "", token)
        line["code"] = code
        line["said"] = said.strip()[:120]
        print(json.dumps(line, ensure_ascii=False))
        if code != 200:
            failed.append(s["name"])
        if i + 1 < len(sends):
            time.sleep(1)

    if failed:
        print("FAILED: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--to", default="",
                    help="a group name from whatsapp.json (staff, surfers_he, "
                         "surfers_en) or a phone number")
    ap.add_argument("--text", default="", help="file holding the message")
    ap.add_argument("--batch", default="",
                    help="a plan from rota.py --plan: every message and who "
                         "it goes to, sent in one run. Nothing is retyped "
                         "between building a message and sending it.")
    ap.add_argument("--file", default="", help="a picture to send with it")
    ap.add_argument("--url", default="",
                    help="send something the gateway already holds, by link. "
                         "Green-API only; nothing is uploaded.")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would be sent, and send nothing")
    ap.add_argument("--once-today", action="store_true",
                    help="skip if this exact message already went to this chat "
                         "today. For the reminders, which a restart or an "
                         "overlapping schedule could otherwise send twice.")
    a = ap.parse_args()

    if bool(a.batch) == bool(a.to):
        print("error: give either --batch or --to, not both and not neither",
              file=sys.stderr)
        return 2
    if a.to and not a.text:
        print("error: --to needs --text", file=sys.stderr)
        return 2

    gid = os.environ.get("GREENAPI_ID")
    gtok = os.environ.get("GREENAPI_TOKEN")
    ttok = os.environ.get("TIMELINESAI_TOKEN")
    gateway = "green" if (gid and gtok) else ("timelines" if ttok else "")

    if a.batch:
        return run_batch(a.batch, gateway, gid, gtok, a.dry_run, a.once_today)

    groups = book()["groups"]
    where = target(a.to, groups)
    with open(a.text, encoding="utf-8") as f:
        text = f.read().rstrip("\n")

    if a.url and gateway != "green":
        print("error: --url is Green-API only", file=sys.stderr)
        return 1
    if (a.file or a.url) and len(text) > CAPTION_MAX:
        print("note: %d characters of caption, %d is the limit -- send the "
              "picture with a short caption and the rest as its own message"
              % (len(text), CAPTION_MAX), file=sys.stderr)

    if a.dry_run or not gateway:
        if not gateway and not a.dry_run:
            print("error: no gateway configured. Set GREENAPI_ID and "
                  "GREENAPI_TOKEN, or TIMELINESAI_TOKEN.", file=sys.stderr)
        print(json.dumps({"gateway": gateway or "none", "to": where["name"],
                          "chatId": where["jid"], "chars": len(text),
                          "file": a.file or a.url or None},
                         ensure_ascii=False))
        return 0 if a.dry_run else 1

    if a.once_today and gateway == "green" and already_said(where, text,
                                                            gid, gtok):
        print(json.dumps({"skipped": "already sent today",
                          "to": where["name"], "chatId": where["jid"]},
                         ensure_ascii=False))
        return 0

    if gateway == "green" and a.url:
        code, said = via_green_url(where, text, a.url, gid, gtok,
                                   os.path.basename(a.url.split("?")[0]))
    elif gateway == "green":
        code, said = via_green(where, text, a.file or "", gid, gtok)
    else:
        code, said = via_timelines(where, text, a.file or "", ttok)

    print(code, said[:400])
    # Green-API answers 200 with an idMessage; TimelinesAI with status ok
    ok = code == 200 and ('"idMessage"' in said or '"status": "ok"' in said)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
