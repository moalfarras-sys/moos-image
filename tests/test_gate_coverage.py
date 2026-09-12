#!/usr/bin/env python3
"""Gate: `just check` must run every gate any CI workflow runs.

WHY THIS EXISTS

The repository has two build workflows with two independent gate lists:

    .github/workflows/build.yml      -- "Repo gates", the x86 editions
    .github/workflows/build-arm.yml  -- "ARM and boot-splash source gates"

`just check` is what AGENTS.md and the engineering skill tell every contributor
to run before pushing, and it is what an agent reaches for. On 2026-09-07 it did
not run `tests/test_moos_arm.py` or `tests/test_arm_initramfs_size.py`, which
existed only in the ARM workflow. The result was exactly what you would predict:
a change to the ARM update-authority wiring passed `just check`, passed the x86
repo gates, was pushed to main, and failed the ARM build on a gate nobody could
have run locally without reading the workflow YAML by hand.

The cost is not just a red build. It is that "I ran the gates" stops meaning
anything -- which is the one thing this repo cannot afford, because several of
its worst defects shipped while every gate a person actually ran was green.

So: the union of the workflow gate lists must be a subset of what `just check`
runs. `just check` may run MORE (it does, deliberately -- some gates are too slow
or too environment-specific for one workflow but still worth running locally).
It may never run less.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
JUSTFILE = ROOT / "Justfile"

GATE_RE = re.compile(r"python3\s+(tests/[A-Za-z0-9_./-]+\.py)")


def gates_in(text: str) -> set[str]:
    return set(GATE_RE.findall(text))


def main() -> int:
    justfile = JUSTFILE.read_text(encoding="utf-8")
    local = gates_in(justfile)

    # The gate list moved out of build.yml into tests/repo-gates.sh so it could run on pull
    # requests too. Reading only the workflows after that would make this check vacuous — the
    # workflows now just call the script — so the script counts as a required source as well.
    required_sources = [*sorted(WORKFLOWS.glob("*.yml"))]
    gate_script = ROOT / "tests/repo-gates.sh"
    if not gate_script.is_file():
        print("gate coverage FAILED: tests/repo-gates.sh is missing; CI has no gate list to run.")
        return 1
    required_sources.append(gate_script)

    missing: dict[str, set[str]] = {}
    for workflow in required_sources:
        required = gates_in(workflow.read_text(encoding="utf-8"))
        gap = {g for g in required if g not in local}
        if gap:
            missing[workflow.name] = gap

    # A gate listed anywhere must also exist on disk; a typo'd path is a gate
    # that silently never runs.
    ghosts = set()
    for workflow in required_sources:
        for gate in gates_in(workflow.read_text(encoding="utf-8")):
            if not (ROOT / gate).exists():
                ghosts.add(f"{workflow.name}: {gate}")
    for gate in local:
        if not (ROOT / gate).exists():
            ghosts.add(f"Justfile: {gate}")

    if not missing and not ghosts:
        total = len(local)
        print(f"gate coverage passed (`just check` runs {total} gates, "
              f"covering every workflow gate)")
        return 0

    if missing:
        print("GATE COVERAGE FAIL: `just check` does not run every gate CI runs.\n")
        for name, gap in missing.items():
            print(f"  {name} runs these, and `just check` does not:")
            for gate in sorted(gap):
                print(f"      python3 {gate}")
        print("\n  Add them to the `check` recipe in the Justfile. Contributors and")
        print("  agents are told to run `just check` before pushing; a gate that is")
        print("  only in a workflow cannot be run locally and will fail after the")
        print("  push instead of before it.")
    if ghosts:
        print("\nGATE COVERAGE FAIL: a gate path does not exist on disk "
              "(it would silently never run):")
        for ghost in sorted(ghosts):
            print(f"      {ghost}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
