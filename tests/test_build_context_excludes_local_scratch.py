#!/usr/bin/env python3
"""What Git refuses to track, the image builder should refuse to read.

`.gitignore` and `.containerignore` answer two different questions — what must never be
committed, and what must never enter the build context — but for LOCAL SCRATCH the answer
is the same, and the two files had drifted apart without anything noticing.

Measured on 2026-09-18: `.containerignore` excluded `moremote/bin/` and `moremote/obj/`,
which do not exist and never did. Mo Remote's .NET output is under `agent-linux/`, which
`.gitignore` names correctly. So those two lines protected nothing, while 196 MB went to
the builder on every local build — `controller/node_modules` 191 MB, `agent-linux/bin`
3.8 MB, `agent-linux/obj` 1.2 MB.

This gate holds two things: every local-scratch path Git ignores is also kept out of the
build context, and every concrete path `.containerignore` names actually exists — because
a rule for a path that is not there is a rule that protects nothing.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def entries(name: str) -> list[str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")]


# Paths Git ignores that are pure BUILD OUTPUT or vendored dependencies — bytes the
# builder has no use for. Things like `.claude/` or `media/` are ignored for other
# reasons and are not this gate's business.
LOCAL_BUILD_OUTPUT = (
    "moremote/agent-linux/bin/",
    "moremote/agent-linux/obj/",
    "moremote/dist-linux/",
    "node_modules/",
    "moplayer/build/",
    "moplayer/.dart_tool/",
    "moplayer/linux/flutter/ephemeral/",
    "output/",
    # Review evidence, and the one entry here that is not merely dead weight: it
    # holds live captures of the development station's own desktop.
    "test-results/",
)


class BuildContext(unittest.TestCase):
    def setUp(self):
        self.container = entries(".containerignore")
        self.git = entries(".gitignore")

    def test_every_build_output_git_ignores_is_kept_out_of_the_build_context(self):
        missing = []
        for path in LOCAL_BUILD_OUTPUT:
            self.assertIn(path, self.git,
                          f"{path} is no longer in .gitignore — update this gate's list too")
            # node_modules/ is matched anywhere by both files; the rest are literal.
            covered = any(entry.rstrip("/") == path.rstrip("/")
                          or entry.rstrip("/").endswith("/" + path.rstrip("/"))
                          for entry in self.container)
            if not covered:
                missing.append(path)
        self.assertEqual(missing, [],
                         "Git refuses to track these, but the builder still reads them:\n"
                         + "\n".join(missing))

    def test_no_rule_names_a_path_that_is_neither_real_nor_known(self):
        """The shape of the bug that was here, generalised.

        `moremote/bin/` did not exist AND was not a path `.gitignore` names — nobody had
        ever produced it, because the build does not put anything there. That is a typo
        wearing a rule's clothes. A path that is absent today but IS in `.gitignore`
        (`output/`, `flutter/`, `moremote/dist-linux/`) is the opposite: a correct rule
        waiting for the local build that creates it.
        """
        stray = []
        for entry in self.container:
            if any(character in entry for character in "*?[]!") or entry.startswith("**"):
                continue
            bare = entry.rstrip("/")
            if (ROOT / bare).exists():
                continue
            if any(rule.rstrip("/") == bare or rule.rstrip("/").endswith("/" + bare)
                   for rule in self.git):
                continue
            stray.append(entry)
        self.assertEqual(stray, [],
                         "these .containerignore rules name paths that do not exist and that "
                         "nothing else in the repository knows about — they exclude nothing:\n"
                         + "\n".join(stray))

    def test_the_moremote_paths_are_the_real_ones(self):
        """Named, so the exact regression that happened is visible if it returns."""
        self.assertNotIn("moremote/bin/", self.container)
        self.assertNotIn("moremote/obj/", self.container)
        self.assertIn("moremote/agent-linux/bin/", self.container)
        self.assertIn("moremote/controller/node_modules/", self.container)


if __name__ == "__main__":
    unittest.main()
