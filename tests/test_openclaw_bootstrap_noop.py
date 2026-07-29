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
import json
import os
import tempfile
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

    # Real paths throughout: the script chmods its config, so a stub object is not a faithful
    # stand-in — and pretending otherwise is how a test stops testing the thing that ships.
    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp) / "openclaw"
        base_dir.mkdir()
        base_file = base_dir / "openclaw.json"
        base_file.write_text(json.dumps(full), encoding="utf-8")

        with mock.patch.object(module, "atomic_save", lambda cfg: saves.append(cfg)), \
             mock.patch.object(module, "ensure_podman_docker_shim", lambda: None), \
             mock.patch.object(module, "OPENCLAW", types.SimpleNamespace(is_file=lambda: True)), \
             mock.patch.object(module, "CONFIG_DIR", base_dir), \
             mock.patch.object(module, "CONFIG", base_file), \
             mock.patch("os.access", lambda *a, **k: True):

            # An already-configured machine: the merge changes nothing -> NO save.
            saves.clear()
            with mock.patch.object(module, "load_existing", lambda: copy.deepcopy(full)):
                sys.argv = ["moai-openclaw-bootstrap"]
                module.main()
            if saves:
                errors.append("an unchanged config still triggered atomic_save — the ~1.7s/428 MB "
                              "Node validate+rewrite runs on every login for no change.")

            # A drifted config (a field went missing): healing MUST still write.
            partial = copy.deepcopy(full)
            partial.pop(next(iter(partial)))
            saves.clear()
            with mock.patch.object(module, "load_existing", lambda: copy.deepcopy(partial)):
                sys.argv = ["moai-openclaw-bootstrap"]
                module.main()
            if not saves:
                errors.append("a drifted config was NOT re-saved — the short-circuit is too broad "
                              "and self-healing is lost.")

    # AND THE PRIVATE MODE MUST STILL BE RE-ASSERTED ON THE SKIP PATH.
    #
    # openclaw.json holds the Telegram bot token; its directory is 0700 and the file 0600. That
    # tightening used to happen only as a side effect of atomic_save, so skipping the save for an
    # unchanged config silently dropped a self-healing security property: a home restored from
    # backup or a stray `chmod -R` would leave the token readable with nothing to put it back.
    # Drive the real main() against loosened permissions and require them tightened anyway.
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp) / "openclaw"
        config_dir.mkdir()
        config_file = config_dir / "openclaw.json"
        config_file.write_text(json.dumps(full), encoding="utf-8")
        os.chmod(config_dir, 0o755)      # as a backup restore or chmod -R would leave them
        os.chmod(config_file, 0o644)
        saves.clear()
        with mock.patch.object(module, "CONFIG_DIR", config_dir), \
             mock.patch.object(module, "CONFIG", config_file), \
             mock.patch.object(module, "atomic_save", lambda cfg: saves.append(cfg)), \
             mock.patch.object(module, "ensure_podman_docker_shim", lambda: None), \
             mock.patch.object(module, "OPENCLAW", types.SimpleNamespace(is_file=lambda: True)), \
             mock.patch.object(module, "load_existing", lambda: copy.deepcopy(full)), \
             mock.patch("os.access", lambda *a, **k: True):
            sys.argv = ["moai-openclaw-bootstrap"]
            module.main()
        if saves:
            errors.append("the unchanged-config path ran the expensive save after all")
        dir_mode = config_dir.stat().st_mode & 0o777
        file_mode = config_file.stat().st_mode & 0o777
        if dir_mode != 0o700:
            errors.append(f"the config DIRECTORY was left {oct(dir_mode)} on the skip path — the "
                          f"token-bearing directory must be re-tightened to 0700 every login")
        if file_mode != 0o600:
            errors.append(f"openclaw.json was left {oct(file_mode)} on the skip path — the file "
                          f"holds the Telegram bot token and must be re-tightened to 0600")

    if errors:
        print("GATE FAIL: openclaw-bootstrap's per-login save is wrong.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: an unchanged config skips the save; a drifted config still heals.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
