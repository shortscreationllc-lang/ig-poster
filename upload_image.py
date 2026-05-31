#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
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


def request_json(url, *, method="POST", data=None, headers=None):
    body = None
    if isinstance(data, dict):
        body = urllib.parse.urlencode(data).encode("utf-8")
    elif isinstance(data, bytes):
        body = data
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def dropbox_access_token():
    token = os.getenv("DROPBOX_ACCESS_TOKEN", "").strip()
    if token:
        return token

    app_key = os.getenv("DROPBOX_APP_KEY", os.getenv("dropbox_app_key", "")).strip()
    app_secret = os.getenv("DROPBOX_APP_SECRET", os.getenv("dropbox_app_secret", "")).strip()
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN", os.getenv("dropbox_refresh_token", "")).strip()
    if not app_key or not app_secret or not refresh_token:
        raise SystemExit("Dropbox needs DROPBOX_ACCESS_TOKEN or DROPBOX_APP_KEY/DROPBOX_APP_SECRET/DROPBOX_REFRESH_TOKEN")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret,
    }
    result = request_json("https://api.dropboxapi.com/oauth2/token", data=data)
    token = result.get("access_token", "")
    if not token:
        raise SystemExit(f"Dropbox refresh did not return access_token: {json.dumps(result, indent=2)}")
    return token


def upload_cloudinary(path):
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    upload_preset = os.getenv("CLOUDINARY_UPLOAD_PRESET", "").strip()
    api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    folder = os.getenv("CLOUDINARY_FOLDER", "shorts-creation/instagram-auto").strip()

    if not cloud_name:
        raise SystemExit("Missing CLOUDINARY_CLOUD_NAME in .env")

    url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    data = {
        "folder": folder,
        "file": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii"),
    }

    if upload_preset:
        data["upload_preset"] = upload_preset
    else:
        if not api_key or not api_secret:
            raise SystemExit("Cloudinary needs either CLOUDINARY_UPLOAD_PRESET or CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET")
        timestamp = str(int(time.time()))
        data["timestamp"] = timestamp
        data["api_key"] = api_key
        to_sign = f"folder={folder}&timestamp={timestamp}{api_secret}"
        data["signature"] = hashlib.sha1(to_sign.encode("utf-8")).hexdigest()

    result = request_json(url, data=data)
    secure_url = result.get("secure_url")
    if not secure_url:
        raise SystemExit(f"Cloudinary upload did not return secure_url: {json.dumps(result, indent=2)}")
    return secure_url


def upload_dropbox(path):
    token = dropbox_access_token()
    folder = os.getenv("DROPBOX_FOLDER", "/Instagram Auto Posts").strip() or "/Instagram Auto Posts"

    dropbox_path = f"{folder.rstrip('/')}/{path.name}"
    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps({
            "path": dropbox_path,
            "mode": "overwrite",
            "autorename": False,
            "mute": True,
        }),
    }
    request_json("https://content.dropboxapi.com/2/files/upload", data=path.read_bytes(), headers=upload_headers)

    share_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "path": dropbox_path,
        "settings": {"requested_visibility": "public"},
    }).encode("utf-8")
    try:
        result = request_json("https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings", data=payload, headers=share_headers)
    except Exception:
        list_payload = json.dumps({"path": dropbox_path, "direct_only": True}).encode("utf-8")
        result = request_json("https://api.dropboxapi.com/2/sharing/list_shared_links", data=list_payload, headers=share_headers)
        links = result.get("links", [])
        if not links:
            raise
        result = links[0]

    url = result.get("url", "")
    if not url:
        raise SystemExit(f"Dropbox upload did not return a shared URL: {json.dumps(result, indent=2)}")
    return url.replace("www.dropbox.com", "dl.dropboxusercontent.com").replace("?dl=0", "?raw=1")


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Upload an image and return a direct public URL.")
    parser.add_argument("image_path")
    parser.add_argument("--provider", default=os.getenv("IMAGE_HOST", "cloudinary"), choices=["cloudinary", "dropbox"])
    args = parser.parse_args()

    image_path = Path(args.image_path).expanduser()
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    if args.provider == "dropbox":
        print(upload_dropbox(image_path))
    else:
        print(upload_cloudinary(image_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
