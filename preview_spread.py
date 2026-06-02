#!/usr/bin/env python3
"""Render a SAMPLE SPREAD of new looks for Joseph to react to.
Same brand colors (orange #F87C11, black, navy, cream) in new *forms*, and
new layouts (big statement / quote / numbered list / news-card). PREVIEW ONLY —
nothing here posts; once Joseph picks favorites we fold them into render_card.py.
"""
from pathlib import Path
from PIL import Image, ImageDraw
from render_card import W, H, M, ORANGE, f_brand, f_sys, wrap, bg

OUT = Path("/tmp/preview"); OUT.mkdir(exist_ok=True)

# --- new FORMS of the same brand colors -------------------------------------
PV = {
    # orange IS the background (their orange, just used boldly), dark ink on top
    "ember":    {"bg_top": (250, 138, 28), "bg_bottom": (206, 92, 12),
                 "head": (22, 16, 10), "sub": (40, 28, 16), "muted": (92, 60, 30),
                 "accent": (20, 16, 10), "glow_a": 0},
    # pure blackout with the HEADLINE in brand orange (high-contrast brand)
    "blackout": {"bg_top": (10, 10, 11), "bg_bottom": (18, 16, 14),
                 "head": ORANGE, "sub": (238, 238, 238), "muted": (150, 150, 150),
                 "accent": ORANGE, "glow_a": 38},
    # warm cream with orange headline (a light form that's still loud)
    "inkcream": {"bg_top": (245, 241, 233), "bg_bottom": (229, 222, 209),
                 "head": ORANGE, "sub": (40, 34, 28), "muted": (120, 112, 100),
                 "accent": ORANGE, "glow_a": 46},
    # existing brand looks (for the news-card variety)
    "dark":     {"bg_top": (12, 12, 13), "bg_bottom": (26, 22, 19),
                 "head": (245, 245, 245), "sub": (245, 245, 245), "muted": (165, 165, 165),
                 "accent": ORANGE, "glow_a": 46},
    "midnight": {"bg_top": (9, 12, 20), "bg_bottom": (15, 21, 34),
                 "head": (240, 243, 250), "sub": (240, 243, 250), "muted": (150, 158, 175),
                 "accent": ORANGE, "glow_a": 54},
    "bone":     {"bg_top": (245, 241, 233), "bg_bottom": (229, 222, 209),
                 "head": (26, 22, 18), "sub": (34, 29, 24), "muted": (120, 112, 100),
                 "accent": ORANGE, "glow_a": 60},
    # navy background with the HEADLINE in orange (two brand colors together)
    "navyorange": {"bg_top": (9, 12, 20), "bg_bottom": (15, 21, 34),
                 "head": ORANGE, "sub": (220, 225, 235), "muted": (150, 158, 175),
                 "accent": ORANGE, "glow_a": 50},
}

def _canvas(p):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255)); bg(img, p)
    return img, ImageDraw.Draw(img)

def _handle(d, p):
    hf = f_brand(34); h = "@josephborroto"; w = d.textlength(h, font=hf)
    d.text(((W - w) // 2, H - 96), h, font=hf, fill=p["muted"])

def _save(img, name):
    out = OUT / name; img.convert("RGB").save(out, quality=95); return out

# --- LAYOUT 1: BIG STATEMENT -------------------------------------------------
def big_statement(text, p, name):
    img, d = _canvas(p)
    size, lines = 80, None
    for s in range(168, 72, -6):
        f = f_brand(s); ls = wrap(d, text, f, W - 2 * M)
        if len(ls) <= 4 and max(d.textlength(x, font=f) for x in ls) <= W - 2 * M:
            size, lines = s, ls; break
    if lines is None:
        size = 80; f = f_brand(size); lines = wrap(d, text, f, W - 2 * M)
    f = f_brand(size); lh = int(size * 1.02); total = lh * len(lines)
    y = (H - total) // 2 - 20
    for ln in lines:
        w = d.textlength(ln, font=f); d.text(((W - w) // 2, y), ln, font=f, fill=p["head"]); y += lh
    d.rectangle((W // 2 - 46, y + 26, W // 2 + 46, y + 38), fill=p["accent"])
    _handle(d, p); return _save(img, name)

# --- LAYOUT 2: QUOTE ---------------------------------------------------------
def quote_card(text, p, name):
    img, d = _canvas(p)
    d.text((M - 12, 120), '"', font=f_brand(240), fill=p["accent"])
    size, lines = 60, None
    for s in range(96, 48, -4):
        f = f_brand(s); ls = wrap(d, text, f, W - 2 * M)
        if len(ls) <= 6:
            size, lines = s, ls; break
    f = f_brand(size); lh = int(size * 1.12); y = 440
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    af = f_sys(42, bold=True); d.text((M, y + 36), "— Joseph Borroto", font=af, fill=p["accent"])
    _handle(d, p); return _save(img, name)

# --- LAYOUT 3: NUMBERED LIST -------------------------------------------------
def list_card(title, items, p, name):
    img, d = _canvas(p)
    tf = f_brand(60)
    for i, ln in enumerate(wrap(d, title, tf, W - 2 * M)):
        d.text((M, 150 + i * 66), ln, font=tf, fill=p["head"])
    d.rectangle((M, 150 + 66 * len(wrap(d, title, tf, W - 2 * M)) + 14, M + 120, 150 + 66 * len(wrap(d, title, tf, W - 2 * M)) + 26), fill=p["accent"])
    y = 420
    for i, it in enumerate(items, 1):
        nf = f_brand(92); d.text((M, y - 8), str(i), font=nf, fill=p["accent"])
        itf = f_sys(46, bold=True); ty = y + 6
        for ln in wrap(d, it, itf, W - 2 * M - 160):
            d.text((M + 160, ty), ln, font=itf, fill=p["head"]); ty += 58
        y += 210
    _handle(d, p); return _save(img, name)

# --- LAYOUT 4: NEWS CARD (palette-correct on any color) ----------------------
def news_card(kicker, headline, sub, p, name):
    img, d = _canvas(p)
    kf = f_brand(34); kw = d.textlength(kicker, font=kf)
    d.rounded_rectangle((M, 150, M + kw + 56, 206), 12, fill=p["accent"])
    d.text((M + 28, 162), kicker, font=kf, fill=(245, 245, 245) if p["accent"] == ORANGE else (245, 245, 245))
    size, lines = 64, None
    for s in range(104, 52, -4):
        f = f_brand(s); ls = wrap(d, headline, f, W - 2 * M)
        if len(ls) <= 4:
            size, lines = s, ls; break
    f = f_brand(size); lh = int(size * 1.06); y = 300
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    d.rectangle((M, y + 18, M + 150, y + 30), fill=p["accent"])
    sf = f_sys(54, bold=True); sy = y + 70
    for ln in wrap(d, sub, sf, W - 2 * M):
        d.text((M, sy), ln, font=sf, fill=p["sub"]); sy += 64
    _handle(d, p); return _save(img, name)

# --- LAYOUT 5: BIG STAT / NUMBER --------------------------------------------
def stat_card(big, label, p, name):
    img, d = _canvas(p)
    nf = f_brand(380)
    while d.textlength(big, font=nf) > W - 2 * M and nf.size > 140:
        nf = f_brand(nf.size - 20)
    bw = d.textlength(big, font=nf); ny = H // 2 - 300
    d.text(((W - bw) // 2, ny), big, font=nf, fill=p["accent"])
    lf = f_brand(58); ly = ny + nf.size + 24
    for ln in wrap(d, label, lf, W - 2 * M):
        lw = d.textlength(ln, font=lf); d.text(((W - lw) // 2, ly), ln, font=lf, fill=p["head"]); ly += int(58 * 1.14)
    _handle(d, p); return _save(img, name)

# --- LAYOUT 6: DON'T / DO (comparison) --------------------------------------
def vs_card(top_text, bot_text, p, name):
    img, d = _canvas(p)
    def block(y0, tag, text, tagfill):
        kf = f_brand(34); kw = d.textlength(tag, font=kf)
        d.rounded_rectangle((M, y0, M + kw + 56, y0 + 56), 12, fill=tagfill)
        d.text((M + 28, y0 + 12), tag, font=kf, fill=(245, 245, 245))
        tf = f_brand(64); ty = y0 + 92
        for ln in wrap(d, text, tf, W - 2 * M):
            d.text((M, ty), ln, font=tf, fill=p["head"]); ty += int(64 * 1.06)
    block(200, "DON'T", top_text, p["muted"])
    d.line((M, H // 2, W - M, H // 2), fill=p["accent"], width=4)
    block(H // 2 + 70, "DO", bot_text, p["accent"])
    _handle(d, p); return _save(img, name)

# --- LAYOUT 7: CHECKLIST -----------------------------------------------------
def checklist_card(title, items, p, name):
    img, d = _canvas(p)
    tf = f_brand(60); ty = 150
    for ln in wrap(d, title, tf, W - 2 * M):
        d.text((M, ty), ln, font=tf, fill=p["head"]); ty += 66
    d.rectangle((M, ty + 14, M + 120, ty + 26), fill=p["accent"])
    y = ty + 90; itf = f_sys(46, bold=True); s = 58
    chk = (20, 16, 10) if p["accent"] == ORANGE else (245, 245, 245)
    for it in items:
        d.rounded_rectangle((M, y, M + s, y + s), 10, fill=p["accent"])
        d.line([(M + 14, y + 30), (M + 25, y + 42), (M + 46, y + 15)], fill=chk, width=7)
        ty2 = y + 6
        for ln in wrap(d, it, itf, W - 2 * M - 110):
            d.text((M + 100, ty2), ln, font=itf, fill=p["head"]); ty2 += 56
        y += max(120, (ty2 - y) + 50)
    _handle(d, p); return _save(img, name)

# --- LAYOUT 8: CAROUSEL COVER ------------------------------------------------
def cover_card(kicker, title, p, name):
    img, d = _canvas(p)
    kf = f_brand(34); kw = d.textlength(kicker, font=kf)
    d.rounded_rectangle((M, 150, M + kw + 56, 206), 12, fill=p["accent"])
    d.text((M + 28, 162), kicker, font=kf, fill=(245, 245, 245))
    size, lines = 80, None
    for sz in range(150, 72, -6):
        f = f_brand(sz); ls = wrap(d, title, f, W - 2 * M)
        if len(ls) <= 5:
            size, lines = sz, ls; break
    f = f_brand(size); y = 320; lh = int(size * 1.04)
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    sf = f_brand(40); d.text((M, H - 156), "SWIPE", font=sf, fill=p["accent"])
    sw = d.textlength("SWIPE", font=sf); ax = M + sw + 26; ay = H - 156 + 6
    d.polygon([(ax, ay), (ax, ay + 36), (ax + 32, ay + 18)], fill=p["accent"])
    _handle(d, p); return _save(img, name)

# --- the spread --------------------------------------------------------------
jobs = [
    lambda: big_statement("THE HOOK IS 90% OF THE POST.", PV["ember"], "1_statement_ember.png"),
    lambda: big_statement("POST LESS.\nEDIT HARDER.".replace("\n", " "), PV["blackout"], "2_statement_blackout.png"),
    lambda: quote_card("If they don't stop scrolling, nothing else you made even matters.", PV["midnight"], "3_quote_midnight.png"),
    lambda: quote_card("Average retention is just a slow way to be ignored.", PV["bone"], "4_quote_bone.png"),
    lambda: list_card("3 WAYS TO STOP THE SCROLL",
                      ["Open on motion, not on a face", "Cut every second before the point", "Say the payoff in the first line"],
                      PV["dark"], "5_list_dark.png"),
    lambda: list_card("3 EDITS THAT ADD RETENTION",
                      ["Trim the dead air between words", "Add a cut every 2-3 seconds", "End on a reason to rewatch"],
                      PV["ember"], "6_list_ember.png"),
    lambda: news_card("EDITING", "Your first frame is doing all the work", "Most posts die in the first second.", PV["inkcream"], "7_news_inkcream.png"),
    lambda: news_card("STRATEGY", "Consistency beats going viral once", "Show up daily and the algorithm follows.", PV["midnight"], "8_news_midnight.png"),
    # --- the new batch ---
    lambda: stat_card("90%", "of viewers decide whether to keep watching in the first 3 seconds", PV["blackout"], "9_stat_blackout.png"),
    lambda: vs_card("Start with a slow, polite intro", "Start at the most interesting moment", PV["dark"], "10_vs_dark.png"),
    lambda: checklist_card("POST-READY CHECKLIST",
                      ["Hook lives in the first line", "One clear idea per post", "Caption adds context", "Obvious reason to follow"],
                      PV["bone"], "11_checklist_bone.png"),
    lambda: cover_card("CAROUSEL", "5 edits that keep people watching to the end", PV["ember"], "12_cover_ember.png"),
    lambda: big_statement("STOP MAKING FORGETTABLE CONTENT.", PV["navyorange"], "13_statement_navyorange.png"),
    lambda: stat_card("3 SEC", "is all you get before they scroll past you", PV["bone"], "14_stat_bone.png"),
]
for j in jobs:
    print("rendered:", j())
print("DONE ->", OUT)
