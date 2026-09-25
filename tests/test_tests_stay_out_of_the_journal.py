#!/usr/bin/env python3
"""Gate: no repository test can write into the owner's journal.

WHY THIS EXISTS
moai-do, moos-image-update, moai-control and moos-control audit what they do with `logger`,
and that journal is product data: `journalctl -t moai-do` is "everything the assistant has
done", `journalctl -t moos-update` is the machine's update history. Between 22:00:23 and
22:00:40 on 2026-09-24 one `just check` on the station added 36 moai-do records (among them
"action=update verdict=ok" three times and a refused "update; rm -rf /") and 22 moos-update
records with invented digests. Journal lines cannot be removed one by one.

The suites now put a recording logger first on PATH (tests/journal_isolation.py). A check
that reads the suites for that import would pass a suite whose child builds its own PATH and
finds /usr/bin/logger anyway, so this gate RUNS them instead:

  * the auditing tools are found by reading system_files (every shipped program whose code
    calls logger), so a new one is covered without editing this file;
  * every suite that names one of those tools by path is run in a private mount namespace
    (bubblewrap) where the real logger is replaced by a trap and the journal socket is an
    empty directory — so the gate itself cannot pollute anything either;
  * a suite that reaches the trap fails this gate with the lines it tried to write;
  * each run first proves the trap bites (a plain `logger` call is caught) and that the
    recording logger keeps a well-behaved caller away from it.

Where bubblewrap cannot make a namespace (a CI runner that forbids user namespaces, the VS
Code sandbox) there is no owner journal to protect and the executed half is skipped with a
notice. On a MoOS machine — the one whose journal this protects — it is never skipped.
"""
from __future__ import annotations

import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system_files"
TESTS = ROOT / "tests"
SELF = Path(__file__).resolve()
LOGGERS = ("/usr/bin/logger", "/usr/sbin/logger", "/bin/logger")
# Known today; the scan below must find at least these, or it has gone blind.
KNOWN_AUDITORS = {"usr/bin/moai-do", "usr/bin/moai-control", "usr/bin/moos-control",
                  "usr/libexec/moos-image-update"}
CALLS_LOGGER = re.compile(r"""(?:^|[\s;&|(`])logger\s+-|["']logger["']""", re.M)


def code_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def auditing_tools() -> set[str]:
    found = set()
    for folder in ("usr/bin", "usr/libexec"):
        for path in sorted((SYSTEM / folder).iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if CALLS_LOGGER.search(code_lines(text)):
                found.add(str(path.relative_to(SYSTEM)))
    return found


def suites_naming(tools: set[str]) -> list[Path]:
    chosen = []
    for path in sorted([*TESTS.glob("test_*.py"), *TESTS.glob("verify_*.py")]):
        if path.resolve() == SELF:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(tool in text for tool in tools):
            chosen.append(path)
    return chosen


def is_moos_machine() -> bool:
    return Path("/usr/lib/moos/edition").is_file() or Path("/usr/share/moos").is_dir()


def trap(folder: Path, name: str) -> tuple[Path, Path]:
    log = folder / f"{name}.trap.log"
    script = folder / f"{name}.trap"
    script.write_text("#!/bin/sh\n"
                      'line="logger"\nfor arg in "$@"; do line="$line $arg"; done\n'
                      f'printf \'%s\\n\' "$line" >> "{log}"\n', encoding="utf-8")
    script.chmod(0o755)
    return script, log


def sandboxed(script: Path, argv: list[str]) -> list[str]:
    command = ["bwrap", "--dev-bind", "/", "/"]
    seen = set()
    for candidate in LOGGERS:
        real = os.path.realpath(candidate)
        if os.path.isfile(candidate) and real not in seen:
            seen.add(real)
            command += ["--ro-bind", str(script), real]
    if os.path.isdir("/run/systemd/journal"):
        command += ["--tmpfs", "/run/systemd/journal"]
    return command + ["--", *argv]


def run_trapped(folder: Path, name: str, argv: list[str], timeout: int = 900):
    script, log = trap(folder, name)
    began = time.monotonic()
    try:
        done = subprocess.run(sandboxed(script, argv), cwd=ROOT, capture_output=True, text=True,
                              errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
        code, tail = done.returncode, (done.stdout + done.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        code, tail = "timeout", ""
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return code, lines, tail, time.monotonic() - began


def main() -> int:
    errors: list[str] = []
    tools = auditing_tools()
    if not KNOWN_AUDITORS <= tools:
        errors.append(f"the auditing-tool scan went blind: it missed {sorted(KNOWN_AUDITORS - tools)}")
    suites = suites_naming(tools)
    for required in ("test_moai_do.py", "test_moai_control.py", "test_moos_auto_update.py",
                     "test_moai_confirmation_flow.py", "test_moos_control.py"):
        if not any(suite.name == required for suite in suites):
            errors.append(f"the suite scan went blind: it missed {required}")

    if shutil.which("bwrap") is None:
        usable = False
    else:
        probe = subprocess.run(["bwrap", "--dev-bind", "/", "/", "--", "true"],
                               capture_output=True, timeout=30)
        usable = probe.returncode == 0
    if not usable:
        if is_moos_machine():
            errors.append("bubblewrap cannot make a namespace on this MoOS machine, so the "
                          "gate cannot prove its suites stay out of this machine's journal")
        else:
            print("NOTICE: no usable bubblewrap here; the executed half is skipped. There is "
                  "no owner journal on this machine to protect.")
        return report(errors, tools, suites, executed=False)

    with tempfile.TemporaryDirectory(prefix="moos-journal-trap-") as tmp:
        folder = Path(tmp)
        # 1. The trap bites: a plain logger call is caught.
        _code, caught, _tail, _secs = run_trapped(
            folder, "probe-plain", ["sh", "-c", "logger -t moos-trap-probe caught"])
        if not any("moos-trap-probe" in line for line in caught):
            errors.append("the trap caught nothing from a plain `logger` call — it proves nothing")
        # 2. The recording logger keeps a well-behaved caller away from it.
        guarded = (f"import sys, subprocess; sys.path.insert(0, {str(TESTS)!r}); "
                   "import journal_isolation as j; j.install(); "
                   "subprocess.run(['logger', '-t', 'moos-trap-probe', 'stubbed'], check=True); "
                   "sys.exit(0 if j.records() else 3)")
        code, reached, tail, _secs = run_trapped(folder, "probe-guarded",
                                                 [sys.executable, "-c", guarded])
        if reached or code != 0:
            errors.append(f"journal_isolation.install() did not keep a caller off the real "
                          f"logger (exit {code}, trapped {reached}): {tail[-300:]}")

        # 3. Every suite that names an auditing tool, run with the trap in place.
        workers = max(2, min(8, os.cpu_count() or 2))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(run_trapped, folder, suite.stem,
                                   [sys.executable, str(suite)]): suite for suite in suites}
            for future in concurrent.futures.as_completed(futures):
                suite = futures[future]
                code, reached, tail, seconds = future.result()
                name = suite.relative_to(ROOT)
                if reached:
                    shown = "\n      ".join(reached[:4])
                    errors.append(f"{name} reached the real logger {len(reached)} time(s) — its "
                                  f"records would be in the owner's journal:\n      {shown}")
                if code != 0:
                    errors.append(f"{name} could not be proven: it failed under the trap "
                                  f"(exit {code}); run it alone to see why.\n{tail[-600:]}")
                print(f"  {name}: {len(reached)} journal write(s), {seconds:.1f} s")
    return report(errors, tools, suites, executed=True)


def report(errors: list[str], tools: set[str], suites: list[Path], executed: bool) -> int:
    if errors:
        print("GATE FAIL: a repository test can write into the owner's journal.\n")
        for error in errors:
            print(f"  - {error}")
        return 1
    how = "ran" if executed else "found"
    print(f"OK: {len(tools)} auditing tools; {how} {len(suites)} suites that name them, "
          f"and none can reach the real logger.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
