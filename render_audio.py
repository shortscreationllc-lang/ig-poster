#!/usr/bin/env python3
"""Generate 100% copyright-safe beat beds in code and mux them into Reels.
Fully synthesized (zero copyright risk): sub-bass groove, punchy kick + click,
backbeat clap, hi-hat pattern, detuned pad, a melodic pluck hook, sidechain
'pump' and soft saturation — so the audio is full and modern, not a thin sine."""
import subprocess, wave
import numpy as np
import imageio_ffmpeg

SR = 44100

# bpm, root (Hz), chord (semitones), and per-element levels. Defaults via .get so
# every variant is full unless it deliberately strips an element back.
BEATS = [
    {"name": "lofi-warm",   "bpm": 82,  "root": 110.00, "chord": [0, 3, 7, 10], "kick": 0.9, "clap": 0.5, "hat": 0.35, "bass": 0.8, "pluck": 0.5, "swing": 0.12},
    {"name": "deep-min",    "bpm": 76,  "root": 98.00,  "chord": [0, 3, 7, 12], "kick": 1.0, "clap": 0.4, "hat": 0.25, "bass": 0.9, "pluck": 0.35, "swing": 0.0},
    {"name": "bright-maj",  "bpm": 92,  "root": 130.81, "chord": [0, 4, 7, 11], "kick": 0.85, "clap": 0.55, "hat": 0.45, "bass": 0.7, "pluck": 0.6, "swing": 0.08},
    {"name": "minimal",     "bpm": 104, "root": 123.47, "chord": [0, 7, 12],    "kick": 0.8, "clap": 0.45, "hat": 0.5, "bass": 0.6, "pluck": 0.3, "swing": 0.0},
    {"name": "chill-sus",   "bpm": 72,  "root": 87.31,  "chord": [0, 5, 7, 10], "kick": 0.75, "clap": 0.4, "hat": 0.2, "bass": 0.8, "pluck": 0.45, "swing": 0.14},
    {"name": "drive-soft",  "bpm": 112, "root": 146.83, "chord": [0, 3, 7, 10], "kick": 0.95, "clap": 0.6, "hat": 0.55, "bass": 0.7, "pluck": 0.5, "swing": 0.0},
    {"name": "trap-dark",   "bpm": 132, "root": 73.42,  "chord": [0, 3, 7, 10], "kick": 1.0, "clap": 0.5, "hat": 0.6, "bass": 1.0, "pluck": 0.4, "swing": 0.0, "rolls": True},
    {"name": "ambient-air", "bpm": 66,  "root": 164.81, "chord": [0, 4, 7, 11], "kick": 0.55, "clap": 0.3, "hat": 0.15, "bass": 0.5, "pluck": 0.6, "swing": 0.18},
    {"name": "house-pulse", "bpm": 124, "root": 110.00, "chord": [0, 5, 7, 12], "kick": 1.0, "clap": 0.55, "hat": 0.6, "bass": 0.85, "pluck": 0.4, "swing": 0.0, "four": True},
    {"name": "phonk-low",   "bpm": 88,  "root": 82.41,  "chord": [0, 3, 7, 10], "kick": 1.0, "clap": 0.5, "hat": 0.4, "bass": 1.0, "pluck": 0.55, "swing": 0.1},
    {"name": "uk-bounce",   "bpm": 140, "root": 98.00,  "chord": [0, 3, 7, 12], "kick": 0.95, "clap": 0.6, "hat": 0.55, "bass": 0.9, "pluck": 0.5, "swing": 0.0},
    {"name": "dreamy-keys", "bpm": 90,  "root": 146.83, "chord": [0, 4, 9, 11], "kick": 0.7, "clap": 0.45, "hat": 0.3, "bass": 0.6, "pluck": 0.7, "swing": 0.1},
]


def _env(L, decay):
    return np.exp(-np.linspace(0, 1, max(1, L)) * decay)


def _reverb(x, decay=0.32, taps=(0.037, 0.053, 0.071, 0.097, 0.131)):
    """Cheap multi-tap reverb — adds space so it sounds produced, not dry/fake."""
    out = x.copy(); g = decay
    for d in taps:
        L = int(d * SR)
        if 0 < L < len(x):
            out[L:] += x[:-L] * g; g *= 0.62
    return out


def _place(buf, i0, sig):
    """Add `sig` into `buf` at sample i0, clipped to bounds."""
    L = min(len(sig), len(buf) - i0)
    if L > 0:
        buf[i0:i0 + L] += sig[:L]


def _synth(variant, dur=30.0, var=0):
    b = BEATS[variant % len(BEATS)]
    rng = np.random.default_rng(variant * 131 + var)   # varied every render
    n = int(SR * dur); t = np.arange(n) / SR
    spb = 60.0 / b["bpm"] * (1.0 + rng.uniform(-0.015, 0.015))  # tiny tempo drift
    pad = np.zeros(n); lead = np.zeros(n); drums = np.zeros(n); duck = np.ones(n)

    # ---- detuned pad (richer than a pure sine: 3 harmonics + slight detune) ----
    for st in b["chord"]:
        f = b["root"] * (2 ** (st / 12.0))
        for h, amp, det in ((1, 1.0, 1.000), (2, 0.35, 1.004), (3, 0.18, 0.997)):
            pad += np.sin(2 * np.pi * f * h * det * t) * amp
    pad *= 0.05
    pad *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.18 * t)  # slow tremolo / movement

    # ---- sub-bass groove (root, one octave down, plays the chord rhythm) ----
    bass_amp = b.get("bass", 0.7)
    bf = b["root"] / 2.0
    bass = np.sin(2 * np.pi * bf * t) * 0.18 * bass_amp
    bass = np.tanh(bass * 2.2)  # saturate for warmth/weight

    # ---- drums ----
    beats = np.arange(0, dur, spb)
    four = b.get("four", False)
    for bi, beat in enumerate(beats):
        i0 = int(beat * SR)
        # kick: every beat for house/4-on-floor, else beats 1 & 3 (+ syncopation)
        if four or bi % 2 == 0:
            L = int(0.20 * SR)
            fk = np.linspace(150, 48, L)
            k = np.sin(2 * np.pi * np.cumsum(fk) / SR) * _env(L, 16) * b.get("kick", 0.9)
            k[:int(0.004 * SR)] += rng.standard_normal(int(0.004 * SR)) * 0.4  # click transient
            _place(drums, i0, k)
            # sidechain pump: duck pad+bass right after each kick
            dL = int(spb * 0.9 * SR)
            duck_env = 0.35 + 0.65 * (1 - _env(dL, 6))
            _place_min = min(dL, n - i0)
            if _place_min > 0:
                duck[i0:i0 + _place_min] = np.minimum(duck[i0:i0 + _place_min], duck_env[:_place_min])
        # clap/snare on the backbeat (beats 2 & 4)
        if bi % 2 == 1:
            L = int(0.16 * SR)
            c = (rng.standard_normal(L) * _env(L, 22) + np.sin(2 * np.pi * 1800 * t[:L]) * _env(L, 30) * 0.3) * b.get("clap", 0.5)
            _place(drums, i0, c * 0.5)

    # ---- hats (8th notes, with optional swing + trap rolls) ----
    hat_amp = b.get("hat", 0.4); sw = b.get("swing", 0.0)
    step = spb / 2.0
    for s, pos in enumerate(np.arange(0, dur, step)):
        off = (sw * step) if (s % 2 == 1) else 0.0
        i0 = int((pos + off) * SR); L = int(0.03 * SR)
        h = rng.standard_normal(L) * _env(L, 60) * hat_amp * (0.7 if s % 2 else 1.0)
        _place(drums, i0, h * 0.4)
    if b.get("rolls"):  # trap-style hi-hat rolls every 2 bars
        for pos in np.arange(spb * 3.5, dur, spb * 4):
            for k in range(6):
                i0 = int((pos + k * spb / 12) * SR); L = int(0.02 * SR)
                _place(drums, i0, rng.standard_normal(L) * _env(L, 70) * hat_amp * 0.3)

    # ---- melodic pluck hook (arpeggiates the chord, gives it identity) ----
    pl = b.get("pluck", 0.5)
    if pl:
        notes = [b["root"] * 2 * (2 ** (st / 12.0)) for st in b["chord"]]
        for s, pos in enumerate(np.arange(0, dur, spb)):
            if rng.random() < 0.18:
                continue  # rest — gives the melody breathing room
            f = notes[rng.integers(0, len(notes))] * (2.0 if rng.random() < 0.25 else 1.0)
            i0 = int(pos * SR); L = int(min(spb * 0.9, 0.5) * SR)
            tone = (np.sin(2 * np.pi * f * t[:L]) + 0.3 * np.sin(2 * np.pi * 2 * f * t[:L]))
            _place(lead, i0, tone * _env(L, 7) * 0.06 * pl)

    music = pad * 1.15 + lead * 1.25            # lead with the MUSIC, not the drums
    music = music + _reverb(music) * 0.5         # space so it doesn't sound dry/fake
    mix = (music + bass) * duck + drums * 0.62   # drums pulled back (less 'drum-machine')
    mix = np.tanh(mix * 1.25)                     # glue / soft saturation
    mix /= (np.max(np.abs(mix)) + 1e-6)
    mix *= 0.72
    return np.repeat((mix * 32767).astype(np.int16)[:, None], 2, axis=1)


def write_wav(path, variant, dur=30.0, var=0):
    st = _synth(variant, dur, var)
    with wave.open(path, "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(st.tobytes())
    return path


def add_beat(video_path, variant, tmp_wav="/tmp/_beat.wav"):
    """Mux a rotating beat onto an existing (silent) video, trimmed to length."""
    import random as _r
    write_wav(tmp_wav, variant, var=_r.randint(0, 99999))
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = video_path + ".beat.mp4"
    subprocess.run([ff, "-y", "-i", video_path, "-i", tmp_wav,
                    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", "-c:a", "aac", "-b:a", "192k", out],
                   check=True, capture_output=True)
    import shutil
    shutil.move(out, video_path)
    return BEATS[variant % len(BEATS)]["name"]


if __name__ == "__main__":
    import os
    os.makedirs("/tmp/proof", exist_ok=True)
    for i in range(len(BEATS)):
        write_wav(f"/tmp/proof/beat_{BEATS[i]['name']}.wav", i, dur=6)
        print("wrote beat", BEATS[i]["name"])
