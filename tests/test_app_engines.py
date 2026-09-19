#!/usr/bin/env python3
"""One registry decides what MoOS can run, and what it calls those things.

MoOS runs programs written for other systems: Windows programs through a Windows
runtime, Android apps through an Android container, Linux apps through Flatpak.
The owner's requirement is that none of that is their problem — they press
install, or drop a file, and it runs. So two things have to stay true, and
neither of them is visible by reading any single file:

1. THE ENGINE NEVER SAYS ITS NAME. A person who downloaded a `.exe` wants
   "Windows programs". Wine, Bottles, Waydroid and Proton are implementation,
   and an implementation detail in a dialog is a system admitting it is several
   systems. Every user-facing string in the registry and in the runner is
   checked here against the brands they are allowed to hide.

2. WHAT THE IMAGE SHIPS AND WHAT THE RUNNER USES MUST BE THE SAME SET. This is
   the defect that prompted the registry. `build.sh` installs wine on every
   desktop edition with the comment "so any .exe the user downloads actually
   runs" — and `moos-run-foreign` knew only about Bottles, so the first `.exe` on
   a fresh MoOS offered a large download on a machine that could already run the
   file. Both halves read green on their own; only comparing them shows it.

The resolver is also exercised for real, because a registry nothing reads is a
document, not a contract.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "system_files/usr/share/moos/app-engines.json"
RESOLVER = ROOT / "system_files/usr/libexec/moos-app-engine"
RUNNER = ROOT / "system_files/usr/bin/moos-run-foreign"
MIMEAPPS = ROOT / "system_files/etc/xdg/mimeapps.list"
BUILD = ROOT / "build_files/build.sh"

# The words that must never reach a person. Each is a real engine or vendor whose
# name would tell the owner they are using something other than MoOS.
ENGINE_BRANDS = ("wine", "bottles", "waydroid", "proton", "lutris",
                 "flatpak", "wayland", "kwin", "plasma", "qemu", "bubblewrap")

DOCUMENT = json.loads(REGISTRY.read_text(encoding="utf-8"))


def user_facing_strings(node, path="") -> list[tuple[str, str]]:
    """Every string a person could read: `name` and `reason` values, recursively.

    Explicitly NOT `id`, `probe` or `_`: an engine's identifier has to be its
    real name for the resolver to find it, and `_` is a note to whoever reads the
    file next. Only what is rendered is policed.
    """
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if key in ("name", "reason") and isinstance(value, dict):
                for language, text in value.items():
                    found.append((f"{here}.{language}", str(text)))
            else:
                found.extend(user_facing_strings(value, here))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(user_facing_strings(value, f"{path}[{index}]"))
    return found


class TheRegistryIsWellFormed(unittest.TestCase):
    def test_schema_and_required_shape(self):
        self.assertEqual(DOCUMENT.get("schema"), 1)
        self.assertTrue(DOCUMENT.get("engines"), "no engines are declared")
        seen = set()
        for engine in DOCUMENT["engines"]:
            for field in ("id", "name", "claims", "runtimes"):
                self.assertIn(field, engine, f"engine {engine.get('id')} has no {field}")
            self.assertNotIn(engine["id"], seen, "two engines share an id")
            seen.add(engine["id"])
            self.assertEqual(set(engine["name"]), {"ar", "en"},
                             f"{engine['id']} must be named in both languages")
            self.assertTrue(engine["runtimes"],
                            f"{engine['id']} claims files it has nothing to run them with")
            for runtime in engine["runtimes"]:
                self.assertIn(runtime.get("carrier"), ("image", "flatpak"),
                              f"{engine['id']}/{runtime.get('id')} has no known carrier")

    def test_no_extension_is_claimed_by_two_engines(self):
        """Two engines claiming `.exe` is a coin toss the owner experiences as chaos."""
        owner: dict[str, str] = {}
        for engine in DOCUMENT["engines"]:
            for extension in engine["claims"].get("extensions", []):
                self.assertNotIn(
                    extension.lower(), owner,
                    f".{extension} is claimed by both {owner.get(extension.lower())} "
                    f"and {engine['id']}")
                owner[extension.lower()] = engine["id"]

    def test_what_cannot_be_run_is_written_down_with_a_reason(self):
        """"Can MoOS run Mac apps?" gets one answer, in the file, in both languages."""
        unsupported = {entry["id"]: entry for entry in DOCUMENT.get("unsupported", [])}
        self.assertIn("macos", unsupported,
                      "macOS must be listed as unsupported with a reason, not omitted — "
                      "an unanswered question gets re-answered differently every time")
        for entry in unsupported.values():
            self.assertEqual(set(entry.get("reason", {})), {"ar", "en"},
                             f"{entry['id']} must say WHY, in both languages")
            self.assertGreater(len(entry["reason"]["en"]), 60,
                               f"{entry['id']}'s reason is too short to be a reason")


class TheEngineNeverSaysItsName(unittest.TestCase):
    def test_no_user_facing_string_in_the_registry_names_an_engine(self):
        offenders = []
        for where, text in user_facing_strings(DOCUMENT):
            lowered = text.lower()
            for brand in ENGINE_BRANDS:
                # macOS's reason is allowed to discuss what does not work and why;
                # it is an explanation, not a label on a button.
                if where.startswith("unsupported"):
                    continue
                if re.search(rf"\b{brand}\b", lowered):
                    offenders.append(f"{where}: {text!r} names {brand!r}")
        self.assertEqual(offenders, [],
                         "these strings are shown to a person and name the engine:\n  "
                         + "\n  ".join(offenders))

    def test_the_runner_shows_the_kind_of_program_not_the_runtime(self):
        """Every dialog and popup string in moos-run-foreign, checked as text."""
        source = RUNNER.read_text(encoding="utf-8")
        # Only the arguments of the two functions that reach a screen.
        shown = re.findall(r'(?:notify|ask)\s+"((?:[^"\\]|\\.)*)"', source)
        self.assertTrue(shown, "found no user-facing strings in the runner to check")
        offenders = []
        for text in shown:
            for brand in ENGINE_BRANDS:
                if re.search(rf"\b{brand}\b", text.lower()):
                    offenders.append(f"{text!r} names {brand!r}")
        self.assertEqual(offenders, [],
                         "moos-run-foreign says these to a person:\n  " + "\n  ".join(offenders))

    def test_the_runner_does_not_hint_a_terminal_command_at_the_owner(self):
        """"try: waydroid app install …" is the engine's name AND its CLI."""
        source = RUNNER.read_text(encoding="utf-8")
        for brand in ("waydroid", "wine", "flatpak"):
            self.assertNotRegex(
                source, rf'echo\s+"[^"]*\b{brand}\b[^"]*"',
                f"the runner echoes a {brand} command at the owner; a person who "
                f"double-clicked a file is not holding a terminal")


class TheImageAndTheRunnerAgree(unittest.TestCase):
    @staticmethod
    def installed_packages(build: str) -> set[str]:
        """Every package name build.sh puts into an install list.

        Collected from the `+=(...)` accumulators and the dnf5 install lines
        rather than matched loosely against the whole file, so a runtime that is
        only MENTIONED in a comment does not read as installed.
        """
        names: set[str] = set()
        for block in re.findall(r"\+=\(([^)]*)\)", build):
            names.update(re.findall(r"[\w.+-]+", block))
        for block in re.findall(r"dnf5[^\n]*install([^\n]*)", build):
            names.update(re.findall(r"[\w.+-]+", block))
        return names

    def test_every_shipped_runtime_is_actually_installed_by_the_build(self):
        """The defect the registry exists for, stated as a check.

        A runtime declared `carrier: image` is a promise that it is IN the signed
        image. If the build stops installing it, the runner silently falls
        through to offering a download on a machine that used to just work.
        """
        build = BUILD.read_text(encoding="utf-8")
        for engine in DOCUMENT["engines"]:
            for runtime in engine["runtimes"]:
                if runtime.get("carrier") != "image":
                    continue
                probe = runtime.get("probe") or runtime["id"]
                origin = runtime.get("from")
                self.assertIn(
                    origin, ("build", "base", "overlay"),
                    f"{engine['id']}/{probe} must say where it comes from, so this "
                    f"gate knows whether build.sh is supposed to install it")
                if origin == "overlay":
                    # MoOS's own tools: they are in the tree or they are not.
                    self.assertTrue(
                        (ROOT / "system_files/usr/bin" / probe).exists()
                        or (ROOT / "system_files/usr/libexec" / probe).exists(),
                        f"{engine['id']} declares the overlay tool {probe!r}, which "
                        f"system_files does not carry")
                    continue
                if origin == "base":
                    # From ghcr.io/ublue-os/kinoite-main; build.sh does not install
                    # it and this gate cannot see inside the base image. The image
                    # build's own gates are where a missing base tool surfaces.
                    continue
                self.assertIn(
                    probe, self.installed_packages(build),
                    f"{engine['id']} declares the shipped runtime {probe!r}, but "
                    f"build.sh never installs it — the registry would promise a "
                    f"runtime the image does not carry")

    def test_every_mime_routed_to_the_runner_is_claimed_by_an_engine(self):
        """mimeapps sends these to moos-run-foreign; something must know what they are."""
        mimeapps = MIMEAPPS.read_text(encoding="utf-8")
        routed = set(re.findall(r"(?m)^([\w.+-]+/[\w.+-]+)=org\.moos\.runforeign\.desktop",
                                mimeapps))
        self.assertTrue(routed, "nothing is routed to the MoOS runner any more")
        claimed = {mime.lower()
                   for engine in DOCUMENT["engines"]
                   for mime in engine["claims"].get("mime", [])}
        # Office documents go to the runner too and are opened by an application,
        # not by an engine; they are out of scope here and covered elsewhere.
        program_like = {mime for mime in routed
                        if "officedocument" not in mime and "opendocument" not in mime
                        and mime not in ("text/csv",)
                        and not mime.startswith("application/msword")
                        and not mime.startswith("application/vnd.ms-")
                        and not mime.startswith("text/rtf")
                        and not mime.startswith("application/rtf")}
        missing = sorted(mime for mime in program_like if mime.lower() not in claimed)
        self.assertEqual(
            missing, [],
            "mimeapps.list hands these to the runner but no engine claims them, so the "
            "resolver returns nothing and a double-click does nothing:\n  "
            + "\n  ".join(missing))

    def test_the_runner_asks_the_resolver_instead_of_deciding_alone(self):
        """Deciding in two places is how the two places came to disagree."""
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("moos-app-engine", source,
                      "the runner must resolve through the shared registry")
        # The old shape: a hardcoded runtime id driving the decision.
        self.assertNotIn('BOTTLES_ID=', source,
                         "the runner still carries a hardcoded runtime constant")


@unittest.skipIf(not os.access("/usr/bin/python3", os.X_OK), "no python3")
class TheResolverAnswers(unittest.TestCase):
    """Run the real resolver, because a registry nothing reads is a document."""

    def resolve(self, name: str):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / name
            target.touch()
            result = subprocess.run(
                ["python3", str(RESOLVER), "resolve", str(target)],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "MOOS_APP_ENGINES": str(REGISTRY),
                     "PATH": "/usr/bin:/bin"})
        return result.returncode, json.loads(result.stdout or "{}")

    def test_each_claimed_extension_resolves_to_its_own_engine(self):
        for engine in DOCUMENT["engines"]:
            for extension in engine["claims"].get("extensions", []):
                code, answer = self.resolve(f"sample.{extension}")
                self.assertEqual(code, 0, f".{extension} did not resolve")
                self.assertEqual(answer.get("engine"), engine["id"],
                                 f".{extension} resolved to the wrong engine")
                self.assertEqual(set(answer.get("name", {})), {"ar", "en"})

    def test_a_file_no_engine_claims_says_so_instead_of_guessing(self):
        code, answer = self.resolve("notes.txt")
        self.assertEqual(code, 3)
        self.assertIsNone(answer.get("engine"))

    def test_the_answer_distinguishes_ready_from_needs_setup(self):
        """Three states, because 'installed' and 'can take a file' differ."""
        code, answer = self.resolve("program.exe")
        self.assertEqual(code, 0)
        for field in ("ready", "needs_setup", "runtimes", "chosen"):
            self.assertIn(field, answer)
        self.assertIsInstance(answer["ready"], bool)
        if answer["ready"]:
            self.assertIsNotNone(answer["chosen"])
            self.assertFalse(answer["needs_setup"],
                             "an engine cannot be both ready and awaiting setup")


if __name__ == "__main__":
    unittest.main(verbosity=2)
