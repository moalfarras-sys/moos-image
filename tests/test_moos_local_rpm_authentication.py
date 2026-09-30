#!/usr/bin/env python3
"""Gate: the administrator question, and a dismissed one, are MoOS's own words.

WHAT WAS MEASURED

On 2026-09-18 the local-RPM route was walked on the running station with a real
signed package (the pointer-driven half of the station review). Two things the
owner sees were not MoOS's:

  * the polkit prompt read "Authentication is needed to run
    `/usr/libexec/moos-install-local-rpm /var/home/... f1bf5962...' as the super
    user" — English, with a helper path and a truncated digest, inside an Arabic
    session;
  * pressing Cancel printed pkexec's own "Error executing command as another
    user: Not authorized" and "This incident has been reported." ABOVE MoOS's
    truthful bilingual line, reading like an accusation for a choice the owner
    had just made.

Nothing about the privilege boundary changes here: the action still demands an
administrator on every path, and the root helper repeats every check afterwards.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "system_files/usr/share/polkit-1/actions/org.moos.install-local-rpm.policy"
HELPER = ROOT / "system_files/usr/libexec/moos-install-local-rpm"
MOAI_DO = ROOT / "system_files/usr/bin/moai-do"
ROUTER = ROOT / "system_files/usr/bin/moos-open"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"
PKEXEC_NOISE = ("Error executing command as another user: Not authorized",
                "This incident has been reported.")


def function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    return source[start:source.index("\n}\n", start) + 3]


class AuthenticationPrompt(unittest.TestCase):
    """The question pkexec asks is about the package, in the owner's language."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ElementTree.parse(POLICY)
        actions = cls.tree.getroot().findall("action")
        assert len(actions) == 1, "one action, so the annotated path is unambiguous"
        cls.action = actions[0]

    def test_the_action_is_the_one_pkexec_finds_for_the_helper(self):
        self.assertEqual(self.action.get("id"), "org.moos.install-local-rpm")
        annotations = {node.get("key"): (node.text or "").strip()
                       for node in self.action.findall("annotate")}
        self.assertEqual(annotations.get("org.freedesktop.policykit.exec.path"),
                         "/usr/libexec/moos-install-local-rpm",
                         "pkexec matches the action by the program it is asked to run")
        self.assertTrue(HELPER.exists(), "the annotated helper must exist in the image")

    def test_the_owner_reads_the_question_in_their_own_language(self):
        languages = {node.get("{http://www.w3.org/XML/1998/namespace}lang")
                     for node in self.action.findall("message")}
        self.assertIn(None, languages, "an English message for a session with no match")
        self.assertIn("ar", languages, "the station's own session is Arabic")
        for node in self.action.findall("message"):
            text = (node.text or "").strip()
            self.assertGreater(len(text), 30, "say what is happening, not a path")
            self.assertNotIn("/usr/libexec", text)
            self.assertNotIn("super user", text)
        arabic = [node.text for node in self.action.findall("message")
                  if node.get("{http://www.w3.org/XML/1998/namespace}lang") == "ar"][0]
        self.assertIn("MoOS", arabic)
        self.assertTrue(any("؀" <= character <= "ۿ" for character in arabic))

    def test_the_prompt_still_demands_an_administrator(self):
        defaults = self.action.find("defaults")
        for element in ("allow_any", "allow_inactive", "allow_active"):
            self.assertEqual(defaults.findtext(element), "auth_admin",
                             f"{element} must keep asking an administrator")


class DismissedAuthentication(unittest.TestCase):
    """Cancelling is an answer: MoOS says what happened, pkexec does not scold."""

    @classmethod
    def setUpClass(cls):
        cls.source = MOAI_DO.read_text(encoding="utf-8")
        cls.run_priv = function(cls.source, "run_priv")

    def drive(self, script: str, argv: list[str] | None = None):
        """Run the real run_priv against a scripted pkexec."""
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="moos-run-priv-")))
        fake = root / "pkexec"
        fake.write_text(script, encoding="utf-8")
        fake.chmod(0o755)
        probe = root / "probe"
        probe.write_text('Y=""; N=""\n' + self.run_priv
                         + '\nrun_priv ' + " ".join(argv or ["/usr/libexec/moos-install-local-rpm"])
                         + '\necho "status=$?"\n', encoding="utf-8")
        return subprocess.run(
            [BASH, str(probe)], capture_output=True, text=True, timeout=60,
            env=os.environ | {"PATH": f"{root}{os.pathsep}{os.environ.get('PATH', '')}"})

    def test_pkexecs_two_sentences_are_not_what_the_owner_reads(self):
        done = self.drive("#!/usr/bin/bash\n"
                          f'echo "{PKEXEC_NOISE[0]}" >&2\n'
                          f'echo "{PKEXEC_NOISE[1]}" >&2\n'
                          "exit 126\n")
        for sentence in PKEXEC_NOISE:
            self.assertNotIn(sentence, done.stderr)
        self.assertIn("status=126", done.stdout,
                      "the caller must still see the refusal and print its own line")

    def test_everything_else_the_program_says_is_kept(self):
        done = self.drive("#!/usr/bin/bash\n"
                          'echo "rpm-ostree: no space left on device" >&2\n'
                          'echo "staged" \n'
                          "exit 0\n")
        self.assertIn("rpm-ostree: no space left on device", done.stderr)
        self.assertIn("staged", done.stdout)
        self.assertIn("status=0", done.stdout)

    def test_the_route_still_says_the_package_was_not_staged(self):
        install = function(self.source, "do_install_rpm")
        self.assertIn("run_priv /usr/libexec/moos-install-local-rpm", install)
        self.assertIn("لم تُجهَّز الحزمة", install)
        self.assertIn("The package was NOT staged", install)


class PackageFolders(unittest.TestCase):
    """The helper accepts exactly the folders moai-do offered: the same function, both sides.

    moai-do learned the caller's XDG folder names («سطح المكتب») so a package on the owner's real
    desktop is accepted; the root helper must agree, or the owner types his password for a
    package the helper then refuses."""

    def test_the_helper_reads_the_folders_exactly_as_moai_do_does(self):
        helper = HELPER.read_text(encoding="utf-8")
        frontend = MOAI_DO.read_text(encoding="utf-8")
        self.assertEqual(function(helper, "rpm_source_dirs"), function(frontend, "rpm_source_dirs"))
        self.assertIn('rpm_source_dirs "$caller_home" "$caller_uid"', helper,
                      "the helper must ask for the CALLER's folders, never root's")
        self.assertNotIn("XDG_CONFIG_HOME", function(helper, "rpm_source_dirs"),
                         "a root helper must not read the caller's environment")

    def test_the_router_offers_exactly_those_folders_too(self):
        # moos://apps/install-rpm/<file> (Mira's Apps page, Mo AI's picker) is refused or passed
        # on by moos-open first: a folder it did not know would be refused before moai-do was asked.
        router = ROUTER.read_text(encoding="utf-8")
        frontend = MOAI_DO.read_text(encoding="utf-8")
        self.assertEqual(function(router, "rpm_source_dirs"), function(frontend, "rpm_source_dirs"))
        self.assertIn('done < <(rpm_source_dirs "$home" "$(id -u)")', router)
        self.assertNotIn('"$home"/Desktop/*.rpm', router, "the router kept its own folder list")

    def test_the_folder_list_names_only_visible_folders_of_the_home(self):
        home = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="moos-rpm-dirs-")))
        (home / ".config").mkdir()
        (home / ".config" / "user-dirs.dirs").write_text(
            'XDG_DESKTOP_DIR="$HOME/سطح المكتب"\nXDG_DOCUMENTS_DIR="$HOME/.ssh"\n'
            'XDG_DOWNLOAD_DIR="/etc"\nXDG_MUSIC_DIR="$HOME/Music"\n', encoding="utf-8")
        probe = function(HELPER.read_text(encoding="utf-8"), "rpm_source_dirs")
        done = subprocess.run([BASH, "-c", probe + '\nrpm_source_dirs "$1" "$(id -u)"', "probe",
                               str(home)], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.stdout.splitlines(),
                         [f"{home}/Downloads", f"{home}/Desktop", f"{home}/Documents",
                          f"{home}/سطح المكتب"])


if __name__ == "__main__":
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite([loader.loadTestsFromTestCase(AuthenticationPrompt),
                                loader.loadTestsFromTestCase(DismissedAuthentication),
                                loader.loadTestsFromTestCase(PackageFolders)])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
