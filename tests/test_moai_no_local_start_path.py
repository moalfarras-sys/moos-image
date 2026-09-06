#!/usr/bin/env python3
"""No externally reachable moai-do action may start a local engine.

THE HOLE THIS CLOSES, found by auditing reachability rather than reading the
obvious function: when Mo AI went cloud-only, `do_setup_brain` was guarded with
an early `moai-config; return $?` — and `do_install_openclaw` was not. It still
called `setup_brain_impl`, which downloads and starts a local model engine and a
local speech model.

That mattered because `install-openclaw` is one of the 28 actions in `moai-do`'s
allowlist, i.e. one of the actions Mo AI itself can NAME. Asking the assistant
for the phone agent would have caused a multi-gigabyte local install on a machine
whose owner had asked for cloud-only inference — with every top-level guard
looking correct.

The lesson, and why this gate checks REACHABILITY: a guard on the function
everyone thinks of is not a policy. The policy is that no path reaches the
engine, and only walking every caller proves that.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOAI_DO = REPO / "system_files/usr/bin/moai-do"

# Helpers that download, install or start a local inference/speech engine.
ENGINE_HELPERS = ("setup_brain_impl",)


def functions(text: str):
    """Yield (name, body_lines) for every shell function, with line numbers."""
    lines = text.splitlines()
    current, start = None, 0
    for i, line in enumerate(lines):
        m = re.match(r"^([a-z_][a-z0-9_]*)\(\)\s*\{", line)
        if m:
            if current:
                yield current, lines[start:i], start
            current, start = m.group(1), i
    if current:
        yield current, lines[start:], start


class NoReachableLocalStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = MOAI_DO.read_text(encoding="utf-8")
        # moai-do now EXPLAINS the closed hole in comments, and a literal search
        # matches the explanation. Read the code. This trap has bitten four
        # times in this branch; strip first, assert second.
        cls.code = "\n".join(
            l for l in cls.text.splitlines() if not l.lstrip().startswith("#"))

    def test_no_function_reaches_an_engine_helper(self) -> None:
        for name, body, _ in functions(self.text):
            if name in ENGINE_HELPERS:
                continue  # its own definition
            # An unconditional `return` before the call makes the rest dead code.
            guard = None
            for i, line in enumerate(body):
                if re.match(r"^\s+return \$\?\s*$", line):
                    guard = i
                    break
            for i, line in enumerate(body):
                if line.lstrip().startswith("#"):
                    continue
                for helper in ENGINE_HELPERS:
                    if re.search(rf"\b{helper}\b", line):
                        with self.subTest(function=name, helper=helper):
                            self.assertIsNotNone(
                                guard,
                                f"{name} calls {helper} with nothing guarding it")
                            self.assertGreater(
                                i, guard,
                                f"{name} reaches {helper} before its guard — "
                                f"this is the install-openclaw hole returning")

    def test_the_cloud_check_reads_what_the_gateway_routes_on(self) -> None:
        """A check against a flag the tool does not have is not a check.

        The first attempt at this fix called `moai-config --check-cloud`.
        moai-config has no such option, so it would fail on an unknown argument
        and open setup unconditionally — indistinguishable from a real check
        until someone reads it.
        """
        self.assertNotIn("--check-cloud", self.code,
                         "moai-config has no --check-cloud option")
        self.assertIn("cloud_base", self.code,
                      "the cloud check must read the same key moai-gateway "
                      "routes on (~/.config/moai/config.json -> cloud_base)")

    def test_install_openclaw_is_still_offered(self) -> None:
        """Closing the hole must not silently delete the action itself; a
        removed allowlist entry would be a dead button in Mo AI's UI."""
        self.assertRegex(self.code, r"install-openclaw\)\s+do_install_openclaw")


if __name__ == "__main__":
    unittest.main(verbosity=2)
