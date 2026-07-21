#!/usr/bin/env python3
"""Gate: every shipped script in an executable directory must carry +x.

`COPY system_files/ /` (Containerfile) preserves the working-tree file mode, and
build.sh chmods only a hand-picked list. Scripts that fell through BOTH paths —
wrong git mode AND absent from build.sh's chmod list — shipped to /usr/bin as
0644 and died the instant anything exec'd them directly:

  * moos-ensure-brain.service failed 203/EXEC ("Permission denied"), so Mo AI's
    fast-instruct brain was never ensured on boot;
  * moos-store and the installer are exec'd straight from their .desktop files.

Scripts invoked via an explicit interpreter (`python3 moai-gateway`, `bash …`)
happened to still run without the bit — which is exactly why the breakage was
intermittent and no existing gate caught it.

This gate makes the working-tree mode the single source of truth for the two
executable directories: any '#!'-script under /usr/bin or /usr/libexec that is
not executable fails the build, before it can ship broken again.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXEC_DIRS = ["system_files/usr/bin", "system_files/usr/libexec"]


def is_script(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


errors: list[str] = []
for rel in EXEC_DIRS:
    base = ROOT / rel
    if not base.is_dir():
        continue
    for path in sorted(base.iterdir()):
        if not path.is_file():
            continue
        if is_script(path) and not (path.stat().st_mode & 0o111):
            errors.append(f"{rel}/{path.name} is a '#!' script but not executable")

if errors:
    print("executable-bit gate FAILED:")
    for error in errors:
        print(f"  - {error}")
    print(
        "\nA script shipped without +x dies with 203/EXEC the moment systemd or a"
        "\n.desktop Exec runs it directly. Fix the git mode: chmod +x the file."
    )
    sys.exit(1)

print(f"executable-bit gate passed ({' + '.join(EXEC_DIRS)} scripts all +x)")
