#!/usr/bin/env python3
"""Render a 9:16 (1080x1920) Instagram Story card.

Two kinds:
  - hook  : a bold attention-grabber to make people tap into the story
  - promo : a "new post is up" reshare nudge pointing at the feed post

Reuses the brand look from render_card (League Spartan, orange #F87C11, palettes).
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

import render_card as rc

ROOT = Path(__file__).resolve().parent
SW, SH = 1080, 1920
M = 110


def _bg(style):
    p = rc.PALETTES.get(style, rc.PALETTES["dark"])
    img = Image.new("RGBA", (SW, SH), p["bg_top"] + (255,))
    d = ImageDraw.Draw(img)
    bt, bb = p["bg_top"], p["bg_bottom"]
    for y in range(SH):
        t = y / SH
        d.line([(0, y), (SW, y)], fill=tuple(int(bt[i] + (bb[i] - bt[i]) * t) for i in range(3)))
    glow = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for r in range(720, 0, -6):
        a = int(p["glow_a"] * (1 - r / 720))
        gd.ellipse((-360, -300, r, r), fill=rc.ORANGE + (a,))
    img.alpha_composite(glow)
    return img, ImageDraw.Draw(img), p


def _wrap(d, text, fnt, max_w):
    return rc.wrap(d, text, fnt, max_w)


def _footer(d, p):
    fy = SH - 180
    d.rounded_rectangle((M, fy + 14, M + 46, fy + 24), radius=5, fill=rc.ORANGE)
    d.text((M + 70, fy - 4), "JOSEPH BORROTO", font=rc.f_brand(40), fill=p["head"])
    d.text((M + 72, fy + 46), "@josephborroto", font=rc.f_sys(28), fill=p["muted"])


def draw_hook(item, out_path, style="dark"):
    """Big centered hook + a 'tap to keep watching' nudge."""
    img, d, p = _bg(style)
    # kicker
    kf = rc.f_brand(32)
    kick = item.get("kicker", "WATCH THIS").upper()
    d.rounded_rectangle((M, 300, M + d.textlength(kick, font=kf) + 60, 364), radius=10, fill=rc.ORANGE)
    d.text((M + 30, 314), kick, font=kf, fill=p["kicker_text"])
    # headline, auto-fit, vertically centered-ish
    top, maxh = 470, 760
    lines, lh, hf = None, 0, None
    for size in range(120, 56, -4):
        f = rc.f_brand(size)
        ls = _wrap(d, item["headline"], f, SW - 2 * M)
        h = int(size * 1.08)
        if len(ls) * h <= maxh:
            lines, lh, hf = ls, h, f
            break
    if lines is None:
        hf = rc.f_brand(60); lines = _wrap(d, item["headline"], hf, SW - 2 * M); lh = 66
    y = top
    for ln in lines:
        d.text((M, y), ln, font=hf, fill=p["head"]); y += lh
    y += 30
    d.rounded_rectangle((M, y, M + 240, y + 10), radius=5, fill=rc.ORANGE)
    y += 70
    if item.get("subheadline"):
        sf = rc.f_sys(52, bold=True)
        for ln in _wrap(d, item["subheadline"], sf, SW - 2 * M):
            d.text((M, y), ln, font=sf, fill=p["sub"]); y += 64
    # tap nudge near bottom
    nudge = item.get("nudge", "Tap to keep watching →")
    nf = rc.f_sys(36, bold=True)
    d.text((M, SH - 320), nudge, font=nf, fill=rc.ORANGE)
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def draw_promo(item, out_path, style="light"):
    """'New post is up' reshare nudge for the feed post."""
    img, d, p = _bg(style)
    kf = rc.f_brand(32)
    kick = "NEW POST"
    d.rounded_rectangle((M, 320, M + d.textlength(kick, font=kf) + 60, 384), radius=10, fill=rc.ORANGE)
    d.text((M + 30, 334), kick, font=kf, fill=p["kicker_text"])
    y = 520
    hf = rc.f_brand(104)
    for ln in _wrap(d, item.get("headline", "Just posted."), hf, SW - 2 * M):
        d.text((M, y), ln, font=hf, fill=p["head"]); y += 112
    y += 30
    d.rounded_rectangle((M, y, M + 240, y + 10), radius=5, fill=rc.ORANGE)
    y += 70
    sf = rc.f_sys(50, bold=True)
    for ln in _wrap(d, item.get("subheadline", "Tap to see it on my feed."), sf, SW - 2 * M):
        d.text((M, y), ln, font=sf, fill=p["sub"]); y += 62
    nf = rc.f_sys(36, bold=True)
    d.text((M, SH - 320), "See the full post →", font=nf, fill=rc.ORANGE)
    _footer(d, p)
    img.convert("RGB").save(out_path, quality=95)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["hook", "promo"], default="hook")
    ap.add_argument("--style", default="dark")
    ap.add_argument("--out", default=str(ROOT / "generated" / "story-test.jpg"))
    args = ap.parse_args()
    bank = json.loads((ROOT / "story_bank.json").read_text())
    item = bank["hooks"][0] if args.kind == "hook" else bank["promos"][0]
    Path(args.out).parent.mkdir(exist_ok=True)
    if args.kind == "hook":
        draw_hook(item, args.out, args.style)
    else:
        draw_promo(item, args.out, args.style)
    print(args.out)


if __name__ == "__main__":
    main()
