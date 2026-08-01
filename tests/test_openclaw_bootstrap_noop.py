#!/usr/bin/env python3
"""Gate: moai-openclaw-bootstrap must not rewrite+revalidate an unchanged config.

WHY THIS EXISTS

moai-openclaw-bootstrap is moai-agent-api's ExecStartPre — it runs at every login. Its
main() called atomic_save(merge_baseline(load_existing())) unconditionally. merge_baseline
only fills MISSING fields, so on an already-configured machine the merge is a no-op — yet
atomic_save always wrote a temp file, ran `openclaw config validate` (a full Node cold
start measured at ~1.7s / ~428 MB RSS), fsynced twice and renamed ~/.openclaw/openclaw.json.
So every login spent ~1.7s and a transient ~428 MB process, and churned the config mtime,
for zero net change — delaying the Agent API's readiness.

The fix short-circuits when the merged config equals what is on disk, while still healing a
drifted config (merged != before). This drives the REAL main() with atomic_save and the Node
validate stubbed out, and asserts: a no-op config skips the save, a drifted config still saves.
"""

import copy
import importlib.util
import sys
import types
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moai-openclaw-bootstrap"


def load_module():
    loader = SourceFileLoader("_openclaw_bootstrap_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing.")
        return 1

    module = load_module()
    errors: list[str] = []
    full = module.merge_baseline({})           # the complete baseline
    saves: list[dict] = []

    with mock.patch.object(module, "atomic_save", lambda cfg: saves.append(cfg)), \
         mock.patch.object(module, "harden_config_permissions", lambda: None), \
         mock.patch.object(module, "retire_legacy_gateway_unit", lambda: False), \
         mock.patch.object(module, "ensure_podman_docker_shim", lambda: None), \
         mock.patch.object(module, "OPENCLAW", types.SimpleNamespace(is_file=lambda: True)), \
         mock.patch.object(module, "CONFIG", types.SimpleNamespace(is_file=lambda: True)), \
         mock.patch("os.access", lambda *a, **k: True):

        # An already-configured machine: the merge changes nothing -> NO save.
        saves.clear()
        with mock.patch.object(module, "load_existing", lambda: copy.deepcopy(full)):
            sys.argv = ["moai-openclaw-bootstrap"]
            module.main()
        if saves:
            errors.append("an unchanged config still triggered atomic_save — the ~1.7s/428 MB Node "
                          "validate+rewrite runs on every login for no change.")

        # A drifted config (a field went missing): healing MUST still write.
        partial = copy.deepcopy(full)
        partial.pop(next(iter(partial)))
        saves.clear()
        with mock.patch.object(module, "load_existing", lambda: copy.deepcopy(partial)):
            sys.argv = ["moai-openclaw-bootstrap"]
            module.main()
        if not saves:
            errors.append("a drifted config was NOT re-saved — the short-circuit is too broad and "
                          "self-healing is lost.")

    if errors:
        print("GATE FAIL: openclaw-bootstrap's per-login save is wrong.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: an unchanged config skips the save; a drifted config still heals.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
