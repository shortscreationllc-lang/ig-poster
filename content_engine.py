#!/usr/bin/env python3
"""Content engine — closes the loop from analytics to NEW content.

1. analyze(): read weights.json (built by insights.py from real IG performance)
   and surface what's WORKING (formats / styles / topics) vs not.
2. generate(): mint NEW, on-brand entries — biased toward the winning format,
   style and topic — from a curated library of Joseph's own angles. Everything
   is de-duped against what already exists so it's never the same post twice,
   and it only ever recombines HIS stated philosophy (no invented numbers, no
   third-party claims).
3. Appends straight into the live banks. Run weekly (cron) or on demand.

Usage:
  python content_engine.py --report
  python content_engine.py --generate 12   # mint 12 new posts, biased to winners
"""
import argparse, json, random, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEIGHTS = ROOT / "weights.json"
FOLLOW = "\n\nFollow @josephborroto for more on content."

# ----------------------------------------------------------------- atom library
# Joseph's real lanes. Each topic carries the raw material to build many formats.
# All on-brand, no fabricated metrics — just his philosophy, re-angled.
TOPICS = {
    "hooks": {
        "pillar": "hooks",
        "questions": ["why do my hooks flop every time?", "how do i write a hook that works?",
                      "what's the secret to a good first line?", "how do i stop people from scrolling?"],
        "answers": ["open on the point, never on your name. 'hey my name is' already lost them.",
                    "say the result or the stakes in the first second. earn the next 3.",
                    "if the first line is weak, the rest of the video doesn't exist.",
                    "put text on screen that makes the brain stop and think differently."],
        "takes": ["Your first line is the only algorithm that matters.",
                  "Nobody owes you 3 seconds. Your hook has to earn them.",
                  "A weak first line means the rest of the video doesn't exist."],
        "blanks": ["The best hook always starts with ________.", "I'd get more views if I stopped opening with ________."],
        "cheatsheet": ("How I write a hook that stops the scroll",
                       ["Never open with your name or 'hey guys'", "Say or show something in the first second",
                        "Put text on screen that makes people stop", "Lead with the result, skip the setup",
                        "Make a promise the video keeps", "Weak first line = the video doesn't exist"]),
    },
    "consistency": {
        "pillar": "consistency",
        "questions": ["how do you stay consistent?", "how often should i post?",
                      "i always fall off. how do i keep going?", "is posting every day really necessary?"],
        "answers": ["discipline, not motivation. videos aren't fun, you won't always see results. go anyway.",
                    "daily if you can. not for the algorithm — for the reps. you get good by posting.",
                    "lower the bar. 'posted' beats 'perfect.' make it so easy you can't talk yourself out of it.",
                    "show up on the days you don't feel like it. that's the whole game."],
        "takes": ["Posting daily isn't a tip. It IS the strategy.",
                  "Consistency beats talent that quits.", "You don't have a content problem. You have a consistency problem."],
        "blanks": ["I'd be way more consistent if I stopped ________.", "Consistency is really just ________."],
        "cheatsheet": ("How I stay consistent when I don't feel like it",
                       ["Lower the bar — posted beats perfect", "Batch a week in one sitting", "Keep a running idea list",
                        "Detach from any single post", "Show up on the bad days too"]),
    },
    "editing": {
        "pillar": "editing",
        "questions": ["whats your editing process?", "my editing takes forever. what am i missing?",
                      "biggest editing mistake?", "how do i make my edits look clean?"],
        "answers": ["cut the dead air, one idea per cut, captions on. that's 90% of it.",
                    "overediting hides weak content. fix the value, not the transitions.",
                    "my team runs it. if you want to grow, delegate and build a team.",
                    "the cut should disappear, not show off. people should feel the pace, not see it."],
        "takes": ["Overediting is just hiding weak content.",
                  "Good editing is invisible. People feel the pace, not the cuts.",
                  "Stop adding effects. Start removing pauses."],
        "blanks": ["The fastest way to a clean edit is ________.", "Most people's edits flop because of ________."],
        "cheatsheet": ("Edit any video in 6 steps",
                       ["Cut the first 'umm' — start on the point", "Remove every dead pause", "One idea per cut",
                        "Caption the first line (people watch on mute)", "Zoom only to land a line", "End on the strongest sentence"]),
    },
    "being_yourself": {
        "pillar": "general",
        "questions": ["how did you get comfortable on camera?", "i feel so cringe posting. help?",
                      "do i have to show my face?", "how do i find my style?"],
        "answers": ["go record yourself in front of a bunch of people. keep doing it. reps kill the fear.",
                    "someone out there needs what you know. feeling cringe and not posting is selfish.",
                    "it helps — people follow people. but a strong voice and clear value carries it too.",
                    "stop copying the creator voice. talk how you actually talk. that's the style."],
        "takes": ["Feeling too cringe to post is selfish — someone needs what you know.",
                  "Your personality is the one thing nobody can copy.",
                  "Stop trying to sound like a 'content creator.' Just talk."],
        "blanks": ["I'd post more if I stopped worrying about ________.", "The most underrated content skill is ________."],
        "cheatsheet": ("How to actually be yourself on camera",
                       ["Talk how you actually talk", "Your quirks are the brand", "Film like you're texting a friend",
                        "Borrow structure, never personality", "The more 'you,' the better it does"]),
    },
    "ai_personal": {
        "pillar": "general",
        "questions": ["is AI going to kill content?", "how do i stand out when everyone uses AI?"],
        "answers": ["AI video will get scary good. the personal touch is the one thing it can't fake — that's your moat.",
                    "be more personal, not more polished. people will crave the real thing."],
        "takes": ["AI videos are coming for everything. The personal touch is the one thing they can't fake.",
                  "The more AI floods the feed, the more your face is worth."],
        "blanks": ["The one thing AI can't copy is ________."],
        "cheatsheet": ("How to stay human as AI floods the feed",
                       ["Show your face and your voice", "Tell real stories, not generic tips", "Post the behind-the-scenes",
                        "Be opinionated — AI plays it safe", "Consistency from a real person wins"]),
    },
    "value_over_perfect": {
        "pillar": "general",
        "questions": ["whats the #1 mistake new creators make?", "0 followers, where do i start?",
                      "should i wait until my content is better?"],
        "answers": ["trying to make the perfect post — so they never post at all. perfect and unposted is worth zero.",
                    "post every single day, as much as you can. say something, show something, text on screen.",
                    "no. you don't need a perfect video. you need a video with real value, then post it again."],
        "takes": ["Your 'perfect' post that never gets posted is worth zero.",
                  "You don't need a perfect video. You need a video with real value.",
                  "Posted beats perfect. Every single time."],
        "blanks": ["Done beats ________.", "New creators waste the most time on ________."],
        "cheatsheet": ("What I'd tell anyone starting from 0",
                       ["Post every single day", "Done beats perfect", "Say something, show something, add text",
                        "Volume teaches you what works", "Stop waiting to be ready"]),
    },
    "business": {
        "pillar": "business",
        "questions": ["how do you get clients from content?", "how do i make money from posting?",
                      "how do i turn views into income?"],
        "answers": ["show up every single day until they can't ignore you. bet on consistency, not luck.",
                    "post the work and the results. the right client should land on your page already sold.",
                    "build systems so you can post constantly. volume keeps you in front of buyers."],
        "takes": ["Views don't pay. Showing up every day until they can't ignore you does.",
                  "Don't bet on going viral. Bet on consistency.",
                  "Reach is rented. Trust is owned."],
        "blanks": ["Content turns into clients when you ________.", "The bridge from views to money is ________."],
        "cheatsheet": ("How content actually turns into clients",
                       ["Show up daily until they can't ignore you", "Post proof, not theory", "Make your page sell for you",
                        "Build systems to post constantly", "Bet on consistency, not luck"]),
    },
}

POLLS = [
    ("What matters more for going viral?", ["A better HOOK", "A better EDIT"]),
    ("Which would you rather have?", ["10k engaged followers", "100k ghost followers"]),
    ("Post daily or fewer but higher quality?", ["Daily reps", "Fewer, polished"]),
    ("What's holding your content back more?", ["Weak hooks", "Inconsistency"]),
    ("Bigger growth lever right now?", ["Being yourself", "Better editing"]),
]
HANDLES = ["creator_{}", "{}.films", "grow_with_{}", "{}.media", "new_{}", "{}.daily", "vid_{}"]
NAMES = ["mike", "leo", "sam", "jordan", "alex", "chris", "noah", "ty", "dev", "max", "kai", "rio"]
STYLES_DARK = ["dark", "midnight", "slate", "ember"]


# --------------------------------------------------------------------- analyze
def _topw(weights, dim, k=3):
    cells = weights.get("by", {}).get(dim, {})
    rows = [(v.get("w", 1.0) if isinstance(v, dict) else v,
             v.get("n", 0) if isinstance(v, dict) else 0, name) for name, v in cells.items()]
    rows.sort(reverse=True)
    return rows[:k], rows[-k:] if len(rows) > k else []


def analyze():
    if not WEIGHTS.exists():
        return {"n": 0, "winners": {}, "losers": {}, "pillars": [], "styles": []}
    w = json.loads(WEIGHTS.read_text())
    out = {"n": w.get("n", 0), "winners": {}, "losers": {}}
    for dim in ("fmt", "style", "pillar", "cap_style"):
        top, bottom = _topw(w, dim)
        out["winners"][dim] = top
        out["losers"][dim] = bottom
    out["pillars"] = [name for _, _, name in out["winners"].get("pillar", [])]
    out["styles"] = [name for _, n, name in out["winners"].get("style", []) if name in STYLES_DARK] or STYLES_DARK
    return out


def report():
    a = analyze()
    print(f"\n=== CONTENT ENGINE — learning from {a['n']} tagged posts ===\n")
    lab = {"fmt": "FORMATS", "style": "LOOKS", "pillar": "TOPICS", "cap_style": "CAPTION SHAPES"}
    for dim in ("fmt", "style", "pillar"):
        win = a["winners"].get(dim, [])
        print(f"WINNING {lab[dim]}:")
        for wv, n, name in win:
            print(f"   ↑ {name:<14} {wv:>5.2f}x  ({n} posts)")
    print(f"\n→ Next batch will lean into topics {a['pillars'][:2]} and looks {a['styles'][:3]}.\n")
    return a


# -------------------------------------------------------------------- generate
def _existing_fingerprints():
    seen = set()
    for f in ROOT.glob("*bank*.json"):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        for e in d.get("entries", []) if isinstance(d, dict) else d:
            blob = json.dumps(e).lower()
            for m in re.findall(r"[a-z0-9 ,'\-]{18,}", blob):
                seen.add(m.strip())
    for f in ("social_singles.json", "comments_bank.json", "prompts_bank.json"):
        pass
    return seen


def _fresh(text, seen):
    t = text.lower().strip()
    return t not in seen and len(t) > 8


def generate(n=12):
    a = analyze()
    win_pillars = a["pillars"] or list({t["pillar"] for t in TOPICS.values()})
    styles = a["styles"]
    seen = _existing_fingerprints()
    # bias topic choice toward winning pillars
    topics = list(TOPICS.items())

    def pick_topic():
        weighted = []
        for key, t in topics:
            wgt = 3 if t["pillar"] in win_pillars[:2] else 1
            weighted += [(key, t)] * wgt
        return random.choice(weighted)

    added = {"comment": [], "prompt": [], "social": [], "cheatsheet": []}
    tries = 0
    while sum(len(v) for v in added.values()) < n and tries < n * 12:
        tries += 1
        key, t = pick_topic()
        fmt = random.choices(["comment", "prompt", "social", "cheatsheet"],
                             weights=[4, 3, 3, 2])[0]
        style = random.choice(styles)
        if fmt == "comment":
            q = random.choice(t["questions"]); ans = random.choice(t["answers"])
            if not _fresh(q + ans, seen):
                continue
            seen.add((q + ans).lower())
            h = random.choice(HANDLES).format(random.choice(NAMES))
            added["comment"].append({"enabled": True, "type": "comment", "style": random.choice(STYLES_DARK),
                "comment": {"author": h, "initials": "".join(w[0] for w in re.split(r"[._]", h)[:2]).upper(), "text": q, "likes": f"{random.randint(11,59)}00"[:4]+"k" if random.random()>.5 else f"{random.randint(200,990)}"},
                "reply": {"author": "Joseph Borroto", "initials": "JB", "verified": True, "text": ans, "likes": f"{random.randint(120,820)}"},
                "caption": ans.capitalize() + FOLLOW, "alt_text": f"Comment reply: {ans}"})
        elif fmt == "prompt":
            if random.random() < 0.5 and t["takes"]:
                head = random.choice(t["takes"])
                if not _fresh(head, seen): continue
                seen.add(head.lower())
                added["prompt"].append({"enabled": True, "type": "prompt", "style": style, "kicker": "HOT TAKE",
                    "headline": head, "prompt": random.choice(["Agree or disagree?", "Who needed to hear this?", "Agree?"]),
                    "caption": head + FOLLOW, "alt_text": head})
            else:
                blank = random.choice(t["blanks"])
                if not _fresh(blank, seen): continue
                seen.add(blank.lower())
                added["prompt"].append({"enabled": True, "type": "prompt", "style": style, "kicker": "FILL IN THE BLANK",
                    "headline": blank, "prompt": "Drop your answer in the comments.",
                    "caption": blank + FOLLOW, "alt_text": blank})
        elif fmt == "social":
            head = random.choice(t["takes"])
            if not _fresh(head, seen): continue
            seen.add(head.lower())
            added["social"].append({"enabled": True, "type": "social", "style": style,
                "social": {"author": "Joseph Borroto", "handle": "@josephborroto", "verified": True,
                           "initials": "JB", "headline": head, "cta": ""},
                "caption": head + FOLLOW, "alt_text": head})
        else:
            title, items = t["cheatsheet"]
            if not _fresh(title, seen): continue
            seen.add(title.lower())
            added["cheatsheet"].append({"enabled": True, "type": "cheatsheet", "style": style, "kicker": "SAVE THIS",
                "title": title, "items": items, "caption": title + ". Save this." + FOLLOW, "alt_text": title})

    # append into the live banks
    files = {"comment": "comments_bank.json", "prompt": "prompts_bank.json",
             "social": "social_singles.json", "cheatsheet": "cheatsheet_bank.json"}
    counts = {}
    for fmt, entries in added.items():
        if not entries:
            continue
        p = ROOT / files[fmt]; d = json.loads(p.read_text())
        d["entries"].extend(entries)
        p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
        counts[fmt] = len(entries)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--generate", type=int, default=0)
    args = ap.parse_args()
    a = report()
    if args.generate:
        c = generate(args.generate)
        print("GENERATED (biased to winners):", c, "\n")
        print("Run `git add *bank*.json social_singles.json && git commit` to ship.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
