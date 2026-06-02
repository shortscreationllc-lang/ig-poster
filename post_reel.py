#!/usr/bin/env python3
"""Render + publish ONE animated Reel to Instagram. Isolated from the image
pipeline so it can't disturb it. Two phases (like the image flow):
  --render   pick content, render the MP4 into queue/, write .pending_reel.json
  --publish  wait for the raw URL to go live, post as a REEL, record state

Run inside the workflow (where IG creds live). Curated, privacy-safe content
with SEO captions + hashtags.
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse
from pathlib import Path

import render_video
from daily_run import (graph_post, wait_ready, load_env_file, _public_base,
                       read_state, write_state, QUEUE_DIR, ROOT)

PENDING = ROOT / ".pending_reel.json"

HASHTAGS = ("#contentcreation #shortformvideo #videoediting #reels "
            "#reelsinstagram #contentstrategy #socialmediatips #videocontent "
            "#editingtips #contentcreator #growyourinstagram #hookwriting "
            "#videomarketing #instagramreels #digitalmarketing")

# Curated, privacy-safe content per type. (item, caption-hook, style)
CONTENT = {
    "stat": [
        ({"type": "stat", "kicker": "THE NUMBER", "stat": "90%",
          "headline": "decide whether to keep watching in the first 3 seconds"},
         "90% of people decide whether to keep watching in the first 3 seconds. Your hook is everything.",
         "blackout"),
        ({"type": "stat", "kicker": "THE NUMBER", "stat": "3 SEC",
          "headline": "is all you get before they scroll past you"},
         "You get about 3 seconds before someone scrolls past. Make them count.", "navyorange"),
    ],
    "statement": [
        ({"type": "statement", "headline": "THE HOOK IS 90% OF THE POST."},
         "The hook is 90% of the post. Nail the first line, the rest takes care of itself.", "blackout"),
        ({"type": "statement", "headline": "POST LESS. EDIT HARDER."},
         "Post less, edit harder. One tight video beats five lazy ones.", "navyorange"),
    ],
    "quote": [
        ({"type": "quote", "headline": "If they don't stop scrolling, nothing else you made even matters."},
         "If they don't stop scrolling, nothing else you made even matters.", "navyorange"),
    ],
    "checklist": [
        ({"type": "checklist", "headline": "Post-ready checklist",
          "bullets": ["Hook in the first line", "One idea per post",
                      "Caption adds context", "Clear reason to follow"]},
         "Run every post through this before you hit publish.", "dark"),
    ],
}


def _pick(kind):
    bucket = CONTENT.get(kind) or CONTENT["stat"]
    st = read_state()
    i = st.get("reel_i", 0)
    item, hook, style = bucket[i % len(bucket)]
    st["reel_i"] = i + 1
    write_state(st)
    caption = f"{hook}\n\nFollow @josephborroto for more.\n\n{HASHTAGS}"
    return item, caption, style


def render(kind):
    QUEUE_DIR.mkdir(exist_ok=True)
    item, caption, style = _pick(kind)
    rel = f"queue/reel-{int(time.time())}.mp4"
    render_video.render_video(item, str(ROOT / rel), style=style)
    PENDING.write_text(json.dumps({"rel": rel, "caption": caption,
                                   "type": item["type"], "style": style}) + "\n")
    print(f"rendered reel -> {rel} (type={item['type']} style={style})")


def _wait_raw(url, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    print("  raw video is live:", url)
                    return True
        except Exception:
            pass
        time.sleep(5)
    print("  WARN: raw video not confirmed live, trying publish anyway")
    return False


def publish_reel(user_id, token, video_url, caption):
    created = graph_post(f"{user_id}/media", {
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": "true", "access_token": token})
    cid = created.get("id")
    if not cid:
        raise RuntimeError(f"reel container failed: {json.dumps(created)}")
    print("  container:", cid, "— waiting for IG to process the video...")
    st = wait_ready(cid, token, timeout=600)  # video takes longer than images
    if st.get("status_code") not in {"FINISHED", None}:
        raise RuntimeError(f"reel not ready: {json.dumps(st)}")
    return graph_post(f"{user_id}/media_publish", {"creation_id": cid, "access_token": token})


def publish():
    load_env_file()
    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        print("ERROR: IG creds not set", file=sys.stderr); return 2
    if not PENDING.exists():
        print("ERROR: no .pending_reel.json (run --render first)", file=sys.stderr); return 2
    base = _public_base()
    if not base:
        print("ERROR: no public base URL", file=sys.stderr); return 2

    pend = json.loads(PENDING.read_text())
    url = f"{base}/{urllib.parse.quote(pend['rel'])}"
    print(f"Posting REEL '{pend['rel']}' -> {url}")
    _wait_raw(url)
    try:
        pub = publish_reel(user_id, token, url, pend["caption"])
    except Exception as e:
        print(f"REEL PUBLISH FAILED: {e}", file=sys.stderr); return 1
    print("Published REEL:", json.dumps(pub))
    # record in history so it's logged
    st = read_state()
    st.setdefault("history", []).append({
        "at": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "id": pend["rel"], "type": "reel", "slot": "video",
        "post_id": pub.get("id")})
    write_state(st)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--kind", default=os.getenv("KIND", "stat"))
    a = ap.parse_args()
    if a.render:
        render(a.kind); sys.exit(0)
    if a.publish:
        sys.exit(publish())
    print("specify --render or --publish", file=sys.stderr); sys.exit(2)
