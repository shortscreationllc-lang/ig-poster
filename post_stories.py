#!/usr/bin/env python3
"""Morning Stories runner — posts a story sequence (hook/fix, series, or quote).

Two phases (same public-URL reason as feed posts):
  --render-only   render the day's story sequence into queue/, record .stories_pending.json
  --publish-only  post each slide as a STORY via the IG API

Stories stand on their own (hook->fix pair, multi-part series, or a quote).
No feed-post reshare (removed 2026-06-01 — it was redundant/mismatched).

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

# Each time-of-day gets its own visual signature so morning/afternoon/evening
# stories never look like the same thing reposted. Same brand (orange + League
# Spartan), different palette per slot.
SLOT_PALETTE = {
    "morning":   "bone",      # warm cream — bright, "good morning" energy
    "afternoon": "midnight",  # cool navy — midday contrast
    "evening":   "dark",      # deep black — night vibe
}


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


def _render_slide(slide, out_path, style):
    """Route a story slide to the right renderer by its role."""
    role = slide.get("role", "hook")
    if role == "fix":
        render_story.draw_fix(slide, out_path, style=style)
    elif role == "value":
        render_story.draw_fix(slide, out_path, style=style)  # value = heading+bullets, same layout
    else:  # hook or single (big statement)
        render_story.draw_hook(slide, out_path, style=style)


def render_only():
    """Render the next story SEQUENCE.

    A sequence with 2 slides is a hook→fix pair (the fix answers the hook).
    A 1-slide sequence is a standalone statement/value story.
    A 'series' sequence expands to intro + one slide per item.
    No feed reshare — stories stand alone.
    """
    state = read_state()
    bank = json.loads(STORY_BANK.read_text())
    seqs = bank["sequences"]

    si = state.get("story_seq_i", 0)
    seq = seqs[si % len(seqs)]
    base = state.get("story_style_i", 0)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    (ROOT / "queue").mkdir(exist_ok=True)

    # time-of-day palette: morning/afternoon/evening each look distinct
    slot_kind = os.getenv("SLOT_KIND", "morning").strip().lower()
    slot_style = SLOT_PALETTE.get(slot_kind, "dark")

    ordered = []  # list of rel paths, in posting order

    if "series" in seq:
        # multi-part: intro slide + one numbered slide per item (single brand style
        # for visual consistency across the run) — keyed to time of day
        s = seq["series"]
        style = slot_style
        intro = dict(s["intro"])
        rel0 = f"queue/story-{seq['id']}-intro-{stamp}.jpg"
        render_story.draw_hook(intro, ROOT / rel0, style=style)
        ordered.append(rel0)
        total = len(s["items"])
        for n, it in enumerate(s["items"], start=1):
            slide = dict(it); slide["series_label"] = s.get("label", "")
            rel = f"queue/story-{seq['id']}-{n}-{stamp}.jpg"
            render_story.draw_series_slide(slide, n, total, ROOT / rel, style=style)
            ordered.append(rel)
    else:
        slides = seq["slides"]
        for n, slide in enumerate(slides):
            # within a hook->fix pair, nudge the shade slightly for separation
            # but stay anchored to the time-of-day palette
            style = slot_style if n == 0 else (
                "midnight" if slot_style != "midnight" else "dark")
            rel = f"queue/story-{seq['id']}-{n}-{stamp}.jpg"
            _render_slide(slide, ROOT / rel, style)
            ordered.append(rel)

    # NOTE: the feed-post "reshare" story was removed (2026-06-01) — re-posting
    # the day's feed image as a story was redundant and could grab a mismatched
    # image. Stories now stand on their own (hook/fix/series/quote only).

    PENDING.write_text(json.dumps({"slides": ordered, "seq_id": seq["id"]}) + "\n")
    state["story_seq_i"] = (si + 1) % len(seqs)
    state["story_style_i"] = base + 1
    write_state(state)
    print(f"Story sequence '{seq['id']}': {len(ordered)} stories")
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

    slides = pend.get("slides", [])
    posted = []
    for n, rel in enumerate(slides):
        url = f"{base}/{urllib.parse.quote(rel)}"
        print(f"Posting story [{n+1}/{len(slides)}]: {url}")
        try:
            pub = _post_story(user_id, token, url)
            print(f"  published: {json.dumps(pub)}")
            posted.append({"slide": n, "id": pub.get("id")})
        except Exception as e:
            print(f"  STORY FAILED [{n}]: {e}", file=sys.stderr)

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
