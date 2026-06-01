#!/usr/bin/env python3
"""Morning Stories runner — posts 2 stories: a hook + a reshare of the AM feed card.

Two phases (same public-URL reason as feed posts):
  --render-only   render hook + reshare story images into queue/, record .stories_pending.json
  --publish-only  post both as STORIES via the IG API

The reshare uses the image of the most recent AM feed post (from state.json history),
falling back to the next queued single if history isn't available.

Env: IG_USER_ID, IG_ACCESS_TOKEN, GITHUB_REPOSITORY, GITHUB_REF_NAME (or IMAGE_BASE_OVERRIDE)
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import render_story

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
MANIFEST = ROOT / "queue" / "manifest.json"
PENDING = ROOT / ".stories_pending.json"
STORY_BANK = ROOT / "story_bank.json"
GRAPH = "https://graph.instagram.com/v25.0"
HOOK_STYLES = ["dark", "midnight"]


def load_env_file():
    env = ROOT / ".env"
    if env.exists():
        for raw in env.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def write_state(s):
    STATE.write_text(json.dumps(s, indent=2) + "\n")


def graph_post(path, params):
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def graph_get(path, params):
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def wait_ready(cid, token, timeout=180):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        d = graph_get(cid, {"fields": "status_code", "access_token": token})
        last = d
        if d.get("status_code") in {"FINISHED", "ERROR", "EXPIRED"}:
            return d
        time.sleep(5)
    return last or {"status_code": "TIMEOUT"}


def _latest_am_feed_image():
    """Image rel-path of the most recent posted AM single; else next queued single."""
    state = read_state()
    for h in reversed(state.get("history", [])):
        if h.get("slot") == "am" and h.get("image"):
            return h["image"]
    # fallback: next unposted single in the manifest
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        for it in m["items"]:
            if it["slot"] == "am" and not it.get("posted") and it.get("images"):
                return it["images"][0]
    return None


def render_only():
    state = read_state()
    bank = json.loads(STORY_BANK.read_text())
    hooks = bank["hooks"]

    hi = state.get("story_hook_i", 0)
    hook = hooks[hi % len(hooks)]
    hook_style = HOOK_STYLES[state.get("story_style_i", 0) % len(HOOK_STYLES)]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    (ROOT / "queue").mkdir(exist_ok=True)
    hook_rel = f"queue/story-hook-{stamp}.jpg"
    render_story.draw_hook(hook, ROOT / hook_rel, style=hook_style)

    pend = {"hook": hook_rel}
    feed_img = _latest_am_feed_image()
    if feed_img and (ROOT / feed_img).exists():
        reshare_rel = f"queue/story-reshare-{stamp}.jpg"
        render_story.draw_reshare(ROOT / feed_img, ROOT / reshare_rel, style="light")
        pend["reshare"] = reshare_rel
    else:
        print("WARN: no feed image found to reshare; hook only", file=sys.stderr)

    PENDING.write_text(json.dumps(pend) + "\n")
    state["story_hook_i"] = (hi + 1) % len(hooks)
    state["story_style_i"] = state.get("story_style_i", 0) + 1
    write_state(state)
    print(f"Story render: hook={hook_rel} reshare={pend.get('reshare','(none)')}")
    return 0


def _public_base():
    override = os.getenv("IMAGE_BASE_OVERRIDE", "")
    if override:
        return override.rstrip("/")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    branch = os.getenv("GITHUB_REF_NAME", "main") or "main"
    return f"https://raw.githubusercontent.com/{repo}/{branch}" if repo else ""


def _post_story(user_id, token, url):
    created = graph_post(f"{user_id}/media",
                         {"image_url": url, "media_type": "STORIES", "access_token": token})
    cid = created.get("id")
    if not cid:
        raise RuntimeError(f"story container failed: {json.dumps(created)}")
    st = wait_ready(cid, token)
    if st.get("status_code") not in {"FINISHED", None}:
        raise RuntimeError(f"story not ready: {json.dumps(st)}")
    return graph_post(f"{user_id}/media_publish", {"creation_id": cid, "access_token": token})


def publish_only():
    load_env_file()
    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    base = _public_base()
    if not user_id or not token or not base:
        print("ERROR: missing creds or base URL", file=sys.stderr)
        return 2
    if not PENDING.exists():
        print("ERROR: no .stories_pending.json", file=sys.stderr)
        return 2
    pend = json.loads(PENDING.read_text())

    order = [k for k in ("hook", "reshare") if k in pend]
    posted = []
    for k in order:
        url = f"{base}/{urllib.parse.quote(pend[k])}"
        print(f"Posting story [{k}]: {url}")
        try:
            pub = _post_story(user_id, token, url)
            print(f"  published: {json.dumps(pub)}")
            posted.append({"kind": k, "id": pub.get("id")})
        except Exception as e:
            print(f"  STORY FAILED [{k}]: {e}", file=sys.stderr)

    state = read_state()
    state.setdefault("story_history", []).append(
        {"at": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "posted": posted})
    state["story_history"] = state["story_history"][-120:]
    write_state(state)
    PENDING.unlink(missing_ok=True)
    return 0 if posted else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--publish-only", action="store_true")
    args = ap.parse_args()
    if args.render_only:
        return render_only()
    if args.publish_only:
        return publish_only()
    render_only()
    return publish_only()


if __name__ == "__main__":
    raise SystemExit(main())
