#!/usr/bin/env python3
"""Daily IG auto-post runner (GitHub Actions + local).

Two phases, because in CI the image must be committed/pushed to the public repo
BEFORE Instagram can fetch it:

  --render-only   pick next post, render JPG, write generated/<stamp>-<idx>.jpg,
                  stash the pending info in .pending.json
  --publish-only  read .pending.json, build the raw URL, publish to Instagram,
                  advance + persist rotation state

With no flag it does both in sequence (fine for local testing where the file
is already reachable or IMAGE_URL_OVERRIDE is supplied).

Env:
  IG_USER_ID, IG_ACCESS_TOKEN      Instagram Graph API
  SLOT                             "am" (dark) or "pm" (light); per-item "style" wins
  GITHUB_REPOSITORY, GITHUB_REF_NAME   auto-set in Actions; used to build raw URL
  IMAGE_URL_OVERRIDE               explicit image URL (local testing)
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
BANK = ROOT / "post_bank.json"
GRAPH = "https://graph.instagram.com/v25.0"


def load_env_file():
    env = ROOT / ".env"
    if env.exists():
        for raw in env.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {"next_index": 0, "history": []}


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


def do_render():
    bank = json.loads(BANK.read_text())
    state = read_state()
    idx = state["next_index"] % len(bank)
    item = bank[idx]
    slot = os.getenv("SLOT", "am").strip().lower()
    style = item.get("style") or ("light" if slot == "pm" else "dark")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    rel = f"generated/{stamp}-{idx}.jpg"
    (ROOT / "generated").mkdir(exist_ok=True)
    render_card.draw_card(item, ROOT / rel, style=style)
    PENDING.write_text(json.dumps({"index": idx, "rel": rel, "slot": slot, "stamp": stamp}) + "\n")
    print(f"Rendered #{idx} ({style}): {item['headline'][:48]} -> {rel}")
    return rel


def do_publish():
    load_env_file()
    user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not user_id or not token:
        print("ERROR: IG_USER_ID / IG_ACCESS_TOKEN not set", file=sys.stderr)
        return 2
    if not PENDING.exists():
        print("ERROR: no .pending.json; run --render-only first", file=sys.stderr)
        return 2

    pend = json.loads(PENDING.read_text())
    bank = json.loads(BANK.read_text())
    item = bank[pend["index"]]
    rel = pend["rel"]

    repo = os.getenv("GITHUB_REPOSITORY", "")
    branch = os.getenv("GITHUB_REF_NAME", "main") or "main"
    image_url = os.getenv("IMAGE_URL_OVERRIDE") or (
        f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}" if repo else "")
    if not image_url:
        print("ERROR: cannot build image URL (no GITHUB_REPOSITORY / IMAGE_URL_OVERRIDE)", file=sys.stderr)
        return 2
    print(f"Image URL: {image_url}")

    payload = {"image_url": image_url, "caption": item["caption"], "access_token": token}
    if item.get("alt_text"):
        payload["alt_text"] = item["alt_text"]
    created = graph_post(f"{user_id}/media", payload)
    cid = created.get("id")
    if not cid:
        print("Container create failed:", json.dumps(created), file=sys.stderr)
        return 1
    status = wait_ready(cid, token)
    if status.get("status_code") not in {"FINISHED", None}:
        print("Container not ready:", json.dumps(status), file=sys.stderr)
        return 1
    pub = graph_post(f"{user_id}/media_publish", {"creation_id": cid, "access_token": token})
    print("Published:", json.dumps(pub))

    state = read_state()
    state["next_index"] = (pend["index"] + 1) % len(bank)
    state.setdefault("history", []).append(
        {"at": pend["stamp"], "index": pend["index"], "post_id": pub.get("id"),
         "image": rel, "slot": pend.get("slot")})
    state["history"] = state["history"][-200:]
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    PENDING.unlink(missing_ok=True)
    print(f"State advanced -> next_index={state['next_index']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-only", action="store_true")
    ap.add_argument("--publish-only", action="store_true")
    args = ap.parse_args()
    if args.render_only:
        do_render()
        return 0
    if args.publish_only:
        return do_publish()
    do_render()
    return do_publish()


if __name__ == "__main__":
    raise SystemExit(main())
