#!/usr/bin/env python3
"""Synthesized, 100% copyright-safe MUSIC beds for Reels — actual little songs,
not a static beat. Each bed plays a 4-chord progression (the kind pop/lofi/
cinematic tracks are built on) with a soft keys timbre, a bassline, a melody
line over the top, gentle drums and reverb. Many moods + per-render variation,
so every video gets its own track and nothing repeats."""
import subprocess, wave
import numpy as np
import imageio_ffmpeg

SR = 44100

# chord shapes (semitone intervals from the chord root)
CH = {"maj": [0, 4, 7], "min": [0, 3, 7], "maj7": [0, 4, 7, 11],
      "min7": [0, 3, 7, 10], "sus": [0, 5, 7], "add9": [0, 4, 7, 14]}

# Song templates. prog = 4 chords as (root-semitones-from-key, quality).
# `inst` shapes the timbre; `drums` 0..1 keeps percussion subtle (musical, not boom).
# Progressions are the common emotional/pop/lofi ones — evocative of today's
# sound without copying any actual song.
BEATS = [
    {"name": "emotional-keys", "key": 261.63, "bpm": 80, "drums": 0.35, "inst": "keys",
     "prog": [(9, "min"), (5, "maj"), (0, "maj"), (7, "maj")]},          # vi IV I V
    {"name": "uplift-pop",     "key": 293.66, "bpm": 96, "drums": 0.5,  "inst": "pluck",
     "prog": [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")]},          # I V vi IV
    {"name": "lofi-rhodes",    "key": 233.08, "bpm": 74, "drums": 0.3,  "inst": "rhodes",
     "prog": [(2, "min7"), (7, "maj7"), (0, "maj7"), (0, "maj7")]},      # ii V I I
    {"name": "cinematic",      "key": 220.00, "bpm": 70, "drums": 0.25, "inst": "pad",
     "prog": [(0, "min"), (8, "maj"), (3, "maj"), (10, "maj")]},         # i VI III VII
    {"name": "dreamy",         "key": 329.63, "bpm": 88, "drums": 0.4,  "inst": "keys",
     "prog": [(0, "maj7"), (9, "min7"), (5, "maj7"), (7, "sus")]},
    {"name": "warm-hopeful",   "key": 246.94, "bpm": 92, "drums": 0.45, "inst": "pluck",
     "prog": [(5, "maj"), (7, "maj"), (9, "min"), (4, "min")]},          # IV V vi iii
    {"name": "night-drive",    "key": 220.00, "bpm": 102, "drums": 0.5, "inst": "rhodes",
     "prog": [(9, "min"), (0, "maj"), (5, "maj"), (7, "maj")]},
    {"name": "soft-anthem",    "key": 277.18, "bpm": 84, "drums": 0.42, "inst": "keys",
     "prog": [(0, "add9"), (5, "maj"), (9, "min7"), (7, "sus")]},
    {"name": "gentle-future",  "key": 311.13, "bpm": 98, "drums": 0.46, "inst": "pluck",
     "prog": [(9, "min"), (5, "maj"), (7, "maj"), (0, "maj")]},
    {"name": "reflective",     "key": 196.00, "bpm": 72, "drums": 0.22, "inst": "pad",
     "prog": [(0, "maj7"), (4, "min7"), (5, "maj7"), (7, "maj")]},
]

# timbre = harmonic amplitudes + ADSR (attack, decay, sustain, release)
TIMBRE = {
    "keys":   {"harm": [1.0, 0.45, 0.28, 0.14, 0.07], "adsr": (0.006, 0.22, 0.45, 0.30)},
    "rhodes": {"harm": [1.0, 0.30, 0.55, 0.12, 0.20], "adsr": (0.004, 0.30, 0.40, 0.35)},
    "pluck":  {"harm": [1.0, 0.50, 0.30, 0.20, 0.10], "adsr": (0.002, 0.16, 0.18, 0.18)},
    "pad":    {"harm": [1.0, 0.60, 0.40, 0.25, 0.15], "adsr": (0.25, 0.40, 0.70, 0.60)},
}


def _adsr(n, a, d, s, r):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    s_n = max(0, n - a_n - d_n - r_n)
    parts = [np.linspace(0, 1, a_n, endpoint=False),
             np.linspace(1, s, d_n, endpoint=False),
             np.full(s_n, s),
             np.linspace(s, 0, max(1, n - a_n - d_n - s_n))]
    env = np.concatenate(parts)
    return env[:n] if len(env) >= n else np.pad(env, (0, n - len(env)))


def _tone(freq, dur, inst, amp=1.0, detune=0.004):
    n = int(dur * SR)
    if n <= 0:
        return np.zeros(0)
    t = np.arange(n) / SR
    tb = TIMBRE[inst]; w = np.zeros(n)
    for i, h in enumerate(tb["harm"], start=1):
        w += h * np.sin(2 * np.pi * freq * i * (1 + detune * (i - 1)) * t)
    return w * _adsr(n, *tb["adsr"]) * amp


def _reverb(x, decay=0.3, taps=(0.041, 0.057, 0.079, 0.103, 0.137)):
    out = x.copy(); g = decay
    for d in taps:
        L = int(d * SR)
        if 0 < L < len(x):
            out[L:] += x[:-L] * g; g *= 0.6
    return out


def _hz(key, semis):
    return key * (2 ** (semis / 12.0))


def _synth(variant, dur=30.0, var=0):
    b = BEATS[variant % len(BEATS)]
    rng = np.random.default_rng(variant * 257 + var)
    n = int(SR * dur); t = np.arange(n) / SR
    spb = 60.0 / b["bpm"]; bar = spb * 4
    inst = b["inst"]; key = b["key"]
    keys = np.zeros(n); bass = np.zeros(n); mel = np.zeros(n); drums = np.zeros(n)

    def place(buf, i0, sig):
        L = min(len(sig), len(buf) - i0)
        if L > 0:
            buf[i0:i0 + L] += sig[:L]

    # ---- walk the chord progression, one chord per bar, looping ----
    bar_idx = 0
    pos = 0.0
    while pos < dur:
        root, qual = b["prog"][bar_idx % len(b["prog"])]
        intervals = CH[qual]
        i0 = int(pos * SR)
        # chord (keys/pad) — held for the bar, soft
        for iv in intervals:
            f = _hz(key, root + iv)
            place(keys, i0, _tone(f, bar * 0.98, inst, amp=0.10))
        # bass — root, one octave down, plays on each beat (subtle pattern)
        for beat in range(4):
            bi0 = int((pos + beat * spb) * SR)
            place(bass, bi0, _tone(_hz(key / 2, root), spb * 0.9, "pad", amp=0.16))
        # melody — notes from the chord, simple motif over 8th notes w/ rests
        scale = [root + iv for iv in intervals] + [root + 12, root + intervals[1] + 12]
        for step in range(8):
            if rng.random() < 0.35:
                continue  # rest -> musical phrasing, not constant
            note = scale[rng.integers(0, len(scale))]
            mi0 = int((pos + step * spb / 2) * SR)
            place(mel, mi0, _tone(_hz(key * 2, note), spb * 0.55, inst, amp=0.06))
        pos += bar; bar_idx += 1

    # ---- gentle, musical drums (soft kick + soft hat, NOT boom-boom) ----
    da = b.get("drums", 0.4)
    for beat in np.arange(0, dur, spb):
        i0 = int(beat * SR); L = int(0.16 * SR)
        fk = np.linspace(120, 50, L)
        place(drums, i0, np.sin(2 * np.pi * np.cumsum(fk) / SR) * np.exp(-np.linspace(0, 1, L) * 14) * da * 0.7)
    for off in np.arange(spb / 2, dur, spb):
        i0 = int(off * SR); L = int(0.025 * SR)
        place(drums, i0, rng.standard_normal(L) * np.exp(-np.linspace(0, 1, L) * 60) * da * 0.18)

    music = keys + bass + mel
    music = music + _reverb(music) * 0.55
    mix = music + drums * 0.5
    mix = np.tanh(mix * 1.2)
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
    """Mux a fresh, unique music bed onto an existing (silent) video."""
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
        write_wav(f"/tmp/proof/song_{BEATS[i]['name']}.wav", i, dur=6)
        print("wrote", BEATS[i]["name"])
