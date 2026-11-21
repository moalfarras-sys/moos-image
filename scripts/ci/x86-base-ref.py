"""Print the x86 base shared by the Containerfile and kernel input review."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def reviewed_base(containerfile, manifest):
    digest = manifest["vendor_base_manifest_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid reviewed x86 base digest")
    reference = "ghcr.io/ublue-os/kinoite-main@sha256:" + digest
    lines = (line.split() for line in containerfile.splitlines())
    first = next((words for words in lines if words and words[0].upper() == "FROM"), None)
    if first != ["FROM", reference, "AS", "base"]:
        raise ValueError("first Containerfile stage differs from the reviewed x86 base")
    return reference


if __name__ == "__main__":
    print(reviewed_base((ROOT / "Containerfile").read_text(),
                        json.loads((ROOT / "build_files/smocf05/manifest.json").read_text())))
