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


def _footer(d, p):
    fy = H - 150
    d.rounded_rectangle((M, fy + 14, M + 46, fy + 24), radius=5, fill=ORANGE)
    nf = f_brand(40)
    d.text((M + 70, fy - 4), "JOSEPH BORROTO", font=nf, fill=p["head"])
    hf2 = f_sys(28)
    d.text((M + 72, fy + 46), "@josephborroto", font=hf2, fill=p["muted"])


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
