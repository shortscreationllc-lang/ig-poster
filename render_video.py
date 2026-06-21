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
import render_card as rcard  # reuse avatar / verified / heart drawing helpers

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


def _acc(p):
    """The 'punch' color for a palette — orange on dark looks, near-black on the
    full-orange look. Drives the big number, dividers, pills, quote marks, etc."""
    return p.get("accent", ORANGE)


def _bg(p):
    top = np.array(p["bg_top"], float); bot = np.array(p["bg_bottom"], float)
    t = np.linspace(0, 1, VH)[:, None]
    col = (top[None, :] * (1 - t) + bot[None, :] * t)
    arr = np.repeat(col[:, None, :], VW, axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGB").convert("RGBA")


def _glow(p):
    g = Image.new("RGBA", (VW, VH), (0, 0, 0, 0)); d = ImageDraw.Draw(g)
    cx, cy = 230, 360
    acc = _acc(p)
    for r in range(640, 0, -6):
        a = int(p.get("glow_a", 50) * (1 - r / 640))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=acc + (a,))
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


def _encode(frames_fn, total_frames, out_path, motion=True):
    """frames_fn(i)->PIL RGB-ish image. Writes MP4 + silent audio. `motion` adds
    a subtle breathing push-in so the frame is never static and loops seamlessly."""
    w = imageio.get_writer(out_path, fps=FPS, codec="libx264", quality=8,
                           macro_block_size=8, ffmpeg_log_level="error",
                           output_params=["-pix_fmt", "yuv420p"])
    for i in range(total_frames):
        fr = frames_fn(i).convert("RGB")
        if motion and total_frames > 1:
            z = 1.0 + 0.030 * (0.5 - 0.5 * np.cos(2 * np.pi * i / total_frames))
            fr = _zoom(fr, z)
        w.append_data(np.array(fr))
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
    d.rounded_rectangle((0, 0, tw + 56, 56), 10, fill=_acc(p))
    d.text((28, 12), txt, font=kf, fill=p.get("kicker_text", (12, 12, 12)))
    return s


# ----------------------------------------------------------------------------- layouts
def video_statement(item, out, style="blackout", secs=5):
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
    footer = _footer_sprite(p); ul = Image.new("RGBA", (240, 14), _acc(p) + (255,))
    ls, ld, stag = 0.2, 0.4, 0.3
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


def video_stat(item, out, style="blackout", secs=6):
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    acc = _acc(p)
    htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    m = re.match(r"\s*(\d+(?:\.\d+)?)(.*)", str(item["stat"]))
    target = float(m.group(1)) if m else None
    suffix = m.group(2) if m else ""
    unit = suffix.strip()
    # Stack the unit on its own line when the number has a trailing WORD
    # ("90 DAYS", "3 SEC") so the number stays huge and NOTHING gets clipped.
    stacked = target is not None and bool(unit) and suffix[:1] == " "

    def numtext(v):
        return f"{int(v)}" if float(v).is_integer() else f"{v:g}"

    def fit(text, cap, floor=64):
        """Largest brand-font size (<=cap) at which `text` fits the frame width."""
        s = cap
        while s > floor and htmp.textlength(text, font=f_brand(s)) > VW - 2 * M:
            s -= 6
        return s

    if target is None:                       # pure word, e.g. "SENDS"
        big_final = str(item["stat"]); num_size = fit(big_final, 300)
    elif stacked:                            # "90" big, "DAYS" below
        big_final = numtext(target); num_size = fit(big_final, 360)
    else:                                    # inline, e.g. "90%", "2X"
        big_final = numtext(target) + suffix; num_size = fit(big_final, 360)
    nf = f_brand(num_size)
    unit_size = fit(unit, min(int(num_size * 0.44), 150)) if stacked else 0
    uf = f_brand(unit_size) if stacked else None

    kick = _kicker_sprite(item.get("kicker", "THE NUMBER"), p)
    hf = f_brand(72)
    hlines = wrap(htmp, item["headline"], hf, VW - 2 * M)
    hsprites = [_text_sprite(ln, hf, p["head"])[0] for ln in hlines]
    footer = _footer_sprite(p)
    cnt_s, cnt_d = 0.3, 1.0  # count-up window (faster)
    num_lh = int(num_size * 1.0); unit_lh = int(unit_size * 1.12) if stacked else 0
    head_h = len(hlines) * 84
    block = 56 + 40 + num_lh + unit_lh + 24 + head_h
    top = (VH - block) // 2          # vertically center kicker + number + headline
    ky = top; numy = top + 96; unity = numy + num_lh + 4
    heady = (unity + unit_lh if stacked else numy + num_lh) + 28

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(36 * np.sin(t * 0.8))))
        fr.alpha_composite(_alpha(kick, ease((t - 0.1) / 0.5)), (M, ky))
        # counting number (left-aligned at the margin)
        if target is None:
            disp = big_final
        else:
            val = round(target * ease((t - cnt_s) / cnt_d))
            disp = numtext(val) + ("" if stacked else suffix)
        nsp = Image.new("RGBA", (VW, nf.getmetrics()[0] + nf.getmetrics()[1] + 20), (0, 0, 0, 0))
        ImageDraw.Draw(nsp).text((M - 8, 0), disp, font=nf, fill=acc)
        fr.alpha_composite(nsp, (0, numy))
        if stacked:
            usp = Image.new("RGBA", (VW, uf.getmetrics()[0] + uf.getmetrics()[1] + 16), (0, 0, 0, 0))
            ImageDraw.Draw(usp).text((M - 4, 0), unit, font=uf, fill=p["head"])
            fr.alpha_composite(_alpha(usp, ease((t - (cnt_s + cnt_d * 0.5)) / 0.5)), (0, unity))
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


def video_quote(item, out, style="navyorange", secs=5):
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
    ImageDraw.Draw(attr).text((M, 0), "— Joseph Borroto", font=af, fill=_acc(p))
    footer = _footer_sprite(p)
    n = len(sprites)
    text_h = n * lh
    y0 = (VH - text_h - 120) // 2 + 30       # vertically center quote + attribution
    qy = max(120, y0 - 240)
    ls, ld, stag = 0.3, 0.4, 0.3
    last = ls + (n - 1) * stag + ld

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(40 * np.sin(t * 0.7))))
        qa = ease((t - 0.1) / 0.6)  # quote mark scales/fades in
        if qa > 0:
            qs = Image.new("RGBA", (VW, 320), (0, 0, 0, 0))
            ImageDraw.Draw(qs).text((M - 12, 0), '"', font=qf, fill=_acc(p))
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


def video_checklist(item, out, style="dark", secs=7):
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
            pr = ease((t - (0.15 + k * 0.15)) / 0.4)
            if pr > 0:
                fr.alpha_composite(_alpha(ts, pr), (0, top + k * 78 + int((1 - pr) * 26)))
        y = rows_top
        for bi, b in enumerate(bullets):
            st = 0.4 + bi * 0.55
            pr = ease((t - st) / 0.5)
            if pr <= 0:
                y += 130; continue
            row = Image.new("RGBA", (VW, 130), (0, 0, 0, 0)); d = ImageDraw.Draw(row)
            d.rounded_rectangle((M, 4, M + 56, 60), 10, fill=_acc(p))
            chk = ease((t - (st + 0.15)) / 0.3)  # check draws in
            # carve the check out in the bg color so it contrasts ANY pill color
            # (dark check on the orange pill; orange check on the full-orange look)
            chkc = p["bg_top"]
            if chk > 0:
                d.line([(M + 13, 34), (M + 25, 47)], fill=chkc, width=7)
                if chk > 0.5:
                    d.line([(M + 25, 47), (M + 47, 18)], fill=chkc, width=7)
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
        d.text((M - 6, y), str(scene["n"]), font=f_brand(150), fill=_acc(p)); y += num_h
    for ln in hl:
        d.text((M, y), ln, font=hf, fill=p["head"]); y += lh
    y += 16
    d.rounded_rectangle((M, y, M + 200, y + 10), 5, fill=_acc(p)); y += 50
    bf = f_sys(46)
    for ln in body_lines:
        d.text((M, y), ln, font=bf, fill=p["sub"]); y += 58
    if scene.get("swipe"):
        sf = f_brand(34); d.text((M, VH - 250), "SWIPE", font=sf, fill=_acc(p))
        sw = d.textlength("SWIPE", font=sf)
        d.polygon([(M + sw + 22, VH - 246), (M + sw + 22, VH - 214), (M + sw + 52, VH - 230)], fill=_acc(p))
    hf2 = f_brand(40); h = "@josephborroto"; hw = d.textlength(h, font=hf2)
    d.text(((VW - hw) / 2, VH - 150), h, font=hf2, fill=p.get("muted", (170, 170, 170)))
    return img


def video_sequence(scenes, out, style="dark", hold=1.6, trans=0.45):
    """Carousel-style Reel: scenes swipe past horizontally (push transition),
    with dot indicators — 'feels like a carousel passing by'."""
    p = PALETTES.get(style, PALETTES["dark"])
    n = len(scenes)

    def dots(im, active):
        dd = ImageDraw.Draw(im); r, gap = 9, 36
        x0 = (VW - (n - 1) * gap) // 2
        for i in range(n):
            c = _acc(p) if i == active else (110, 110, 110)
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


def video_xpost(item, out, style="dark", secs=6):
    """Animated X (Twitter) post: the profile + claim build in line by line, an
    optional reply card slides up, then the CTA — the moving version of the card."""
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    soc = item.get("social", item)
    MX = 96; INNER = VW - 2 * MX; blue = (45, 140, 255); r = 58
    pad = 34; rr = 42; rbf = f_sys(36)
    muted = p.get("muted", (150, 150, 150))
    htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    def fit(text):
        for size in range(54, 37, -3):
            f = f_sys(size, bold=True); ls = wrap(htmp, text, f, INNER)
            if len(ls) <= 4:
                return f, ls, int(size * 1.16)
        f = f_sys(38, bold=True); return f, wrap(htmp, text, f, INNER), int(38 * 1.16)
    hf, hlines, hlh = fit(soc["headline"]); claim_h = len(hlines) * hlh
    rp = soc.get("reply"); body_lines, card_h = [], 0
    if rp:
        body_lines = wrap(htmp, rp["body"], rbf, (VW - MX - pad) - (MX + pad))
        card_h = 34 + 2 * rr + 16 + len(body_lines) * 48 + 14 + 52 + 20 + 40 + 26
    cta = soc.get("cta", ""); cta_h = 56 if cta else 0
    total = (2 * r + 46) + claim_h + ((30 + card_h) if rp else 0) + ((48 + cta_h) if cta else 0)
    block_top = max(150, (VH - total) // 2)

    # header sprite (avatar + name + verified + handle)
    head = Image.new("RGBA", (VW, 2 * r + 24), (0, 0, 0, 0)); hd = ImageDraw.Draw(head)
    rcard._put_avatar(head, hd, MX, 0, r, soc.get("initials", "JB"), ORANGE,
                      photo=soc.get("photo"), use_default=True,
                      focus=tuple(soc.get("avatar_focus", (0.5, 0.44))))
    nx = MX + 2 * r + 28; nf = f_sys(46, bold=True); name = soc.get("author", "Joseph Borroto")
    hd.text((nx, 6), name, font=nf, fill=p["head"]); nw = hd.textlength(name, font=nf)
    if soc.get("verified", True):
        rcard._verified(hd, nx + nw + 34, 30, 24)
    hd.text((nx, 64), soc.get("handle", "@josephborroto"), font=f_sys(38), fill=muted)

    claim_sprites = []
    for ln in hlines:
        s = Image.new("RGBA", (VW, hlh), (0, 0, 0, 0))
        ImageDraw.Draw(s).text((MX, 0), ln, font=hf, fill=p["head"]); claim_sprites.append(s)

    reply = None
    if rp:
        reply = Image.new("RGBA", (VW, card_h), (0, 0, 0, 0)); rd = ImageDraw.Draw(reply)
        ax0, ax1 = MX, VW - MX
        rd.rounded_rectangle((ax0, 0, ax1, card_h), radius=28, fill=(30, 30, 33), outline=(58, 58, 64), width=2)
        cy = 34
        rcard._put_avatar(reply, rd, ax0 + pad, cy, rr, rp.get("initials", "TV"), (70, 110, 150), photo=rp.get("photo"))
        rnx = ax0 + pad + 2 * rr + 20; rnf = f_sys(38, bold=True)
        rd.text((rnx, cy + 4), rp["author"], font=rnf, fill=p["head"]); rnw = rd.textlength(rp["author"], font=rnf)
        rd.text((rnx + rnw + 16, cy + 12), rp.get("time", ""), font=f_sys(28), fill=muted)
        by = cy + 2 * rr + 16
        for ln in body_lines:
            rd.text((ax0 + pad, by), ln, font=rbf, fill=(220, 222, 226)); by += 48
        by += 14; cnt = str(rp.get("reactions", 4)); pillf = f_sys(30, bold=True); cw = rd.textlength(cnt, font=pillf)
        rd.rounded_rectangle((ax0 + pad, by, ax0 + pad + 56 + cw + 28, by + 52), radius=26, outline=(70, 130, 180), width=3)
        rcard._heart(rd, ax0 + pad + 32, by + 26, 28, (235, 90, 110))
        rd.text((ax0 + pad + 54, by + 11), cnt, font=pillf, fill=(150, 190, 220))
        by += 72; rcard._avatar(rd, ax0 + pad, by + 2, 16, "", (70, 110, 150))
        rd.text((ax0 + pad + 46, by + 2), rp.get("replies", ""), font=f_sys(28), fill=muted)

    cta_sprite = None
    if cta:
        cta_sprite = Image.new("RGBA", (VW, 60), (0, 0, 0, 0))
        ImageDraw.Draw(cta_sprite).text((MX, 0), cta, font=f_sys(44, bold=True), fill=blue)

    y_claim0 = block_top + 2 * r + 46
    y_reply = y_claim0 + claim_h + 30
    y_cta = (y_reply + card_h if rp else y_claim0 + claim_h) + 48
    t_claim = [0.5 + i * 0.22 for i in range(len(claim_sprites))]
    last_claim = t_claim[-1] if t_claim else 0.5
    t_reply = last_claim + 0.35
    t_cta = (t_reply + 0.5) if rp else (last_claim + 0.35)

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(30 * np.sin(t * 0.7))))
        a = ease((t - 0.15) / 0.5)
        if a > 0:
            fr.alpha_composite(_alpha(head, a), (0, block_top + int((1 - a) * 24)))
        for k, s in enumerate(claim_sprites):
            pr = ease((t - t_claim[k]) / 0.45)
            if pr > 0:
                fr.alpha_composite(_alpha(s, pr), (0, y_claim0 + k * hlh + int((1 - pr) * 26)))
        if reply is not None:
            pr = ease((t - t_reply) / 0.55)
            if pr > 0:
                fr.alpha_composite(_alpha(reply, pr), (0, y_reply + int((1 - pr) * 40)))
        if cta_sprite is not None:
            pr = ease((t - t_cta) / 0.5)
            if pr > 0:
                fr.alpha_composite(_alpha(cta_sprite, pr), (0, y_cta + int((1 - pr) * 20)))
        return fr
    return _encode(frame, int(secs * FPS), out)


def video_comment(item, out, style="dark", secs=6):
    """Animated comment reel: the question fades in, then Joseph's verified reply
    slides up underneath — the moving version of the comment card."""
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    footer = _footer_sprite(p)
    name_c = p["head"]; txt_c = (224, 224, 228); meta_c = (150, 150, 156)
    nf = f_sys(40, bold=True); tf = f_sys(44); mf = f_sys(30)
    htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    def block(x, av_init, av_fill, photo, name, text, likes, verified):
        tx = x + 2 * 46 + 24
        lines = wrap(htmp, rcard._no_emoji(text), tf, (VW - M) - tx)
        h = max(2 * 46, 56 + len(lines) * 56 + 8 + 50)
        s = Image.new("RGBA", (VW, h), (0, 0, 0, 0)); bd = ImageDraw.Draw(s)
        rcard._put_avatar(s, bd, x, 0, 46, av_init, av_fill, photo=photo)
        bd.text((tx, 2), name, font=nf, fill=name_c)
        if verified:
            rcard._verified(bd, tx + bd.textlength(name, font=nf) + 28, 22, 18)
        yy = 56
        for ln in lines:
            bd.text((tx, yy), ln, font=tf, fill=txt_c); yy += 56
        bd.text((tx, yy + 8), f"♥ {likes}    Reply", font=mf, fill=meta_c)
        return s, h

    c = item["comment"]; rp = item["reply"]
    c_sp, ch = block(M, c.get("initials", "•"), (90, 110, 140), c.get("photo"),
                     c.get("author", "someone"), c["text"], c.get("likes", "2.1k"), False)
    r_sp, rh = block(M + 90, rp.get("initials", "JB"), ORANGE,
                     rp.get("photo") or (str(rcard.AVATAR_PATH) if rcard.AVATAR_PATH else None),
                     rp.get("author", "Joseph Borroto"), rp["text"], rp.get("likes", "480"),
                     rp.get("verified", True))
    total = ch + 40 + rh
    y_c = max(220, (VH - total) // 2); y_r = y_c + ch + 40
    t_reply = 1.5

    def frame(i):
        t = i / FPS; fr = bg.copy()
        fr.alpha_composite(glow, (0, int(28 * np.sin(t * 0.7))))
        a = ease((t - 0.25) / 0.5)
        if a > 0:
            fr.alpha_composite(_alpha(c_sp, a), (0, y_c + int((1 - a) * 30)))
        ra = ease((t - t_reply) / 0.55)
        if ra > 0:
            fr.alpha_composite(_alpha(r_sp, ra), (0, y_r + int((1 - ra) * 40)))
        fr.alpha_composite(_alpha(footer, ease((t - t_reply - 0.3) / 0.6)), (0, VH - 150))
        return fr
    return _encode(frame, int(secs * FPS), out)


def video_imessage(item, out, style="dark", secs=6):
    """Animated DM thread — bubbles pop in one at a time, grey 'them' + blue 'me'."""
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    footer = _footer_sprite(p)
    them_bub, them_txt = (38, 38, 40), (245, 245, 245)
    me_bub, me_txt = (10, 132, 255), (255, 255, 255)
    f = f_sys(44); htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10))); maxw = int(VW * 0.70)
    laid = []
    for m in item["messages"]:
        lines = wrap(htmp, rcard._no_emoji(m["text"]), f, maxw - 64)
        bw = int(max(htmp.textlength(l, font=f) for l in lines)) + 64
        bh = len(lines) * 54 + 36
        laid.append((m.get("from") == "me", lines, bw, bh))
    total = sum(bh for *_, bh in laid) + 24 * (len(laid) - 1)
    y = max(220, (VH - total) // 2)
    sprites = []
    for mine, lines, bw, bh in laid:
        s = Image.new("RGBA", (VW, bh), (0, 0, 0, 0)); sd = ImageDraw.Draw(s)
        x0 = (VW - 70 - bw) if mine else 70
        sd.rounded_rectangle((x0, 0, x0 + bw, bh), radius=36, fill=me_bub if mine else them_bub)
        ty = 18
        for l in lines:
            sd.text((x0 + 32, ty), l, font=f, fill=me_txt if mine else them_txt); ty += 54
        sprites.append((s, y)); y += bh + 24
    t0, step = 0.35, 0.62
    secs = max(secs, t0 + len(sprites) * step + 2.2)

    def frame(i):
        t = i / FPS; fr = bg.copy(); fr.alpha_composite(glow, (0, int(26 * np.sin(t * 0.7))))
        for k, (s, yy) in enumerate(sprites):
            pr = ease((t - (t0 + k * step)) / 0.4)
            if pr > 0:
                fr.alpha_composite(_alpha(s, pr), (0, yy + int((1 - pr) * 26)))
        fr.alpha_composite(_alpha(footer, ease((t - 0.3) / 0.7)), (0, VH - 150))
        return fr
    return _encode(frame, int(secs * FPS), out)


def video_typewriter(item, out, style="blackout", secs=6):
    """A headline that types out letter by letter with a blinking cursor."""
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    footer = _footer_sprite(p); acc = _acc(p)
    txt = item.get("headline", ""); htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    size = 116
    while size > 56:
        f = f_brand(size); lines = wrap(htmp, txt, f, VW - 2 * M)
        if len(lines) <= 5 and max(htmp.textlength(l, font=f) for l in lines) <= VW - 2 * M:
            break
        size -= 6
    f = f_brand(size); lh = int(size * 1.06)
    starts, cum = [], 0
    for l in lines:
        starts.append(cum); cum += len(l)
    total_chars = cum; cps = 26
    block_h = len(lines) * lh; y0 = (VH - block_h) // 2 - 40

    def frame(i):
        t = i / FPS; fr = bg.copy(); fr.alpha_composite(glow, (0, int(34 * np.sin(t * 0.9))))
        d = ImageDraw.Draw(fr); n = int(t * cps)
        y = y0; cursor = None
        for li, l in enumerate(lines):
            take = max(0, min(len(l), n - starts[li]))
            shown = l[:take]
            if shown:
                d.text((M, y), shown, font=f, fill=p["head"])
            if 0 < take <= len(l) and n < total_chars and starts[li] + take == n:
                cursor = (M + htmp.textlength(shown, font=f) + 6, y)
            y += lh
        # blinking cursor (steady while typing, blink after)
        if n >= total_chars:
            cursor = (M + htmp.textlength(lines[-1], font=f) + 6, y0 + (len(lines) - 1) * lh)
        if cursor and (n < total_chars or int(t * 2) % 2 == 0):
            d.rectangle((cursor[0], cursor[1] + 6, cursor[0] + 10, cursor[1] + size), fill=acc)
        fr.alpha_composite(_alpha(footer, ease((t - 0.3) / 0.7)), (0, VH - 150))
        return fr
    secs = max(secs, total_chars / cps + 2.2)
    return _encode(frame, int(secs * FPS), out)


def video_countdown(item, out, style="navyorange", secs=7):
    """A numbered list that reveals one row at a time with a big slamming number."""
    p = PALETTES.get(style, PALETTES["dark"]); bg, glow = _bg(p), _glow(p)
    footer = _footer_sprite(p); acc = _acc(p)
    htmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    title = item.get("headline", ""); items = item.get("items", [])[:5]
    tf = f_brand(64); tlines = wrap(htmp, title, tf, VW - 2 * M)
    nf = f_brand(96); bf = f_sys(46)
    rows = []
    for it in items:
        bl = wrap(htmp, it, bf, VW - 2 * M - 150)
        rows.append((bl, max(110, len(bl) * 54 + 30)))
    th = len(tlines) * 74
    total = th + 40 + sum(h for _, h in rows)
    top = max(150, (VH - total) // 2)
    t0, step = 0.5, 0.8
    secs = max(secs, t0 + len(rows) * step + 2.2)

    def frame(i):
        t = i / FPS; fr = bg.copy(); fr.alpha_composite(glow, (0, int(28 * np.sin(t * 0.7))))
        d = ImageDraw.Draw(fr); y = top
        for ln in tlines:
            d.text((M, y), ln, font=tf, fill=p["head"]); y += 74
        y += 40
        for k, (bl, h) in enumerate(rows):
            pr = ease((t - (t0 + k * step)) / 0.4)
            if pr > 0:
                sc = 0.6 + 0.4 * pr
                d.text((M, y + int((1 - pr) * 20)), str(k + 1), font=f_brand(int(96 * sc)), fill=acc)
                ty = y + int((1 - pr) * 20)
                for bln in bl:
                    d.text((M + 150, ty + 14), bln, font=bf, fill=p["sub"]); ty += 54
            y += h
        fr.alpha_composite(_alpha(footer, ease((t - 0.3) / 0.7)), (0, VH - 150))
        return fr
    return _encode(frame, int(secs * FPS), out)


def render_video(item, out, style="dark"):
    """Dispatch a content item to the right animated Reel by its type."""
    t = item.get("type", "single")
    if t == "social":
        return video_xpost(item, out, style=style)
    if t == "comment":
        return video_comment(item, out, style=style)
    if t == "imessage":
        return video_imessage(item, out, style=style)
    if t == "typewriter":
        return video_typewriter(item, out, style=style)
    if t == "countdown":
        return video_countdown(item, out, style=style)
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
