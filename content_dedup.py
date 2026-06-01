"""Cross-channel content de-dup.

Guarantees a feed post and a story never show the same line. A content item is
fingerprinted as the SET of its distinctive text lines — headlines, sub-lines,
proof, slide titles/bodies — but NOT captions, kickers, alt text or CTAs (those
are long-form or generic and shouldn't drive a match). We keep a rolling memory
of recently-posted lines across BOTH channels (state["recent_texts"]); any
candidate that shares a line with that memory is skipped at selection time.
"""
import re

# structural / generic / long-form fields that must not drive a match
_SKIP = {
    "kicker", "caption", "alt_text", "alt", "nudge", "label", "series_label",
    "type", "id", "style", "role", "slot", "images", "source_index",
    "posted", "posted_at", "post_id", "fp", "at",
}
_MIN = 12  # ignore very short fragments (kickers, labels, "THE FIX", etc.)


def _norm(s):
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s.strip('"').strip("“”").strip()


def fingerprint(obj):
    """Set of normalized distinctive text lines in a content item / bank entry."""
    out = set()

    def walk(x):
        if isinstance(x, str):
            t = _norm(x)
            if len(t) >= _MIN:
                out.add(t)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in _SKIP:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return out


def collides(fp, state):
    """True if any line in fp was posted recently on either channel."""
    return bool(set(fp) & set(state.get("recent_texts", [])))


def remember(state, fp, cap=80):
    """Record an item's lines as recently posted (most-recent-last, capped)."""
    rt = state.setdefault("recent_texts", [])
    for line in fp:
        if line in rt:
            rt.remove(line)
        rt.append(line)
    if len(rt) > cap:
        del rt[: len(rt) - cap]
    return state
