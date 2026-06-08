#!/usr/bin/env python3
"""Pull Instagram Insights DAILY and feed the learning loop.

What it does each run (on GitHub Actions, where the IG token + open net live):
  1. Pulls per-post performance for BOTH the bot's posts AND your own organic
     posts/pictures/reels (via the account media endpoint) — reach, views,
     watch time, saves, shares, engagement.
  2. Joins each bot post to the tags it was published with (format, style,
     pillar, caption style) and hands everything to weighting.build_weights(),
     which writes weights.json — the multipliers the selectors learn from.
  3. Writes insights_report.md (human-readable) + insights.json (raw): top
     performers, organic-vs-bot benchmarks, and the learned leaderboards.

More information every day -> sharper weights -> better content. That's the loop.
"""
import json, os, urllib.request, urllib.parse, urllib.error
from pathlib import Path

import weighting

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


def fetch_account_media(user_id, token, limit=25):
    """Recent media on the account — INCLUDING your own organic posts, not just
    the bot's. Returns list of {id, media_product_type, timestamp, permalink}."""
    if not user_id:
        return []
    d = gget(f"{user_id}/media",
             {"fields": "id,media_product_type,media_type,permalink,timestamp",
              "limit": limit, "access_token": token})
    return d.get("data", []) if isinstance(d.get("data"), list) else []


def pull_row(pid, token, when=None, typ=None, bot=False):
    base = gget(pid, {"fields": "media_product_type,permalink,timestamp", "access_token": token})
    mpt = base.get("media_product_type", "")
    core = insights(pid, "reach,likes,comments,shares,saved,total_interactions", token)
    r = {"at": when or (base.get("timestamp", "") or "").replace("-", "").replace(":", ""),
         "type": typ, "mpt": mpt, "post_id": pid, "bot": bot,
         "permalink": base.get("permalink", ""), **core}
    if mpt == "REELS":
        r.update(insights(pid, "ig_reels_avg_watch_time,ig_reels_video_view_total_time", token))
        v = insights(pid, "views", token)
        if "views" in v:
            r["views"] = v["views"]
    return r


def _fmt_row(r):
    aw = r.get("ig_reels_avg_watch_time")
    aw_s = f"{aw/1000:.1f}s watch" if isinstance(aw, (int, float)) else "—"
    reach = r.get("reach") if isinstance(r.get("reach"), (int, float)) else 0
    inter = r.get("total_interactions") or 0
    er = f"{(inter/reach*100):.1f}%" if reach else "n/a"
    sc = weighting.score_post(r)
    tag = "🧪" if r.get("trial") else ("🤖" if r.get("bot") else "👤")
    fmt = (r.get("type") or r.get("mpt") or "?")
    return (f"- {tag} {r.get('at','')[:8]} | {fmt} | reach {reach} | "
            f"views {r.get('views','-')} | {aw_s} | saves {r.get('saved','-')} "
            f"shares {r.get('shares','-')} | eng {er} | "
            f"score {sc if sc is not None else '-'} | {r.get('permalink','')}")


def _leaderboard(by, dim, title):
    cells = by.get(dim, {})
    if not cells:
        return [f"### {title}", "_no data yet — keep posting_", ""]
    rows = sorted(cells.items(), key=lambda kv: kv[1].get("w", 1.0), reverse=True)
    out = [f"### {title}"]
    for v, c in rows:
        w, n = c.get("w", 1.0), c.get("n", 0)
        arrow = "▲" if w > 1.05 else ("▼" if w < 0.95 else "▬")
        conf = "" if n >= weighting.SHRINK_K else f"  _(only {n}, low confidence)_"
        out.append(f"- {arrow} **{v}** — weight {w}  ·  {n} post(s){conf}")
    out.append("")
    return out


def main():
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    user_id = os.getenv("IG_USER_ID", "").strip()
    if not token:
        print("ERROR: IG_ACCESS_TOKEN not set"); return 2
    state = json.loads((ROOT / "state.json").read_text())
    hist = [h for h in state.get("history", []) if h.get("post_id")]
    bot_meta = {h["post_id"]: h for h in hist}
    bot_ids = list(bot_meta)[-30:]

    # Account media = your organic posts/pictures/reels too (not only the bot's).
    organic = fetch_account_media(user_id, token, limit=25)
    organic_ids = [m["id"] for m in organic]

    seen, rows = set(), []
    for pid in bot_ids + organic_ids:
        if pid in seen:
            continue
        seen.add(pid)
        meta = bot_meta.get(pid)
        r = pull_row(pid, token, when=(meta or {}).get("at"),
                     typ=(meta or {}).get("type"), bot=pid in bot_meta)
        r["trial"] = bool((meta or {}).get("trial"))
        rows.append(r)

    err = next((r.get("_err") for r in rows if r.get("_err")), None)

    # ---- learn: rebuild weights.json from the freshly pulled performance ----
    weights = weighting.build_weights(rows, hist)

    # ---- report ----
    L = ["# Instagram Insights — daily performance report", ""]
    if err:
        L += [f"> ⚠️ Insights API note: **{err}**",
              "> (If this mentions permissions, re-auth with `instagram_manage_insights`.)", ""]
    n_trial = sum(1 for r in rows if r.get("trial"))
    n_bot = sum(1 for r in rows if r.get("bot") and not r.get("trial"))
    n_org = sum(1 for r in rows if not r.get("bot"))
    L += [f"**Tracked:** {len(rows)} posts ({n_bot} auto-posted 🤖, {n_trial} trial 🧪, "
          f"{n_org} your own 👤)  ·  learning from {weights.get('n', 0)} tagged posts", ""]

    # top performers by composite score (saves+shares heavy, +watch time)
    scored = [(weighting.score_post(r), r) for r in rows]
    scored = [(s, r) for s, r in scored if s is not None]
    scored.sort(key=lambda sr: sr[0], reverse=True)
    L.append(f"## 🏆 Top performers (by save/share/watch score)")
    for s, r in scored[:8]:
        L.append(_fmt_row(r))
    L.append("")
    if len(scored) > 8:
        L.append("## 🧊 Weakest (rework or retire these)")
        for s, r in scored[-3:]:
            L.append(_fmt_row(r))
        L.append("")

    # organic vs bot benchmark
    def _avg(items, key, scale=1.0):
        vals = [it.get(key) for it in items if isinstance(it.get(key), (int, float))]
        return f"{sum(vals)/len(vals)*scale:.1f}" if vals else "—"
    bot_reels = [r for r in rows if r.get("bot") and r.get("mpt") == "REELS"]
    org_reels = [r for r in rows if not r.get("bot") and r.get("mpt") == "REELS"]
    L += ["## 👤 vs 🤖 benchmark (reels)",
          f"- avg watch — yours: {_avg(org_reels,'ig_reels_avg_watch_time',0.001)}s  ·  "
          f"bot: {_avg(bot_reels,'ig_reels_avg_watch_time',0.001)}s",
          f"- avg reach — yours: {_avg(org_reels,'reach')}  ·  bot: {_avg(bot_reels,'reach')}",
          f"- avg saves — yours: {_avg(org_reels,'saved')}  ·  bot: {_avg(bot_reels,'saved')}", ""]

    # learned leaderboards (what the rotation will now favor)
    by = weights.get("by", {})
    L += ["## 📈 What the loop is learning (weights → what we make more of)",
          f"_overall avg score: {weights.get('overall_avg','—')} · "
          f"weights pull toward neutral until a tag has {weighting.SHRINK_K}+ posts_", ""]
    L += _leaderboard(by, "fmt", "By format")
    L += _leaderboard(by, "pillar", "By topic / pillar")
    L += _leaderboard(by, "style", "By visual style")
    L += _leaderboard(by, "cap_style", "By caption shape (0=save 3=question 4=send …)")

    json.dump(rows, open(ROOT / "insights.json", "w"), indent=1)
    (ROOT / "insights_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nWrote insights.json ({len(rows)} posts), insights_report.md, weights.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
