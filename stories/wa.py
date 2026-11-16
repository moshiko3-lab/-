#!/usr/bin/env python3
"""WhatsApp for the stories: the morning preview, and the owner's answer.

    python3 stories/wa.py status
    python3 stories/wa.py send --image sheet.jpg --caption-file caption.txt
    python3 stories/wa.py send-url --url https://... --caption-file caption.txt
    python3 stories/wa.py text --message "..."
    python3 stories/wa.py check --since 1794830000

Same gateway and credentials as bloowatch/send.py (Green-API, read from the
environment: GREENAPI_ID, GREENAPI_TOKEN, GREENAPI_URL, optionally
GREENAPI_MEDIA), and the same reading of a reply as bloowatch/approval.py:
a whole reply or its first word, "stop" words checked before "go" words.
Credentials never appear in output, arguments or logs.

Every message this file sends ends with MARK, so anything in the chat
without it was typed by a person. The reply is looked for in both
journals: typed on the account's own phone it is outgoing, typed from
another phone it is incoming.
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

TO = os.environ.get("STORIES_WA_TO", "50762596666@c.us")   # the owner, +507 6259 6666
MARK = "#SHOKOGI-STORIES"

STOP = ("עצור", "עצרי", "עצרו", "לא", "בטל", "בטלי", "אל תעלה", "אל תפרסם",
        "רגע", "חכה", "stop", "no", "cancel", "hold", "wait")
GO = ("כן", "אישור", "מאושר", "מאשר", "אשר", "תעלה", "פרסם", "שלח", "אוקיי", "אוקי",
      "סבבה", "ok", "okay", "yes", "go", "approved", "👍", "✅", "👌")
EDGE = " \t\r\n.!?,;:\"'״׳`*_-–—()[]…"


def creds():
    ident, token = os.environ.get("GREENAPI_ID", ""), os.environ.get("GREENAPI_TOKEN", "")
    base = (os.environ.get("GREENAPI_URL") or "").rstrip("/")
    if not (ident and token and base):
        missing = [n for n, v in (("GREENAPI_ID", ident), ("GREENAPI_TOKEN", token), ("GREENAPI_URL", base)) if not v]
        sys.exit(json.dumps({"ok": False, "error": "missing environment variables: " + ", ".join(missing)}))
    media = (os.environ.get("GREENAPI_MEDIA") or base).rstrip("/")
    return ident, token, base, media


def call(url, body=None, ctype=None, timeout=120):
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype} if ctype else {})
    wait = 2
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace") or "null")
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"Green-API answered HTTP {e.code}")
        except urllib.error.URLError as e:
            last = e
        if attempt < 2:
            time.sleep(wait)
            wait *= 3
    raise RuntimeError("Green-API did not answer after three tries")


def multipart(fields, path):
    b = uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out += [f"--{b}", f'Content-Disposition: form-data; name="{k}"', "", str(v)]
    head = "\r\n".join(out).encode("utf-8") + b"\r\n"
    name = os.path.basename(path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    filepart = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode("utf-8") + open(path, "rb").read() + b"\r\n"
    return head + filepart + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def _text(m):
    for k in ("textMessage", "caption"):
        if m.get(k):
            return str(m[k])
    ext = m.get("extendedTextMessage")
    return str(ext.get("text") or "") if isinstance(ext, dict) else str(ext or "")


def verdict(text):
    said = " ".join(str(text or "").split()).strip(EDGE).lower()
    if not said:
        return ""
    for words, answer in ((STOP, "stop"), (GO, "go")):
        for w in words:
            if said == w or said.startswith(w + " ") or said.startswith(w + ","):
                return answer
    return ""


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("send"); s.add_argument("--image", required=True); s.add_argument("--caption-file", required=True)
    u = sub.add_parser("send-url"); u.add_argument("--url", required=True); u.add_argument("--caption-file", required=True)
    t = sub.add_parser("text"); t.add_argument("--message", required=True)
    c = sub.add_parser("check"); c.add_argument("--since", type=float, required=True)
    a = ap.parse_args()
    ident, token, base, media = creds()

    if a.cmd == "status":
        st = call(f"{base}/waInstance{ident}/getStateInstance/{token}")
        print(json.dumps({"ok": True, "state": (st or {}).get("stateInstance"), "to": TO}))
    elif a.cmd == "send":
        caption = open(a.caption_file, encoding="utf-8").read().strip() + "\n\n" + MARK
        body, ctype = multipart({"chatId": TO, "caption": caption[:1000]}, a.image)
        r = call(f"{media}/waInstance{ident}/sendFileByUpload/{token}", body, ctype, timeout=180)
        print(json.dumps({"ok": True, "id": (r or {}).get("idMessage"), "sent_at": time.time()}))
    elif a.cmd == "send-url":
        # Green-API fetches the image itself: for a machine whose network cannot reach the file
        caption = open(a.caption_file, encoding="utf-8").read().strip() + "\n\n" + MARK
        body = json.dumps({"chatId": TO, "urlFile": a.url, "fileName": "shokogi-stories.jpg",
                           "caption": caption[:1000]}).encode("utf-8")
        r = call(f"{base}/waInstance{ident}/sendFileByUrl/{token}", body, "application/json", timeout=180)
        print(json.dumps({"ok": True, "id": (r or {}).get("idMessage"), "sent_at": time.time()}))
    elif a.cmd == "text":
        body = json.dumps({"chatId": TO, "message": a.message.strip() + "\n\n" + MARK}).encode("utf-8")
        r = call(f"{base}/waInstance{ident}/sendMessage/{token}", body, "application/json")
        print(json.dumps({"ok": True, "id": (r or {}).get("idMessage")}))
    elif a.cmd == "check":
        rows, reached = [], False
        for journal in ("lastOutgoingMessages", "lastIncomingMessages"):
            try:
                rows += call(f"{base}/waInstance{ident}/{journal}/{token}?minutes=1440") or []
                reached = True
            except Exception:
                pass
        if not reached:
            print(json.dumps({"ok": False, "decision": "unknown", "error": "neither journal could be read"}))
            return
        said = sorted((m.get("timestamp") or 0, _text(m)) for m in rows
                      if m.get("chatId") == TO and (m.get("timestamp") or 0) >= a.since
                      and _text(m).strip() and MARK not in _text(m))
        decision, when, text = "silent", 0, ""
        for stamp, t in said:                    # the latest answer that is an answer wins
            v = verdict(t)
            if v:
                decision, when, text = v, stamp, t
        print(json.dumps({"ok": True, "decision": decision, "when": when, "said": text[:120]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
