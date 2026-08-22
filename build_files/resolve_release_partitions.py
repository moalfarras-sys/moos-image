#!/usr/bin/env python3
"""Resolve the three release filesystems from lsblk JSON without assuming GPT order."""

from __future__ import annotations

import argparse
import json
import re
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nbd", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"/dev/nbd[0-9]+", args.nbd):
        parser.error("unexpected NBD path")

    data = json.load(sys.stdin)
    partitions: list[dict[str, object]] = []

    def visit(nodes: list[dict[str, object]]) -> None:
        for node in nodes:
            if node.get("type") == "part":
                partitions.append(node)
            children = node.get("children")
            if isinstance(children, list):
                visit(children)

    visit(data.get("blockdevices", []))
    expected_path = re.compile(re.escape(args.nbd) + r"p[0-9]+")
    roles = {"vfat": "EFI", "ext4": "boot", "btrfs": "root"}
    resolved: dict[str, str] = {}
    for filesystem, role in roles.items():
        matches = [
            str(part.get("name", ""))
            for part in partitions
            if str(part.get("fstype", "")).lower() == filesystem
            and expected_path.fullmatch(str(part.get("name", "")))
        ]
        if len(matches) != 1:
            layout = ", ".join(
                f"{part.get('name', '?')}:{part.get('fstype') or 'unformatted'}"
                for part in partitions
            )
            print(
                f"MOOS DISK FATAL: expected exactly one {role} ({filesystem}) "
                f"partition on {args.nbd}; found {len(matches)}; layout: {layout}",
                file=sys.stderr,
            )
            return 1
        resolved[filesystem] = matches[0]

    print(resolved["vfat"])
    print(resolved["ext4"])
    print(resolved["btrfs"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
