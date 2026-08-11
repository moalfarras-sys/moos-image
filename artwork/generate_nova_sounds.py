#!/usr/bin/env python3
"""Synthesize the original MoOS system sound family.

Generation dependency (not shipped in MoOS): ``soundfile==0.14.0``.
Outputs are OGG/Vorbis I, 48 kHz, stereo, with conservative peaks suitable for
desktop mixing. No recorded samples or third-party audio are used.

The family is intentionally small and semantic: one glass timbre, ascending
motion for arrival/success, descending motion for removal/failure, and quieter
micro-events for direct manipulation. It covers the names Plasma and GTK ask
for without turning ordinary navigation into a soundtrack.
"""

from __future__ import annotations

import math
from pathlib import Path
import struct
import zlib

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "system_files" / "usr" / "share" / "sounds" / "moos" / "stereo"
RATE = 48_000


def ogg_crc(page: bytes) -> int:
    """Return the non-reflected CRC-32 used by an Ogg page."""
    crc = 0
    for value in page:
        crc ^= value << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF \
                if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc


def canonicalize_ogg(path: Path, event_name: str) -> None:
    """Replace libsndfile's random stream serial and repair every page CRC.

    Vorbis audio from identical samples was byte-identical except for the random
    Ogg stream serial and the CRC that covers it. That made a generator rerun
    dirty every committed sound for no audible reason. A serial derived from the
    semantic event name makes the output reproducible without touching packets.
    """
    payload = bytearray(path.read_bytes())
    serial = zlib.crc32(event_name.encode("utf-8")) & 0xFFFFFFFF
    offset = 0
    while offset < len(payload):
        if payload[offset:offset + 4] != b"OggS" or offset + 27 > len(payload):
            raise ValueError(f"invalid Ogg page at byte {offset}: {path}")
        segment_count = payload[offset + 26]
        header_end = offset + 27 + segment_count
        if header_end > len(payload):
            raise ValueError(f"truncated Ogg segment table: {path}")
        body_size = sum(payload[offset + 27:header_end])
        page_end = header_end + body_size
        if page_end > len(payload):
            raise ValueError(f"truncated Ogg page body: {path}")

        payload[offset + 14:offset + 18] = struct.pack("<I", serial)
        payload[offset + 22:offset + 26] = b"\0\0\0\0"
        checksum = ogg_crc(bytes(payload[offset:page_end]))
        payload[offset + 22:offset + 26] = struct.pack("<I", checksum)
        offset = page_end

    path.write_bytes(payload)


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


def logout() -> np.ndarray:
    duration = 1.05
    audio = chime(duration, 987.77, start=0.02, decay=4.7, amplitude=0.62, pan=0.22)
    audio += chime(duration, 739.99, start=0.20, decay=4.5, amplitude=0.67, pan=0.0)
    audio += chime(duration, 587.33, start=0.39, decay=4.1, amplitude=0.72, pan=-0.22)
    return finish(audio, peak=0.19)


def information() -> np.ndarray:
    duration = 0.38
    audio = chime(duration, 783.99, start=0.01, decay=12.0, amplitude=0.75, pan=-0.12)
    audio += chime(duration, 1174.66, start=0.09, decay=13.0, amplitude=0.55, pan=0.16)
    return finish(audio, peak=0.16)


def question() -> np.ndarray:
    duration = 0.54
    audio = chime(duration, 659.25, start=0.02, decay=8.0, amplitude=0.72, pan=-0.12)
    audio += chime(duration, 880.00, start=0.22, decay=7.2, amplitude=0.78, pan=0.14)
    return finish(audio, peak=0.17)


def warning() -> np.ndarray:
    duration = 0.66
    audio = chime(duration, 523.25, start=0.02, decay=7.6, amplitude=0.74, pan=-0.10)
    audio += chime(duration, 466.16, start=0.24, decay=6.8, amplitude=0.82, pan=0.10)
    return finish(audio, peak=0.18)


def serious_error() -> np.ndarray:
    duration = 0.82
    audio = chime(duration, 311.13, start=0.01, decay=6.2, amplitude=0.78, pan=-0.14)
    audio += chime(duration, 293.66, start=0.01, decay=7.0, amplitude=0.30, pan=0.14)
    audio += chime(duration, 261.63, start=0.30, decay=5.8, amplitude=0.90, pan=0.12)
    return finish(audio, peak=0.20)


def device_added() -> np.ndarray:
    duration = 0.46
    audio = soft_noise(duration, 0.01, 0.025, 61)
    audio += chime(duration, 698.46, start=0.02, decay=9.5, amplitude=0.68, pan=-0.18)
    audio += chime(duration, 1046.50, start=0.17, decay=9.0, amplitude=0.74, pan=0.18)
    return finish(audio, peak=0.16)


def device_removed() -> np.ndarray:
    duration = 0.46
    audio = soft_noise(duration, 0.01, 0.02, 62)
    audio += chime(duration, 1046.50, start=0.02, decay=9.5, amplitude=0.62, pan=0.18)
    audio += chime(duration, 698.46, start=0.17, decay=9.0, amplitude=0.70, pan=-0.18)
    return finish(audio, peak=0.15)


def volume_tick() -> np.ndarray:
    duration = 0.12
    audio = soft_noise(duration, 0.005, 0.018, 70)
    audio += chime(duration, 880.00, start=0.005, attack=0.003,
                   decay=28.0, amplitude=0.70)
    return finish(audio, peak=0.095)


def button_tick() -> np.ndarray:
    duration = 0.10
    audio = soft_noise(duration, 0.002, 0.024, 71)
    audio += chime(duration, 1318.51, start=0.004, attack=0.002,
                   decay=34.0, amplitude=0.40)
    return finish(audio, peak=0.075)


def battery_caution() -> np.ndarray:
    duration = 0.78
    audio = chime(duration, 466.16, start=0.02, decay=7.0, amplitude=0.72, pan=-0.12)
    audio += chime(duration, 466.16, start=0.34, decay=7.0, amplitude=0.76, pan=0.12)
    return finish(audio, peak=0.17)


def battery_low() -> np.ndarray:
    duration = 1.02
    audio = chime(duration, 349.23, start=0.01, decay=6.2, amplitude=0.78, pan=-0.15)
    audio += chime(duration, 329.63, start=0.31, decay=6.0, amplitude=0.82, pan=0.0)
    audio += chime(duration, 293.66, start=0.61, decay=5.6, amplitude=0.88, pan=0.15)
    return finish(audio, peak=0.19)


def power_plug() -> np.ndarray:
    duration = 0.58
    audio = soft_noise(duration, 0.01, 0.018, 80)
    audio += chime(duration, 523.25, start=0.02, decay=7.8, amplitude=0.62, pan=-0.16)
    audio += chime(duration, 783.99, start=0.20, decay=7.4, amplitude=0.76, pan=0.16)
    return finish(audio, peak=0.16)


def power_unplug() -> np.ndarray:
    duration = 0.58
    audio = soft_noise(duration, 0.01, 0.018, 81)
    audio += chime(duration, 783.99, start=0.02, decay=7.8, amplitude=0.58, pan=0.16)
    audio += chime(duration, 523.25, start=0.20, decay=7.4, amplitude=0.72, pan=-0.16)
    return finish(audio, peak=0.15)


def trash_empty() -> np.ndarray:
    duration = 0.48
    audio = soft_noise(duration, 0.01, 0.045, 90)
    audio += chime(duration, 1174.66, start=0.03, decay=13.0, amplitude=0.46, pan=-0.20)
    audio += chime(duration, 1567.98, start=0.14, decay=14.0, amplitude=0.40, pan=0.20)
    return finish(audio, peak=0.13)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    success = complete()
    failure = error()
    arrival = device_added()
    departure = device_removed()
    events = {
        "desktop-login.oga": login(),
        "desktop-logout.oga": logout(),
        "message-new-instant.oga": notification(),
        "message-new-email.oga": notification(),
        "dialog-information.oga": information(),
        "dialog-question.oga": question(),
        "dialog-warning.oga": warning(),
        "dialog-warning-auth.oga": warning(),
        "dialog-error.oga": failure,
        "dialog-error-serious.oga": serious_error(),
        "device-added.oga": arrival,
        "device-removed.oga": departure,
        "service-login.oga": arrival,
        "service-logout.oga": departure,
        "audio-volume-change.oga": volume_tick(),
        "button-pressed.oga": button_tick(),
        "button-pressed-modifier.oga": button_tick(),
        "battery-caution.oga": battery_caution(),
        "battery-low.oga": battery_low(),
        "power-plug.oga": power_plug(),
        "power-unplug.oga": power_unplug(),
        "complete-download.oga": success,
        "completion-success.oga": success,
        "outcome-success.oga": success,
        "completion-fail.oga": failure,
        "outcome-failure.oga": failure,
        "trash-empty.oga": trash_empty(),
    }
    for name, audio in events.items():
        destination = OUT / name
        sf.write(destination, audio, RATE, format="OGG", subtype="VORBIS")
        canonicalize_ogg(destination, name)
        print(f"wrote {name}: {audio.shape[0] / RATE:.2f}s, 48kHz stereo")


if __name__ == "__main__":
    main()
