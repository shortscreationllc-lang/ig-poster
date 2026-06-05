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

import re
import render_video
import render_audio
import captions
from daily_run import (graph_post, wait_ready, load_env_file, _public_base,
                       read_state, write_state, QUEUE_DIR, ROOT)

PENDING = ROOT / ".pending_reel.json"

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


# AUTO rotation — every reel pulls the next recipe so format + style vary post to
# post (and the caption + beat rotate independently). Mix of single-message reels
# and multi-scene "carousel" sequence reels. Value-based, privacy-safe.
ROTATION = [
    {"type": "stat", "kicker": "THE NUMBER", "stat": "90%", "style": "blackout",
     "headline": "decide whether to keep watching in the first 3 seconds",
     "hook": "90% of viewers decide whether to keep watching in the first 3 seconds."},
    {"type": "statement", "headline": "THE HOOK IS 90% OF THE POST.", "style": "navyorange",
     "hook": "Your hook is 90% of the post — the first line does almost all the work."},
    {"type": "quote", "style": "dark",
     "headline": "If they don't stop scrolling, nothing else you made even matters.",
     "hook": "If they don't stop scrolling, nothing else you made even matters."},
    {"type": "checklist", "headline": "Post-ready checklist", "style": "blackout",
     "bullets": ["Hook in the first line", "One idea per post", "Caption adds context", "Clear reason to follow"],
     "hook": "The short-form posting checklist — run every video through this before you publish."},
    {"type": "sequence", "style": "blackout",
     "hook": "3 edits that keep people watching your short-form videos to the end.",
     "scenes": [{"kicker": "PLAYBOOK", "headline": "3 edits that keep people watching", "swipe": True},
                {"n": 1, "headline": "Cut the dead air", "body": "Tighten every pause between words — momentum holds attention."},
                {"n": 2, "headline": "Add a cut every 2-3 sec", "body": "Fresh motion resets the eye and stops the scroll."},
                {"n": 3, "headline": "End on a reason to rewatch", "body": "A loop or payoff quietly doubles your watch time."},
                {"kicker": "YOUR MOVE", "headline": "Follow for one of these every few days.", "body": "@josephborroto"}]},
    {"type": "stat", "kicker": "THE NUMBER", "stat": "3 SEC", "style": "navyorange",
     "headline": "is all you get before they scroll past you",
     "hook": "You get about 3 seconds before someone scrolls past your video."},
    {"type": "statement", "headline": "POST LESS. EDIT HARDER.", "style": "dark",
     "hook": "Post less, edit harder — one tight short-form video beats five lazy ones."},
    {"type": "sequence", "style": "navyorange",
     "hook": "3 ways to stop the scroll on short-form video.",
     "scenes": [{"kicker": "PLAYBOOK", "headline": "3 ways to stop the scroll", "swipe": True},
                {"n": 1, "headline": "Open on motion", "body": "Start mid-action, not on a static face."},
                {"n": 2, "headline": "Cut the intro", "body": "Delete every second before the actual point."},
                {"n": 3, "headline": "Say the payoff first", "body": "Lead with the result, then explain how."},
                {"kicker": "YOUR MOVE", "headline": "Follow for more short-form tips.", "body": "@josephborroto"}]},
    {"type": "statement", "headline": "STOP MAKING FORGETTABLE CONTENT.", "style": "navyorange",
     "hook": "Most short-form content isn't bad — it's forgettable. Make one thing memorable."},
    {"type": "stat", "kicker": "THE NUMBER", "stat": "2X", "style": "blackout",
     "headline": "more watch time when you cut the first 2 seconds",
     "hook": "Cutting the first 2 seconds of your video can double your watch time."},
    {"type": "quote", "style": "dark",
     "headline": "Your content doesn't have a reach problem. It has a hook problem.",
     "hook": "Your content doesn't have a reach problem — it has a hook problem."},
    {"type": "statement", "headline": "CONSISTENCY BEATS GOING VIRAL.", "style": "blackout",
     "hook": "Consistency beats going viral once — show up and the algorithm follows."},
    {"type": "checklist", "headline": "Before you hit post", "style": "navyorange",
     "bullets": ["Does the first line stop the scroll?", "Is there one clear idea?",
                 "Would you send it to a friend?", "Is there a reason to follow?"],
     "hook": "The 4-question check every short-form video should pass before you post it."},
    {"type": "sequence", "style": "blackout",
     "hook": "3 hooks that work in any niche for short-form video.",
     "scenes": [{"kicker": "PLAYBOOK", "headline": "3 hooks that work in any niche", "swipe": True},
                {"n": 1, "headline": "The mistake hook", "body": "\"Stop doing this if you want more views.\""},
                {"n": 2, "headline": "The number hook", "body": "\"3 things I'd change about your content.\""},
                {"n": 3, "headline": "The result hook", "body": "\"This got 1M views — here's why.\""},
                {"kicker": "YOUR MOVE", "headline": "Follow for more hooks like these.", "body": "@josephborroto"}]},
]


def _prune_old_reels(keep=5):
    reels = sorted(QUEUE_DIR.glob("reel-*.mp4"))
    for old in reels[:-keep]:
        try:
            old.unlink()
        except Exception:
            pass


def _reel_key(spec):
    h = spec.get("hook") or spec.get("headline") or ""
    return re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()[:60]


def _pick(kind):
    st = read_state()
    i = st.get("reel_i", 0); cap_i = st.get("reel_cap_i", 0); aud_i = st.get("reel_audio_i", 0)
    if kind == "auto":
        # Skip any item posted in the last several reels so nothing repeats soon.
        recent = st.get("reel_recent", [])
        n = len(ROTATION); spec = ROTATION[i % n]
        for step in range(n):
            cand = ROTATION[(i + step) % n]
            if _reel_key(cand) not in recent:
                spec = cand; i = i + step; break
        item, hook, style = spec, spec["hook"], spec.get("style", "blackout")
        st["reel_recent"] = (recent + [_reel_key(spec)])[-7:]
    else:
        bucket = CONTENT.get(kind) or CONTENT["stat"]
        it, hk, style = bucket[i % len(bucket)]; item, hook = it, hk
    st["reel_i"] = i + 1
    st["reel_cap_i"] = cap_i + 1       # rotate caption style
    st["reel_audio_i"] = aud_i + 1     # rotate beat
    write_state(st)
    caption = captions.caption_for(hook, cap_i)   # SEO-rotating caption
    return item, caption, style, aud_i


def render(kind):
    QUEUE_DIR.mkdir(exist_ok=True)
    _prune_old_reels()
    item, caption, style, aud_i = _pick(kind)
    rel = f"queue/reel-{int(time.time())}.mp4"; out = str(ROOT / rel)
    if item.get("type") == "sequence":
        render_video.video_sequence(item["scenes"], out, style=style)
    else:
        render_video.render_video(item, out, style=style)
    beat = render_audio.add_beat(out, aud_i)   # rotating copyright-safe beat
    PENDING.write_text(json.dumps({"rel": rel, "caption": caption, "type": item.get("type"),
                                   "style": style, "beat": beat}) + "\n")
    print(f"rendered reel -> {rel} (type={item.get('type')} style={style} beat={beat})")


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
