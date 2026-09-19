#!/usr/bin/env python3
"""P4.1: exactly one thing in MoOS installs, removes or updates an application.

The rule is already written, in moai-do's own "App lifecycle" comment: Mo Store's
backend is the one authority, because `flatpak install` lands in the SYSTEM
installation while Mo Store installs per user. Two scopes means two job locks, no
Island row, and apps MoOS installed that Mo Store can never remove — measured on the
daily driver on 2026-09-11: 22 user apps, 3 system apps.

The rule was written and then not kept. `moai-do`'s Windows setup and `moos-setup`'s
first-run selection both still called flatpak directly, and `moos-setup` is the worst
possible place for it: the apps a person picks in their first five minutes were exactly
the ones Mo Store could never remove afterwards.

A comment cannot hold a rule. This gate can.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "system_files/usr/bin"
# The backend itself, and the tools whose whole job is to talk to flatpak on its behalf.
AUTHORITIES = {"moos-storectl", "moos-store-index", "moos-one-store"}
# Verbs that change what is installed. `flatpak info`, `list`, `remotes` and `run` read.
CHANGING = re.compile(r"\bflatpak\b[^\n|;&]*\b(install|uninstall|remove|update|mask)\b")
# One exception, and it is not an app transaction: `--unused` removes runtimes and
# extensions that NO installed application references any more. It cannot touch an app a
# person chose, Mo Store's backend has no verb for it, and it is what makes "free up
# space" free anything. Anything broader than this flag is an app transaction.
GARBAGE_COLLECTION = re.compile(r"\bflatpak\s+uninstall\s+--unused\b")


def sources():
    for path in sorted(BIN.iterdir()):
        if path.is_file() and path.name not in AUTHORITIES:
            try:
                yield path, path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue


class OneAuthority(unittest.TestCase):
    def test_nothing_outside_the_store_backend_changes_what_is_installed(self):
        offenders = []
        for path, text in sources():
            for number, line in enumerate(text.splitlines(), start=1):
                stripped = line.strip()
                # A comment may quote the command it no longer runs — that is how the
                # reason survives in the file.
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                if CHANGING.search(line) and not GARBAGE_COLLECTION.search(line):
                    offenders.append(f"{path.name}:{number}: {stripped[:100]}")
        self.assertEqual(offenders, [], "these change apps outside Mo Store's backend:\n"
                                        + "\n".join(offenders))

    def test_the_two_that_were_fixed_now_call_the_backend(self):
        """Named, so a revert is visible rather than merely absent."""
        moai_do = (BIN / "moai-do").read_text(encoding="utf-8")
        self.assertIn("store_job install com.usebottles.bottles", moai_do)
        setup = (BIN / "moos-setup").read_text(encoding="utf-8")
        self.assertIn('moos-storectl install "${SELECTED[@]}"', setup)

    def test_android_install_mutation_has_one_store_authority(self):
        """An APK is a Store transaction too, even though its carrier is not Flatpak."""
        def normalized(text: str) -> str:
            uncommented = "\n".join(
                line for line in text.splitlines()
                if not line.lstrip().startswith(("#", "//"))
            )
            return re.sub(r"[\s\"',\[\]()]+", " ", uncommented)

        mutation = re.compile(r"(?:^|\s)(?:/usr/bin/)?waydroid\s+app\s+install(?:\s|$)")
        offenders = []
        for path, text in sources():
            if mutation.search(normalized(text)):
                offenders.append(path.name)
        self.assertEqual(offenders, [],
                         "these install APKs outside Mo Store's job/lock authority: "
                         + ", ".join(offenders))

        backend = (BIN / "moos-storectl").read_text(encoding="utf-8")
        self.assertRegex(normalized(backend), mutation,
                         "Mo Store no longer owns the actual Android install mutation")

    def test_the_one_exception_stays_exactly_as_narrow_as_it_is(self):
        """`--unused` collects garbage; anything else named uninstall is a transaction."""
        allowed = []
        for path, text in sources():
            for number, line in enumerate(text.splitlines(), start=1):
                if line.strip().startswith("#"):
                    continue
                if GARBAGE_COLLECTION.search(line):
                    allowed.append(f"{path.name}:{number}")
                    # It must not carry an app id: `--unused APP` would remove the app.
                    tail = line.split("--unused", 1)[1]
                    self.assertNotRegex(tail, r"[A-Za-z0-9]+(\.[A-Za-z0-9-]+){2,}",
                                        f"{path.name}:{number} names an app beside --unused")
        self.assertEqual(len(allowed), 1,
                         f"the garbage-collection exception spread: {allowed}")

    def test_the_rule_is_still_written_where_the_next_agent_will_look(self):
        moai_do = (BIN / "moai-do").read_text(encoding="utf-8")
        self.assertIn("ONE authority for installing", moai_do)
        self.assertIn("P4.1", moai_do)


if __name__ == "__main__":
    unittest.main()
