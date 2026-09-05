#!/usr/bin/env python3
"""Relationship gate for Mo PC Remote's reconnect lifecycle."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "moremote/controller/src/lib/ws.ts"


def method(source: str, name: str, next_name: str) -> str:
    match = re.search(
        rf"\n  {re.escape(name)}\([^\n]*\).*?(?=\n  {re.escape(next_name)}\()",
        source,
        re.S,
    )
    if match is None:
        raise AssertionError(f"cannot locate {name}()")
    return match.group(0)


def main() -> None:
    source = WS.read_text(encoding="utf-8")
    connect = method(source, "connect", "disconnect")
    disconnect = method(source, "disconnect", "setInputMode")
    failures: list[str] = []
    for token in (
        "private reconnectTimer: number | null = null",
        "this.stopReconnect();",
        "nextGeneration === this.generation && !this.closedByUs",
        "window.clearTimeout(this.reconnectTimer)",
    ):
        if token not in source:
            failures.append(f"missing reconnect lifecycle contract: {token}")
    if "this.stopReconnect();" not in connect:
        failures.append("connect() does not retire an older pending reconnect")
    if "this.stopReconnect();" not in disconnect:
        failures.append("disconnect() leaves a reconnect timer alive after logout/unmount")
    if re.search(r"(?<!window\.)setTimeout\(\(\) => this\.connect\(\)", source):
        failures.append("an unowned reconnect timeout can resurrect a closed screen")
    if failures:
        raise SystemExit("remote connection lifecycle gate failed:\n - " +
                         "\n - ".join(failures))
    print("remote connection lifecycle gate passed")


if __name__ == "__main__":
    main()
