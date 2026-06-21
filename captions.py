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
    "#contentcreatortips #reelsforbusiness #videomarketing #hooks",
    "#instagramgrowth #shortformstrategy #editingforcreators #reelideas",
    "#personalbrand #contentcreators #videotips #scrollstoppers",
    "#creatoreconomy #reelstutorial #videohooks #organicgrowth",
    "#smallbusinessmarketing #contenttips #reelsofinstagram #videoediting",
]
QUESTIONS = [
    "What's stopping people from finishing your videos?",
    "How long do your first 3 seconds really hold?",
    "Which one are you guilty of?",
    "What would you add to this list?",
    "Be honest — which one is you?",
    "What's the hardest part of posting for you?",
    "Agree or disagree? Tell me below.",
    "What would you ask me if I was sitting across from you?",
    "Drop a 🎯 if this hit.",
    "What's your biggest content struggle right now?",
]
SEND_CTAS = [
    "Send this to a creator who needs it.",
    "Share this with someone posting this week.",
    "Send this to someone whose videos flop.",
    "Tag the friend who keeps overthinking their content.",
    "Send this to your editor.",
    "Share this to your story if it helped.",
]
SAVE_CTAS = [
    "Save this for your next post.",
    "Save this so you don't forget it.",
    "Bookmark this for your next video.",
    "Save this before your next batch day.",
    "Save it — you'll need it on a slow day.",
    "Keep this where you'll actually see it.",
]
FOLLOW_CTAS = [
    f"Follow {HANDLE} for more short-form tips.",
    f"Follow {HANDLE} — new one every few days.",
    f"More like this: follow {HANDLE}.",
    f"Follow {HANDLE} for the stuff nobody tells you about content.",
    f"{HANDLE} drops one of these every few days. Follow along.",
]


def caption_for(hook, idx, value="", style=None):
    """Build a caption. `hook` = keyword-rich first line (always SEO-leading).
    `idx` rotates the wording (pass a per-post counter). `value` = optional 2nd
    line. `style` (0-5) forces a specific caption shape — when the weighting loop
    has learned which CTA shape earns the most saves/sends, it pins that one;
    leave None to rotate by `idx`.
    """
    tags = TAG_SETS[idx % len(TAG_SETS)]
    q = QUESTIONS[idx % len(QUESTIONS)]
    send = SEND_CTAS[idx % len(SEND_CTAS)]
    save = SAVE_CTAS[idx % len(SAVE_CTAS)]
    follow = FOLLOW_CTAS[idx % len(FOLLOW_CTAS)]
    body = f"{hook}\n\n{value}".strip()
    style = (idx % 6) if style is None else (style % 6)
    if style == 0:   # hook + value + SAVE CTA + 4 tags (drives saves)
        return f"{body}\n\n{save}\n\n{tags}"
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
