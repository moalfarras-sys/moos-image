#!/usr/bin/env python3
"""Run the source design reference with isolated settings and optional native capture.

WHAT THIS HARNESS HAS TO GET RIGHT

A design reference is only evidence if the fixture it renders in is the one a
reviewer thinks it is. Four things went wrong here and each produced a picture
that looked fine and proved nothing:

* the fixture replaced XDG_CONFIG_DIRS with a directory that held no kwinrc, so
  Tokens.readBlurPreference() found no policy in any layer, took its `return
  false` fallback, and every surface painted the opaque no-blur material. The
  studio could not render the frosted material it exists to demonstrate. Blur is
  now an explicit argument (`--blur on|off|unset`) written into the fixture's own
  kwinrc, so a reviewer renders BOTH materials deliberately;
* `dbus-run-session` activated xdg-desktop-portal, xdg-desktop-portal-kde and
  kwalletd on the private bus. When that bus died the children were reparented to
  `systemd --user` and survived forever, one set per run, each holding a HOME
  inside an already-deleted temp directory; 31 of them were counted on this
  station. There is now no session bus to activate anything on;
* the documents portal FUSE-mounted `<work>/run/doc`, and TemporaryDirectory's
  rmtree hit the stale mount AFTER the PNG had been written and validated, so a
  successful capture exited 1 with `Errno 107 Transport endpoint is not
  connected`. The fixture is now removed without letting its removal fail a
  capture that already succeeded;
* nothing looked at the pixels. Exit status, an error regex, file existence and
  mtime all pass for a flat-colour or half-drawn PNG. The capture is now decoded
  (pure zlib+struct; this repository has no image dependency) and rejected if it
  is one flat colour, has no plausible variance, or has an empty band.
"""
from __future__ import annotations

import argparse
import configparser
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# What a QML failure actually looks like. The first version of this listed four
# spellings and missed most of them; a module that is not installed, a file that
# is not found, a binding loop and a plain assignment error all produced a
# green run. The last alternative is the generic shape every QML diagnostic
# carries — `<something>.qml:<line>:<column>:` — which catches the next kind of
# failure nobody enumerated here.
QML_FAILURE = re.compile(
    r"^.*(?:"
    r"ReferenceError|TypeError|SyntaxError|RangeError"
    r"|Unable to assign|Cannot assign|Cannot read propert"
    r"|is not a type|is not a function|is not defined|is not installed"
    r"|Binding loop|QQmlApplicationEngine failed|Component is not ready"
    r"|File not found|Cannot open:|Error decoding|Failed to load"
    r"|Expected token|Invalid property|Invalid attached"
    r"|DESIGN_STUDIO_LOCALE_MISMATCH"
    r"|\.qml:\d+:\d+:"
    r").*$",
    flags=re.MULTILINE,
)

# The generic `<file>.qml:<line>:<column>:` catcher above is deliberately wide, so
# the few diagnostics that carry that shape WITHOUT being failures are named here
# rather than left to narrow the catcher back down to uselessness. Qt.labs.settings
# is deprecated and the shipped Tokens.qml still uses it on purpose: it is the one
# settings API the session splash and the login greeter can both load.
QML_BENIGN = re.compile(r"is deprecated and will be removed|Please use the one from QtCore")


# ── the capture, as pixels ──────────────────────────────────────────────────

def decode_png(path: Path) -> tuple[int, int, int, int, bytes | None, list[bytes]]:
    """Decode an 8-bit non-interlaced PNG to unfiltered scanlines.

    Pure standard library on purpose: MoOS has no Pillow dependency and a review
    tool must not acquire one. Qt writes exactly this shape.
    """
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    position, chunks, header, palette = 8, [], None, None
    while position < len(data):
        (length,) = struct.unpack(">I", data[position:position + 4])
        kind = data[position + 4:position + 8]
        body = data[position + 8:position + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            chunks.append(body)
        elif kind == b"PLTE":
            palette = body
        elif kind == b"IEND":
            break
        position += 12 + length
    if header is None or not chunks:
        raise ValueError("PNG has no header or no image data")
    width, height, bits, colour, _, _, interlace = header
    if bits != 8 or interlace != 0:
        raise ValueError(f"unsupported PNG (bits={bits}, interlace={interlace})")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[colour]
    raw = zlib.decompress(b"".join(chunks))
    stride = width * channels
    rows: list[bytes] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        step = channels
        if filter_type == 1:
            for i in range(step, stride):
                line[i] = (line[i] + line[i - step]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - step] if i >= step else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - step] if i >= step else 0
                up = previous[i]
                corner = previous[i - step] if i >= step else 0
                pa, pb, pc = abs(up - corner), abs(left - corner), abs(left + up - 2 * corner)
                predictor = left if (pa <= pb and pa <= pc) else (up if pb <= pc else corner)
                line[i] = (line[i] + predictor) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"unknown PNG filter {filter_type}")
        rows.append(bytes(line))
        previous = line
    return width, height, channels, colour, palette, rows


def survey(path: Path) -> dict:
    """Sample the capture and describe it: colours, spread, and per-band content."""
    width, height, channels, colour, palette, rows = decode_png(path)

    def pixel(x: int, y: int) -> tuple[int, int, int]:
        line = rows[y]
        index = x * channels
        if colour == 3:
            entry = line[index] * 3
            return palette[entry], palette[entry + 1], palette[entry + 2]
        if colour in (0, 4):
            value = line[index]
            return value, value, value
        return line[index], line[index + 1], line[index + 2]

    step_x = max(1, width // 160)
    step_y = max(1, height // 160)
    colours: Counter = Counter()
    luma: list[float] = []
    bands = [Counter() for _ in range(4)]
    for y in range(0, height, step_y):
        band = bands[min(3, y * 4 // height)]
        for x in range(0, width, step_x):
            r, g, b = pixel(x, y)
            colours[(r, g, b)] += 1
            band[(r, g, b)] += 1
            luma.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
    samples = len(luma)
    mean = sum(luma) / samples
    deviation = (sum((value - mean) ** 2 for value in luma) / samples) ** 0.5
    return {
        "width": width, "height": height, "samples": samples,
        "distinct": len(colours),
        "dominant": colours.most_common(1)[0][1] / samples,
        "deviation": deviation,
        "band_distinct": [len(band) for band in bands],
    }


def complaints(report: dict) -> list[str]:
    """Everything wrong with the pixels. Empty means the capture is plausible."""
    problems = []
    if report["distinct"] < 24:
        problems.append(f"only {report['distinct']} distinct sampled colours — flat or blank")
    if report["dominant"] > 0.97:
        problems.append(f"{report['dominant']:.1%} of the frame is one colour")
    if report["deviation"] < 3.0:
        problems.append(f"luminance spread is {report['deviation']:.2f} — nothing was drawn")
    for index, distinct in enumerate(report["band_distinct"]):
        if distinct < 4:
            problems.append(f"horizontal band {index + 1} of 4 has {distinct} colours — half-drawn")
    return problems


# ── the fixture ─────────────────────────────────────────────────────────────

def write_palette(config: Path, scheme: str) -> None:
    """The fixture's kdeglobals: the MoOS defaults with one scheme merged in.

    Merging the scheme's own [Colors:*] groups is what makes Kirigami.Theme pick
    the MoOS palette up. A kdeglobals that only names `ColorScheme=` resolves
    nothing here — the fixture does not carry the scheme's data directory — and
    Qt silently falls back to Breeze's #eff0f1.
    """
    palette = configparser.ConfigParser(strict=False, interpolation=None)
    palette.optionxform = str
    palette.read([ROOT / "system_files/etc/xdg/kdeglobals",
                  ROOT / "system_files/usr/share/color-schemes" / (scheme + ".colors")])
    palette["General"]["ColorScheme"] = scheme
    with (config / "kdeglobals").open("w") as handle:
        palette.write(handle, space_around_delimiters=False)


def write_blur_policy(config: Path, policy: str) -> None:
    """State the blur policy the way KWin states it, inside the fixture.

    `unset` writes no kwinrc at all, which is the third real case: no layer has
    an opinion and Tokens falls back to the readable opaque material.
    """
    if policy == "unset":
        return
    (config / "kwinrc").write_text(
        f"[Plugins]\nblurEnabled={'true' if policy == 'on' else 'false'}\n",
        encoding="utf-8")


def discard(fixture: Path) -> None:
    """Remove the fixture without letting its removal fail a good capture."""
    shutil.rmtree(fixture, ignore_errors=True)
    if fixture.exists():
        print(f"note: fixture {fixture} could not be removed completely", file=sys.stderr)


def main() -> int:
    if Path('/.flatpak-info').exists():
        os.execvp('flatpak-spawn', ['flatpak-spawn', '--host', 'python3',
                                    str(Path(__file__).resolve()), *sys.argv[1:]])
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--scheme', default='MoOSUI2AuroraLight')
    parser.add_argument('--language', choices=('ar', 'en'), default='ar')
    parser.add_argument('--blur', choices=('on', 'off', 'unset'), default='on',
                        help='the blur policy written into the fixture kwinrc; '
                             '"on" renders the frosted material, "off" and "unset" '
                             'render the opaque fallback (default: on)')
    parser.add_argument('--width', type=int, default=1440)
    parser.add_argument('--height', type=int, default=960)
    parser.add_argument('--scale', type=float, default=1)
    parser.add_argument('--capture', type=Path)
    args = parser.parse_args()
    schemes = ROOT / 'system_files/usr/share/color-schemes'
    if args.scheme not in {p.stem for p in schemes.glob('*.colors')}:
        parser.error('choose a shipped MoOS colour scheme')
    if not (720 <= args.width <= 3840 and 480 <= args.height <= 2160 and 1 <= args.scale <= 3):
        parser.error('viewport must be 720–3840 × 480–2160; scale must be 1–3')
    # Validate what this run will WRITE before asking whether it can run at all,
    # so a bad destination is reported on any machine rather than only on MoOS.
    output = log_path = None
    if args.capture:
        output = args.capture.resolve()
        if output.suffix.lower() != '.png':
            parser.error('capture output must be a PNG file')
        # A review tool builds review artefacts, inside the repository it reviews.
        if not output.is_relative_to(ROOT):
            parser.error(f'capture must land inside {ROOT} (try test-results/…)')
        # The log carries the PNG's FULL name, so it can only ever replace the
        # log of this same capture. The old `.log` sibling silently overwrote an
        # unrelated file that happened to share the stem.
        log_path = output.with_name(output.name + '.log')
        if log_path.exists() and not log_path.is_file():
            parser.error(f'{log_path} exists and is not a regular file')

    runtime = shutil.which('moos-qml-shell')
    if not runtime:
        parser.error('run on MoOS or a configured native review environment')

    fixture = Path(tempfile.mkdtemp(prefix='moos-design-studio-'))
    try:
        config = fixture / 'config'
        config.mkdir()
        write_palette(config, args.scheme)
        write_blur_policy(config, args.blur)
        # Never inherit a live settings or session bus into a fixture, and never
        # hand the fixture a WORKING bus either: a private `dbus-run-session`
        # activates the desktop portals, which outlive the bus and the fixture.
        # An address that resolves to nothing is the one arrangement in which
        # Qt starts nothing, leaks nothing, and renders identically.
        env = {k: v for k, v in os.environ.items()
               if k not in ('DBUS_SESSION_BUS_ADDRESS', 'SESSION_MANAGER', 'QT_STYLE_OVERRIDE')}
        env.update(HOME=str(fixture), XDG_CONFIG_HOME=str(config),
                   XDG_CONFIG_DIRS=str(config), XDG_DATA_HOME=str(fixture / 'data'),
                   XDG_CACHE_HOME=str(fixture / 'cache'),
                   DBUS_SESSION_BUS_ADDRESS=f'unix:path={fixture}/absent-session-bus',
                   QML_IMPORT_PATH=str(ROOT / 'system_files/usr/lib64/qt6/qml'),
                   QML2_IMPORT_PATH=str(ROOT / 'system_files/usr/lib64/qt6/qml'),
                   QML_DISABLE_DISK_CACHE='1', QT_FORCE_STDERR_LOGGING='1',
                   QT_LOGGING_RULES='qml=true', QT_QPA_PLATFORMTHEME='kde',
                   QT_QUICK_CONTROLS_STYLE='org.kde.desktop',
                   XDG_CURRENT_DESKTOP='KDE', KDE_SESSION_VERSION='6',
                   QT_SCALE_FACTOR=str(args.scale), GTK_USE_PORTAL='0',
                   LANG='ar_EG.UTF-8' if args.language == 'ar' else 'en_US.UTF-8')
        command = [runtime, '--app-id', 'org.moos.designstudio', '--icon', 'moos-logo', '--qml',
                   str(ROOT / 'artwork/moos-ui2/DesignStudio.qml'), '--',
                   f'--language={args.language}', f'--width={args.width}', f'--height={args.height}']
        if output is None:
            return subprocess.run(command, env=env).returncode

        output.parent.mkdir(parents=True, exist_ok=True)
        previous_stamp = output.stat().st_mtime_ns if output.exists() else None
        env.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        runtime_dir = fixture / 'run'
        runtime_dir.mkdir(mode=0o700)
        env['XDG_RUNTIME_DIR'] = str(runtime_dir)
        env.pop('DISPLAY', None)
        env.pop('WAYLAND_DISPLAY', None)
        command.append(f'--capture={output}')
        # Diagnostics go to a file rather than a pipe: a pipe can outlive the Qt
        # process in any child that inherited it, and waiting for its EOF has
        # hung this tool before.
        with log_path.open('w') as log_file:
            try:
                result = subprocess.run(command, env=env, stdout=log_file,
                                        stderr=subprocess.STDOUT, timeout=120)
            except subprocess.TimeoutExpired:
                print(f'Capture timed out; inspect {log_path}', file=sys.stderr)
                return 1
        log = log_path.read_text(errors='replace')
        errors = [line for line in QML_FAILURE.findall(log) if not QML_BENIGN.search(line)]
        if result.returncode or errors:
            print('\n'.join(errors) or log, file=sys.stderr)
            print(f'Capture failed (exit {result.returncode}); runtime log: {log_path}',
                  file=sys.stderr)
            return 1
        if not output.exists() or output.stat().st_mtime_ns == previous_stamp:
            print(f'No new PNG was written; runtime log: {log_path}', file=sys.stderr)
            return 1
        if 'DESIGN_STUDIO_READY true' not in log:
            print(f'The window never reported itself ready; runtime log: {log_path}',
                  file=sys.stderr)
            return 1
        report = survey(output)
        problems = complaints(report)
        if problems:
            print(f'{output} is not a plausible render:', file=sys.stderr)
            for problem in problems:
                print(f'  - {problem}', file=sys.stderr)
            print(f'runtime log: {log_path}', file=sys.stderr)
            return 1
        print(f'Rendered {output} — {report["width"]}×{report["height"]}, '
              f'{report["distinct"]} sampled colours, luminance spread '
              f'{report["deviation"]:.1f}, blur policy {args.blur}')
        print(f'runtime log: {log_path}')
        return 0
    finally:
        discard(fixture)


if __name__ == '__main__':
    sys.exit(main())
