#!/usr/bin/env python3
"""Gate: the file-indexing budget has exactly one consumer, and no second authority.

WHY THIS EXISTS

`moos-visual-tier` is the single authority on what this machine can afford. Its
`budget()` block publishes `file_indexing` as "content" or "filenames", and its
docstring is explicit that the value is ADVISORY -- the tool deliberately does
not write baloofilerc, because that file has its own owner.

For as long as the budget existed, nothing consumed it. Measured on the live
Oracle A1 on 2026-09-07, on a signed image, tier `essential`:

    budget.file_indexing   filenames
    baloofilerc            only basic indexing=false   <- full content extraction
    baloo_file RSS         439.3 MiB                   <- largest MoOS process
    index database         2.8 GB for 12,460 files

After wiring the consumer, on the same machine, same boot:

    baloo_file RSS         36.1 MiB    (-92%)
    index database         108 MB      (-2.7 GB)
    files indexed          12,468      (filename search intact)

THE FAILURE MODE THIS GUARDS

The obvious "fix" for a slow indexer is to add a core count or a memory
threshold to whichever script is in front of you. Do that and the machine has
two performance authorities that will disagree the moment either is edited --
which is precisely what `moos-visual-tier` centralises to prevent. So this gate
asserts the consumer reads the budget and owns no thresholds of its own, and
that it can never turn indexing off (the filename index is what the Launcher's
file results and the Places page's search promise depend on; content EXTRACTION
is the cost, and that is all that is allowed to stop).
"""
from __future__ import annotations

import re
import os
import json
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / "system_files/usr/libexec/moos-index-policy"
UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-index-policy.service"
AUTHORITY = ROOT / "system_files/usr/bin/moos-visual-tier"


def check_effective_config(source: str) -> list[str]:
    """Read the setting as Baloo does, including stale wrong-section keys."""
    errors = []
    consumer = types.ModuleType("index_policy_test")
    exec(compile(source, str(CONSUMER), "exec"), consumer.__dict__)
    with tempfile.TemporaryDirectory(prefix="moos-index-policy-") as directory:
        base = Path(directory)
        config = base / "baloofilerc"
        env = {"HOME": directory, "XDG_CONFIG_HOME": directory,
               "XDG_CONFIG_DIRS": str(base / "defaults"), "LC_ALL": "C"}
        with patch.dict(os.environ, env):
            config.write_text("[Basic Settings]\nonly basic indexing=true\n"
                              "[General]\nonly basic indexing=false\n")
            with patch.object(consumer.shutil, "which", return_value=None):
                if consumer.current_value() != "false":
                    errors.append("fallback trusts an ignored Basic Settings key")
                config.write_text("[Basic Settings]\nonly basic indexing=true\n")
                if consumer.current_value() is not None:
                    errors.append("fallback invents a General value from another group")

            # No daemon is started: kwriteconfig writes only the isolated file,
            # and balooctl's config-list command reads it through Baloo itself.
            if all(shutil.which(tool) for tool in ("kwriteconfig6", "kreadconfig6", "balooctl6")):
                config.write_text("[Basic Settings]\nonly basic indexing=true\n"
                                  "[General]\nonly basic indexing=false\n")
                for value, expected in (("true", "no"), ("false", "yes")):
                    if not consumer.write_value(value):
                        errors.append("consumer could not write isolated config")
                        continue
                    result = subprocess.run(
                        ["balooctl6", "config", "list", "contentIndexing"],
                        text=True, capture_output=True, timeout=10, check=True)
                    if result.stdout.strip() != expected:
                        errors.append(f"Baloo ignored consumer value {value}: {result.stdout.strip()!r}")
                    if consumer.current_value() != value:
                        errors.append("consumer readback disagrees with its effective setting")
            else:
                print("SKIP real Baloo readback: requires kwriteconfig6, kreadconfig6, balooctl6")
    return errors


def check_diagnostics() -> list[str]:
    errors = []
    for path in (ROOT / "system_files/usr/bin/moos-selfcheck", ROOT / "tests/post-update-check.sh"):
        source = path.read_text()
        match = re.search(r"# BEGIN INDEXING BUDGET CHECK\n(.*?)# END INDEXING BUDGET CHECK", source, re.S)
        if not match:
            errors.append(f"{path.name}: missing effective indexing-budget check")
            continue
        for budget, content, valid in (("filenames", "no", True), ("content", "yes", True),
                                       ("filenames", "yes", False), ("content", "no", False),
                                       ("unknown", "no", False), ("filenames", "", False)):
            env = os.environ | {"TEST_BUDGET": json.dumps({"budget": {"file_indexing": budget}}),
                                "TEST_CONTENT": content}
            script = '''
ok() { echo PASS; }
bad() { echo FAIL; }
moos-visual-tier() { printf '%s\\n' "$TEST_BUDGET"; }
balooctl6() { printf '%s\\n' "$TEST_CONTENT"; }
''' + match[1]
            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True,
                                    text=True, timeout=10, check=True)
            if result.stdout.strip() != ("PASS" if valid else "FAIL"):
                errors.append(f"{path.name}: incorrect result for budget={budget}, content={content!r}")
    return errors


def main() -> int:
    errors: list[str] = []

    if not CONSUMER.is_file():
        print("INDEX POLICY GATE FAIL: the consumer is missing entirely; the "
              "published file_indexing budget would go unread again.")
        return 1
    source = CONSUMER.read_text(encoding="utf-8")
    errors.extend(check_effective_config(source))
    errors.extend(check_diagnostics())

    # It must ask the authority, by running it -- not re-derive the answer.
    if "moos-visual-tier" not in source:
        errors.append("the consumer does not read moos-visual-tier; a budget it "
                      "does not ask for is a second authority")
    if '["budget"]["file_indexing"]' not in source:
        errors.append("the consumer does not read budget.file_indexing specifically")

    # No thresholds of its own. These are the exact facts moos-visual-tier owns;
    # seeing one here means the two will drift.
    for token in ("cores", "memory_gib", "gpu_class", "FLAGSHIP", "nproc"):
        if re.search(rf"\b{re.escape(token)}\b", source):
            errors.append(
                f"the consumer references {token!r} -- it must apply the budget, "
                f"not re-derive it. Put new reasoning in moos-visual-tier.budget().")

    # It may never disable indexing.
    if re.search(r"Indexing-Enabled", source):
        errors.append("the consumer touches Indexing-Enabled; it may only change "
                      "'only basic indexing'. Disabling the index deletes the "
                      "Launcher's file search from the machines that need it most.")

    # Fail closed: an unreachable authority must leave Baloo alone.
    if "leaving Baloo untouched" not in source:
        errors.append("the consumer must do nothing when the budget cannot be "
                      "read, rather than guess a policy")

    if not UNIT.is_file():
        errors.append("moos-index-policy.service is missing; the consumer would "
                      "never run")
    else:
        unit = UNIT.read_text(encoding="utf-8")
        if "graphical-session.target" not in unit:
            errors.append("the unit is not bound to the graphical session")
        # A rebuild must never compete with the desktop it is meant to help.
        if "IOSchedulingClass=idle" not in unit:
            errors.append("the unit must rebuild the index at idle IO priority")

    # The authority must still be the one publishing the value.
    if AUTHORITY.is_file():
        auth = AUTHORITY.read_text(encoding="utf-8")
        if '"file_indexing"' not in auth:
            errors.append("moos-visual-tier no longer publishes file_indexing; "
                          "the consumer would silently stop applying anything")
        # ai_default advertised a local route that stage C2b removed. It must
        # stay constant until a local engine actually exists again.
        if re.search(r'"ai_default":\s*\(', auth):
            errors.append(
                'budget.ai_default branches on hardware again. Mo AI is '
                'cloud-only (tests/test_moai_cloud_only.py: "the one door to a '
                'local engine is closed"), so a hardware branch here advertises '
                'a route the OS does not have.')

    if errors:
        print("INDEX POLICY GATE FAIL:\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("index policy gate passed (one authority, one consumer, fails closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
