#!/usr/bin/env python3
"""Generate 100% copyright-safe beat beds in code and mux them into Reels.
Several distinct variants (tempo/key/mood) so the audio rotates and never feels
repetitive. Everything is synthesized here, so there is zero copyright risk."""
import subprocess, wave
import numpy as np
import imageio_ffmpeg

SR = 44100

# Each beat is fully synthesized — different tempo, root note, chord and feel.
BEATS = [
    {"name": "lofi-warm",   "bpm": 82,  "root": 110.00, "chord": [0, 3, 7, 10], "kick": 0.55, "hat": 0.05, "pad": 0.050, "trem": 0.22},
    {"name": "deep-min",    "bpm": 76,  "root": 98.00,  "chord": [0, 3, 7, 12], "kick": 0.60, "hat": 0.00, "pad": 0.060, "trem": 0.15},
    {"name": "bright-maj",  "bpm": 92,  "root": 130.81, "chord": [0, 4, 7, 11], "kick": 0.50, "hat": 0.06, "pad": 0.045, "trem": 0.30},
    {"name": "minimal",     "bpm": 100, "root": 123.47, "chord": [0, 7, 12],    "kick": 0.45, "hat": 0.07, "pad": 0.035, "trem": 0.00},
    {"name": "chill-sus",   "bpm": 70,  "root": 87.31,  "chord": [0, 5, 7, 10], "kick": 0.42, "hat": 0.00, "pad": 0.070, "trem": 0.18},
    {"name": "drive-soft",  "bpm": 110, "root": 146.83, "chord": [0, 3, 7],     "kick": 0.55, "hat": 0.08, "pad": 0.040, "trem": 0.10},
    {"name": "trap-dark",   "bpm": 130, "root": 73.42,  "chord": [0, 3, 7, 10], "kick": 0.62, "hat": 0.09, "pad": 0.045, "trem": 0.12},
    {"name": "ambient-air", "bpm": 64,  "root": 164.81, "chord": [0, 4, 7, 11], "kick": 0.30, "hat": 0.00, "pad": 0.075, "trem": 0.25},
    {"name": "house-pulse", "bpm": 122, "root": 110.00, "chord": [0, 5, 7, 12], "kick": 0.58, "hat": 0.10, "pad": 0.040, "trem": 0.08},
    {"name": "phonk-low",   "bpm": 88,  "root": 82.41,  "chord": [0, 3, 7],     "kick": 0.66, "hat": 0.04, "pad": 0.050, "trem": 0.20},
]


def _synth(variant, dur=30.0):
    b = BEATS[variant % len(BEATS)]
    n = int(SR * dur); t = np.arange(n) / SR
    spb = 60.0 / b["bpm"]
    audio = np.zeros(n)
    # chord pad
    for st in b["chord"]:
        f = b["root"] * (2 ** (st / 12.0))
        audio += np.sin(2 * np.pi * f * t) * b["pad"]
    if b["trem"]:
        audio *= (1 - b["trem"]) + b["trem"] * np.sin(2 * np.pi * 0.22 * t)
    # kick on each beat (pitch-swept sine)
    for beat in np.arange(0, dur, spb):
        i0 = int(beat * SR); L = min(int(0.18 * SR), n - i0)
        if L <= 0:
            break
        env = np.exp(-np.linspace(0, 1, L) * 20)
        fk = np.linspace(115, 45, L)
        audio[i0:i0 + L] += np.sin(2 * np.pi * np.cumsum(fk) / SR) * env * b["kick"]
    # hats on offbeats
    if b["hat"]:
        for beat in np.arange(spb / 2, dur, spb):
            i0 = int(beat * SR); L = min(int(0.05 * SR), n - i0)
            if L <= 0:
                break
            env = np.exp(-np.linspace(0, 1, L) * 38)
            audio[i0:i0 + L] += np.random.randn(L) * env * b["hat"]
    audio /= (np.max(np.abs(audio)) + 1e-6)
    audio *= 0.5  # headroom — it's a bed, not the focus
    return np.repeat((audio * 32767).astype(np.int16)[:, None], 2, axis=1)


def write_wav(path, variant, dur=30.0):
    st = _synth(variant, dur)
    with wave.open(path, "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(st.tobytes())
    return path


def add_beat(video_path, variant, tmp_wav="/tmp/_beat.wav"):
    """Mux a rotating beat onto an existing (silent) video, trimmed to length."""
    write_wav(tmp_wav, variant)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    out = video_path + ".beat.mp4"
    subprocess.run([ff, "-y", "-i", video_path, "-i", tmp_wav,
                    "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", "-c:a", "aac", "-b:a", "160k", out],
                   check=True, capture_output=True)
    import shutil
    shutil.move(out, video_path)
    return BEATS[variant % len(BEATS)]["name"]


if __name__ == "__main__":
    for i in range(len(BEATS)):
        write_wav(f"/tmp/proof/beat_{BEATS[i]['name']}.wav", i, dur=6)
        print("wrote beat", BEATS[i]["name"])
