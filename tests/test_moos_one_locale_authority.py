#!/usr/bin/env python3
"""One question, one answer: is this session Arabic?

MoOS asked it in four different ways and got two different answers, and the
visible result was that the Command Center — the flagship first-party app —
rendered its ENTIRE interface in English on an Arabic-first operating system,
while the launcher sitting next to it in the same panel was correctly Arabic.

Measured with a QML probe through moos-qml-shell on the live session
(LANG=ar_SA.UTF-8, LANGUAGE=ar, Qt.locale().name == "ar_SA"):

    Qt.locale().textDirection === Qt.RightToLeft       ->  true
    Qt.application.layoutDirection === Qt.RightToLeft  ->  false

`Qt.application.layoutDirection` follows the installed TRANSLATOR, not the
locale. MoOS's QML apps carry their own bilingual strings via a `local(ar, en)`
helper instead of Qt translation catalogues, so no translator is ever installed
and that property is LeftToRight on every MoOS session, Arabic included.

What each surface used before this gate:

    settings    Qt.application.layoutDirection   BROKEN — English on Arabic
    installer   Qt.application.layoutDirection   BROKEN — first-run screen
    welcome     Qt.application.layoutDirection   BROKEN — first-run screen
    moai        …|| Qt.application.layoutDirection  BROKEN at the fallback
    store       Qt.locale().textDirection        correct
    launcher    Qt.locale().textDirection        correct
    heroclock / island / nova.clock              correct

Two of the broken ones are the installer and the welcome screen: the very first
thing a person sees on an Arabic install opened in English.

The fix is not "use the right expression in nine places" — that is the same bug
waiting to happen a tenth time. It is one authority, `org.moos.ui`'s `Locale`
singleton, which every surface imports. This gate holds that shape.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "system_files/usr/lib64/qt6/qml/org/moos/ui"
SURFACES = sorted(
    list((REPO / "system_files/usr/share/moos/apps").glob("*/main.qml"))
    + list((REPO / "system_files/usr/share/plasma/plasmoids").glob("*/contents/ui/main.qml"))
)

# The expression that silently answers "English" on an Arabic session.
BROKEN = "Qt.application.layoutDirection"
# Correct, but only the singleton is allowed to use it.
RAW_LOCALE = "Qt.locale().textDirection"


def qml_code(text: str) -> str:
    """Strip comments: these files now EXPLAIN the broken expression by name."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(l for l in without_blocks.splitlines()
                     if not l.lstrip().startswith("//"))


class OneAuthority(unittest.TestCase):
    def test_there_are_surfaces_to_check(self) -> None:
        self.assertGreaterEqual(len(SURFACES), 8, f"only found {SURFACES}")

    def test_no_surface_uses_the_broken_expression(self) -> None:
        for path in SURFACES:
            with self.subTest(surface=path.parent.name):
                self.assertNotIn(
                    BROKEN, qml_code(path.read_text(encoding="utf-8")),
                    f"{path.parent.name} reads {BROKEN}, which follows an "
                    f"installed translator rather than the locale and is "
                    f"LeftToRight on every MoOS session — including Arabic ones.")

    def test_only_the_singleton_reads_the_locale_directly(self) -> None:
        """Nine surfaces each doing it correctly is still nine places to break."""
        for path in SURFACES:
            with self.subTest(surface=path.parent.name):
                self.assertNotIn(
                    RAW_LOCALE, qml_code(path.read_text(encoding="utf-8")),
                    f"{path.parent.name} computes direction itself; it must "
                    f"read MoUI.Locale so there is one answer, not nine.")

    def test_the_singleton_exists_and_is_registered(self) -> None:
        locale = MODULE / "Locale.qml"
        self.assertTrue(locale.is_file(), "org.moos.ui Locale singleton is missing")
        body = qml_code(locale.read_text(encoding="utf-8"))
        self.assertIn("pragma Singleton", body)
        self.assertIn(RAW_LOCALE, body, "the singleton must read the LOCALE")
        self.assertNotIn(BROKEN, body)
        self.assertRegex(body, r"function local\(\s*ar\s*,\s*en\s*\)")
        qmldir = (MODULE / "qmldir").read_text(encoding="utf-8")
        self.assertIn("singleton Locale 1.0 Locale.qml", qmldir)

    def test_every_surface_that_needs_direction_imports_the_module(self) -> None:
        for path in SURFACES:
            body = qml_code(path.read_text(encoding="utf-8"))
            if "MoUI.Locale" not in body:
                continue
            with self.subTest(surface=path.parent.name):
                self.assertRegex(body, r"import org\.moos\.ui as MoUI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
