#!/usr/bin/env python3
"""Rewrite shim's visible fallback boot label to the MoOS product identity."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


LEGACY_LABEL = "".join(map(chr, (70, 101, 100, 111, 114, 97)))
SEARCH_ROOTS = ("usr/share", "usr/lib/efi", "usr/lib/bootupd")


def encoding_for(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    if b"\x00" in raw[:128]:
        return "utf-16-le"
    return "utf-8-sig"


def rewrite(root: Path) -> list[Path]:
    paths = sorted(
        {
            path
            for relative in SEARCH_ROOTS
            if (base := root / relative).exists()
            for path in base.rglob("BOOT*.CSV")
        }
    )
    if not paths:
        raise SystemExit("GATE FAIL: shim fallback BOOT*.CSV was not found")

    for path in paths:
        raw = path.read_bytes()
        encoding = encoding_for(raw)
        text = raw.decode(encoding)
        updated = re.sub(re.escape(LEGACY_LABEL), "MoOS", text, flags=re.IGNORECASE)
        path.write_bytes(updated.encode(encoding))
        check = path.read_bytes().decode(encoding)
        if LEGACY_LABEL.casefold() in check.casefold():
            raise SystemExit(f"GATE FAIL: foreign firmware label survived in {path}")
        print(f"MoOS firmware fallback label: {path}")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/"))
    args = parser.parse_args()
    rewrite(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
