#!/usr/bin/env python3
import argparse
import json
import textwrap
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "generated"
BRAND = "Shorts Creation"


def font(size, bold=True):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(draw, text, fnt, max_width):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=fnt) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_post(item, out_path):
    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), (10, 10, 10))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        shade = int(10 + 18 * y / height)
        draw.line([(0, y), (width, y)], fill=(shade, shade, shade))

    orange = (255, 107, 26)
    white = (245, 245, 245)
    muted = (190, 190, 190)
    panel = (18, 18, 18)

    for r in range(520, 0, -8):
        alpha = r / 520
        color = (int(20 + 55 * alpha), int(10 + 25 * alpha), 8)
        draw.ellipse((-260, -240, r, r), outline=color, width=8)

    headline_font = font(100, True)
    sub_font = font(52, True)
    proof_font = font(34, False)
    brand_font = font(30, True)

    y = 215
    for line in wrap(draw, item["headline"], headline_font, 850):
        draw.text((120, y), line, font=headline_font, fill=white)
        y += 118

    y += 75
    draw.rounded_rectangle((120, y, 350, y + 8), radius=4, fill=orange)
    y += 58

    sub_lines = wrap(draw, item["subheadline"], sub_font, 800)
    for line in sub_lines:
        draw.text((120, y), line, font=sub_font, fill=white)
        y += 64

    box_top = 990
    draw.rounded_rectangle((120, box_top, 960, box_top + 128), radius=18, outline=(60, 60, 60), width=2, fill=panel)
    proof_lines = wrap(draw, item["proof"], proof_font, 740)[:2]
    py = box_top + 28
    for i, line in enumerate(proof_lines):
        draw.text((155, py), line, font=proof_font, fill=white if i else muted)
        py += 42

    for i in range(8):
        offset = i * 28
        draw.arc((620 + offset, 760 + offset, 1380 + offset, 1600 + offset), 200, 315, fill=(80, 36, 12), width=2)

    bottom = 1240
    draw.rounded_rectangle((120, bottom, 150, bottom + 5), radius=3, fill=orange)
    draw.text((175, bottom - 16), BRAND, font=brand_font, fill=white)
    image.save(out_path, quality=95)


def main():
    parser = argparse.ArgumentParser(description="Create a Shorts Creation Instagram tip image and caption package.")
    parser.add_argument("--index", type=int, default=None, help="Post bank index. Defaults to day-based rotation.")
    args = parser.parse_args()

    bank = json.loads((ROOT / "post_bank.json").read_text())
    index = args.index if args.index is not None else datetime.now().toordinal() % len(bank)
    item = bank[index % len(bank)]

    OUT.mkdir(exist_ok=True)
    slug = item["headline"].lower().replace(".", "").replace(" ", "-")[:48]
    image_path = OUT / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}.png"
    caption_path = OUT / f"{image_path.stem}.caption.txt"
    alt_path = OUT / f"{image_path.stem}.alt.txt"

    draw_post(item, image_path)
    caption_path.write_text(item["caption"])
    alt_path.write_text(item["alt_text"])

    result = {
        "image_path": str(image_path),
        "caption_path": str(caption_path),
        "alt_path": str(alt_path),
        "headline": item["headline"],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
