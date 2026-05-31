#!/usr/bin/env python3
"""Refresh the long-lived Instagram access token.

Instagram Graph API long-lived tokens last 60 days and can be refreshed any time
after they're 24h old, each refresh extending another 60 days. Running this on a
schedule keeps the poster alive indefinitely with no manual re-auth.

In GitHub Actions this prints the new token to GITHUB_OUTPUT so a follow-up step
can update the IG_ACCESS_TOKEN repo secret. Locally it just prints it.

Env: IG_ACCESS_TOKEN (current, still-valid token)
"""
import json
import os
import sys
import urllib.parse
import urllib.request


def main():
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: IG_ACCESS_TOKEN not set", file=sys.stderr)
        return 2
    params = urllib.parse.urlencode({
        "grant_type": "ig_refresh_token",
        "access_token": token,
    })
    url = f"https://graph.instagram.com/refresh_access_token?{params}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"Refresh request failed: {e}", file=sys.stderr)
        return 1

    new_token = data.get("access_token")
    expires = data.get("expires_in")
    if not new_token:
        print(f"No token returned: {json.dumps(data)}", file=sys.stderr)
        return 1

    days = round((expires or 0) / 86400, 1)
    print(f"Token refreshed. Valid ~{days} more days.")

    out = os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"new_token={new_token}\n")
        print("Wrote new token to GITHUB_OUTPUT.")
    else:
        print("New token:", new_token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
