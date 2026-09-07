#!/usr/bin/env python3
"""A comment inside a backslash continuation silently truncates the command.

This shipped to main and broke every x86 edition. build.sh had:

    sed -i \\
        -e 's|^Name=.*|Name=MoOS UI|' \\
        -e 's|^Comment=.*|...|' \\
        # Fedora's papirus-icon-theme ships ONE theme directory...
        -e 's|^Inherits=.*|...|' \\
        /usr/share/icons/MoOSUI2/index.theme

Bash joins a continuation into ONE logical line, so the '#' commented out the
rest of it -- three expressions and the target file. sed ran with no input,
printed "sed: no input files" and exited 4, killing the build. The Inherits fix
those lines describe never applied either, so the bug also hid a second bug.

`bash -n` does NOT catch this: the result is perfectly valid syntax. Only a
structural check does, which is why this gate exists rather than relying on the
syntax check that was already running in CI and passed.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

failures = []
for path in sorted(ROOT.rglob("*.sh")):
    if ".git/" in str(path):
        continue
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Only a continuation begun by CODE can be truncated. A comment block whose
    # lines happen to end in "\" (documentation showing a wrapped command) is
    # harmless, so track what actually opened the continuation.
    continuing_code = False
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        is_comment = stripped.startswith("#")
        if continuing_code and is_comment:
            failures.append(
                f"{path.relative_to(ROOT)}:{number}: comment inside a line "
                f"continuation truncates the command -> {stripped[:60]}")
        if line.rstrip().endswith("\\"):
            # A comment line ending in "\" continues a comment, not a command.
            if not is_comment:
                continuing_code = True
        else:
            continuing_code = False

if failures:
    print("Shell line-continuation gate FAILED:")
    for failure in failures:
        print(f"  {failure}")
    sys.exit(1)

print("shell line-continuation gate passed")
