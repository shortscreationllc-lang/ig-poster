#!/usr/bin/env python3
"""Render an on-brand Shorts Creation / Joseph Borroto news-style card.

Uses League Spartan Bold (Joseph's brand font), the brand orange #EE892B,
and composites the real logo. 1080x1350 (4:5 Instagram portrait).
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DOWNLOADS = ROOT.parent

# --- brand ---
ORANGE = (248, 124, 17)      # #F87C11 sampled straight from the logo
WHITE = (245, 245, 245)
MUTED = (165, 165, 165)
BG_TOP = (12, 12, 13)
BG_BOTTOM = (26, 22, 19)
PANEL = (20, 20, 21)
PANEL_LINE = (60, 56, 52)

# Headline font: bundled in repo fonts/ first (CI-safe), else local Downloads copy.
def _first_existing(paths):
    for p in paths:
        if p and Path(p).exists():
            return str(p)
    return None

FONT_BOLD = _first_existing([
    ROOT / "fonts" / "league-spartan.bold.ttf",
    DOWNLOADS / "fwdcarvemysignalllogofiles" / "league-spartan.bold.ttf",
])

# Body font: bundled -> macOS Arial -> Ubuntu/CI DejaVu -> PIL default.
SYS_REG = _first_existing([
    ROOT / "fonts" / "body.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
])
SYS_BOLD = _first_existing([
    ROOT / "fonts" / "body-bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
])

# Joseph's real profile photo — drop a square-ish headshot at any of these paths
# and it's used as the avatar on social cards (falls back to a monogram if absent).
AVATAR_PATH = _first_existing([
    ROOT / "assets" / "joseph-avatar.jpg",
    ROOT / "assets" / "joseph-avatar.png",
    ROOT / "assets" / "avatar.jpg",
])

W, H = 1080, 1350
M = 110  # side margin


def f_brand(size):
    return ImageFont.truetype(FONT_BOLD, size) if FONT_BOLD else ImageFont.load_default()


def f_sys(size, bold=False):
    p = SYS_BOLD if bold else SYS_REG
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


def wrap(draw, text, fnt, max_w):
    out, line = [], ""
    for word in text.split():
        c = f"{line} {word}".strip()
        if draw.textlength(c, font=fnt) <= max_w:
            line = c
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    return out


# Two palettes so morning/evening posts don't look identical.
PALETTES = {
    "dark": {
        "bg_top": (12, 12, 13), "bg_bottom": (26, 22, 19),
        "head": (245, 245, 245), "sub": (245, 245, 245), "muted": (165, 165, 165),
        "panel": (20, 20, 21), "panel_line": (60, 56, 52),
        "kicker_text": (12, 12, 12), "glow_a": 46,
    },
    "light": {
        "bg_top": (245, 244, 242), "bg_bottom": (231, 228, 223),
        "head": (20, 18, 16), "sub": (28, 26, 24), "muted": (110, 106, 100),
        "panel": (255, 255, 255), "panel_line": (210, 205, 198),
        "kicker_text": (255, 255, 255), "glow_a": 60,
    },
    # second dark look — deep navy/blue-black, cooler than 'dark'
    "midnight": {
        "bg_top": (9, 12, 20), "bg_bottom": (15, 21, 34),
        "head": (240, 243, 250), "sub": (240, 243, 250), "muted": (150, 158, 175),
        "panel": (16, 21, 32), "panel_line": (44, 52, 72),
        "kicker_text": (12, 12, 12), "glow_a": 54,
    },
    # second light look — warmer cream/paper, softer than 'light'
    "bone": {
        "bg_top": (245, 241, 233), "bg_bottom": (229, 222, 209),
        "head": (26, 22, 18), "sub": (34, 29, 24), "muted": (120, 112, 100),
        "panel": (255, 253, 248), "panel_line": (208, 200, 186),
        "kicker_text": (255, 255, 255), "glow_a": 64,
    },
    # NEW FORMS of the same brand colors — orange moved into the HEADLINE.
    # blackout: near-black bg with an orange headline (high-contrast brand).
    "blackout": {
        "bg_top": (12, 12, 13), "bg_bottom": (20, 17, 14),
        "head": ORANGE, "sub": (235, 235, 235), "muted": (150, 150, 150),
        "panel": (20, 20, 21), "panel_line": (60, 56, 52),
        "kicker_text": (12, 12, 12), "glow_a": 40,
    },
    # navy bg with an orange headline (two brand colors together).
    "navyorange": {
        "bg_top": (9, 12, 20), "bg_bottom": (15, 21, 34),
        "head": ORANGE, "sub": (220, 225, 235), "muted": (150, 158, 175),
        "panel": (16, 21, 32), "panel_line": (44, 52, 72),
        "kicker_text": (12, 12, 12), "glow_a": 50,
    },
    # warm cream with an orange headline (a light form that still reads loud).
    "creamorange": {
        "bg_top": (245, 241, 233), "bg_bottom": (229, 222, 209),
        "head": ORANGE, "sub": (40, 34, 28), "muted": (120, 112, 100),
        "panel": (255, 253, 248), "panel_line": (208, 200, 186),
        "kicker_text": (255, 255, 255), "glow_a": 50,
    },
    # deep BURNT-orange on near-black — a darker, moodier shade of the brand.
    "ember": {
        "bg_top": (14, 10, 8), "bg_bottom": (24, 14, 9),
        "head": (214, 100, 28), "sub": (236, 226, 216), "muted": (150, 130, 115),
        "panel": (22, 16, 12), "panel_line": (70, 50, 38),
        "kicker_text": (16, 12, 10), "glow_a": 44, "accent": (214, 100, 28),
    },
    # cool SLATE blue-grey with orange — a different cool tone than navy.
    "slate": {
        "bg_top": (20, 24, 28), "bg_bottom": (30, 36, 42),
        "head": (238, 242, 245), "sub": (220, 226, 230), "muted": (150, 160, 168),
        "panel": (26, 31, 36), "panel_line": (58, 66, 74),
        "kicker_text": (12, 12, 12), "glow_a": 48,
    },
    # FULL ORANGE background with bold BLACK words — the loud pattern-break.
    "orangepop": {
        "bg_top": (245, 138, 28), "bg_bottom": (236, 110, 12),
        "head": (20, 16, 12), "sub": (28, 22, 16), "muted": (96, 64, 32),
        "panel": (250, 196, 130), "panel_line": (200, 120, 40),
        "kicker_text": (245, 238, 230), "glow_a": 0, "accent": (20, 16, 12),
    },
}


def bg(img, p):
    d = ImageDraw.Draw(img)
    bt, bb = p["bg_top"], p["bg_bottom"]
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(bt[i] + (bb[i] - bt[i]) * t) for i in range(3)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(560, 0, -6):
        a = int(p["glow_a"] * (1 - r / 560))
        gd.ellipse((-300, -260, r, r), fill=ORANGE + (a,))
    img.alpha_composite(glow)


def draw_card(item, out_path, style="dark"):
    p = PALETTES.get(style, PALETTES["dark"])
    img = Image.new("RGBA", (W, H), p["bg_top"] + (255,))
    bg(img, p)
    d = ImageDraw.Draw(img)
    WHITE, MUTED, PANEL, PANEL_LINE = p["head"], p["muted"], p["panel"], p["panel_line"]

    # kicker / category tag (news vibe)
    kicker = item.get("kicker", "SHORTS CREATION").upper()
    kf = f_brand(30)
    d.rounded_rectangle((M, 150, M + d.textlength(kicker, font=kf) + 56, 150 + 56),
                        radius=10, fill=ORANGE)
    d.text((M + 28, 150 + 12), kicker, font=kf, fill=p["kicker_text"])

    # headline (League Spartan Bold) — auto-fit into a fixed zone so any
    # length lays out cleanly. Pick the largest size whose wrapped lines fit.
    HEAD_TOP, HEAD_MAX_H = 252, 540
    head_size, head_lines, line_h = 104, None, 0
    for size in range(104, 52, -4):
        hf = f_brand(size)
        lines = wrap(d, item["headline"], hf, W - 2 * M)
        lh = int(size * 1.06)
        if len(lines) * lh <= HEAD_MAX_H:
            head_size, head_lines, line_h = size, lines, lh
            break
    if head_lines is None:  # extreme fallback
        hf = f_brand(56)
        head_lines, line_h = wrap(d, item["headline"], hf, W - 2 * M), 60
    hf = f_brand(head_size)
    y = HEAD_TOP
    for line in head_lines:
        d.text((M, y), line, font=hf, fill=WHITE)
        y += line_h

    # orange divider — fixed anchor below the headline zone
    div_y = HEAD_TOP + HEAD_MAX_H + 30
    d.rounded_rectangle((M, div_y, M + 230, div_y + 9), radius=4, fill=ORANGE)

    # subheadline (bold) — fixed anchor, auto-fit width
    sub_size = 58
    sf = f_sys(sub_size, bold=True)
    while d.textlength(item["subheadline"], font=sf) > (W - 2 * M) and sub_size > 34:
        sub_size -= 4
        sf = f_sys(sub_size, bold=True)
    sy = div_y + 60
    for line in wrap(d, item["subheadline"], sf, W - 2 * M):
        d.text((M, sy), line, font=sf, fill=p["sub"])
        sy += int(sub_size * 1.18)

    # proof panel — fixed, auto-fit up to 3 lines so nothing gets cut
    box_top, box_h = 1015, 150
    proof_size = 34
    pf = f_sys(proof_size)
    plines = wrap(d, item["proof"], pf, W - 2 * M - 70)
    while len(plines) > 3 and proof_size > 24:
        proof_size -= 2
        pf = f_sys(proof_size)
        plines = wrap(d, item["proof"], pf, W - 2 * M - 70)
    plines = plines[:3]
    d.rounded_rectangle((M, box_top, W - M, box_top + box_h), radius=20,
                        outline=PANEL_LINE, width=2, fill=PANEL)
    lh = int(proof_size * 1.3)
    py = box_top + (box_h - lh * len(plines)) // 2
    for i, line in enumerate(plines):
        d.text((M + 35, py), line, font=pf, fill=WHITE if i == 0 else MUTED)
        py += lh

    # personal-brand footer: orange dash + name + handle
    fy = H - 150
    d.rounded_rectangle((M, fy + 14, M + 46, fy + 24), radius=5, fill=ORANGE)
    nf = f_brand(40)
    d.text((M + 70, fy - 4), "JOSEPH BORROTO", font=nf, fill=p["head"])
    hf2 = f_sys(28)
    d.text((M + 72, fy + 46), "@josephborroto", font=hf2, fill=MUTED)

    img.convert("RGB").save(out_path, quality=95)
    return out_path


def _footer(d, p):
    fy = H - 150
    d.rounded_rectangle((M, fy + 14, M + 46, fy + 24), radius=5, fill=ORANGE)
    nf = f_brand(40)
    d.text((M + 70, fy - 4), "JOSEPH BORROTO", font=nf, fill=p["head"])
    hf2 = f_sys(28)
    d.text((M + 72, fy + 46), "@josephborroto", font=hf2, fill=p["muted"])


def _fit_lines(d, text, max_w, max_h, start, floor, lh_mult=1.06):
    """Return (font, lines, line_height) for the biggest brand size that fits."""
    for size in range(start, floor - 1, -4):
        f = f_brand(size)
        ls = wrap(d, text, f, max_w)
        lh = int(size * lh_mult)
        if len(ls) * lh <= max_h:
            return f, ls, lh
    f = f_brand(floor)
    return f, wrap(d, text, f, max_w), int(floor * lh_mult)


def _new_img(style):
    p = PALETTES.get(style, PALETTES["dark"])
    img = Image.new("RGBA", (W, H), p["bg_top"] + (255,))
    bg(img, p)
    return img, ImageDraw.Draw(img), p


def draw_quote(item, out_path, style="midnight"):
    """Big centered quotation — for things Joseph has said."""
    img, d, p = _new_img(style)
    _kicker(d, item.get("kicker", "ON CONTENT"), p)
    # giant orange quote mark
    d.text((M - 10, 250), "“", font=f_brand(220), fill=ORANGE)
    f, lines, lh = _fit_lines(d, item["headline"], W - 2 * M, 560, 92, 52)
    y = 470
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    y += 30
    d.rounded_rectangle((M, y, M + 230, y + 9), radius=4, fill=ORANGE)
    if item.get("subheadline"):
        y += 56
        sf = f_sys(44)
        for ln in wrap(d, item["subheadline"], sf, W - 2 * M):
            d.text((M, y), ln, font=sf, fill=p["muted"]); y += 54
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_versus(item, out_path, style="dark"):
    """Two-panel layout for Myth/Truth or This/That comparisons."""
    img, d, p = _new_img(style)
    _kicker(d, item.get("kicker", "MYTH VS TRUTH"), p)
    top_label = item.get("top_label", "MYTH")
    bot_label = item.get("bottom_label", "TRUTH")
    # Panel A (problem) — muted/red-ish outline
    ax, ay, aw, ah = M, 270, W - 2 * M, 380
    d.rounded_rectangle((ax, ay, ax + aw, ay + ah), radius=24, fill=p["panel"], outline=p["panel_line"], width=2)
    lf = f_brand(34)
    d.text((ax + 36, ay + 30), top_label.upper(), font=lf, fill=p["muted"])
    tf, tl, tlh = _fit_lines(d, item["top"], aw - 72, ah - 130, 60, 36)
    ty = ay + 100
    for ln in tl:
        d.text((ax + 36, ty), ln, font=tf, fill=p["head"]); ty += tlh
    # Panel B (answer) — orange highlight
    by = ay + ah + 40
    d.rounded_rectangle((ax, by, ax + aw, by + ah), radius=24, fill=ORANGE)
    d.text((ax + 36, by + 30), bot_label.upper(), font=lf, fill=(20, 14, 6))
    bf, bl, blh = _fit_lines(d, item["bottom"], aw - 72, ah - 130, 60, 36)
    bly = by + 100
    for ln in bl:
        d.text((ax + 36, bly), ln, font=bf, fill=(20, 14, 6)); bly += blh
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_value(item, out_path, style="dark"):
    """Generic value card with a heading + up to ~5 bullet lines.

    Used for: video ideas, written news, behind-the-process, safe results.
    item: {kicker, headline, bullets:[...], footer_note?}
    """
    img, d, p = _new_img(style)
    _kicker(d, item.get("kicker", "VALUE"), p)
    f, lines, lh = _fit_lines(d, item["headline"], W - 2 * M, 360, 88, 48)
    bf = f_sys(42)
    bullets = item.get("bullets", [])[:5]
    rows = [wrap(d, b, bf, W - (M + 44) - M) for b in bullets]
    total = len(lines) * lh + 24 + 9 + 60 + sum(len(wl) * 52 + 22 for wl in rows)
    y = max(260, (H - total) // 2)        # vertically center the block (below the kicker)
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    y += 24
    d.rounded_rectangle((M, y, M + 230, y + 9), radius=4, fill=ORANGE)
    y += 60
    for wl in rows:
        # orange dot + wrapped text
        d.ellipse((M, y + 16, M + 16, y + 32), fill=ORANGE)
        bx = M + 44
        for j, ln in enumerate(wl):
            d.text((bx, y), ln, font=bf, fill=p["head"] if j == 0 else p["sub"]); y += 52
        y += 22
    if item.get("footer_note"):
        nf = f_sys(34)
        d.text((M, H - 240), item["footer_note"], font=nf, fill=p["muted"])
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_testimonial(item, out_path, style="bone"):
    """Anonymized client testimonial card. Requires a REAL quote in item['quote']."""
    img, d, p = _new_img(style)
    _kicker(d, "CLIENT WIN", p)
    d.text((M - 10, 250), "“", font=f_brand(220), fill=ORANGE)
    f, lines, lh = _fit_lines(d, item["quote"], W - 2 * M, 560, 80, 44)
    y = 480
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    y += 30
    d.rounded_rectangle((M, y, M + 180, y + 9), radius=4, fill=ORANGE)
    y += 50
    af = f_sys(40, bold=True)
    d.text((M, y), "— " + item.get("attribution", "a Shorts Creation client"), font=af, fill=p["muted"])
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_stat(item, out_path, style="midnight"):
    """Big-number / stat card. item: {kicker, stat, headline, subheadline?}
    The stat is huge and orange (e.g. '3s', '2x', '90%')."""
    img, d, p = _new_img(style)
    _kicker(d, item.get("kicker", "THE NUMBER"), p)
    # giant stat
    sf = f_brand(360)
    stat = str(item["stat"])
    # shrink if very wide
    while d.textlength(stat, font=sf) > (W - 2 * M) and sf.size > 120:
        sf = f_brand(sf.size - 20)
    d.text((M - 8, 250), stat, font=sf, fill=ORANGE)
    y = 250 + int(sf.size * 1.05)
    f, lines, lh = _fit_lines(d, item["headline"], W - 2 * M, 300, 80, 44)
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    if item.get("subheadline"):
        y += 20
        subf = f_sys(42)
        for ln in wrap(d, item["subheadline"], subf, W - 2 * M):
            d.text((M, y), ln, font=subf, fill=p["muted"]); y += 50
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_checklist(item, out_path, style="dark"):
    """Checklist card — orange ✓ marks instead of dots. item: {kicker, headline, bullets}"""
    img, d, p = _new_img(style)
    _kicker(d, item.get("kicker", "CHECKLIST"), p)
    f, lines, lh = _fit_lines(d, item["headline"], W - 2 * M, 320, 84, 48)
    bf = f_sys(42)
    rows = [wrap(d, b, bf, W - (M + 64) - M) for b in item.get("bullets", [])[:6]]
    total = len(lines) * lh + 24 + 9 + 56 + sum(len(wl) * 50 + 22 for wl in rows)
    y = max(260, (H - total) // 2)        # vertically center the block (below the kicker)
    for ln in lines:
        d.text((M, y), ln, font=f, fill=p["head"]); y += lh
    y += 24
    d.rounded_rectangle((M, y, M + 230, y + 9), radius=4, fill=ORANGE)
    y += 56
    for wl in rows:
        d.rounded_rectangle((M, y + 4, M + 40, y + 44), radius=8, fill=ORANGE)
        d.line([(M + 9, y + 24), (M + 18, y + 34)], fill=(20, 14, 6), width=5)
        d.line([(M + 18, y + 34), (M + 33, y + 13)], fill=(20, 14, 6), width=5)
        bx = M + 64
        for j, ln in enumerate(wl):
            d.text((bx, y), ln, font=bf, fill=p["head"] if j == 0 else p["sub"]); y += 50
        y += 22
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_statement(item, out_path, style="dark"):
    """Bold statement — huge centered text, minimal. item: {kicker?, headline}"""
    img, d, p = _new_img(style)
    if item.get("kicker"):
        _kicker(d, item["kicker"], p)
    # large headline, vertically centered
    f, lines, lh = _fit_lines(d, item["headline"], W - 2 * M, 760, 120, 60)
    block_h = len(lines) * lh
    y = (H - block_h) // 2 - 40
    for ln in lines:
        w = d.textlength(ln, font=f)
        d.text(((W - w) / 2, y), ln, font=f, fill=p["head"]); y += lh
    # centered orange underline
    d.rounded_rectangle(((W - 200) / 2, y + 16, (W + 200) / 2, y + 26), radius=5, fill=ORANGE)
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def _kicker(d, text, p):
    kf = f_brand(30)
    d.rounded_rectangle((M, 150, M + d.textlength(text.upper(), font=kf) + 56, 206),
                        radius=10, fill=ORANGE)
    d.text((M + 28, 162), text.upper(), font=kf, fill=p["kicker_text"])


def _new(style):
    p = PALETTES.get(style, PALETTES["dark"])
    img = Image.new("RGBA", (W, H), p["bg_top"] + (255,))
    bg(img, p)
    return img, ImageDraw.Draw(img), p


def draw_cover(cover, kicker, out_path, style="dark"):
    """Carousel slide 1 — big hook + 'swipe' nudge."""
    img, d, p = _new(style)
    _kicker(d, kicker, p)
    # big headline auto-fit
    HEAD_TOP, HEAD_MAX_H = 280, 640
    lines, lh, hf = None, 0, None
    for size in range(110, 52, -4):
        f = f_brand(size)
        ls = wrap(d, cover["headline"], f, W - 2 * M)
        h = int(size * 1.06)
        if len(ls) * h <= HEAD_MAX_H:
            lines, lh, hf = ls, h, f
            break
    if lines is None:
        hf = f_brand(56); lines = wrap(d, cover["headline"], hf, W - 2 * M); lh = 60
    y = HEAD_TOP
    for ln in lines:
        d.text((M, y), ln, font=hf, fill=p["head"]); y += lh
    y += 24
    d.rounded_rectangle((M, y, M + 230, y + 9), radius=4, fill=ORANGE)
    y += 56
    sf = f_sys(50, bold=True)
    for ln in wrap(d, cover.get("subheadline", ""), sf, W - 2 * M):
        d.text((M, y), ln, font=sf, fill=p["sub"]); y += 60
    # swipe nudge
    sw = f_sys(30, bold=True)
    d.text((M, H - 230), "Swipe →", font=sw, fill=ORANGE)
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


# ----------------------------------------------------------------- X-post hook
def _circle_photo(img, x, y, r, path, focus=(0.5, 0.44)):
    """Center-crop `path` to a circle of radius r and paste at (x,y). `focus`
    keeps the face centered (slightly above the vertical middle by default)."""
    from PIL import ImageOps
    av = ImageOps.fit(Image.open(path).convert("RGB"), (2 * r, 2 * r),
                      Image.LANCZOS, centering=focus)
    mask = Image.new("L", (2 * r, 2 * r), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * r, 2 * r), fill=255)
    img.paste(av, (x, y), mask)


def _put_avatar(img, d, x, y, r, initials, fill, photo=None, use_default=False, focus=(0.5, 0.44)):
    """Real photo if available, else a monogram circle. `use_default` allows
    falling back to Joseph's global AVATAR_PATH (only for his own avatar, never
    for a third-party reply)."""
    src = photo or (str(AVATAR_PATH) if (use_default and AVATAR_PATH) else None)
    if src and Path(src).exists():
        try:
            _circle_photo(img, x, y, r, src, focus); return
        except Exception:
            pass
    _avatar(d, x, y, r, initials, fill)


def _avatar(d, x, y, r, initials, fill):
    """A round monogram avatar — no external image needed."""
    d.ellipse((x, y, x + 2 * r, y + 2 * r), fill=fill)
    f = f_brand(int(r * 0.95))
    tw = d.textlength(initials, font=f); asc, desc = f.getmetrics()
    d.text((x + r - tw / 2, y + r - (asc + desc) / 2 - 2), initials, font=f, fill=(255, 255, 255))


def _verified(d, cx, cy, r):
    """Blue X-style verified badge."""
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(29, 155, 240))
    w = max(3, int(r * 0.22))
    d.line([(cx - r * 0.46, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.42)], fill=(255, 255, 255), width=w)
    d.line([(cx - r * 0.1, cy + r * 0.42), (cx + r * 0.5, cy - r * 0.4)], fill=(255, 255, 255), width=w)


def _heart(d, cx, cy, s, fill):
    """A small filled heart (for the reaction pill) — drawn, so no emoji font needed."""
    r = s * 0.5
    d.ellipse((cx - s * 0.5, cy - r * 0.55, cx - s * 0.02, cy + r * 0.45), fill=fill)
    d.ellipse((cx + s * 0.02, cy - r * 0.55, cx + s * 0.5, cy + r * 0.45), fill=fill)
    d.polygon([(cx - s * 0.46, cy + r * 0.05), (cx + s * 0.46, cy + r * 0.05),
               (cx, cy + s * 0.62)], fill=fill)


def draw_social_hook(item, out_path, style="dark"):
    """Carousel slide 1 styled as an X (Twitter) post: profile + bold claim, an
    embedded reply that shows a real result, and a blue 'here's how' CTA. A high-
    converting social-proof hook that leads into the breakdown slides."""
    img, d, p = _new(style)
    MX = 96; INNER = W - 2 * MX
    blue = (45, 140, 255)
    # ---- author row
    top = 150; r = 58
    _put_avatar(img, d, MX, top, r, item.get("initials", "JB"), ORANGE,
                photo=item.get("photo"), use_default=True,
                focus=tuple(item.get("avatar_focus", (0.5, 0.44))))
    nx = MX + 2 * r + 28
    nf = f_sys(46, bold=True); name = item.get("author", "Joseph Borroto")
    d.text((nx, top + 6), name, font=nf, fill=p["head"])
    nw = d.textlength(name, font=nf)
    if item.get("verified", True):
        _verified(d, nx + nw + 34, top + 30, 24)
    d.text((nx, top + 64), item.get("handle", "@josephborroto"), font=f_sys(38), fill=p["muted"])
    # ---- the claim
    y = top + 2 * r + 46
    hf, hlines, hlh = _social_fit(d, item["headline"], INNER, 54, 38)
    for ln in hlines:
        d.text((MX, y), ln, font=hf, fill=p["head"]); y += hlh
    # ---- embedded reply card (measure first, then draw so it never overflows)
    rp = item.get("reply")
    if rp:
        y += 30
        pad = 34; rr = 42
        ax0, ax1 = MX, W - MX
        rbf = f_sys(36)
        body_lines = wrap(d, rp["body"], rbf, (ax1 - pad) - (ax0 + pad))
        card_h = 34 + 2 * rr + 16 + len(body_lines) * 48 + 14 + 52 + 20 + 40 + 26
        d.rounded_rectangle((ax0, y, ax1, y + card_h), radius=28,
                            fill=(30, 30, 33), outline=(58, 58, 64), width=2)
        cy = y + 34
        _put_avatar(img, d, ax0 + pad, cy, rr, rp.get("initials", "TV"),
                    (70, 110, 150), photo=rp.get("photo"))
        rnx = ax0 + pad + 2 * rr + 20
        rnf = f_sys(38, bold=True)
        d.text((rnx, cy + 4), rp["author"], font=rnf, fill=p["head"])
        rnw = d.textlength(rp["author"], font=rnf)
        d.text((rnx + rnw + 16, cy + 12), rp.get("time", ""), font=f_sys(28), fill=p["muted"])
        by = cy + 2 * rr + 16
        for ln in body_lines:
            d.text((ax0 + pad, by), ln, font=rbf, fill=(220, 222, 226)); by += 48
        by += 14
        # reaction pill (heart + count)
        cnt = str(rp.get("reactions", 4))
        pillf = f_sys(30, bold=True); cw = d.textlength(cnt, font=pillf)
        d.rounded_rectangle((ax0 + pad, by, ax0 + pad + 56 + cw + 28, by + 52), radius=26,
                            outline=(70, 130, 180), width=3)
        _heart(d, ax0 + pad + 32, by + 26, 28, (235, 90, 110))
        d.text((ax0 + pad + 54, by + 11), cnt, font=pillf, fill=(150, 190, 220))
        by += 72
        # replies meta row
        _avatar(d, ax0 + pad, by + 2, 16, "", (70, 110, 150))
        d.text((ax0 + pad + 46, by + 2), rp.get("replies", ""), font=f_sys(28), fill=p["muted"])
        y += card_h
    # ---- blue CTA (no brand footer — this card mimics a real screenshot)
    y += 48
    d.text((MX, y), item.get("cta", "Here's exactly how he did it →"),
           font=f_sys(44, bold=True), fill=blue)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def _social_fit(d, text, max_w, start, floor):
    for size in range(start, floor - 1, -3):
        f = f_sys(size, bold=True)
        ls = wrap(d, text, f, max_w); lh = int(size * 1.16)
        if len(ls) <= 4:
            return f, ls, lh
    f = f_sys(floor, bold=True)
    return f, wrap(d, text, f, max_w), int(floor * 1.16)


def draw_content_slide(slide, idx, total, out_path, style="dark"):
    """Carousel middle slide — big number, title, body."""
    img, d, p = _new(style)
    # step indicator top-right
    si = f_brand(30)
    txt = f"{idx}/{total}"
    d.text((W - M - d.textlength(txt, font=si), 162), txt, font=si, fill=p["muted"])
    # giant number
    nf = f_brand(150)
    d.text((M, 210), str(idx), font=nf, fill=ORANGE)
    # title
    y = 420
    tf = f_brand(64)
    for ln in wrap(d, slide["title"], tf, W - 2 * M):
        d.text((M, y), ln, font=tf, fill=p["head"]); y += 70
    y += 30
    d.rounded_rectangle((M, y, M + 180, y + 8), radius=4, fill=ORANGE); y += 50
    # body
    bf = f_sys(44)
    for ln in wrap(d, slide["body"], bf, W - 2 * M):
        d.text((M, y), ln, font=bf, fill=p["sub"]); y += 56
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_cta_slide(out_path, style="dark"):
    """Carousel final slide — follow prompt (no action required of viewer beyond following)."""
    img, d, p = _new(style)
    _kicker(d, "Keep these coming", p)
    hf = f_brand(96)
    y = 380
    for ln in ["Follow for one", "of these every", "few days."]:
        d.text((M, y), ln, font=hf, fill=p["head"]); y += 104
    y += 30
    d.rounded_rectangle((M, y, M + 230, y + 9), radius=4, fill=ORANGE); y += 60
    hf2 = f_brand(70)
    d.text((M, y), "@josephborroto", font=hf2, fill=ORANGE)
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def render_carousel(entry, outdir, prefix, style="dark"):
    """Render all slides for one carousel. Returns ordered list of file paths."""
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    cover = outdir / f"{prefix}-0.jpg"
    # Social-proof carousels open with an X-post screenshot hook instead of the
    # standard cover; everything after is the usual breakdown + CTA.
    if entry.get("cover_kind") == "social":
        draw_social_hook(entry["social"], cover, style)
    else:
        draw_cover(entry["cover"], entry.get("kicker", ""), cover, style)
    paths.append(str(cover))
    slides = entry["slides"]
    for i, s in enumerate(slides, start=1):
        sp = outdir / f"{prefix}-{i}.jpg"
        draw_content_slide(s, i, len(slides), sp, style)
        paths.append(str(sp))
    cta = outdir / f"{prefix}-{len(slides)+1}.jpg"
    draw_cta_slide(cta, style)
    paths.append(str(cta))
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--bank", default=str(ROOT / "post_bank.json"))
    ap.add_argument("--style", default="dark", choices=["dark", "light"])
    ap.add_argument("--carousel", action="store_true", help="Render a carousel from carousel_bank.json")
    args = ap.parse_args()
    if args.carousel:
        bank = json.loads((ROOT / "carousel_bank.json").read_text())
        entry = bank[args.index % len(bank)]
        paths = render_carousel(entry, ROOT / "generated", f"carousel-{args.index}", args.style)
        print("\n".join(paths))
        return
    bank = json.loads(Path(args.bank).read_text())
    item = bank[args.index % len(bank)]
    out = args.out or str(ROOT / "generated" / f"sample-{args.index}.png")
    Path(out).parent.mkdir(exist_ok=True)
    draw_card(item, out, style=args.style)
    print(out)


if __name__ == "__main__":
    main()
