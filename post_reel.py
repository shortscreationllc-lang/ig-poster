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
import random
import render_video
import render_audio
import captions
import weighting
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
    # --- EDITING & PRODUCTION CRAFT ---
    {"type": "statement", "headline": "CUT EVERY SILENCE.", "style": "blackout",
     "hook": "Cut every silence in your video — dead air is where people swipe away."},
    {"type": "checklist", "headline": "A tighter edit in 4 moves", "style": "navyorange",
     "bullets": ["Trim the pause between words", "Cut every 2-3 seconds", "Sync captions to the audio", "End on a clean loop"],
     "hook": "4 editing moves that make any short-form video tighter and more watchable."},
    # --- MISTAKES & MYTHS ---
    {"type": "statement", "headline": "YOU DON'T NEED A BETTER CAMERA.", "style": "navyorange",
     "hook": "You don't need a better camera — you need a better hook and a tighter edit."},
    {"type": "quote", "style": "dark",
     "headline": "Nobody cares how it was filmed. They care if it's worth watching.",
     "hook": "Nobody cares how your video was filmed — only whether it's worth watching."},
    # --- ALGORITHM & PLATFORM ---
    {"type": "stat", "kicker": "THE SIGNAL", "stat": "SENDS", "style": "blackout",
     "headline": "are the #1 thing growing your reach right now",
     "hook": "Shares in DMs are the #1 signal growing reach in 2026 — make content people send."},
    {"type": "statement", "headline": "REACH IS RENTED. TRUST IS OWNED.", "style": "dark",
     "hook": "Reach is rented; trust is owned — build content that earns trust, not just views."},
    # --- GETTING CLIENTS WITH VIDEO (business owners) ---
    {"type": "statement", "headline": "VIEWS DON'T PAY. CLIENTS DO.", "style": "blackout",
     "hook": "Views don't pay the bills — content that books clients does."},
    {"type": "checklist", "headline": "Make content that books clients", "style": "navyorange",
     "bullets": ["Speak to one customer problem", "Show proof you can solve it", "Make the next step obvious", "Post where buyers already scroll"],
     "hook": "How to make short-form that actually books clients, not just views."},
    {"type": "quote", "style": "navyorange",
     "headline": "Your best salesperson is a video that works while you sleep.",
     "hook": "Your best salesperson is a video that works while you sleep."},
    {"type": "sequence", "style": "blackout",
     "hook": "3 videos every business owner should be posting to get clients.",
     "scenes": [{"kicker": "FOR OWNERS", "headline": "3 videos that bring you clients", "swipe": True},
                {"n": 1, "headline": "Answer the #1 question", "body": "The thing every customer asks before they buy."},
                {"n": 2, "headline": "Show a before / after", "body": "Proof of the work beats any sales pitch."},
                {"n": 3, "headline": "Make the next step obvious", "body": "Tell them exactly how to start."},
                {"kicker": "YOUR MOVE", "headline": "Follow for content that books clients.", "body": "@josephborroto"}]},
    # --- MINDSET & CONSISTENCY ---
    {"type": "statement", "headline": "BORING + CONSISTENT BEATS PERFECT + RARE.", "style": "navyorange",
     "hook": "Boring and consistent beats perfect and rare — just keep showing up."},
    {"type": "stat", "kicker": "THE NUMBER", "stat": "90 DAYS", "style": "blackout",
     "headline": "is where most people quit — right before it works",
     "hook": "Most people quit posting at 90 days — right before the reach starts to compound."},
    # --- RESULTS & PROOF ---
    {"type": "statement", "headline": "SHOW THE PROOF, NOT THE THEORY.", "style": "dark",
     "hook": "Show the before-and-after, not the theory — proof sells better than promises."},
    # --- BEHIND THE SCENES / PROCESS ---
    {"type": "statement", "headline": "CONTENT IS A SYSTEM, NOT A MOOD.", "style": "blackout",
     "hook": "Content is a system, not a mood — build the system and it runs without motivation."},
    # --- TRENDS / WHAT'S WORKING ---
    {"type": "statement", "headline": "ADD B-ROLL. STOP TALKING AT THE CAMERA.", "style": "navyorange",
     "hook": "Pure talking-head is fading — pair your words with B-roll that shows it."},
    # --- X-POST REELS (animated tweet, Joseph's face + voice) ---
    {"type": "social", "style": "dark",
     "social": {"author": "Joseph Borroto", "handle": "@josephborroto", "verified": True,
                "initials": "JB", "headline": "I treat the camera like a client, not a camera. That one shift changed all my content.",
                "cta": "Here's exactly how I do it →"},
     "hook": "I treat the camera like a client, not a camera — that one shift changed all my content."},
    {"type": "social", "style": "midnight",
     "social": {"author": "Joseph Borroto", "handle": "@josephborroto", "verified": True,
                "initials": "JB", "headline": "Stop trying to sound like a 'content creator.' Just be yourself on camera.",
                "cta": "Here's how I stay myself →"},
     "hook": "Stop trying to sound like a content creator — just be yourself on camera."},
    {"type": "social", "style": "slate",
     "social": {"author": "Joseph Borroto", "handle": "@josephborroto", "verified": True,
                "initials": "JB", "headline": "Most people overthink their content. I just get it out — and that's why mine grows.",
                "cta": "Here's my posting system →"},
     "hook": "Most people overthink content. I just get it out — and that's why mine grows."},
    {"type": "social", "style": "ember",
     "social": {"author": "Joseph Borroto", "handle": "@josephborroto", "verified": True,
                "initials": "JB", "headline": "You don't need a better camera. You need a better first sentence."},
     "hook": "You don't need a better camera — you need a better first sentence."},
    # --- COMMENT REELS (animated comment + Joseph's verified reply) ---
    {"type": "comment", "style": "dark",
     "comment": {"author": "creator_mike", "initials": "CM", "text": "how do you make every video feel different? mine all blur together", "likes": "2.1k"},
     "reply": {"author": "Joseph Borroto", "initials": "JB", "verified": True, "text": "same energy, new angle every time. one idea, told 5 ways. never reinvent — re-angle.", "likes": "480"},
     "hook": "How to make every video feel different — same idea, new angle every time."},
    {"type": "comment", "style": "midnight",
     "comment": {"author": "samanthaedits", "initials": "SE", "text": "i post good content but nobody watches", "likes": "3.4k"},
     "reply": {"author": "Joseph Borroto", "initials": "JB", "verified": True, "text": "good content nobody sees = a weak hook. fix the first 3 seconds before anything else.", "likes": "612"},
     "hook": "Good content nobody sees is just a weak hook — fix the first 3 seconds."},
    {"type": "comment", "style": "slate",
     "comment": {"author": "quietkid.media", "initials": "QK", "text": "i feel so awkward on camera", "likes": "1.8k"},
     "reply": {"author": "Joseph Borroto", "initials": "JB", "verified": True, "text": "everyone does at first. talk to ONE person, not 'an audience.' it gets easy fast.", "likes": "390"},
     "hook": "Awkward on camera? Talk to one person, not an audience."},
    {"type": "comment", "style": "ember",
     "comment": {"author": "viral.chase", "initials": "VC", "text": "whats the actual secret to going viral?", "likes": "5.2k"},
     "reply": {"author": "Joseph Borroto", "initials": "JB", "verified": True, "text": "stop chasing viral. chase clarity. one idea said so well it's impossible to scroll past.", "likes": "830"},
     "hook": "Stop chasing viral. Chase clarity — one idea, impossible to scroll past."},
]


def _prune_old_reels(keep=5):
    for pat in ("reel-*.mp4", "reel-*.jpg"):
        old = sorted(QUEUE_DIR.glob(pat))[:-keep]
        for f in old:
            try:
                f.unlink()
            except Exception:
                pass


# A reel's first second is intentionally near-empty (text animates IN), so IG's
# auto-cover grabs a blank frame. We instead grab the FULLY-COMPOSED frame — the
# finished design — at a per-type "hero" moment and hand IG that as cover_url.
COVER_AT = {"statement": 3.0, "stat": 4.0, "quote": 4.0, "checklist": 6.5, "sequence": 1.0}


def _make_cover(mp4_path, typ, out_jpg):
    """Extract the hero frame (all text revealed) as a 1080x1920 JPG cover."""
    import imageio_ffmpeg, subprocess
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    secs = COVER_AT.get(typ, 3.0)
    subprocess.run([ff, "-y", "-ss", str(secs), "-i", mp4_path,
                    "-frames:v", "1", "-q:v", "2", out_jpg],
                   check=True, capture_output=True)
    return out_jpg


def _reel_key(spec):
    h = spec.get("hook") or spec.get("headline") or ""
    return re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()[:60]


# The looks a reel can wear — all the brand colors, in different treatments
# (orange-on-dark, white headline + orange number, full-orange/black, burnt,
# slate, cream). We ROTATE through these so the same format never looks the same
# two posts in a row.
VIDEO_STYLES = ["blackout", "navyorange", "dark", "midnight",
                "ember", "slate", "orangepop", "creamorange"]
# X-post reels only look right on DARK grounds (the blue CTA / grey reply card
# clash with the orange and cream looks), so they draw from this subset.
SOCIAL_STYLES = ["dark", "midnight", "slate", "ember"]


def _next_style(st, avoid=(), pool=None):
    """Pick a look that differs from the last few used (style_recent) and from any
    in `avoid` (e.g. others in the same trial batch) — strong variety, no repeats.
    `pool` restricts the candidate looks (e.g. dark-only for X-post reels)."""
    pool = pool or VIDEO_STYLES
    rec = st.get("style_recent", [])
    blocked = set(avoid) | set(rec[-4:])
    cands = ([s for s in pool if s not in blocked]
             or [s for s in pool if s not in set(avoid)] or list(pool))
    s = random.choice(cands)
    st["style_recent"] = (rec + [s])[-7:]
    return s


def _pick(kind):
    st = read_state()
    i = st.get("reel_i", 0); cap_i = st.get("reel_cap_i", 0); aud_i = st.get("reel_audio_i", 0)
    w = weighting.load_weights()
    cap_style = None
    if kind == "auto":
        # WEIGHTED pick: among recipes not used in the last 7 reels, score each by
        # what the insights loop has learned (format + style + topic), plus a dash
        # of exploration so we keep sampling everything and the loop keeps learning.
        recent = st.get("reel_recent", [])
        # Also steer clear of anything posted as a TRIAL — the two streams must
        # never overlap, or whichever posts second gets throttled as a duplicate.
        blocked = set(recent) | set(st.get("trial_recent", []))
        elig = [c for c in ROTATION if _reel_key(c) not in blocked] or list(ROTATION)
        spec = max(elig, key=lambda c: weighting.score_spec(c, w) + random.uniform(0, 0.15))
        item, hook, style = spec, spec["hook"], spec.get("style", "blackout")
        st["reel_recent"] = (recent + [_reel_key(spec)])[-7:]
        # Pin the caption shape the data likes best (falls back to rotation).
        cap_style = weighting.best_cap_style(w)
    else:
        bucket = CONTENT.get(kind) or CONTENT["stat"]
        it, hk, style = bucket[i % len(bucket)]; item, hook = it, hk
    # Rotate the LOOK every post (overrides the recipe's default) for variety.
    # X-post reels are restricted to dark grounds so the blue CTA never clashes.
    pool = SOCIAL_STYLES if item.get("type") in ("social", "comment") else None
    style = _next_style(st, pool=pool)
    st["reel_i"] = i + 1
    st["reel_cap_i"] = cap_i + 1       # rotate caption wording
    st["reel_audio_i"] = aud_i + 1     # rotate beat
    # Remember which beat this normal reel uses so trials can pick DIFFERENT music.
    st["beat_recent"] = (st.get("beat_recent", []) + [aud_i % len(render_audio.BEATS)])[-5:]
    write_state(st)
    eff_cap = cap_style if cap_style is not None else (cap_i % 6)
    caption = captions.caption_for(hook, cap_i, style=cap_style)   # SEO caption, learned shape
    pillar = weighting.pillar_of(hook or item.get("headline", ""))
    return item, caption, style, aud_i, pillar, eff_cap


def render(kind):
    QUEUE_DIR.mkdir(exist_ok=True)
    _prune_old_reels()
    item, caption, style, aud_i, pillar, cap_style = _pick(kind)
    rel = f"queue/reel-{int(time.time())}.mp4"; out = str(ROOT / rel)
    if item.get("type") == "sequence":
        render_video.video_sequence(item["scenes"], out, style=style)
    else:
        render_video.render_video(item, out, style=style)
    beat = render_audio.add_beat(out, aud_i)   # rotating copyright-safe beat
    # Custom cover = the finished, fully-revealed design (not IG's blank auto-grab).
    cover_rel = rel[:-4] + ".jpg"
    try:
        _make_cover(out, item.get("type"), str(ROOT / cover_rel))
    except Exception as e:
        print(f"  (cover render skipped: {e})"); cover_rel = None
    PENDING.write_text(json.dumps({"rel": rel, "caption": caption, "type": item.get("type"),
                                   "style": style, "beat": beat, "pillar": pillar,
                                   "cap_style": cap_style, "cover": cover_rel,
                                   "hook": item.get("hook") or item.get("headline", "")}) + "\n")
    print(f"rendered reel -> {rel} (type={item.get('type')} style={style} "
          f"pillar={pillar} cap_style={cap_style} beat={beat} cover={cover_rel})")


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


def publish_reel(user_id, token, video_url, caption, cover_url=None, trial_params=None):
    params = {"media_type": "REELS", "video_url": video_url, "caption": caption,
              "access_token": token}
    if trial_params:
        # TRIAL REEL — shown only to non-followers; no share_to_feed. graduation_strategy
        # MANUAL (you promote in-app) or SS_PERFORMANCE (IG auto-promotes winners).
        params["trial_params"] = json.dumps(trial_params)
        print("  trial:", trial_params)
    else:
        params["share_to_feed"] = "true"
    if cover_url:
        params["cover_url"] = cover_url   # the finished design as the Reel cover
        print("  cover:", cover_url)
    created = graph_post(f"{user_id}/media", params)
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
    cover_url = f"{base}/{urllib.parse.quote(pend['cover'])}" if pend.get("cover") else None
    print(f"Posting REEL '{pend['rel']}' -> {url}")
    _wait_raw(url)
    if cover_url:
        _wait_raw(cover_url)   # cover ships in the same commit, but confirm it's live
    try:
        pub = publish_reel(user_id, token, url, pend["caption"], cover_url=cover_url)
    except Exception as e:
        # A custom cover must never block the post — retry once without it.
        if cover_url:
            print(f"  cover rejected ({e}) — retrying without custom cover", file=sys.stderr)
            try:
                pub = publish_reel(user_id, token, url, pend["caption"])
            except Exception as e2:
                print(f"REEL PUBLISH FAILED: {e2}", file=sys.stderr); return 1
        else:
            print(f"REEL PUBLISH FAILED: {e}", file=sys.stderr); return 1
    print("Published REEL:", json.dumps(pub))
    # record in history so it's logged
    st = read_state()
    st.setdefault("history", []).append({
        "at": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "id": pend["rel"], "type": "reel", "slot": "video",
        "post_id": pub.get("id"),
        "tags": {"fmt": pend.get("type"), "style": pend.get("style"),
                 "pillar": pend.get("pillar"), "cap_style": pend.get("cap_style")},
        "hook": pend.get("hook", "")})
    st["history"] = st["history"][-200:]
    write_state(st)
    return 0


def publish_reel_as_story(user_id, token, video_url):
    created = graph_post(f"{user_id}/media", {
        "media_type": "STORIES", "video_url": video_url, "access_token": token})
    cid = created.get("id")
    if not cid:
        raise RuntimeError(f"story container failed: {json.dumps(created)}")
    st = wait_ready(cid, token, timeout=600)
    if st.get("status_code") not in {"FINISHED", None}:
        raise RuntimeError(f"story not ready: {json.dumps(st)}")
    return graph_post(f"{user_id}/media_publish", {"creation_id": cid, "access_token": token})


def publish_story():
    """Reshare the SAME thing we just posted to the feed, as the story — so the
    story always matches the day's post (consistent, not different content)."""
    load_env_file()
    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        print("ERROR: IG creds not set", file=sys.stderr); return 2
    if not PENDING.exists():
        print("No pending reel to reshare as story — skipping."); return 0
    base = _public_base()
    pend = json.loads(PENDING.read_text())
    url = f"{base}/{urllib.parse.quote(pend['rel'])}"
    print(f"Resharing the day's reel to the story (same content): {url}")
    _wait_raw(url)
    try:
        pub = publish_reel_as_story(user_id, token, url)
    except Exception as e:
        print(f"STORY RESHARE FAILED: {e}", file=sys.stderr); return 1
    print("Story posted:", json.dumps(pub))
    st = read_state()
    st.setdefault("story_history", []).append({
        "at": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "reshare_of": pend["rel"], "posted": [{"id": pub.get("id")}]})
    write_state(st)
    return 0


# ============================ TRIAL REELS (batch) ============================
# Trial reels are shown ONLY to non-followers — a cold-audience content lab. We
# fire a varied batch (distinct format + style + topic, no repeats), let IG (or
# you) graduate the winners to followers, and feed every trial's performance
# back into the same weights.json that steers the main rotation. Pure signal:
# cold viewers judge the CONTENT, not your follower relationship.
TRIAL_PENDING = ROOT / ".pending_trials.json"


def trials_remaining(target):
    """How many more trials to post today to reach `target` (the daily cap)."""
    st = read_state()
    today = time.strftime("%Y%m%d", time.gmtime())
    return max(0, target - st.get("trial_daily", {}).get(today, 0))


def _pick_trial_beat(st, used):
    """Pick a beat that DIFFERS from what normal reels recently used (beat_recent)
    and from the other trials in this same batch (`used`) — so a trial never shares
    music with something already on the feed."""
    n = len(render_audio.BEATS)
    avoid = set(used) | set(st.get("beat_recent", []))
    cands = [b for b in range(n) if b not in avoid]
    if not cands:                          # all recent — at least differ within batch
        cands = [b for b in range(n) if b not in set(used)] or list(range(n))
    return random.choice(cands)


def _pick_trial_batch(n):
    """Pick n recipes maximizing variety — distinct format, style, and topic —
    skipping anything used recently by EITHER stream (trials OR normal posts), so a
    trial never duplicates a reel that's already live (which would kill its reach)."""
    st = read_state()
    recent = st.get("trial_recent", [])
    # Block recipes already used by trials AND by recent normal posts.
    blocked = set(recent) | set(st.get("reel_recent", []))
    pool = [c for c in ROTATION if _reel_key(c) not in blocked]
    if len(pool) < n:                      # exhausted the catalog — fall back to trial-only
        pool = [c for c in ROTATION if _reel_key(c) not in set(recent)] or list(ROTATION)
    random.shuffle(pool)                   # break ties differently each run
    chosen, used_fmt, used_style, used_pillar = [], set(), set(), set()

    def gain(c):                           # how much new variety this adds
        p = weighting.pillar_of(c.get("hook") or c.get("headline", ""))
        return ((c.get("type") not in used_fmt) + (c.get("style") not in used_style)
                + (p not in used_pillar))

    while pool and len(chosen) < n:
        pool.sort(key=gain, reverse=True)
        c = pool.pop(0)
        chosen.append(c)
        used_fmt.add(c.get("type")); used_style.add(c.get("style"))
        used_pillar.add(weighting.pillar_of(c.get("hook") or c.get("headline", "")))
    st["trial_recent"] = (recent + [_reel_key(c) for c in chosen])[-14:]
    write_state(st)
    return chosen


def render_trials(n, strategy="SS_PERFORMANCE"):
    QUEUE_DIR.mkdir(exist_ok=True); _prune_old_reels(keep=12)
    batch = _pick_trial_batch(n)
    st = read_state(); cap_i = st.get("reel_cap_i", 0); aud_i = st.get("reel_audio_i", 0)
    w = weighting.load_weights()
    used_beats, used_styles = [], []       # keep beats AND looks distinct in-batch
    items = []
    for k, spec in enumerate(batch):
        rel = f"queue/reel-{int(time.time())}-{k}.mp4"; out = str(ROOT / rel)
        pool = SOCIAL_STYLES if spec.get("type") in ("social", "comment") else None
        style = _next_style(st, avoid=used_styles, pool=pool); used_styles.append(style)
        if spec.get("type") == "sequence":
            render_video.video_sequence(spec["scenes"], out, style=style)
        else:
            render_video.render_video(spec, out, style=style)
        bi = _pick_trial_beat(st, used_beats); used_beats.append(bi)
        beat = render_audio.add_beat(out, bi)
        cover_rel = rel[:-4] + ".jpg"
        try:
            _make_cover(out, spec.get("type"), str(ROOT / cover_rel))
        except Exception as e:
            print(f"  (cover skipped: {e})"); cover_rel = None
        hook = spec["hook"]
        cs = weighting.best_cap_style(w)
        caption = captions.caption_for(hook, cap_i + k, style=cs)
        items.append({"rel": rel, "cover": cover_rel, "caption": caption,
                      "type": spec.get("type"), "style": style,
                      "pillar": weighting.pillar_of(hook),
                      "cap_style": cs if cs is not None else (cap_i + k) % 6,
                      "beat": beat, "hook": hook})
        print(f"  trial {k+1}/{len(batch)}: {spec.get('type')}/{style}/{beat} -> {rel}")
    st = read_state()
    st["reel_cap_i"] = cap_i + len(batch); st["reel_audio_i"] = aud_i + len(batch)
    # Record the trial beats too, so the next normal reel also avoids them.
    st["beat_recent"] = (st.get("beat_recent", []) + used_beats)[-5:]
    write_state(st)
    TRIAL_PENDING.write_text(json.dumps({"strategy": strategy, "items": items}, indent=1) + "\n")
    print(f"rendered {len(items)} trial reels (strategy={strategy})")


def publish_trials():
    load_env_file()
    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        print("ERROR: IG creds not set", file=sys.stderr); return 2
    if not TRIAL_PENDING.exists():
        print("ERROR: no .pending_trials.json (run --render-trials N first)", file=sys.stderr); return 2
    base = _public_base()
    if not base:
        print("ERROR: no public base URL", file=sys.stderr); return 2
    data = json.loads(TRIAL_PENDING.read_text())
    strat = data.get("strategy", "SS_PERFORMANCE"); items = data.get("items", [])
    st = read_state(); today = time.strftime("%Y%m%d", time.gmtime()); posted = 0
    for idx, it in enumerate(items):
        url = f"{base}/{urllib.parse.quote(it['rel'])}"
        cover_url = f"{base}/{urllib.parse.quote(it['cover'])}" if it.get("cover") else None
        print(f"Posting TRIAL reel {idx+1}/{len(items)}: {it['rel']}")
        _wait_raw(url)
        if cover_url:
            _wait_raw(cover_url)
        tp = {"graduation_strategy": strat}
        try:
            pub = publish_reel(user_id, token, url, it["caption"], cover_url=cover_url, trial_params=tp)
        except Exception as e:
            # never let a cover block a trial — retry once without it (keep trial_params)
            if cover_url:
                print(f"  cover rejected ({e}) — retrying without cover", file=sys.stderr)
                try:
                    pub = publish_reel(user_id, token, url, it["caption"], trial_params=tp)
                except Exception as e2:
                    print(f"  TRIAL {idx+1} FAILED: {e2}", file=sys.stderr); continue
            else:
                print(f"  TRIAL {idx+1} FAILED: {e}", file=sys.stderr); continue
        print("  Published TRIAL reel:", json.dumps(pub))
        st.setdefault("history", []).append({
            "at": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
            "id": it["rel"], "type": "reel", "slot": "trial", "post_id": pub.get("id"),
            "trial": True, "graduation": strat,
            "tags": {"fmt": it.get("type"), "style": it.get("style"),
                     "pillar": it.get("pillar"), "cap_style": it.get("cap_style")},
            "hook": it.get("hook", "")})
        posted += 1
        if idx < len(items) - 1:
            time.sleep(30)   # small stagger between publishes (kinder to the API)
    st["history"] = st["history"][-200:]
    st.setdefault("trial_daily", {})[today] = st.get("trial_daily", {}).get(today, 0) + posted
    write_state(st)
    TRIAL_PENDING.unlink(missing_ok=True)
    print(f"Posted {posted} trial reel(s). Today's trial total: {st['trial_daily'][today]}")
    return 0 if posted else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--publish-story", dest="publish_story", action="store_true")
    ap.add_argument("--render-trials", type=int, default=0,
                    help="render N varied TRIAL reels into a batch")
    ap.add_argument("--publish-trials", dest="publish_trials", action="store_true")
    ap.add_argument("--trials-remaining", type=int, default=-1,
                    help="print how many trials are left to hit this daily target, then exit")
    ap.add_argument("--trial-strategy", default=os.getenv("TRIAL_STRATEGY", "SS_PERFORMANCE"),
                    help="MANUAL or SS_PERFORMANCE")
    ap.add_argument("--kind", default=os.getenv("KIND", "auto"))
    a = ap.parse_args()
    if a.trials_remaining >= 0:
        print(trials_remaining(a.trials_remaining)); sys.exit(0)
    if a.render_trials > 0:
        render_trials(a.render_trials, strategy=a.trial_strategy); sys.exit(0)
    if a.publish_trials:
        sys.exit(publish_trials())
    if a.render:
        render(a.kind); sys.exit(0)
    if a.publish:
        sys.exit(publish())
    if a.publish_story:
        sys.exit(publish_story())
    print("specify --render | --publish | --publish-story | --render-trials N | --publish-trials",
          file=sys.stderr); sys.exit(2)
