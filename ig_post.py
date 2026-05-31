#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def graph_url(path):
    version = os.getenv("GRAPH_VERSION", "v25.0")
    host = os.getenv("IG_API_HOST", "graph.instagram.com").strip() or "graph.instagram.com"
    return f"https://{host}/{version}/{path}"


def graph_post(path, params):
    body = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(graph_url(path), data=body, method="POST")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def graph_get(path, params):
    url = f"{graph_url(path)}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_container(container_id, token, timeout_seconds=180):
    deadline = time.time() + timeout_seconds
    last = None
    while time.time() < deadline:
        data = graph_get(
            container_id,
            {
                "fields": "id,status,status_code",
                "access_token": token,
            },
        )
        last = data
        status_code = data.get("status_code")
        if status_code in {"FINISHED", "ERROR", "EXPIRED"}:
            return data
        time.sleep(5)
    return last or {"status_code": "TIMEOUT"}


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Publish one Instagram image post through the Graph API.")
    parser.add_argument("--image-url", required=True, help="Public direct image URL.")
    parser.add_argument("--caption", required=True, help="Instagram caption text.")
    parser.add_argument("--alt-text", default="", help="Alt text for image posts.")
    parser.add_argument("--dry-run", action="store_true", help="Print the planned API payload without posting.")
    args = parser.parse_args()

    create_payload = {
        "image_url": args.image_url,
        "caption": args.caption,
        "access_token": os.getenv("IG_ACCESS_TOKEN", "").strip() or "***",
    }
    if args.alt_text:
        create_payload["alt_text"] = args.alt_text

    safe_payload = dict(create_payload)
    safe_payload["access_token"] = "***"

    if args.dry_run:
        print("Dry run. Would create media container:")
        print(json.dumps(safe_payload, indent=2))
        return 0

    ig_user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not ig_user_id or not token:
        print("Missing IG_USER_ID or IG_ACCESS_TOKEN in .env")
        return 2
    create_payload["access_token"] = token

    print("Creating Instagram media container...")
    created = graph_post(f"{ig_user_id}/media", create_payload)
    container_id = created.get("id")
    if not container_id:
        print("No container id returned:")
        print(json.dumps(created, indent=2))
        return 1

    print(f"Container created: {container_id}")
    print("Waiting for Meta processing...")
    status = wait_for_container(container_id, token)
    print(json.dumps(status, indent=2))

    if status.get("status_code") not in {"FINISHED", None}:
        print("Container is not ready to publish.")
        return 1

    print("Publishing Instagram post...")
    published = graph_post(
        f"{ig_user_id}/media_publish",
        {
            "creation_id": container_id,
            "access_token": token,
        },
    )
    print("Published.")
    print(json.dumps(published, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
