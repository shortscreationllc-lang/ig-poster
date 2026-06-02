#!/usr/bin/env python3
"""Rotating, SEO-optimized captions. 2026 reality: Instagram is a search engine,
so the FIRST LINE is a keyword-rich hook (that's what ranks you), hashtags are
just 3-5 niche categorizers, and 'sends' are the top reach signal — so some
styles push shares. We rotate 6 styles to A/B test what actually moves.
"""
HANDLE = "@josephborroto"

# 3-5 niche hashtag sets (broad tags add nothing in 2026 — niche only).
TAG_SETS = [
    "#shortformvideo #videoediting #contentstrategy #reelstips",
    "#contentcreator #videoediting #hookwriting #instagramreels",
    "#shortformcontent #editingtips #audienceretention #reels",
    "#contentcreation #videocontent #socialmediatips #creatortips",
    "#reelsstrategy #videoediting #shortform #growthtips",
]
QUESTIONS = [
    "What's stopping people from finishing your videos?",
    "How long do your first 3 seconds really hold?",
    "Which one are you guilty of?",
    "What would you add to this list?",
]
SEND_CTAS = [
    "Send this to a creator who needs it.",
    "Share this with someone posting this week.",
    "Save this for your next edit.",
]
FOLLOW_CTAS = [
    f"Follow {HANDLE} for more short-form tips.",
    f"Follow {HANDLE} — new one every few days.",
    f"More like this: follow {HANDLE}.",
]


def caption_for(hook, idx, value=""):
    """Build a caption. `hook` = keyword-rich first line (always SEO-leading).
    `idx` rotates the style (pass a per-post counter). `value` = optional 2nd line.
    """
    tags = TAG_SETS[idx % len(TAG_SETS)]
    q = QUESTIONS[idx % len(QUESTIONS)]
    send = SEND_CTAS[idx % len(SEND_CTAS)]
    follow = FOLLOW_CTAS[idx % len(FOLLOW_CTAS)]
    body = f"{hook}\n\n{value}".strip()
    style = idx % 6
    if style == 0:   # hook + value + follow CTA + 4 tags
        return f"{body}\n\n{follow}\n\n{tags}"
    if style == 1:   # pure SEO caption — no hashtags, no CTA
        return body
    if style == 2:   # one sentence only (the hook)
        return hook
    if style == 3:   # hook + question (drives comments) + 3 tags
        return f"{body}\n\n{q}\n\n{' '.join(tags.split()[:3])}"
    if style == 4:   # hook + SEND cta (the #1 reach signal) + 3 tags
        return f"{body}\n\n{send}\n\n{' '.join(tags.split()[:3])}"
    # style 5: hook + follow CTA, no hashtags
    return f"{body}\n\n{follow}"


if __name__ == "__main__":
    for i in range(6):
        print(f"--- style {i} ---")
        print(caption_for("90% of viewers decide in the first 3 seconds whether to keep watching.",
                          i, "Your hook is doing almost all the work."))
        print()
