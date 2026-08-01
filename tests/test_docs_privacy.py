#!/usr/bin/env python3
"""Keep operator identifiers and unsafe live channel policy out of docs."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
E164 = re.compile(r"(?<!\d)\+[1-9]\d{9,14}(?!\d)")
UNSAFE_CHANNEL = re.compile(
    r'"allowFrom"\s*:\s*\[\s*"\*"\s*\]', re.IGNORECASE
)


def main() -> None:
    failures: list[str] = []
    documents = [ROOT / "AGENTS.md", ROOT / "PROJECT_STATE.md",
                 ROOT / "MOOS_ROADMAP.md", ROOT / "README.md"]
    documents.extend(sorted((ROOT / "docs").rglob("*.md")))
    for path in documents:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if E164.search(text):
            failures.append(f"{path.relative_to(ROOT)} contains an E.164 phone number")
        if UNSAFE_CHANNEL.search(text):
            failures.append(
                f"{path.relative_to(ROOT)} documents a live allow-all phone policy"
            )
    if failures:
        raise SystemExit("documentation privacy gate failed:\n - " + "\n - ".join(failures))
    print(f"documentation privacy gate passed ({len(documents)} files)")


if __name__ == "__main__":
    main()
