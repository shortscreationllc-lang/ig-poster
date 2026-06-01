#!/usr/bin/env python3
"""Daily IG auto-poster with a pre-rendered buffer queue.

Design ("never miss a day"):
  - A QUEUE of ready-to-post items lives in the repo under queue/ with a
    queue/manifest.json index. Each item is FULLY RENDERED ahead of time, so
    even if rendering code breaks later, there's always a stockpile to post.
  - AM slot posts the next SINGLE card (dark). PM slot posts the next CAROUSEL
    (light). Each has its own rotation pointer in state.json.
  - After posting, the queue is refilled back up to QUEUE_DEPTH per slot.

Commands:
  --refill        (re)build the queue up to depth, render any missing images
  --render-only   ensure queue is filled, then mark the head item for `SLOT`
                  as "pending" (writes .pending.json) — does NOT post
  --publish-only  read .pending.json, build public raw URLs, post to IG,
                  mark item posted, advance, refill
  (no flag)       refill + render-only + publish-only in sequence (local use)

Env:
  IG_USER_ID, IG_ACCESS_TOKEN
  SLOT = am | pm
  GITHUB_REPOSITORY, GITHUB_REF_NAME   (to build raw.githubusercontent URLs)
  IMAGE_BASE_OVERRIDE                   (local testing: base raw URL)
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

import render_card

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state.json"
PENDING = ROOT / ".pending.json"
QUEUE_DIR = ROOT / "queue"
MANIFEST = QUEUE_DIR / "manifest.json"
SINGLE_BANK = ROOT / "post_bank.json"
CAROUSEL_BANK = ROOT / "carousel_bank.json"
GRAPH = "https://graph.instagram.com/v25.0"

QUEUE_DEPTH = 14   # keep this many ready items per slot at all times

# Design variety: AM (singles) cycle the dark family, PM (carousels) the light
# family — so every day is one dark + one light, and no two consecutive posts
# in the feed share the exact same look.
AM_STYLES = ["dark", "midnight"]
PM_STYLES = ["light", "bone"]


# ---------- helpers ----------
def load_env_file():
    env = ROOT / ".env"
    if env.exists():
        for raw in env.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read_state():
    if STATE.exists():
        s = json.loads(STATE.read_text())
    else:
        s = {}
    s.setdefault("single_index", 0)
    s.setdefault("carousel_index", 0)
    s.setdefault("seq", 0)
    s.setdefault("am_style_i", 0)
    s.setdefault("pm_style_i", 0)
    s.setdefault("history", [])
    return s


def write_state(s):
    STATE.write_text(json.dumps(s, indent=2) + "\n")


def read_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"items": []}


def write_manifest(m):
    QUEUE_DIR.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")


def graph_post(path, params):
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def graph_get(path, params):
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def wait_ready(cid, token, timeout=240):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        d = graph_get(cid, {"fields": "status_code", "access_token": token})
        last = d
        if d.get("status_code") in {"FINISHED", "ERROR", "EXPIRED"}:
            return d
        time.sleep(5)
    return last or {"status_code": "TIMEOUT"}


# ---------- queue building ----------
def _next_unposted(manifest, slot):
    for it in manifest["items"]:
        if it["slot"] == slot and not it.get("posted"):
            return it
    return None


def _count_unposted(manifest, slot):
    return sum(1 for it in manifest["items"] if it["slot"] == slot and not it.get("posted"))


CONTENT_BANK = ROOT / "content_bank.json"
QUOTE_BANK = ROOT / "quote_bank.json"


def _build_am_pool():
    """Round-robin tips + typed value cards + verified quotes so the feed cycles
    through formats (tip, quote, myth, versus, value, …). Each entry keeps its
    own 'type' for the renderer. Quotes are interleaved so they show up often."""
    tips = json.loads(SINGLE_BANK.read_text())
    for t in tips:
        t.setdefault("type", "single")
    typed = json.loads(CONTENT_BANK.read_text()) if CONTENT_BANK.exists() else []
    quotes = json.loads(QUOTE_BANK.read_text()) if QUOTE_BANK.exists() else []
    pool = []
    i = j = k = 0
    # pattern: tip, quote, typed, repeat — keeps quotes & value frequent
    while i < len(tips) or j < len(quotes) or k < len(typed):
        if i < len(tips):
            pool.append(tips[i]); i += 1
        if j < len(quotes):
            pool.append(quotes[j]); j += 1
        if k < len(typed):
            pool.append(typed[k]); k += 1
    return pool


def _render_am_item(item, out_path, style):
    """Route an AM pool item to the right card renderer by its type."""
    t = item.get("type", "single")
    if t == "quote":
        render_card.draw_quote(item, out_path, style=style)
    elif t in ("myth", "versus"):
        render_card.draw_versus(item, out_path, style=style)
    elif t == "value":
        render_card.draw_value(item, out_path, style=style)
    elif t == "testimonial":
        render_card.draw_testimonial(item, out_path, style=style)
    else:
        render_card.draw_card(item, out_path, style=style)


def refill():
    """Top up both slot queues to QUEUE_DEPTH, rendering images ahead of time."""
    QUEUE_DIR.mkdir(exist_ok=True)
    state = read_state()
    manifest = read_manifest()
    am_pool = _build_am_pool()
    carousels = json.loads(CAROUSEL_BANK.read_text())

    made = 0
    # AM singles — mixed formats (tip / quote / myth / versus / value)
    while _count_unposted(manifest, "am") < QUEUE_DEPTH:
        idx = state["single_index"] % len(am_pool)
        item = am_pool[idx]
        state["seq"] += 1
        uid = f"single-{state['seq']:05d}"
        rel = f"queue/{uid}.jpg"
        style = item.get("style") or AM_STYLES[state["am_style_i"] % len(AM_STYLES)]
        state["am_style_i"] += 1
        _render_am_item(item, ROOT / rel, style)
        manifest["items"].append({
            "id": uid, "slot": "am", "type": item.get("type", "single"),
            "images": [rel], "caption": item["caption"],
            "alt": item.get("alt_text", ""), "posted": False,
            "source_index": idx,
        })
        state["single_index"] = (idx + 1) % len(am_pool)
        made += 1

    # PM carousels (light)
    while _count_unposted(manifest, "pm") < QUEUE_DEPTH:
        idx = state["carousel_index"] % len(carousels)
        entry = carousels[idx]
        state["seq"] += 1
        uid = f"carousel-{state['seq']:05d}"
        style = entry.get("style") or PM_STYLES[state["pm_style_i"] % len(PM_STYLES)]
        state["pm_style_i"] += 1
        paths = render_card.render_carousel(entry, QUEUE_DIR, uid, style=style)
        rels = [str(Path(p).relative_to(ROOT)) for p in paths]
        manifest["items"].append({
            "id": uid, "slot": "pm", "type": "carousel",
            "images": rels, "caption": entry["caption"],
            "alt": entry.get("alt_text", ""), "posted": False,
            "source_index": idx,
        })
        state["carousel_index"] = (idx + 1) % len(carousels)
        made += 1

    # trim posted history in the manifest (keep last 60 posted for traceability)
    posted = [it for it in manifest["items"] if it.get("posted")]
    fresh = [it for it in manifest["items"] if not it.get("posted")]
    manifest["items"] = posted[-60:] + fresh
    write_manifest(manifest)
    write_state(state)
    print(f"Refill complete: +{made} items. "
          f"Ready -> am:{_count_unposted(manifest,'am')} pm:{_count_unposted(manifest,'pm')}")


# ---------- render-only (mark head pending) ----------
def render_only():
    slot = os.getenv("SLOT", "am").strip().lower()
    refill()
    manifest = read_manifest()
    head = _next_unposted(manifest, slot)
    if not head:
        print(f"ERROR: queue empty for slot {slot}", file=sys.stderr)
        return 2
    PENDING.write_text(json.dumps({"slot": slot, "id": head["id"]}) + "\n")
    print(f"Pending {slot}: {head['id']} ({head['type']}, {len(head['images'])} image(s))")
    return 0


# ---------- publish ----------
def _public_base():
    repo = os.getenv("GITHUB_REPOSITORY", "")
    branch = os.getenv("GITHUB_REF_NAME", "main") or "main"
    override = os.getenv("IMAGE_BASE_OVERRIDE", "")
    if override:
        return override.rstrip("/")
    if repo:
        return f"https://raw.githubusercontent.com/{repo}/{branch}"
    return ""


def _publish_single(user_id, token, url, caption, alt):
    payload = {"image_url": url, "caption": caption, "access_token": token}
    if alt:
        payload["alt_text"] = alt
    created = graph_post(f"{user_id}/media", payload)
    cid = created.get("id")
    if not cid:
        raise RuntimeError(f"container failed: {json.dumps(created)}")
    st = wait_ready(cid, token)
    if st.get("status_code") not in {"FINISHED", None}:
        raise RuntimeError(f"not ready: {json.dumps(st)}")
    pub = graph_post(f"{user_id}/media_publish", {"creation_id": cid, "access_token": token})
    return pub


def _publish_carousel(user_id, token, urls, caption):
    children = []
    for u in urls:
        r = graph_post(f"{user_id}/media",
                       {"image_url": u, "is_carousel_item": "true", "access_token": token})
        cid = r.get("id")
        if not cid:
            raise RuntimeError(f"child failed for {u}: {json.dumps(r)}")
        wait_ready(cid, token)
        children.append(cid)
    parent = graph_post(f"{user_id}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
        "access_token": token,
    })
    pid = parent.get("id")
    if not pid:
        raise RuntimeError(f"carousel container failed: {json.dumps(parent)}")
    st = wait_ready(pid, token)
    if st.get("status_code") not in {"FINISHED", None}:
        raise RuntimeError(f"carousel not ready: {json.dumps(st)}")
    pub = graph_post(f"{user_id}/media_publish", {"creation_id": pid, "access_token": token})
    return pub


def publish_only():
    load_env_file()
    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        print("ERROR: IG creds not set", file=sys.stderr)
        return 2
    if not PENDING.exists():
        print("ERROR: no .pending.json (run --render-only)", file=sys.stderr)
        return 2
    base = _public_base()
    if not base:
        print("ERROR: no public base URL", file=sys.stderr)
        return 2

    pend = json.loads(PENDING.read_text())
    manifest = read_manifest()
    item = next((it for it in manifest["items"] if it["id"] == pend["id"]), None)
    if not item:
        print(f"ERROR: pending id {pend['id']} not in manifest", file=sys.stderr)
        return 2

    urls = [f"{base}/{urllib.parse.quote(rel)}" for rel in item["images"]]
    print(f"Posting {item['type']} '{item['id']}' ({len(urls)} image(s))")
    try:
        if item["type"] == "carousel":
            pub = _publish_carousel(user_id, token, urls, item["caption"])
        else:
            pub = _publish_single(user_id, token, urls[0], item["caption"], item.get("alt", ""))
    except Exception as e:
        print(f"PUBLISH FAILED: {e}", file=sys.stderr)
        return 1
    print("Published:", json.dumps(pub))

    item["posted"] = True
    item["posted_at"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    item["post_id"] = pub.get("id")
    write_manifest(manifest)
    state = read_state()
    state["history"].append({"at": item["posted_at"], "id": item["id"],
                             "slot": item["slot"], "type": item["type"],
                             "post_id": pub.get("id")})
    state["history"] = state["history"][-200:]
    write_state(state)
    PENDING.unlink(missing_ok=True)
    refill()  # immediately top the queue back up
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refill", action="store_true")
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--publish-only", action="store_true")
    args = ap.parse_args()
    if args.refill:
        refill(); return 0
    if args.render_only:
        return render_only()
    if args.publish_only:
        return publish_only()
    refill()
    if render_only() != 0:
        return 1
    return publish_only()


if __name__ == "__main__":
    raise SystemExit(main())
