#!/usr/bin/env python3
"""Gate Mo Remote's explicit, absolute isolated config boundary."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATHS = ROOT / "moremote/agent/Core/Logging.cs"
PROGRAM = ROOT / "moremote/agent-linux/Program.cs"


def main() -> None:
    source = PATHS.read_text(encoding="utf-8")
    required = (
        'GetEnvironmentVariable("MOREMOTE_DATA_DIR")',
        "Path.IsPathFullyQualified(explicitDir)",
        "return Path.GetFullPath(explicitDir)",
        "MOREMOTE_DATA_DIR must be an absolute path",
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise SystemExit("remote data-dir gate failed; missing: " + ", ".join(missing))
    program = PROGRAM.read_text(encoding="utf-8")
    for token in (
        'GetEnvironmentVariable("MOREMOTE_DATA_DIR")',
        "SHA256.HashData",
        'mutexName += "_" + digest',
    ):
        if token not in program:
            raise SystemExit(f"isolated data directory does not isolate mutex: {token}")
    print("remote isolated data-dir gate passed")


if __name__ == "__main__":
    main()
