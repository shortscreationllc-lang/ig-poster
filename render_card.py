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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--out", default=None)
    ap.add_argument("--bank", default=str(ROOT / "post_bank.json"))
    ap.add_argument("--style", default="dark", choices=["dark", "light"])
    args = ap.parse_args()
    bank = json.loads(Path(args.bank).read_text())
    item = bank[args.index % len(bank)]
    out = args.out or str(ROOT / "generated" / f"sample-{args.index}.png")
    Path(out).parent.mkdir(exist_ok=True)
    draw_card(item, out, style=args.style)
    print(out)


if __name__ == "__main__":
    main()
