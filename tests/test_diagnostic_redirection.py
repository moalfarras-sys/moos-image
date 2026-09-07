#!/usr/bin/env python3
"""Failure diagnostics must actually reach the log.

WHY THIS GATE EXISTS
--------------------
Every x86 boot proof that `promote-x86.yml` requires -- the live ISO boot, the
offline ISO install, and the three QCOW2 disk boots -- ends in a `cleanup()`
that dumps the QEMU log, the guest serial console, the installer status and the
failed-unit list when the run fails. Those dumps were written as:

    tail -100 "$evidence/qemu.log" 2>/dev/null >&2 || true

Redirections are applied LEFT TO RIGHT. `2>/dev/null` points fd 2 at
/dev/null; `>&2` then points fd 1 at *whatever fd 2 is now*, which is
/dev/null. Both streams are discarded, so the dump prints its heading and
nothing else.

That shipped in 14 places across the three gates. Run 34160471709 (2026-09-07)
failed the ISO install gate with "PLM login did not reach the desktop" and
printed four empty evidence sections -- no QEMU log, no serial console, no
installer log. The x86/NVIDIA release train has been blocked behind that gate
since 2026-08-23 (`moos-nvidia:latest` has not moved), and the one artifact
that would say why was being thrown away on every run.

The correct order is `>&2 2>/dev/null`: fd 1 goes to the real stderr, then
fd 2 is silenced so a missing evidence file does not add noise.

This gate proves the behaviour by running both forms, then asserts the broken
order is absent from every shell script in the repository.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# `tail -100 a b` is the obsolete -N form applied to MULTIPLE operands. GNU
# coreutils rejects exactly that combination ("tail: option used in invalid
# context") whenever POSIXLY_CORRECT is set, so a diagnostic written that way
# prints nothing but an error on some shells. `tail -100 file` with a single
# operand, and `... | tail -20` in a pipeline, are fine and are NOT flagged --
# this gate only covers the form that actually breaks.
OBSOLETE_TAIL = re.compile(
    r"\btail[^\S\n]+-\d+((?:[^\S\n]+(?!-)[^\s;|&<>()]+){2,})"
    r"(?=[^\S\n]*(?:[;|&<>)\\]|$))",
    re.MULTILINE,
)
DISCARDING_ORDER = re.compile(r"2>\s*/dev/null\s*(?:\\\s*\n\s*)?>&2")


def shell_scripts():
    for path in sorted(ROOT.rglob("*.sh")):
        if ".git/" in str(path.relative_to(ROOT)):
            continue
        yield path


def prove_the_redirection_actually_discards():
    """Execute both orders and confirm the claim above is true, not folklore."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "evidence.log").write_text("EVIDENCE-LINE\n")
        script = tmp / "probe.sh"
        script.write_text(
            'cd "$(dirname "$0")"\n'
            'tail -n 5 evidence.log missing.log 2>/dev/null >&2 || true\n'
        )
        broken = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, timeout=30,
        )
        script.write_text(
            'cd "$(dirname "$0")"\n'
            'tail -n 5 evidence.log missing.log >&2 2>/dev/null || true\n'
        )
        fixed = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, timeout=30,
        )

    assert "EVIDENCE-LINE" not in broken.stderr, (
        "the premise of this gate no longer holds: `2>/dev/null >&2` reached "
        f"stderr on this shell (got {broken.stderr!r}). Re-derive the rule "
        "before relaxing it."
    )
    assert "EVIDENCE-LINE" in fixed.stderr, (
        "`>&2 2>/dev/null` failed to deliver the diagnostic on this shell "
        f"(stderr={fixed.stderr!r}, stdout={fixed.stdout!r})"
    )
    # The whole point of keeping 2>/dev/null is suppressing the missing-file
    # noise; if that regressed, the dumps get unreadable again.
    assert "missing.log" not in fixed.stderr, (
        "the fixed order should still silence tail's missing-file error, got "
        f"{fixed.stderr!r}"
    )


def main():
    prove_the_redirection_actually_discards()

    discarding = []
    obsolete = []
    for path in shell_scripts():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        for match in DISCARDING_ORDER.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            discarding.append(f"{rel}:{line}: {match.group(0).strip()!r}")
        for match in OBSOLETE_TAIL.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            obsolete.append(f"{rel}:{line}: {match.group(0)!r}")

    problems = []
    if discarding:
        problems.append(
            "these diagnostics send stdout to the /dev/null that fd 2 was just\n"
            "pointed at, so nothing is ever printed. Write `>&2 2>/dev/null`:\n  "
            + "\n  ".join(discarding)
        )
    if obsolete:
        problems.append(
            "obsolete `tail -N` form with multiple file operands; GNU tail\n"
            "rejects exactly this under POSIXLY_CORRECT. Use `tail -n N`:\n  "
            + "\n  ".join(obsolete)
        )

    if problems:
        print("FAIL: " + "\n\nFAIL: ".join(problems), file=sys.stderr)
        return 1

    print("OK: failure diagnostics reach stderr in every shell gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
