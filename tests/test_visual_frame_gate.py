#!/usr/bin/env python3
"""Behaviour tests for QEMU visual evidence and NVIDIA greeter GPU selection."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from assert_visual_frame import frame_metrics


ROOT = Path(__file__).resolve().parents[1]
GREETER_ENV = ROOT / "system_files/usr/libexec/moos-greeter-gl-env"


def write_ppm(path: Path, width: int, height: int, pixels: bytes) -> None:
    path.write_bytes(f"P6\n{width} {height}\n255\n".encode() + pixels)


with tempfile.TemporaryDirectory(prefix="moos-visual-frame-") as tmp:
    root = Path(tmp)
    black_cursor = root / "black-cursor.ppm"
    authored = root / "authored.ppm"
    width = height = 100
    black = bytearray(width * height * 3)
    for y in range(48, 52):
        for x in range(48, 52):
            start = (y * width + x) * 3
            black[start : start + 3] = b"\xff\xff\xff"
    write_ppm(black_cursor, width, height, bytes(black))
    write_ppm(
        authored,
        width,
        height,
        b"".join(
            bytes((20 + x * 2, 35 + y * 2, 70 + (x + y) % 120))
            for y in range(height)
            for x in range(width)
        ),
    )
    _, _, black_visible = frame_metrics(black_cursor)
    _, _, authored_visible = frame_metrics(authored)
    assert black_visible < 0.03
    assert authored_visible > 0.90
    assert subprocess.run(
        ["python3", str(ROOT / "tests/assert_visual_frame.py"), str(black_cursor)],
        capture_output=True,
        text=True,
    ).returncode != 0
    subprocess.run(
        ["python3", str(ROOT / "tests/assert_visual_frame.py"), str(authored)],
        check=True,
    )


def run_greeter_helper(devices: tuple[str, ...]) -> str | None:
    with tempfile.TemporaryDirectory(prefix="moos-greeter-env-") as tmp:
        root = Path(tmp)
        devroot = root / "dev"
        envfile = root / "run/greeter.env"
        for relative in devices:
            path = devroot / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        envfile.parent.mkdir(parents=True, exist_ok=True)
        envfile.write_text("STALE=1\n", encoding="utf-8")
        subprocess.run(
            [str(GREETER_ENV)],
            env=os.environ
            | {
                "MOOS_GREETER_DEV_ROOT": str(devroot),
                "MOOS_GREETER_GL_ENV": str(envfile),
                "MOOS_GREETER_ARCH": "x86_64",
            },
            check=True,
        )
        return envfile.read_text(encoding="utf-8") if envfile.exists() else None


assert run_greeter_helper(("dri/renderD128",)) is None
assert run_greeter_helper(("nvidiactl",)) is None
fallback = run_greeter_helper(())
assert fallback is not None
assert "LIBGL_ALWAYS_SOFTWARE=1" in fallback
assert "__EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json" in fallback

print("Visual frame and greeter GPU-selection gates passed")
