#!/usr/bin/env python3
"""Silent kinetic-typography Reels (1080x1920) from the SAME content + brand
looks as the image cards. No talking, no music — just live graphics. Frames are
drawn with Pillow and encoded to MP4 with ffmpeg (imageio-ffmpeg, free; also
preinstalled on GitHub runners). One function per content type + a dispatcher.

A silent AAC audio track is added so Instagram's Reels API never rejects it.
"""
import re
import numpy as np
import imageio.v2 as imageio
from PIL import Image, ImageDraw
from render_card import PALETTES, ORANGE, f_brand, f_sys, wrap

VW, VH, M, FPS = 1080, 1920, 120, 30


# ----------------------------------------------------------------------------- helpers
def ease(p):
    p = max(0.0, min(1.0, p)); return 1 - (1 - p) ** 3


def _smooth(p):  # smoothstep (ease in-out) — for silky transitions
    p = max(0.0, min(1.0, p)); return p * p * (3 - 2 * p)


def _zoom(img, s):
    """Scale by s (>=1.0) and center-crop back to frame — for ken-burns / zoom."""
    if s <= 1.0005:
        return img
    w2, h2 = int(VW * s), int(VH * s)
    big = img.resize((w2, h2), Image.BILINEAR)
    x, y = (w2 - VW) // 2, (h2 - VH) // 2
    return big.crop((x, y, x + VW, y + VH))


def _bg(p):
    top = np.array(p["bg_top"], float); bot = np.array(p["bg_bottom"], float)
    t = np.linspace(0, 1, VH)[:, None]
    col = (top[None, :] * (1 - t) + bot[None, :] * t)
    arr = np.repeat(col[:, None, :], VW, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _glow(p):
    g = Image.new("RGBA", (VW, VH), (0, 0, 0, 0)); d = ImageDraw.Draw(g)
    cx, cy = 230, 360
    for r in range(640, 0, -6):
        a = int(p.get("glow_a", 50) * (1 - r / 640))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ORANGE + (a,))
    return g


def _alpha(sprite, f):
    arr = np.array(sprite); arr[..., 3] = (arr[..., 3] * max(0.0, min(1.0, f))).astype(np.uint8)
    return Image.fromarray(arr)


def _text_sprite(text, font, fill, center=True, maxw=None):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = tmp.textlength(text, font=font)
    asc, desc = font.getmetrics(); h = asc + desc + 8
    s = Image.new("RGBA", (VW, h), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
    x = (VW - w) / 2 if center else M
    d.text((x, 0), text, font=font, fill=fill + (255,) if len(fill) == 3 else fill)
    return s, h


def _footer_sprite(p):
    hf = f_brand(40); s, _ = _text_sprite("@josephborroto", hf, p.get("muted", (170, 170, 170)))
    return s


def _encode(frames_fn, total_frames, out_path):
    """frames_fn(i)->PIL RGB-ish image. Writes MP4 + silent audio."""
    w = imageio.get_writer(out_path, fps=FPS, codec="libx264", quality=8,
                           macro_block_size=8, ffmpeg_log_level="error",
                           output_params=["-pix_fmt", "yuv420p"])
    for i in range(total_frames):
        w.append_data(np.array(frames_fn(i).convert("RGB")))
    w.close()
    _add_silent_audio(out_path)
    return out_path


def _add_silent_audio(path):
    """Mux a silent stereo AAC track so IG accepts the Reel."""
    try:
        import imageio_ffmpeg, subprocess, os, shutil
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        tmp = path + ".aac.mp4"
        subprocess.run([ff, "-y", "-i", path, "-f", "lavfi", "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-c:v", "copy", "-c:a", "aac", "-shortest", tmp],
                       check=True, capture_output=True)
        shutil.move(tmp, path)
    except Exception as e:
        print("  (silent-audio mux skipped:", e, ")")


def _kicker_sprite(text, p):
    kf = f_brand(30); txt = text.upper()
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10))); tw = tmp.textlength(txt, font=kf)
    s = Image.new("RGBA", (int(tw) + 80, 70), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
    d.rounded_rectangle((0, 0, tw + 56, 56), 10, fill=ORANGE)
    d.text((28, 12), txt, font=kf, fill=p.get("kicker_text", (12, 12, 12)))
    return s


# ----------------------------------------------------------------------------- layouts
def video_statement(item, out, style="blackout", secs=8):
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    size = 150
    while size > 60:
        f = f_brand(size); lines = wrap(tmp, item["headline"], f, VW - 2 * M)
        if len(lines) <= 4 and max(tmp.textlength(x, font=f) for x in lines) <= VW - 2 * M:
            break
        size -= 6
    f = f_brand(size); lh = int(size * 1.04)
    sprites = [_text_sprite(ln, f, p["head"])[0] for ln in lines]
    n = len(sprites); block_h = n * lh; y0 = (VH - block_h) // 2 - 40
    footer = _footer_sprite(p); ul = Image.new("RGBA", (240, 14), ORANGE + (255,))
    ls, ld, stag = 0.5, 0.6, 0.55
    last = ls + (n - 1) * stag + ld; uls = last + 0.1

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(40 * np.sin(t * 0.9))))
        fr.alpha_composite(_alpha(footer, ease((t - 0.2) / 0.7)), (0, VH - 150))
        for k, spr in enumerate(sprites):
            pr = ease((t - (ls + k * stag)) / ld)
            if pr > 0:
                fr.alpha_composite(_alpha(spr, pr), (0, y0 + k * lh + int((1 - pr) * 46)))
        up = ease((t - uls) / 0.6)
        if up > 0:
            fr.alpha_composite(ul.crop((0, 0, max(1, int(240 * up)), 14)),
                               (int((VW - 240) / 2), y0 + block_h + 30))
        return fr
    return _encode(frame, int(secs * FPS), out)


def video_stat(item, out, style="blackout", secs=9):
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    m = re.match(r"\s*(\d+(?:\.\d+)?)(.*)", str(item["stat"]))
    target = float(m.group(1)) if m else None
    suffix = m.group(2) if m else ""
    nf = f_brand(360)
    kick = _kicker_sprite(item.get("kicker", "THE NUMBER"), p)
    hf = f_brand(72)
    htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    hlines = wrap(htmp, item["headline"], hf, VW - 2 * M)
    hsprites = [_text_sprite(ln, hf, p["head"])[0] for ln in hlines]
    footer = _footer_sprite(p)
    cnt_s, cnt_d = 0.4, 1.6  # count-up window
    head_h = len(hlines) * 84
    block = 56 + 40 + nf.size + 24 + head_h
    top = (VH - block) // 2          # vertically center kicker + number + headline
    ky = top; numy = top + 96; heady = numy + nf.size + 24

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(36 * np.sin(t * 0.8))))
        fr.alpha_composite(_alpha(kick, ease((t - 0.1) / 0.5)), (M, ky))
        # counting number
        if target is not None:
            pr = ease((t - cnt_s) / cnt_d)
            val = int(round(target * pr))
            disp = f"{val}{suffix}"
        else:
            disp = str(item["stat"])
        spr, _ = _text_sprite(disp, nf, ORANGE, center=False)
        # left-aligned at M
        d2 = ImageDraw.Draw(spr)  # already drawn centered; redo left
        spr2 = Image.new("RGBA", (VW, nf.getmetrics()[0] + nf.getmetrics()[1] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(spr2).text((M - 8, 0), disp, font=nf, fill=ORANGE)
        fr.alpha_composite(spr2, (0, numy))
        # headline reveal after count
        y = heady
        for k, hs in enumerate(hsprites):
            pr = ease((t - (cnt_s + cnt_d + 0.1 + k * 0.3)) / 0.5)
            if pr > 0:
                hs2 = Image.new("RGBA", (VW, hs.height), (0, 0, 0, 0))
                hs2.alpha_composite(hs, (M - (VW - int(htmp.textlength(hlines[k], font=hf))) // 2, 0))
                fr.alpha_composite(_alpha(hs2, pr), (0, y + k * 84 + int((1 - pr) * 30)))
        fr.alpha_composite(_alpha(footer, ease((t - 0.3) / 0.7)), (0, VH - 150))
        return fr
    return _encode(frame, int(secs * FPS), out)


def video_quote(item, out, style="navyorange", secs=10):
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    qf = f_brand(240)
    tf_size = 92; htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while tf_size > 50:
        f = f_brand(tf_size); lines = wrap(htmp, item["headline"], f, VW - 2 * M)
        if len(lines) <= 6:
            break
        tf_size -= 4
    f = f_brand(tf_size); lh = int(f.size * 1.12)
    lsp = [(_text_sprite(ln, f, p["head"], center=False)[0], ln) for ln in lines]
    # left-aligned sprites
    sprites = []
    for ln in lines:
        s = Image.new("RGBA", (VW, lh + 10), (0, 0, 0, 0)); ImageDraw.Draw(s).text((M, 0), ln, font=f, fill=p["head"])
        sprites.append(s)
    af = f_sys(42, bold=True)
    attr = Image.new("RGBA", (VW, 70), (0, 0, 0, 0))
    ImageDraw.Draw(attr).text((M, 0), "— Joseph Borroto", font=af, fill=ORANGE)
    footer = _footer_sprite(p)
    n = len(sprites)
    text_h = n * lh
    y0 = (VH - text_h - 120) // 2 + 30       # vertically center quote + attribution
    qy = max(120, y0 - 240)
    ls, ld, stag = 0.7, 0.5, 0.4
    last = ls + (n - 1) * stag + ld

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(40 * np.sin(t * 0.7))))
        qa = ease((t - 0.1) / 0.6)  # quote mark scales/fades in
        if qa > 0:
            qs = Image.new("RGBA", (VW, 320), (0, 0, 0, 0))
            ImageDraw.Draw(qs).text((M - 12, 0), '"', font=qf, fill=ORANGE)
            fr.alpha_composite(_alpha(qs, qa), (0, qy))
        for k, spr in enumerate(sprites):
            pr = ease((t - (ls + k * stag)) / ld)
            if pr > 0:
                fr.alpha_composite(_alpha(spr, pr), (0, y0 + k * lh + int((1 - pr) * 36)))
        aa = ease((t - (last + 0.1)) / 0.6)
        if aa > 0:
            fr.alpha_composite(_alpha(attr, aa), (0, y0 + n * lh + 40))
        fr.alpha_composite(_alpha(footer, ease((t - 0.3) / 0.7)), (0, VH - 150))
        return fr
    return _encode(frame, int(secs * FPS), out)


def video_checklist(item, out, style="dark", secs=12):
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    tf = f_brand(64); htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    title_lines = wrap(htmp, item["headline"], tf, VW - 2 * M)
    title_sprites = [(_mk_left(ln, tf, p["head"])) for ln in title_lines]
    itf = f_sys(46, bold=True)
    bullets = item.get("bullets", [])[:5]
    footer = _footer_sprite(p)
    title_h = len(title_lines) * 78
    rows_h = len(bullets) * 130
    top = (VH - (title_h + 50 + rows_h)) // 2     # vertically center the whole block
    rows_top = top + title_h + 50

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(36 * np.sin(t * 0.8))))
        for k, ts in enumerate(title_sprites):
            pr = ease((t - (0.3 + k * 0.2)) / 0.5)
            if pr > 0:
                fr.alpha_composite(_alpha(ts, pr), (0, top + k * 78 + int((1 - pr) * 26)))
        y = rows_top
        for bi, b in enumerate(bullets):
            st = 1.0 + bi * 0.9
            pr = ease((t - st) / 0.5)
            if pr <= 0:
                y += 130; continue
            row = Image.new("RGBA", (VW, 130), (0, 0, 0, 0)); d = ImageDraw.Draw(row)
            d.rounded_rectangle((M, 4, M + 56, 60), 10, fill=ORANGE)
            chk = ease((t - (st + 0.15)) / 0.3)  # check draws in
            if chk > 0:
                d.line([(M + 13, 34), (M + 25, 47)], fill=(20, 14, 6), width=7)
                if chk > 0.5:
                    d.line([(M + 25, 47), (M + 47, 18)], fill=(20, 14, 6), width=7)
            for j, ln in enumerate(wrap(d, b, itf, VW - (M + 90) - M)):
                d.text((M + 90, j * 56), ln, font=itf, fill=p["head"] if j == 0 else p["sub"])
            fr.alpha_composite(_alpha(row, pr), (int((1 - pr) * 40), y))
            y += 130
        fr.alpha_composite(_alpha(footer, ease((t - 0.3) / 0.7)), (0, VH - 150))
        return fr
    return _encode(frame, int(secs * FPS), out)


def _mk_left(text, font, fill):
    s = Image.new("RGBA", (VW, font.size + 30), (0, 0, 0, 0))
    ImageDraw.Draw(s).text((M, 0), text, font=font, fill=fill)
    return s


def _scene_card(scene, p):
    """One full-frame scene for a carousel-style Reel (returns RGBA)."""
    img = _bg(p); img.alpha_composite(_glow(p)); d = ImageDraw.Draw(img)
    if scene.get("kicker"):
        img.alpha_composite(_kicker_sprite(scene["kicker"], p), (M, 230))
    # headline (auto-fit)
    size = scene.get("hsize", 92)
    while size > 50:
        hf = f_brand(size); hl = wrap(d, scene["headline"], hf, VW - 2 * M)
        if len(hl) <= 4:
            break
        size -= 6
    hf = f_brand(size); lh = int(size * 1.05)
    body_lines = wrap(d, scene["body"], f_sys(46), VW - 2 * M) if scene.get("body") else []
    num_h = 170 if scene.get("n") else 0
    block = num_h + len(hl) * lh + 66 + len(body_lines) * 58
    y = (VH - block) // 2            # vertically center number + headline + body
    if scene.get("n"):
        d.text((M - 6, y), str(scene["n"]), font=f_brand(150), fill=ORANGE); y += num_h
    for ln in hl:
        d.text((M, y), ln, font=hf, fill=p["head"]); y += lh
    y += 16
    d.rounded_rectangle((M, y, M + 200, y + 10), 5, fill=ORANGE); y += 50
    bf = f_sys(46)
    for ln in body_lines:
        d.text((M, y), ln, font=bf, fill=p["sub"]); y += 58
    if scene.get("swipe"):
        sf = f_brand(34); d.text((M, VH - 250), "SWIPE", font=sf, fill=ORANGE)
        sw = d.textlength("SWIPE", font=sf)
        d.polygon([(M + sw + 22, VH - 246), (M + sw + 22, VH - 214), (M + sw + 52, VH - 230)], fill=ORANGE)
    hf2 = f_brand(40); h = "@josephborroto"; hw = d.textlength(h, font=hf2)
    d.text(((VW - hw) / 2, VH - 150), h, font=hf2, fill=p.get("muted", (170, 170, 170)))
    return img


def video_sequence(scenes, out, style="dark", hold=2.1, trans=0.5):
    """Carousel-style Reel: scenes swipe past horizontally (push transition),
    with dot indicators — 'feels like a carousel passing by'."""
    p = PALETTES.get(style, PALETTES["dark"])
    n = len(scenes)

    def dots(im, active):
        dd = ImageDraw.Draw(im); r, gap = 9, 36
        x0 = (VW - (n - 1) * gap) // 2
        for i in range(n):
            c = ORANGE if i == active else (110, 110, 110)
            dd.ellipse((x0 + i * gap - r, 120 - r, x0 + i * gap + r, 120 + r), fill=c)

    cards = []
    for s in scenes:
        c = _scene_card(s, p).convert("RGB"); dots(c, scenes.index(s)); cards.append(c)

    w = imageio.get_writer(out, fps=FPS, codec="libx264", quality=8,
                           macro_block_size=8, ffmpeg_log_level="error",
                           output_params=["-pix_fmt", "yuv420p"])
    hf, tf = int(hold * FPS), int(trans * FPS)
    bare = [_scene_card(s, p).convert("RGB") for s in scenes]  # without dots

    def emit(img, active):
        im = img.copy(); dots(im, active); w.append_data(np.array(im))

    for i in range(n):
        # hold: gentle "ken-burns" zoom so the scene feels alive, not frozen
        for k in range(hf):
            emit(_zoom(bare[i], 1.0 + 0.03 * (k / max(1, hf))), i)
        # transition: smooth crossfade + both scenes easing through a soft zoom
        if i < n - 1:
            for t in range(tf):
                a = _smooth(t / tf)
                fa = _zoom(bare[i], 1.03 + 0.06 * a)        # outgoing drifts in
                fb = _zoom(bare[i + 1], 1.08 - 0.06 * a)    # incoming settles
                emit(Image.blend(fa, fb, a), i if a < 0.5 else i + 1)
    w.close(); _add_silent_audio(out)
    return out


def render_video(item, out, style="dark"):
    """Dispatch a content item to the right animated Reel by its type."""
    t = item.get("type", "single")
    if t == "stat":
        return video_stat(item, out, style=style)
    if t == "quote":
        return video_quote(item, out, style=style)
    if t == "checklist":
        return video_checklist(item, out, style=style)
    if t == "statement":
        return video_statement(item, out, style=style)
    # default: animate the headline as a statement
    return video_statement({"headline": item.get("headline", item.get("caption", ""))}, out, style=style)


if __name__ == "__main__":
    import sys
    render_video({"type": "statement", "headline": "POST LESS. EDIT HARDER."}, "/tmp/proof/v_statement.mp4", "blackout")
    print("ok")
