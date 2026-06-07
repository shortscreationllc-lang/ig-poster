#!/usr/bin/env python3
"""Pull Instagram Insights for recent posts and write a performance report.
Runs on GitHub Actions (where the IG token + open internet live). Builds the
feedback loop: which posts/formats win, which flop (low watch time = high skip).
"""
import json, os, urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.instagram.com/v25.0"


def gget(path, params):
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return {"_err": json.loads(e.read().decode()).get("error", {}).get("message", "")}
        except Exception:
            return {"_err": f"HTTP {e.code}"}


def insights(pid, metrics, token):
    d = gget(f"{pid}/insights", {"metric": metrics, "access_token": token})
    out = {}
    if "data" in d:
        for m in d["data"]:
            vals = m.get("values", [{}])
            out[m["name"]] = vals[0].get("value") if vals else None
    elif d.get("_err"):
        out["_err"] = d["_err"]
    return out


def main():
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print("ERROR: IG_ACCESS_TOKEN not set"); return 2
    state = json.loads((ROOT / "state.json").read_text())
    hist = [h for h in state.get("history", []) if h.get("post_id")][-30:]
    rows = []
    for h in hist:
        pid = h["post_id"]
        base = gget(pid, {"fields": "media_product_type,permalink,timestamp", "access_token": token})
        mpt = base.get("media_product_type", "")
        core = insights(pid, "reach,likes,comments,shares,saved,total_interactions", token)
        r = {"at": h.get("at"), "type": h.get("type"), "mpt": mpt, "post_id": pid,
             "permalink": base.get("permalink", ""), **core}
        if mpt == "REELS":
            r.update(insights(pid, "ig_reels_avg_watch_time,ig_reels_video_view_total_time", token))
            v = insights(pid, "views", token)
            if "views" in v:
                r["views"] = v["views"]
        rows.append(r)

    err = next((r.get("_err") for r in rows if r.get("_err")), None)
    lines = ["# Instagram Insights — performance report", ""]
    if err:
        lines += [f"> ⚠️ Insights API error: **{err}**",
                  "> (If this says the token lacks permission, we need to re-auth with `instagram_manage_insights`.)", ""]
    # rank reels by reach
    reels = [r for r in rows if r.get("mpt") == "REELS" and isinstance(r.get("reach"), (int, float))]
    reels.sort(key=lambda r: r.get("reach") or 0, reverse=True)
    lines.append(f"## Reels by reach ({len(reels)})")
    for r in reels:
        aw = r.get("ig_reels_avg_watch_time")
        aw_s = f"{aw/1000:.1f}s avg watch" if isinstance(aw, (int, float)) else "watch n/a"
        inter = r.get("total_interactions") or 0
        reach = r.get("reach") or 0
        er = f"{(inter/reach*100):.1f}%" if reach else "n/a"
        lines.append(f"- {r['at'][:8]} | reach {reach} | views {r.get('views','-')} | {aw_s} | "
                     f"saves {r.get('saved','-')} shares {r.get('shares','-')} | eng {er} | {r['permalink']}")
    lines.append("")
    json.dump(rows, open(ROOT / "insights.json", "w"), indent=1)
    (ROOT / "insights_report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote insights.json ({len(rows)} posts) + insights_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
