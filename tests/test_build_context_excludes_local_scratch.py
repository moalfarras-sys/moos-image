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

Mo Remote's nested .gitignore applies bin/obj/publish to EVERY .NET project,
including tests and visual tools. The source contract below preserves those
recursive exclusions; MOOS_BUILD_CONTEXT_PROBE=1 additionally exercises the
real Podman COPY engine against private old/fixed scratch contexts.
"""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid

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
            # A slash-free Git rule such as `node_modules/` matches that
            # directory at any depth, including controller/node_modules in a
            # clean worktree before dependencies have been installed.
            if any(rule.rstrip("/") == bare
                   or ("/" not in rule.rstrip("/")
                       and rule.rstrip("/") == Path(bare).name)
                   or rule.rstrip("/").endswith("/" + bare)
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

    def test_every_moremote_dotnet_project_output_is_excluded(self):
        remote_git = entries("moremote/.gitignore")
        for directory in ("bin", "obj", "publish"):
            self.assertIn(directory + "/", remote_git)
            self.assertIn(f"moremote/**/{directory}/", self.container,
                          "nested test/tool output must not enter COPY moremote")

    @unittest.skipUnless(os.environ.get("MOOS_BUILD_CONTEXT_PROBE") == "1",
                         "set MOOS_BUILD_CONTEXT_PROBE=1 for the private Podman context proof")
    def test_real_builder_old_and_fixed_recursive_dotnet_rules(self):
        """Use the real COPY/ignore engine on tiny scratch images, never owner output."""
        self.assertIsNotNone(shutil.which("podman"))
        with tempfile.TemporaryDirectory(prefix="moos-context-proof-") as raw:
            root = Path(raw)
            context = root / "context"
            context.mkdir()
            forbidden = []
            for project in ("agent", "agent-linux", "tests/Input.Tests", "tools/VisualInputTest"):
                for directory in ("bin", "obj", "publish"):
                    name = f"{project}/{directory}/probe.txt"
                    path = context / "moremote" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("private local build output")
                    forbidden.append(name)
            kept = ("agent/wwwroot/index.html", "tests/Input.Tests/Test.cs",
                    "tools/VisualInputTest/binoculars/source.txt")
            for name in kept:
                path = context / "moremote" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source")
            (context / "Containerfile").write_text("FROM scratch\nCOPY moremote/ /payload/\n")
            fixed = (ROOT / ".containerignore").read_text()
            old = "\n".join(line for line in fixed.splitlines()
                            if line not in {f"moremote/**/{d}/" for d in ("bin", "obj", "publish")})

            def copied_files(rules):
                (context / ".containerignore").write_text(rules)
                identity = "moos-context-proof-" + uuid.uuid4().hex
                image = "localhost/" + identity
                container = ""

                def command(*args):
                    return subprocess.run(["podman", *args], check=True, capture_output=True,
                                          text=True, timeout=120).stdout.strip()

                try:
                    command("build", "--pull=never", "--layers=false", "-q", "-t", image, str(context))
                    container = command("create", image, "/unused")
                    destination = root / identity
                    command("cp", container + ":/payload", str(destination))
                    return {str(p.relative_to(destination)) for p in destination.rglob("*") if p.is_file()}
                finally:
                    if container:
                        command("rm", container)
                    subprocess.run(["podman", "image", "rm", image], capture_output=True,
                                   text=True, timeout=120, check=False)

            old_files = copied_files(old)
            self.assertIn("tests/Input.Tests/bin/probe.txt", old_files,
                          "the old ignore rules must reproduce the context leak")
            fixed_files = copied_files(fixed)
            self.assertFalse(set(forbidden) & fixed_files, fixed_files)
            self.assertTrue(set(kept) <= fixed_files, fixed_files)


if __name__ == "__main__":
    unittest.main()
