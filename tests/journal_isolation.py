"""Keep repository tests out of the owner's journal.

WHY THIS EXISTS
moai-do, moos-image-update, moai-control and moos-control write an audit line with
`logger` for everything they do. That journal is product data: `journalctl -t moai-do`
is "everything the assistant has done", and `journalctl -t moos-update` is the update
history the owner reads when something went wrong. On 2026-09-24 one `just check` on the
station wrote 36 fabricated moai-do records (among them "action=update verdict=ok" three
times) and 22 moos-update records with invented digests between 22:00:23 and 22:00:40.
Journal lines cannot be removed one by one, so those stay.

Importing this module and calling `install()` puts a recording `logger` first on this
process's PATH. Everything the test runs in-process (a tool loaded with runpy or a
SourceFileLoader) and every child that inherits or extends PATH then records into a file
the test owns instead of the journal. A child given a hand-written PATH must include
`STUB_DIR` itself; tests/test_tests_stay_out_of_the_journal.py runs every suite that names
an auditing tool with the real logger replaced by a trap, and fails when one is reached.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_STATE: dict[str, Path] = {}


def install() -> Path:
    """Put the recording logger first on PATH (once per process); return its folder."""
    if "dir" not in _STATE:
        folder = Path(tempfile.mkdtemp(prefix="moos-test-logger-"))
        log = folder / "logger.log"
        stub = folder / "logger"
        # One write per call, so concurrent jobs cannot interleave half lines.
        stub.write_text("#!/bin/sh\n"
                        'line="logger"\n'
                        'for arg in "$@"; do line="$line $arg"; done\n'
                        f'printf \'%s\\n\' "$line" >> "{log}"\n', encoding="utf-8")
        stub.chmod(0o755)
        atexit.register(shutil.rmtree, folder, True)
        _STATE["dir"], _STATE["log"] = folder, log
    folder = _STATE["dir"]
    entries = os.environ.get("PATH", "").split(os.pathsep)
    if not entries or entries[0] != str(folder):
        os.environ["PATH"] = os.pathsep.join([str(folder), *[e for e in entries
                                                           if e and e != str(folder)]])
    return folder


def stub_dir() -> Path:
    """The folder holding the recording logger, for a child given its own PATH."""
    return install()


def records() -> list[str]:
    """What the tools under test tried to write to the journal, one line per call."""
    install()
    log = _STATE["log"]
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []
