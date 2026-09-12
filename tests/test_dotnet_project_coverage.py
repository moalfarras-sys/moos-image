#!/usr/bin/env python3
"""Gate: every .NET project under moremote/ is built by `moremote/dotnet-check.sh`.

WHY THIS EXISTS

The agent's C# is compiled in seven places with seven different file lists. The two agents are
real products; the five test executables each pull in a HAND-WRITTEN subset of the shared
`agent/Core` and `agent/Web` sources. So adding one shared file and wiring it into some of those
lists compiles perfectly — until the one that was missed.

That is what happened to `Core/HostBudget.cs`. It was added, wired into the Linux agent and
MoRemote.Tests, and both built clean locally. Twenty-five minutes into the ARM image build:

    /src/agent/Web/StreamSession.cs(200,22): error CS0103:
        The name 'HostBudget' does not exist in the current context
        [/src/tests/MoRemote.Stream.Tests/MoRemote.Stream.Tests.csproj]

MoRemote.Stream.Tests compiles StreamSession.cs and had not been given the new file. The fast
x86 job that runs these executables in about a minute exists — and `build.yml` triggers only on
pushes to `main`, so on a branch it never ran. The only pre-merge signal was the 180-minute ARM
build, and it spent all of it to say "you forgot one line of XML".

`moremote/dotnet-check.sh` gives that signal locally in under a minute. This keeps it honest: a
project that exists in the tree and not in the script is a project nobody builds before pushing.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOREMOTE = ROOT / "moremote"
SCRIPT = MOREMOTE / "dotnet-check.sh"


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing — nothing builds the .NET tree locally.")
        return 1

    script = SCRIPT.read_text(encoding="utf-8")
    # The script names projects either by .csproj path or by their directory (dotnet run --project).
    listed = {
        line.strip()
        for line in script.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
        and (line.strip().endswith(".csproj") or re.fullmatch(r"(agent-linux|agent|tests)/[\w.-]+", line.strip()))
    }

    errors: list[str] = []
    for csproj in sorted(MOREMOTE.rglob("*.csproj")):
        if "/obj/" in str(csproj) or "/bin/" in str(csproj):
            continue
        rel = csproj.relative_to(MOREMOTE).as_posix()
        directory = csproj.parent.relative_to(MOREMOTE).as_posix()
        if rel not in listed and directory not in listed:
            errors.append(
                f"{rel} is not built by dotnet-check.sh. Add it to `run` (an executable that "
                f"asserts) or `build` (compiled only), so a shared source file missing from its "
                f"<Compile Include> list fails in a minute instead of in the image build."
            )

    # And the reverse: a name in the script that no longer exists is a project silently not built.
    on_disk = set()
    for csproj in MOREMOTE.rglob("*.csproj"):
        if "/obj/" in str(csproj) or "/bin/" in str(csproj):
            continue
        on_disk.add(csproj.relative_to(MOREMOTE).as_posix())
        on_disk.add(csproj.parent.relative_to(MOREMOTE).as_posix())
    for name in sorted(listed - on_disk):
        errors.append(f"dotnet-check.sh names {name}, which does not exist.")

    # The image builds are the reason this matters: whatever they RUN must be in the script's own
    # run list, or the local check is weaker than the build it is standing in for.
    for containerfile in ("Containerfile", "Containerfile.arm"):
        text = (ROOT / containerfile).read_text(encoding="utf-8")
        for project in re.findall(r"dotnet run --project (\S+)", text):
            if project not in listed:
                errors.append(f"{containerfile} runs {project}, which dotnet-check.sh does not.")

    if errors:
        print("GATE FAIL: the local .NET check does not cover the .NET tree.")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"PASS: dotnet-check.sh covers all {len(listed)} moremote .NET projects, "
          f"including everything the image builds run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
