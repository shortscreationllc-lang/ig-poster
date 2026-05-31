#!/usr/bin/env python3
import json
import os
import sys
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


def graph_get(path, params):
    version = os.getenv("GRAPH_VERSION", "v25.0")
    host = os.getenv("IG_API_HOST", "graph.instagram.com").strip() or "graph.instagram.com"
    url = f"https://{host}/{version}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    load_env()
    ig_user_id = os.getenv("IG_USER_ID", "").strip()
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()

    if not ig_user_id or not token:
        print("Missing IG_USER_ID or IG_ACCESS_TOKEN in .env")
        return 2

    try:
        data = graph_get(
            ig_user_id,
            {
                "fields": "id,username,account_type,media_count",
                "access_token": token,
            },
        )
    except Exception as exc:
        print(f"Instagram API check failed: {exc}")
        return 1

    print("Instagram API connected.")
    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
