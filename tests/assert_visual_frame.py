#!/usr/bin/env python3
"""Reject a mapped QEMU frame that is only black pixels plus a cursor."""

from __future__ import annotations

import math
from pathlib import Path
import sys


def read_token(data: bytes, offset: int) -> tuple[bytes, int]:
    while True:
        while offset < len(data) and data[offset] in b" \t\r\n":
            offset += 1
        if offset >= len(data):
            raise ValueError("truncated PPM header")
        if data[offset] != ord("#"):
            break
        newline = data.find(b"\n", offset)
        if newline < 0:
            raise ValueError("unterminated PPM comment")
        offset = newline + 1

    end = offset
    while end < len(data) and data[end] not in b" \t\r\n":
        end += 1
    return data[offset:end], end


def frame_metrics(path: Path) -> tuple[float, float, float]:
    data = path.read_bytes()
    offset = 0
    tokens: list[bytes] = []
    for _ in range(4):
        token, offset = read_token(data, offset)
        tokens.append(token)

    magic, width_raw, height_raw, maximum_raw = tokens
    if magic != b"P6":
        raise ValueError("visual gate accepts binary P6 PPM frames only")
    width, height, maximum = map(int, (width_raw, height_raw, maximum_raw))
    if width <= 0 or height <= 0 or maximum <= 0 or maximum > 65535:
        raise ValueError("invalid PPM dimensions or channel maximum")

    if data[offset : offset + 2] == b"\r\n":
        offset += 2
    elif offset < len(data) and data[offset] in b" \t\r\n":
        offset += 1
    else:
        raise ValueError("PPM header has no pixel separator")

    bytes_per_channel = 1 if maximum < 256 else 2
    stride = 3 * bytes_per_channel
    payload = data[offset:]
    expected = width * height * stride
    if len(payload) != expected:
        raise ValueError(f"PPM payload is {len(payload)} bytes; expected {expected}")

    # A mapped GTK capture can include QEMU's own title or menu border. That
    # bright host chrome plus one hardware cursor made a black ARM guest appear
    # five-percent visible. Judge the inset guest canvas instead; trimming five
    # percent keeps 81% of the rendered desktop at every supported resolution.
    x_margin = max(1, width // 20)
    y_margin = max(1, height // 20)
    x_start, x_end = x_margin, width - x_margin
    y_start, y_end = y_margin, height - y_margin
    if x_start >= x_end or y_start >= y_end:
        raise ValueError("visual frame is too small for the inset canvas gate")

    total = 0.0
    total_squared = 0.0
    visible = 0
    pixels = (x_end - x_start) * (y_end - y_start)
    for y in range(y_start, y_end):
        for x in range(x_start, x_end):
            start = (y * width + x) * stride
            channels = [
                int.from_bytes(payload[start + index * bytes_per_channel :
                                       start + (index + 1) * bytes_per_channel], "big")
                / maximum
                for index in range(3)
            ]
            luminance = (
                0.2126 * channels[0]
                + 0.7152 * channels[1]
                + 0.0722 * channels[2]
            )
            total += luminance
            total_squared += luminance * luminance
            visible += luminance > 0.02

    mean = total / pixels
    deviation = math.sqrt(max(0.0, total_squared / pixels - mean * mean))
    return mean, deviation, visible / pixels


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(f"usage: {Path(sys.argv[0]).name} FRAME.ppm [LABEL]", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) == 3 else path.name
    try:
        mean, deviation, visible = frame_metrics(path)
    except (OSError, ValueError) as error:
        raise SystemExit(f"VISUAL FRAME FATAL: {label}: {error}") from error

    print(
        f"{label}: mean={mean:.6f} stddev={deviation:.6f} "
        f"visible-pixels={visible:.6f}"
    )
    if deviation < 0.01 or visible < 0.03:
        raise SystemExit(
            f"VISUAL FRAME FATAL: {label} is black/flat "
            f"(stddev={deviation:.6f}, visible-pixels={visible:.6f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
