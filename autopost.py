#!/usr/bin/env python3
"""
Auto-poster v2: posts Joseph's REAL approved videos from Dropbox to Instagram.

Replaces the old generated-card poster (daily_run.py / post_reel.py renderers stay
untouched but disabled). Plan: vault Operations/Agent Pipeline — Build Plan.md.

Modes (autopost_config.json "mode", or --mode):
  practice  Runs on the real schedule, picks the video it WOULD post, checks
            everything it can without posting (Dropbox link, file size/format,
            caption, IG token), writes the report, emails it if Gmail is set up.
            Posts nothing, moves nothing.
  live      Posts the oldest captioned video in the queue folder as a Reel,
            reads it back from Instagram to prove it exists, moves the file to
            the posted folder, emails the permalink. Any failure exits non-zero
            and texts Joseph (if the SMS gateway secret exists).

Every other day at ~4:40 PM Miami time (his best reel hour from insights.json).
Cron fires twice a day; this script decides whether today is a posting day.
"""
import argparse, datetime, json, os, smtplib, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "autopost_config.json"
STATE = ROOT / "autopost_state.json"
LOG = ROOT / "autopost_log.md"
CAPTIONS = ROOT / "captions"
GRAPH = "https://graph.instagram.com/v25.0"
MIAMI = ZoneInfo("America/New_York")
VIDEO_EXT = (".mp4", ".mov", ".m4v")


# ---------- small helpers ----------
def load_env_file():
    env = ROOT / ".env"
    if env.exists():
        for raw in env.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def mask(value):
    """Keep secrets out of GitHub logs."""
    if value and os.getenv("GITHUB_ACTIONS"):
        print(f"::add-mask::{value}")


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def http_json(url, data=None, headers=None, method=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {body}") from None


# ---------- Dropbox ----------
class Dropbox:
    def __init__(self):
        key, secret, refresh = (os.getenv(k, "").strip() for k in
                                ("DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN"))
        if not (key and secret and refresh):
            raise RuntimeError("Dropbox secrets missing (DROPBOX_APP_KEY / _SECRET / _REFRESH_TOKEN)")
        data = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": refresh,
                                       "client_id": key, "client_secret": secret}).encode()
        self.token = http_json("https://api.dropboxapi.com/oauth2/token", data)["access_token"]
        mask(self.token)

    def rpc(self, endpoint, body):
        return http_json(f"https://api.dropboxapi.com/2/{endpoint}", json.dumps(body).encode(),
                         {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})

    def videos(self, folder):
        """Posts waiting in a folder, oldest first. Two shapes work:
          - a post folder:  <folder>/<any name>/  holding one video + one image (the cover)
          - a loose video:  <folder>/C9208.mp4  (cover = C9208.jpg / "C9208 cover.jpg" beside it)
        Each video entry gets "_post_folder" (or None) and "_cover" (image entry or None)."""
        try:
            res = self.rpc("files/list_folder", {"path": folder, "recursive": True, "include_media_info": True})
        except RuntimeError as e:
            if "not_found" in str(e):
                return []                                      # queue folder not created yet
            raise
        entries = res["entries"]
        while res.get("has_more"):
            res = self.rpc("files/list_folder/continue", {"cursor": res["cursor"]})
            entries += res["entries"]
        root = folder.rstrip("/").lower()
        files = [e for e in entries if e[".tag"] == "file"]
        is_img = lambda e: e["name"].lower().endswith((".jpg", ".jpeg", ".png"))
        parent = lambda e: e["path_lower"].rsplit("/", 1)[0]
        out = []
        for v in files:
            if not v["name"].lower().endswith(VIDEO_EXT):
                continue
            par = parent(v)
            if par == root:
                stem = v["name"].rsplit(".", 1)[0].lower()
                names = (stem, f"{stem} cover", f"{stem}_cover", f"{stem}-cover")
                cover = next((e for e in files if parent(e) == root and is_img(e)
                              and e["name"].lower().rsplit(".", 1)[0] in names), None)
                v["_post_folder"] = None
            elif par.count("/") == root.count("/") + 1:      # one level down = a post folder
                siblings = [e for e in files if parent(e) == par]
                if sum(e["name"].lower().endswith(VIDEO_EXT) for e in siblings) > 1:
                    continue                                   # ambiguous folder: skip, reported below
                cover = next((e for e in siblings if is_img(e)), None)
                v["_post_folder"] = next((e["path_display"] for e in entries
                                          if e[".tag"] == "folder" and e["path_lower"] == par), par)
            else:
                continue
            v["_cover"] = cover
            out.append(v)
        return sorted(out, key=lambda e: e.get("server_modified", ""))

    def temp_link(self, path):
        link = self.rpc("files/get_temporary_link", {"path": path})["link"]
        mask(link)
        return link

    def upload(self, local, path):
        with open(local, "rb") as f:
            data = f.read()
        arg = json.dumps({"path": path, "mode": "overwrite", "mute": True})
        return http_json("https://content.dropboxapi.com/2/files/upload", data,
                         {"Authorization": f"Bearer {self.token}", "Dropbox-API-Arg": arg,
                          "Content-Type": "application/octet-stream"}, timeout=600)["path_display"]

    def move(self, src, dest_folder):
        name = src.rsplit("/", 1)[-1]
        return self.rpc("files/move_v2", {"from_path": src, "to_path": f"{dest_folder}/{name}",
                                          "autorename": True})["metadata"]["path_display"]


def duration_ms(entry):
    info = (entry.get("media_info") or {}).get("metadata") or {}
    return info.get("duration")


def probe(url):
    """Width, height, codec, duration from the file itself (ffprobe reads only the header)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,codec_name:format=duration", "-of", "json", url],
            capture_output=True, text=True, timeout=90)
        d = json.loads(out.stdout or "{}")
        s = (d.get("streams") or [{}])[0]
        return {"width": s.get("width"), "height": s.get("height"), "codec": s.get("codec_name"),
                "duration_s": float((d.get("format") or {}).get("duration") or 0) or None}
    except Exception as e:
        return {"error": str(e)[:120]}


def shrink(dbx, link, tmp_path):
    """Oversized export (4K, 500 MB+): re-encode to 1080x1920 H.264 so Instagram takes it.
    Uploads to one fixed temp file in Dropbox (overwritten each time) and returns its link."""
    src, out = "/tmp/autopost_src", "/tmp/autopost_1080.mp4"
    urllib.request.urlretrieve(link, src)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True, timeout=1200)
    mb = os.path.getsize(out) / 1e6
    if mb > 290:
        raise RuntimeError(f"still {mb:.0f} MB after shrinking to 1080p")
    return dbx.temp_link(dbx.upload(out, tmp_path)), round(mb, 1)


# ---------- captions ----------
def caption_key(entry):
    return entry["id"].replace("id:", "")


def load_caption(entry):
    f = CAPTIONS / f"{caption_key(entry)}.json"
    if not f.exists():
        return None
    c = json.loads(f.read_text())
    text = c["caption"].strip()
    tags = " ".join(c.get("hashtags", []))
    full = f"{text}\n\n{tags}".strip()
    problems = []
    if "—" in full or "–" in full:
        problems.append("caption has a dash (Joseph's rule: none)")
    if len(full) > 2200:
        problems.append(f"caption is {len(full)} chars (IG max 2,200)")
    cap_rules = json.loads(CONFIG.read_text()).get("captions", {})
    if len(c.get("hashtags", [])) > cap_rules.get("max_hashtags", 5):
        problems.append(f"more than {cap_rules.get('max_hashtags', 5)} hashtags")
    problems += [f"caption writer flagged: {p}" for p in c.get("open_problems", [])]
    return {"text": full, "problems": problems, "file": f.name}


# ---------- Instagram ----------
def ig_get(path, params):
    return http_json(f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}", timeout=30)


def ig_post(path, params):
    return http_json(f"{GRAPH}/{path}", urllib.parse.urlencode(params).encode())


def ig_check(user_id, token):
    me = ig_get("me", {"fields": "user_id,username", "access_token": token})
    return me.get("username", "?")


def ig_publish_reel(user_id, token, video_url, caption, thumb_offset_ms=None, cover_url=None):
    params = {"media_type": "REELS", "video_url": video_url, "caption": caption,
              "share_to_feed": "true", "access_token": token}
    if cover_url:
        params["cover_url"] = cover_url      # his designed thumbnail wins over any frame
    elif thumb_offset_ms is not None:
        params["thumb_offset"] = str(int(thumb_offset_ms))
    cid = ig_post(f"{user_id}/media", params).get("id")
    if not cid:
        raise RuntimeError("Instagram did not create a video container")
    deadline = time.time() + 900
    status = {}
    while time.time() < deadline:
        status = ig_get(cid, {"fields": "status_code,status", "access_token": token})
        if status.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"):
            break
        time.sleep(10)
    if status.get("status_code") != "FINISHED":
        raise RuntimeError(f"Instagram could not process the video: {json.dumps(status)[:200]}")
    media_id = ig_post(f"{user_id}/media_publish", {"creation_id": cid, "access_token": token}).get("id")
    if not media_id:
        raise RuntimeError("Instagram publish returned no media id")
    # Prove it exists: the old poster ran green for 2.5 months posting nothing.
    for _ in range(6):
        try:
            m = ig_get(media_id, {"fields": "id,permalink,timestamp,media_type", "access_token": token})
            if m.get("permalink"):
                return m
        except RuntimeError:
            pass
        time.sleep(10)
    raise RuntimeError(f"Published media {media_id} could not be read back from Instagram")


# ---------- notices ----------
def send_mail(to, subject, body):
    user = os.getenv("GMAIL_USER", "shortscreationllc@gmail.com").strip()
    pw = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not (pw and to):
        print(f"  (notice not sent, Gmail app password not set up yet): {subject}")
        return False
    mask(pw)
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)
    return True


def notify_ok(subject, body):
    try:
        send_mail(os.getenv("NOTIFY_EMAIL", "shortscreationllc@gmail.com"), subject, body)
    except Exception as e:
        print(f"  WARN email failed: {e}", file=sys.stderr)


def notify_broken(short):
    """Text Joseph through his carrier's email-to-text address. Short, plain."""
    try:
        send_mail(os.getenv("SMS_GATEWAY", "").strip(), "", f"Auto-poster: {short}"[:150])
    except Exception as e:
        print(f"  WARN text failed: {e}", file=sys.stderr)


# ---------- schedule ----------
def is_posting_day(cfg, state, now, force):
    if force:
        return True, "forced run"
    if now.hour < cfg["post_hour_miami"]:
        return False, f"before {cfg['post_hour_miami']}:00 Miami time"
    last = state.get("last_action_date")
    today = now.date().isoformat()
    if last == today:
        return False, "already handled today"
    if last:
        gap = (now.date() - datetime.date.fromisoformat(last)).days
        if gap < cfg["every_n_days"]:
            return False, f"off day (every {cfg['every_n_days']} days, last {last})"
    return True, "posting day"



def log_entry(lines):
    head = "# Auto-poster log\n\nNewest at top. Written by autopost.py.\n\n"
    old = LOG.read_text()[len(head):] if LOG.exists() and LOG.read_text().startswith(head) else ""
    LOG.write_text(head + "\n".join(lines) + "\n\n" + old)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("\n".join(lines) + "\n")


# ---------- main ----------
def run(mode, force, dry):
    load_env_file()
    cfg = read_json(CONFIG, {})
    state = read_json(STATE, {"rehearsed": [], "posted": {}, "last_action_date": None})
    mode = mode or cfg["mode"]
    now = datetime.datetime.now(MIAMI)
    stamp = now.strftime("%Y-%m-%d %H:%M")

    go, why = is_posting_day(cfg, state, now, force)
    print(f"[{stamp} Miami] mode={mode}: {why}")
    if not go:
        return 0

    problems, notes = [], []
    dbx = Dropbox()
    folder = cfg["queue_folder"]
    videos = dbx.videos(folder)
    if mode == "practice" and not videos:
        folder = cfg["practice_source_folder"]           # nothing queued yet: rehearse on Finals
        videos = dbx.videos(folder)
    if mode == "practice":
        done = set(state.get("rehearsed", []))
        if videos and all(v["id"] in done for v in videos):
            state["rehearsed"], done = [], set()      # cycle through the folder again
    else:
        done = set(state.get("posted", {}).keys())
    # live mode never posts an uncaptioned video; it takes the next captioned one
    candidates = [v for v in videos if v["id"] not in done]
    if mode == "live":
        candidates = [v for v in candidates if load_caption(v)] or candidates
    video = candidates[0] if candidates else None

    if not video:
        problems.append(f"nothing to post: no new videos in {folder}")
    else:
        size_mb = round(video["size"] / 1e6, 1)
        cap = load_caption(video)
        link = dbx.temp_link(video["path_display"])
        info = probe(link)
        dur_ms = duration_ms(video) or (info.get("duration_s") or 0) * 1000
        notes += [f"- Video: `{video['name']}` ({size_mb} MB, {round(dur_ms / 1000) if dur_ms else '?'} s)",
                  f"- Format: {info.get('width')}x{info.get('height')} {info.get('codec')}" if "error" not in info
                  else f"- Format: could not read ({info['error']})"]
        oversize = size_mb > cfg["max_mb"]
        if oversize:
            notes.append(f"- Size: {size_mb} MB is over Instagram's {cfg['max_mb']} MB limit, so it gets shrunk to 1080p before posting")
        if info.get("width") and info.get("height") and info["width"] > info["height"]:
            problems.append("video is landscape, Reels need vertical 9:16")
        if not cap:
            problems.append(f"no caption written yet (captions/{caption_key(video)}.json)")
        else:
            problems += cap["problems"]
            notes.append("- Caption:\n\n" + "\n".join("  > " + l for l in cap["text"].splitlines()))
        thumb, cover_url = None, None
        cover = video.get("_cover")
        if video.get("_post_folder"):
            notes.insert(0, f"- Post folder: `{video['_post_folder']}`")
        if cover:
            cover_url = dbx.temp_link(cover["path_display"])
            ci = probe(cover_url)
            notes.append(f"- Cover: your thumbnail `{cover['name']}` ({ci.get('width')}x{ci.get('height')})")
            if ci.get("width") and ci.get("height") and abs(ci["width"] / ci["height"] - 9 / 16) > 0.02:
                notes.append("- Cover note: not 9:16, Instagram will crop it (design at 1080x1920)")
        elif cfg.get("cover_is_last_frame") and dur_ms:
            thumb = max(0, dur_ms - cfg.get("cover_frame_from_end_ms", 150))
            notes.append(f"- Cover: last frame at {round(thumb / 1000, 2)} s")
        else:
            notes.append("- Cover: Instagram default frame (no thumbnail image next to this video)")

    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    mask(token)
    try:
        notes.append(f"- Instagram: connected as @{ig_check(user_id, token)}")
    except Exception as e:
        problems.append(f"Instagram token check failed: {str(e)[:160]}")

    if mode == "practice" or dry:
        verdict = "WOULD POST" if not problems else "WOULD FAIL"
        lines = [f"## {stamp} · practice · {verdict}"] + notes + [f"- Problem: {p}" for p in problems]
        print("\n".join(lines))
        if not dry:
            log_entry(lines)
            if video:
                state.setdefault("rehearsed", []).append(video["id"])
            state["last_action_date"] = now.date().isoformat()
            STATE.write_text(json.dumps(state, indent=2) + "\n")
            subject = (f"Practice: would post {video['name']} today" if video and not problems
                       else f"Practice: today's post would have FAILED")
            notify_ok(subject, "\n".join(lines) + "\n\nNothing was posted. Practice mode.")
        return 1 if problems else 0

    # ---- live ----
    if problems:
        lines = [f"## {stamp} · live · NOT POSTED"] + notes + [f"- Problem: {p}" for p in problems]
        log_entry(lines)
        print("\n".join(lines), file=sys.stderr)
        notify_broken(problems[0])
        return 1
    try:
        if oversize:
            link, new_mb = shrink(dbx, link, cfg["temp_upload_path"])
            notes.append(f"- Shrunk to {new_mb} MB")
        try:
            media = ig_publish_reel(user_id, token, link, cap["text"], thumb, cover_url)
        except Exception as e:
            if not cover_url:
                raise
            # a thumbnail problem must never block the post: retry once without it
            notes.append(f"- Cover rejected by Instagram ({str(e)[:80]}), posted with the default frame")
            media = ig_publish_reel(user_id, token, link, cap["text"], thumb)
    except Exception as e:
        lines = [f"## {stamp} · live · FAILED"] + notes + [f"- Error: {str(e)[:300]}"]
        log_entry(lines)
        notify_broken(f"{video['name']} did not post to Instagram. {str(e)[:80]}")
        return 1
    moved_to = None
    try:
        moved_to = dbx.move(video.get("_post_folder") or video["path_display"], cfg["posted_folder"])
    except Exception as e:
        notify_broken(f"{video['name']} posted but the file did not move to Posted: {str(e)[:60]}")
    state.setdefault("posted", {})[video["id"]] = {
        "name": video["name"], "ig": media["permalink"], "at": media.get("timestamp"), "moved_to": moved_to}
    state["last_action_date"] = now.date().isoformat()
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    lines = [f"## {stamp} · live · POSTED", *notes, f"- Instagram: {media['permalink']}",
             f"- File moved to: `{moved_to}`" if moved_to else "- File NOT moved (see text)"]
    log_entry(lines)
    notify_ok(f"Live on Instagram: {video['name']}", "\n".join(lines))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["practice", "live"])
    ap.add_argument("--force", action="store_true", help="ignore the schedule and run now")
    ap.add_argument("--dry", action="store_true", help="report only; do not save state or send notices")
    a = ap.parse_args()
    sys.exit(run(a.mode, a.force, a.dry))
