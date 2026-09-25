#!/usr/bin/env python3
"""Execute the settings modules' status contract on real and on broken documents.

    check_status_contract.py <moos-settings-contract-check> <moos-settings-status> <moosbackend.cpp>

The image builds run this in the kcm-contract stage of both Containerfiles, before the
modules are copied into the image. It runs the real status helper in a private runtime
directory, and the C++ contract (MoOSSettingsModule::acceptStatus, compiled into
moos-settings-contract-check from the same source as every module) must:

  * ACCEPT the document the helper really publishes — the helper and the pages agree;
  * REFUSE, with the reason the pages show, every broken copy: stale or future-dated,
    another schema or product, a group or field missing or of the wrong type, a label
    without one of its languages, a destination that is not a flag — and each field of
    the backend's StatusShape table deleted in turn, read from the C++ source itself so
    a field added there is checked here the day it is added.

A mismatch prints every failed case and exits 1, which fails the image build.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


def status_shape(source: str) -> list[tuple[str | None, str]]:
    table = source.split("constexpr Field StatusShape[] = {", 1)[1].split("};", 1)[0]
    fields = [(None if group == "nullptr" else group.strip('"'), key) for group, key in
              re.findall(r'\{(nullptr|"[a-zA-Z]+"), "([a-zA-Z]+)", QJsonValue::\w+\}', table)]
    if len(fields) < 20:
        raise SystemExit(f"FATAL: read only {len(fields)} StatusShape fields from the backend source")
    return fields


def bilingual_labels(source: str) -> list[str]:
    return re.findall(r'"([a-zA-Z]+)"', source.split("BilingualLabels[] = {", 1)[1].split("};", 1)[0])


def publish(helper: str, home: Path) -> dict[str, Any]:
    runtime = home / "runtime"
    runtime.mkdir(mode=0o700)
    env = {key: value for key, value in os.environ.items()
           if key not in {"DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY"}}
    env.update(HOME=str(home), XDG_RUNTIME_DIR=str(runtime), XDG_CONFIG_HOME=str(home / "config"),
               XDG_STATE_HOME=str(home / "state"), XDG_CACHE_HOME=str(home / "cache"))
    subprocess.run([helper], env=env, check=True, timeout=120)
    return json.loads((runtime / "moos-settings/status.json").read_text(encoding="utf-8"))


def verdict(checker: str, document: Any, directory: Path) -> str:
    path = directory / "case.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = subprocess.run([checker, str(path)], capture_output=True, text=True, timeout=30)
    said = result.stdout.strip()
    if (result.returncode == 0) != (said == "accepted"):
        return f"exit {result.returncode} with '{said}'"
    return said


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__.split("\n\n", 2)[1], file=sys.stderr)
        return 2
    checker, helper, backend = sys.argv[1:]
    source = Path(backend).read_text(encoding="utf-8")
    cases: list[tuple[str, Any, str]] = []

    with tempfile.TemporaryDirectory(prefix="moos-status-contract-") as tmp:
        home = Path(tmp)
        real = publish(helper, home)
        cases.append(("the helper's own document", real, "accepted"))

        def broken(label: str, change: Callable[[dict[str, Any]], None], expected: str = "invalid") -> None:
            document = copy.deepcopy(real)
            change(document)
            cases.append((label, document, expected))

        # A helper that stopped publishing something must fail as a refused document,
        # not as a KeyError here: missing levels are created, missing keys are no-ops.
        def set_path(*path: str, value: Any) -> Callable[[dict[str, Any]], None]:
            def change(document: dict[str, Any]) -> None:
                target = document
                for key in path[:-1]:
                    target = target.setdefault(key, {}) if isinstance(target, dict) else {}
                if isinstance(target, dict):
                    target[path[-1]] = value
            return change

        def drop(*path: str) -> Callable[[dict[str, Any]], None]:
            def change(document: dict[str, Any]) -> None:
                target: Any = document
                for key in path[:-1]:
                    target = target.get(key) if isinstance(target, dict) else None
                if isinstance(target, dict):
                    target.pop(path[-1], None)
            return change

        generated = real.get("generatedAt") if isinstance(real.get("generatedAt"), int) else 0
        broken("generated 100 s ago", set_path("generatedAt", value=generated - 100), "stale")
        broken("generated 60 s in the future", set_path("generatedAt", value=generated + 60), "stale")
        broken("generatedAt as text", set_path("generatedAt", value=str(generated)))
        broken("schema 2", set_path("schema", value=2))
        broken("schema as text", set_path("schema", value="1"))
        broken("another product", set_path("product", value="X"))
        broken("no apps group", drop("apps"))
        broken("apps as a list", set_path("apps", value=[]))
        broken("remote.fast as text", set_path("remote", "fast", value="yes"))
        broken("whatsNew.entries not a list", set_path("whatsNew", "entries", value={}))
        broken("deployment.version a number", set_path("deployment", "version", value=44))
        broken("a destination that is not a flag",
               lambda document: document.setdefault("destinations", {}).update(display="yes"))
        broken("destinations as a list", set_path("destinations", value=[]))
        for label in bilingual_labels(source):
            broken(f"{label} without Arabic", drop(label, "ar"))
            broken(f"{label} as plain text", set_path(label, value="MoOS"))
        for group, key in status_shape(source):
            broken(f"{group + '.' if group else ''}{key} missing",
                   drop(group, key) if group else drop(key))
        cases.append(("a list instead of a document", [real], "invalid"))

        failures = []
        for label, document, expected in cases:
            said = verdict(checker, document, home)
            if said != expected:
                failures.append(f"  {label}: expected '{expected}', the contract said '{said}'")

    if failures:
        print("FATAL: the MoOS settings status contract does not behave as the pages rely on:")
        print("\n".join(failures))
        return 1
    print(f"MoOS settings status contract: the helper's document accepted, "
          f"{len(cases) - 1} broken copies refused with the right reason")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
