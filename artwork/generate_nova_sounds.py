#!/usr/bin/env python3
"""Synthesize the four original MoOS Nova sound-theme events.

Generation dependency (not shipped in MoOS): ``soundfile==0.14.0``.
Outputs are OGG/Vorbis I, 48 kHz, stereo, with conservative peaks suitable for
desktop mixing. No recorded samples or third-party audio are used.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "system_files" / "usr" / "share" / "sounds" / "moos" / "stereo"
RATE = 48_000


def timeline(duration: float) -> np.ndarray:
    return np.arange(round(duration * RATE), dtype=np.float64) / RATE


def chime(
    duration: float,
    frequency: float,
    *,
    start: float = 0.0,
    attack: float = 0.008,
    decay: float = 4.8,
    amplitude: float = 1.0,
    pan: float = 0.0,
) -> np.ndarray:
    t = timeline(duration)
    local = t - start
    active = local >= 0
    x = np.maximum(local, 0.0)
    envelope = (1.0 - np.exp(-x / max(attack, 1e-4))) * np.exp(-decay * x)
    envelope *= active
    fundamental = np.sin(2.0 * math.pi * frequency * x)
    glass = 0.28 * np.sin(2.0 * math.pi * frequency * 2.008 * x + 0.35)
    shimmer = 0.11 * np.sin(2.0 * math.pi * frequency * 3.997 * x + 1.10)
    mono = amplitude * envelope * (fundamental + glass + shimmer)
    left = mono * math.sqrt((1.0 - pan) / 2.0)
    right = mono * math.sqrt((1.0 + pan) / 2.0)
    return np.column_stack((left, right))


def soft_noise(duration: float, start: float, amplitude: float, seed: int) -> np.ndarray:
    t = timeline(duration)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1.0, t.size)
    # A tiny differentiated noise impulse gives glass contact without a clicky
    # OS-default character.
    noise = np.concatenate(([0.0], np.diff(noise)))
    local = np.maximum(t - start, 0.0)
    envelope = (t >= start) * np.exp(-42.0 * local)
    mono = noise * envelope * amplitude
    return np.column_stack((mono, mono))


def finish(audio: np.ndarray, peak: float = 10 ** (-12 / 20)) -> np.ndarray:
    # Short cosine fade prevents codec-edge clicks.
    fade = min(round(0.025 * RATE), audio.shape[0] // 3)
    if fade:
        audio[-fade:] *= np.linspace(1.0, 0.0, fade)[:, None]
    current = float(np.max(np.abs(audio))) or 1.0
    audio = np.tanh(audio / current * 1.08)
    audio *= peak / (float(np.max(np.abs(audio))) or 1.0)
    return audio.astype(np.float32)


def login() -> np.ndarray:
    duration = 1.32
    audio = chime(duration, 587.33, start=0.04, decay=3.7, amplitude=0.85, pan=-0.26)
    audio += chime(duration, 739.99, start=0.23, decay=3.9, amplitude=0.78, pan=0.12)
    audio += chime(duration, 987.77, start=0.43, decay=3.5, amplitude=0.72, pan=0.28)
    audio += chime(duration, 1479.98, start=0.44, decay=7.0, amplitude=0.16, pan=-0.05)
    return finish(audio, peak=0.23)


def notification() -> np.ndarray:
    duration = 0.29
    audio = soft_noise(duration, 0.01, 0.04, 22)
    audio += chime(duration, 1046.50, start=0.01, decay=15.5, amplitude=0.92, pan=-0.12)
    audio += chime(duration, 1567.98, start=0.055, decay=17.5, amplitude=0.55, pan=0.18)
    return finish(audio, peak=0.18)


def error() -> np.ndarray:
    duration = 0.49
    audio = chime(duration, 440.00, start=0.02, decay=9.5, amplitude=0.82, pan=-0.15)
    audio += chime(duration, 415.30, start=0.02, decay=10.2, amplitude=0.30, pan=0.15)
    audio += chime(duration, 349.23, start=0.19, decay=8.5, amplitude=0.88, pan=0.12)
    audio += chime(duration, 329.63, start=0.19, decay=9.4, amplitude=0.22, pan=-0.12)
    return finish(audio, peak=0.20)


def complete() -> np.ndarray:
    duration = 0.62
    audio = chime(duration, 659.25, start=0.02, decay=7.0, amplitude=0.82, pan=-0.20)
    audio += chime(duration, 987.77, start=0.20, decay=6.8, amplitude=0.86, pan=0.20)
    audio += chime(duration, 1318.51, start=0.205, decay=9.0, amplitude=0.25, pan=-0.04)
    return finish(audio, peak=0.20)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = {
        "desktop-login.oga": login(),
        "message-new-instant.oga": notification(),
        "dialog-error.oga": error(),
        "complete-download.oga": complete(),
    }
    for name, audio in events.items():
        sf.write(OUT / name, audio, RATE, format="OGG", subtype="VORBIS")
        print(f"wrote {name}: {audio.shape[0] / RATE:.2f}s, 48kHz stereo")


if __name__ == "__main__":
    main()
