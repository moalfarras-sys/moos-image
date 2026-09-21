#!/usr/bin/env python3
"""The promise in mimeapps.list has to be keepable on BOTH architectures.

THE DEFECT THIS FILE EXISTS FOR, measured on the Oracle A1 on 2026-09-21:

  `system_files/etc/xdg/mimeapps.list` is copied verbatim into every edition and
  pointed application/pdf, application/postscript and application/epub+zip at
  `org.kde.okular.desktop`. That file was not in the ARM image at all, because
  the x86 editions build FROM kinoite-main — which already carries KDE's apps —
  while `Containerfile.arm` starts from bare fedora-bootc and gets only what
  `build_files/build-arm.sh` names. `xdg-mime query default application/pdf`
  answered `org.chromium.Chromium.desktop`, a Flatpak the owner happened to have
  installed, and application/epub+zip answered nothing. On a fresh ARM install
  with no browser a double-clicked PDF had NO handler.

  It survived because the only check that mentioned okular greps `build.sh` for
  the package name (`tests/verify_user_experience.py`), so it could only ever
  describe x86. A gate that reads one of two build scripts is a green check that
  means nothing about the other edition.

So this file holds two things the image build cannot hold for us:

  * the ARM build script must NAME every third-party handler the list promises,
    because on ARM nothing arrives unasked — that is the half a source gate can
    prove in seconds, and it is the half that broke;
  * both build scripts must still CALL the in-image gate, so the authoritative
    check (does the .desktop exist in the finished image?) cannot be dropped.
"""
import importlib.machinery
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIMEAPPS = ROOT / "system_files/etc/xdg/mimeapps.list"
GATE = ROOT / "build_files/verify_mime_handlers.py"
BUILD_X86 = ROOT / "build_files/build.sh"
BUILD_ARM = ROOT / "build_files/build-arm.sh"

# A handler id maps to its package by its last dotted component
# (org.kde.okular.desktop -> okular), which is true for every handler MoOS
# promises today. Anything that stops being true belongs here rather than in a
# cleverer regex, so the exception is visible.
PACKAGE_OVERRIDES: dict[str, str] = {}


def code(text: str) -> str:
    """Strip shell comments so a gate cannot be satisfied by prose.

    This test was written without it and was VACUOUS: the comment added beside
    the okular fix says the word "okular", so a bare search for the package name
    passed even with the package removed. `verify_user_experience.py` carries the
    same helper for the same reason.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


gate = load("verify_mime_handlers", GATE)


def package_for(desktop: str) -> str:
    if desktop in PACKAGE_OVERRIDES:
        return PACKAGE_OVERRIDES[desktop]
    return desktop[: -len(".desktop")].rsplit(".", 1)[-1]


class ThePromiseIsKeepableOnArm(unittest.TestCase):
    def setUp(self):
        self.handlers = gate.promised_handlers(MIMEAPPS)
        self.arm = code(BUILD_ARM.read_text(encoding="utf-8"))

    def test_the_list_actually_promises_something(self):
        """A parser that silently returns {} would make every test below vacuous."""
        self.assertGreater(len(self.handlers), 5)

    def test_every_first_party_handler_ships_in_the_overlay(self):
        for desktop, mimes in sorted(self.handlers.items()):
            if not desktop.startswith("org.moos."):
                continue
            with self.subTest(desktop=desktop):
                self.assertTrue(
                    (ROOT / "system_files/usr/share/applications" / desktop).is_file(),
                    f"{desktop} is promised for {', '.join(sorted(set(mimes)))} but MoOS "
                    f"does not ship it")

    def test_the_arm_build_names_every_third_party_handler_it_promises(self):
        """The ARM base ships no KDE apps, so an unnamed package is an absent app.

        This is the exact assertion that would have caught okular before it
        reached a release.
        """
        for desktop, mimes in sorted(self.handlers.items()):
            if desktop.startswith("org.moos."):
                continue
            package = package_for(desktop)
            with self.subTest(desktop=desktop, package=package):
                self.assertRegex(
                    self.arm, rf"(?m)(^|\s){re.escape(package)}(\s|$)",
                    f"build-arm.sh never installs '{package}', but mimeapps.list "
                    f"promises {desktop} for {', '.join(sorted(set(mimes)))}. On ARM "
                    f"nothing arrives unasked, so that type would open in whatever the "
                    f"user happens to have installed, or in nothing at all")


class TheImageGateStaysWired(unittest.TestCase):
    def test_the_gate_exists_and_is_executable(self):
        self.assertTrue(GATE.is_file())
        self.assertTrue(GATE.stat().st_mode & 0o111, "the build calls it directly")

    def test_both_build_scripts_run_it(self):
        """The in-image check is the authoritative one; neither edition may skip it."""
        for script in (BUILD_X86, BUILD_ARM):
            with self.subTest(script=script.name):
                self.assertIn("python3 /ctx/verify_mime_handlers.py",
                              code(script.read_text(encoding="utf-8")),
                              f"{script.name} must run the handler gate, or that "
                              f"edition can ship a promise it cannot keep")


class TheGateReadsWhatItClaimsTo(unittest.TestCase):
    """The gate is only worth wiring in if its reader and its verdict are right."""

    def _write(self, tmp: Path, body: str) -> Path:
        (tmp / "etc/xdg").mkdir(parents=True, exist_ok=True)
        (tmp / "etc/xdg/mimeapps.list").write_text(body, encoding="utf-8")
        return tmp

    def test_comments_groups_and_blank_lines_are_not_handlers(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = self._write(Path(raw), "# a comment=x.desktop\n\n[Default Applications]\n"
                                          "application/pdf=org.kde.okular.desktop\n")
            found = gate.promised_handlers(root / "etc/xdg/mimeapps.list")
            self.assertEqual(list(found), ["org.kde.okular.desktop"])

    def test_a_multi_handler_line_promises_every_one_of_them(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = self._write(Path(raw),
                               "[Default Applications]\n"
                               "application/pdf=a.desktop;b.desktop;\n")
            self.assertEqual(sorted(gate.promised_handlers(root / "etc/xdg/mimeapps.list")),
                             ["a.desktop", "b.desktop"])

    def test_a_repeated_key_across_groups_does_not_crash_the_reader(self):
        """configparser raises DuplicateOptionError here; mimeapps.list allows it."""
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = self._write(Path(raw),
                               "[Default Applications]\napplication/pdf=a.desktop\n"
                               "[Added Associations]\napplication/pdf=b.desktop\n")
            self.assertEqual(sorted(gate.promised_handlers(root / "etc/xdg/mimeapps.list")),
                             ["a.desktop", "b.desktop"])

    def test_a_present_handler_passes_and_an_absent_one_is_reported_with_its_types(self):
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = self._write(Path(raw), "[Default Applications]\n"
                                          "application/pdf=there.desktop\n"
                                          "text/plain=gone.desktop\n")
            apps = root / "usr/share/applications"
            apps.mkdir(parents=True)
            (apps / "there.desktop").write_text("[Desktop Entry]\n", encoding="utf-8")
            handlers = gate.promised_handlers(root / "etc/xdg/mimeapps.list")
            absent = gate.missing(root, handlers)
            self.assertEqual([name for name, _ in absent], ["gone.desktop"])
            self.assertEqual(absent[0][1], ["text/plain"])

    def test_a_flatpak_exported_handler_counts_as_present(self):
        """Store apps land in the flatpak export dir, not /usr/share/applications."""
        import tempfile
        with tempfile.TemporaryDirectory() as raw:
            root = self._write(Path(raw), "[Default Applications]\napplication/pdf=f.desktop\n")
            exported = root / "var/lib/flatpak/exports/share/applications"
            exported.mkdir(parents=True)
            (exported / "f.desktop").write_text("[Desktop Entry]\n", encoding="utf-8")
            handlers = gate.promised_handlers(root / "etc/xdg/mimeapps.list")
            self.assertEqual(gate.missing(root, handlers), [])


if __name__ == "__main__":
    unittest.main()
