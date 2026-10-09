#!/usr/bin/env python3
"""Hold Remote's reviewed, licence-compatible managed/native codec contract."""

from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "moremote/agent-linux/MoRemoteLinux.csproj"
REVIEWED = "4.153.1"


def validate(source):
    references = {item.attrib["Include"]: item.attrib.get("Version", "")
                  for item in ET.fromstring(source).iter("PackageReference")}
    if "SixLabors.ImageSharp" in references:
        raise ValueError("ImageSharp is not the reviewed fallback codec")
    for name in ("SkiaSharp", "SkiaSharp.NativeAssets.Linux.NoDependencies"):
        if references.get(name) != REVIEWED:
            raise ValueError(f"{name} must match the reviewed MIT/native version {REVIEWED}")


def main() -> None:
    validate(PROJECT.read_text(encoding="utf-8"))
    validate((ROOT / "moremote/tests/MoRemote.Linux.Input.Tests/MoRemote.Linux.Input.Tests.csproj").read_text())
    # Prove refusal of the vulnerable package, absent native asset and ABI drift.
    for bad in (
        '<Project><PackageReference Include="SixLabors.ImageSharp" Version="3.1.11" /></Project>',
        '<Project><PackageReference Include="SkiaSharp" Version="4.153.1" /></Project>',
        '<Project><PackageReference Include="SkiaSharp" Version="4.153.1" />'
        '<PackageReference Include="SkiaSharp.NativeAssets.Linux.NoDependencies" Version="4.152.3" /></Project>',
    ):
        try:
            validate(bad)
        except ValueError:
            continue
        raise SystemExit("dependency gate accepted an unsupported or mismatched codec")
    print(f"remote dependency gate passed (MIT SkiaSharp {REVIEWED}; negative controls rejected)")


if __name__ == "__main__":
    main()
