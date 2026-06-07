#!/usr/bin/env python3
"""Cross-post a feed item to Threads (Meta) via the Threads API.

Threads is a SEPARATE API from Instagram (graph.threads.net) and needs its own
credentials — your Instagram token will NOT work here:
    THREADS_USER_ID         the Threads-scoped user id
    THREADS_ACCESS_TOKEN    a long-lived Threads token with scopes
                            threads_basic, threads_content_publish

Notes:
  - Threads has no "stories", so only feed posts cross-post (this module is only
    called from the feed path; stories never call it).
  - Threads text limit is 500 chars, so captions are trimmed for Threads only.
  - Single image -> one IMAGE post. 2+ images -> a CAROUSEL.

Public API:
  configured()                 -> True if THREADS_* creds are present
  cross_post(image_urls, text) -> publish response dict, or None if not
                                  configured. Raises on a Threads API error
                                  (the caller treats failures as non-fatal so a
                                  Threads problem never blocks the IG post).
"""
import json
import os
import time
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"
TEXT_LIMIT = 500


def _post(path, params):
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}", data=body, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def _get(path, params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def _wait(cid, token, timeout=120):
    """Threads recommends waiting for the container to finish before publishing."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        d = _get(cid, {"fields": "status,error_message", "access_token": token})
        last = d
        if d.get("status") in {"FINISHED", "ERROR", "PUBLISHED"}:
            return d
        time.sleep(5)
    return last or {"status": "TIMEOUT"}


def _trim(caption):
    """Fit a caption into the Threads 500-char limit on a clean boundary."""
    c = (caption or "").strip()
    if len(c) <= TEXT_LIMIT:
        return c
    cut = c[:TEXT_LIMIT]
    for sep in ("\n\n", "\n", ". ", " "):
        i = cut.rfind(sep)
        if i > TEXT_LIMIT * 0.6:
            return cut[:i].rstrip()
    return cut.rstrip()


def configured():
    return bool(os.getenv("THREADS_USER_ID", "").strip()
                and os.getenv("THREADS_ACCESS_TOKEN", "").strip())


def cross_post(image_urls, text):
    uid = os.getenv("THREADS_USER_ID", "").strip()
    token = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
    if not uid or not token:
        return None
    text = _trim(text)

    # single image
    if len(image_urls) == 1:
        created = _post(f"{uid}/threads", {
            "media_type": "IMAGE", "image_url": image_urls[0],
            "text": text, "access_token": token})
        cid = created.get("id")
        if not cid:
            raise RuntimeError(f"threads container failed: {json.dumps(created)}")
        st = _wait(cid, token)
        if st.get("status") not in {"FINISHED", None}:
            raise RuntimeError(f"threads not ready: {json.dumps(st)}")
        return _post(f"{uid}/threads_publish",
                     {"creation_id": cid, "access_token": token})

    # carousel (2+ images)
    children = []
    for u in image_urls:
        r = _post(f"{uid}/threads", {
            "media_type": "IMAGE", "image_url": u,
            "is_carousel_item": "true", "access_token": token})
        cid = r.get("id")
        if not cid:
            raise RuntimeError(f"threads child failed for {u}: {json.dumps(r)}")
        _wait(cid, token)
        children.append(cid)
    parent = _post(f"{uid}/threads", {
        "media_type": "CAROUSEL", "children": ",".join(children),
        "text": text, "access_token": token})
    pid = parent.get("id")
    if not pid:
        raise RuntimeError(f"threads carousel failed: {json.dumps(parent)}")
    st = _wait(pid, token)
    if st.get("status") not in {"FINISHED", None}:
        raise RuntimeError(f"threads carousel not ready: {json.dumps(st)}")
    return _post(f"{uid}/threads_publish",
                 {"creation_id": pid, "access_token": token})
