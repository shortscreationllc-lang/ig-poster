#!/usr/bin/env python3
"""DEMO: silent kinetic-typography Reel from a statement — same brand look,
animated. 1080x1920 (9:16). Proof of concept for motion-graphic posts.
Frames via Pillow, encoded to MP4 via the bundled ffmpeg (imageio)."""
import numpy as np, imageio.v2 as imageio
from PIL import Image, ImageDraw
from render_card import ORANGE, f_brand, f_sys, wrap

VW, VH, M, FPS, SECS = 1080, 1920, 120, 30, 8
N = VH  # for glow math
OUT = "/tmp/proof/reel_demo.mp4"
HEADLINE = "THE HOOK IS 90% OF THE POST."

def ease(p):  # easeOutCubic
    p = max(0.0, min(1.0, p));  return 1 - (1 - p) ** 3

# --- static background (dark gradient) rendered once ---
def make_bg():
    img = Image.new("RGB", (VW, VH))
    top, bot = (12, 12, 13), (24, 20, 17)
    px = img.load()
    for y in range(VH):
        t = y / VH; c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(VW):
            px[x, y] = c
    return img.convert("RGBA")

# --- orange radial glow as its own layer (we drift it for "life") ---
def make_glow():
    g = Image.new("RGBA", (VW, VH), (0, 0, 0, 0)); d = ImageDraw.Draw(g)
    cx, cy = 230, 360
    for r in range(640, 0, -6):
        a = int(60 * (1 - r / 640))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ORANGE + (a,))
    return g

def alpha_scaled(sprite, f):
    arr = np.array(sprite); arr[..., 3] = (arr[..., 3] * f).astype(np.uint8)
    return Image.fromarray(arr)

# --- precompute line sprites (orange headline) ---
def line_sprites():
    tmp = Image.new("RGBA", (VW, VH)); d = ImageDraw.Draw(tmp)
    size = 150
    while True:
        f = f_brand(size); lines = wrap(d, HEADLINE, f, VW - 2 * M)
        if len(lines) <= 4 and max(d.textlength(x, font=f) for x in lines) <= VW - 2 * M:
            break
        size -= 6
    f = f_brand(size); lh = int(size * 1.04)
    sprites = []
    for ln in lines:
        s = Image.new("RGBA", (VW, lh + 20), (0, 0, 0, 0)); sd = ImageDraw.Draw(s)
        w = sd.textlength(ln, font=f)
        sd.text(((VW - w) / 2, 0), ln, font=f, fill=ORANGE + (255,))
        sprites.append(s)
    return sprites, lh

def main():
    bg, glow = make_bg(), make_glow()
    sprites, lh = line_sprites()
    n = len(sprites)
    block_h = n * lh
    y0 = (VH - block_h) // 2 - 40
    # handle + underline sprites
    hf = f_brand(40)
    handle = Image.new("RGBA", (VW, 70), (0, 0, 0, 0)); hd = ImageDraw.Draw(handle)
    hw = hd.textlength("@josephborroto", font=hf)
    hd.text(((VW - hw) / 2, 0), "@josephborroto", font=hf, fill=(170, 170, 170, 255))
    ul = Image.new("RGBA", (240, 14), ORANGE + (255,))

    # timeline (seconds)
    line_start, line_dur, stag = 0.5, 0.6, 0.55
    last_end = line_start + (n - 1) * stag + line_dur
    ul_start, ul_dur = last_end + 0.1, 0.6
    total = SECS
    frames = int(total * FPS)

    w = imageio.get_writer(OUT, fps=FPS, codec="libx264", quality=8,
                           macro_block_size=8, ffmpeg_log_level="error",
                           output_params=["-pix_fmt", "yuv420p"])
    for fi in range(frames):
        t = fi / FPS
        frame = bg.copy()
        # drifting glow (gentle vertical sway)
        dy = int(40 * np.sin(t * 0.9))
        frame.alpha_composite(glow, (0, dy))
        # handle fades in 0.2-0.9s, stays
        ha = ease((t - 0.2) / 0.7)
        if ha > 0:
            frame.alpha_composite(alpha_scaled(handle, ha), (0, VH - 150))
        # lines reveal (fade + slide up)
        for i, spr in enumerate(sprites):
            st = line_start + i * stag
            p = ease((t - st) / line_dur)
            if p <= 0:
                continue
            yoff = int((1 - p) * 46)
            frame.alpha_composite(alpha_scaled(spr, p), (0, y0 + i * lh + yoff))
        # underline wipes left->right
        up = ease((t - ul_start) / ul_dur)
        if up > 0:
            cw = max(1, int(240 * up))
            frame.alpha_composite(ul.crop((0, 0, cw, 14)),
                                  (int((VW - 240) / 2), y0 + block_h + 30))
        w.append_data(np.array(frame.convert("RGB")))
    w.close()
    print("wrote", OUT)

if __name__ == "__main__":
    main()
