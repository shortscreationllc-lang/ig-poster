#!/usr/bin/env python3
"""The learning brain of the loop.

Every post is TAGGED at publish time (format, style, content pillar, caption
style). insights.py pulls each post's real performance, scores it, and this
module turns that into weights.json — a per-tag multiplier saying "posts with
this tag earn more saves/shares/watch-time than average."

Selectors (post_reel.py) read those weights to bias what we make next toward
what's working, while exploration keeps trying everything so we keep learning.

Two guards keep it sane on tiny data:
  - SHRINKAGE: a tag's weight is pulled toward neutral (1.0) until it has
    enough posts behind it, so one fluke can't swing the rotation.
  - composite SCORE weights SAVES and SHARES 3x (the reach signals that were at
    zero) plus a watch-time bonus for reels.

No third-party deps — safe to import anywhere in the pipeline.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEIGHTS = ROOT / "weights.json"

DIMS = ("fmt", "style", "pillar", "cap_style")
SHRINK_K = 3          # posts needed before a tag's weight is half-trusted
SAVE_W, SHARE_W, ENG_W = 3.0, 3.0, 1.0   # saves & shares matter most
CAP_STYLES = 6


# --------------------------------------------------------------------- pillars
def pillar_of(text):
    """Coarse content theme from a hook/headline/caption — so we learn which
    TOPICS land, not just which formats. Keyword-matched, order = priority."""
    t = (text or "").lower()
    buckets = [
        ("hook",      ["hook", "first 3", "first line", "first 2", "scroll", "3 sec", "3 seconds", "stop the scroll", "attention"]),
        ("business",  ["client", "business", "owner", "sell", "sale", "book", "buyer", "salesperson", "customer"]),
        ("editing",   ["edit", "cut", "b-roll", "broll", "silence", "caption", "pause", "loop", "trim", "dead air"]),
        ("algorithm", ["reach", "algorithm", "send", "share", "signal", "views", "viral", "dms", "rented"]),
        ("mindset",   ["consistent", "consistency", "quit", "90 days", "mindset", "system", "mood", "show up", "boring"]),
        ("proof",     ["proof", "before", "after", "result", "theory", "promise"]),
    ]
    for name, keys in buckets:
        if any(k in t for k in keys):
            return name
    return "general"


# ----------------------------------------------------------------- scoring
def score_post(r):
    """Composite performance score for one post's insight row, or None if it
    hasn't reached anyone yet. Normalized by reach so a post isn't rewarded just
    for being shown more (e.g. luckier time slot)."""
    reach = r.get("reach")
    if not isinstance(reach, (int, float)) or reach <= 0:
        return None
    saved = r.get("saved") or 0
    shares = r.get("shares") or 0
    inter = r.get("total_interactions") or 0
    score = 100.0 * (SAVE_W * saved / reach + SHARE_W * shares / reach + ENG_W * inter / reach)
    aw = r.get("ig_reels_avg_watch_time")   # ms, reels only
    if isinstance(aw, (int, float)):
        score += min(aw / 1000.0, 30.0)     # +1 per avg-watch-second, capped
    return round(score, 3)


def build_weights(rows, history):
    """rows = insight dicts (need post_id, reach, ...). history = state['history']
    entries carrying a 'tags' dict. Returns the weights structure to persist.
    Only TAGGED (bot) posts feed the weights; organic posts inform the report."""
    tagmap = {h.get("post_id"): h.get("tags", {}) for h in history if h.get("post_id")}
    scored = []
    for r in rows:
        tags = tagmap.get(r.get("post_id"))
        if tags is None:           # organic / untagged — not used for learning
            continue
        s = score_post(r)
        if s is None:
            continue
        scored.append((s, tags))

    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "n": len(scored), "baseline": 1.0, "by": {d: {} for d in DIMS}}
    if not scored:
        WEIGHTS.write_text(json.dumps(out, indent=1) + "\n")
        return out
    overall = sum(s for s, _ in scored) / len(scored) or 1.0
    out["overall_avg"] = round(overall, 3)

    agg = {d: {} for d in DIMS}
    for s, tags in scored:
        for d in DIMS:
            v = tags.get(d)
            if v is None:
                continue
            agg[d].setdefault(str(v), []).append(s)
    for d in DIMS:
        for v, vals in agg[d].items():
            n = len(vals)
            ratio = (sum(vals) / n) / overall if overall else 1.0
            alpha = n / (n + SHRINK_K)          # trust grows with sample size
            out["by"][d][v] = {"w": round((1 - alpha) * 1.0 + alpha * ratio, 3), "n": n}
    WEIGHTS.write_text(json.dumps(out, indent=1) + "\n")
    return out


# ----------------------------------------------------------------- selection
def load_weights():
    try:
        return json.loads(WEIGHTS.read_text())
    except Exception:
        return {"baseline": 1.0, "by": {}, "n": 0}


def _w(weights, dim, val):
    cell = weights.get("by", {}).get(dim, {}).get(str(val))
    if isinstance(cell, dict):
        return cell.get("w", 1.0)
    return cell if isinstance(cell, (int, float)) else 1.0


def score_spec(spec, weights, pillar=None):
    """Multiplier for a candidate reel recipe = product of its tag weights.
    ~1.0 means "no signal yet"; >1.0 means this format/style/topic over-performs."""
    if pillar is None:
        pillar = pillar_of(spec.get("hook") or spec.get("headline") or "")
    s = 1.0
    s *= _w(weights, "fmt", spec.get("type"))
    s *= _w(weights, "style", spec.get("style"))
    s *= _w(weights, "pillar", pillar)
    return s


def best_cap_style(weights, default=None):
    """The caption shape (0-5) with the strongest learned weight, or `default`
    if we have no caption-style signal yet (so it falls back to rotation)."""
    cs = weights.get("by", {}).get("cap_style", {})
    if not cs:
        return default
    return max(range(CAP_STYLES), key=lambda k: _w(weights, "cap_style", k))
