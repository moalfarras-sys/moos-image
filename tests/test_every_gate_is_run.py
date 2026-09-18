#!/usr/bin/env python3
"""A test nothing runs is not a gate; it is a file that passes in one second.

Five of them were found on 2026-09-18 by listing `tests/*.py` and grepping the things
that actually execute tests. All five PASSED — which is exactly why nobody noticed. One
of them, `test_post_update_deployment.py`, gates the behaviour of an image after an
update: the day it starts failing is the day it would have earned its keep, and until
today nothing would have told anyone.

This gate closes that loop. It lists every `tests/test_*.py` Git tracks and fails on any
that no runner mentions. A test deliberately kept out of `just check` — because it needs
hardware, a network or a display — says so by naming itself here, with the reason.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Runners: everything that can execute a test in this repository.
RUNNERS = [ROOT / "Justfile", ROOT / "build.sh", ROOT / "build_files/build.sh"]
RUNNERS += sorted((ROOT / ".github/workflows").glob("*.yml"))
RUNNERS += sorted((ROOT / "scripts").rglob("*.sh"))

# Tests that are deliberately not in a runner, each with the reason it cannot be.
# A name here is a claim someone can check, not a way to silence this gate.
EXEMPT = {
    # (none today — every tracked gate is executed by something)
}


def tracked_tests() -> list[str]:
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "tests/test_*.py"],
                            capture_output=True, text=True, timeout=30, check=True)
    return [name for name in listed.stdout.split() if name]


class EveryGateIsRun(unittest.TestCase):
    def test_no_test_file_is_orphaned(self):
        text = ""
        for path in RUNNERS:
            if path.exists():
                text += path.read_text(encoding="utf-8", errors="replace")
        orphans = []
        for name in tracked_tests():
            stem = Path(name).stem
            if stem in EXEMPT:
                continue
            if Path(name).name not in text and stem not in text:
                orphans.append(name)
        self.assertEqual(orphans, [],
                         "nothing runs these, so they gate nothing:\n" + "\n".join(orphans))

    def test_every_exemption_still_names_a_file_that_exists(self):
        for stem, reason in EXEMPT.items():
            self.assertTrue((ROOT / "tests" / f"{stem}.py").exists(),
                            f"exemption {stem!r} names no file")
            self.assertTrue(reason.strip(), f"exemption {stem!r} gives no reason")

    def test_the_runner_list_still_points_at_things_that_exist(self):
        """A renamed workflow would empty this gate without failing it."""
        present = [path for path in RUNNERS if path.exists()]
        self.assertIn(ROOT / "Justfile", present)
        self.assertGreaterEqual(len(present), 5,
                                "the runner list has stopped finding the workflows")


if __name__ == "__main__":
    unittest.main()
