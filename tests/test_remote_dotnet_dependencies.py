#!/usr/bin/env python3
"""Hold Mo Remote's buildable/licensed .NET dependency contract."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "moremote/agent-linux/MoRemoteLinux.csproj"


def main() -> None:
    source = PROJECT.read_text(encoding="utf-8")
    match = re.search(
        r'PackageReference Include="SixLabors\.ImageSharp" Version="([^"]+)"',
        source,
    )
    if match is None:
        raise SystemExit("MoRemoteLinux lost its explicit ImageSharp version")
    major = int(match.group(1).split(".", 1)[0])
    if major >= 4:
        raise SystemExit(
            "ImageSharp 4+ requires a separate build license; the self-contained "
            "Mo Remote stage will fail until MoOS intentionally acquires/configures it"
        )
    if "commercial license" not in source:
        raise SystemExit("the ImageSharp major-version licensing pin is undocumented")
    print(f"remote .NET dependency gate passed (ImageSharp {match.group(1)})")


if __name__ == "__main__":
    main()
