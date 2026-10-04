#!/usr/bin/env python3
"""Gate: everything MoOS teaches or lets Mira do has a name in both languages in her window.

WHAT THIS PREVENTS

MoOS declares the assistant's tools and playbooks once, in `moai_tool_schemas.py`. Mira shows them
with her own words: `mira/moai_tools.py` holds a title for every tool, and her System page holds
one for every playbook (`sy_sk_<id>`). A tool or playbook added on the MoOS side without those
words still works — and appears in an Arabic window as `oracle-cloud-workstation` or
`desktop size`, the raw identifier.

Mira's own suites check this in the image build, twenty minutes into it. The tool titles are
checked for real there, because the stage receives the schema file. The playbook words were not:
her check listed the playbook FOLDER, which the stage does not receive, so it passed on nothing,
and the `oracle-cloud-workstation` playbook reached `main` on 2026-10-04 with no words, green
everywhere. Her check now reads SKILLS from the schema file too; this gate says the same thing in
a second, in `just check`.

This reads both trees without importing Mira (her modules need PySide6 and her pinned packages,
which a repository gate does not have).
"""

from __future__ import annotations

import ast
import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "system_files/usr/lib/moai/moai_tool_schemas.py"
SKILLS_DIR = ROOT / "system_files/usr/share/moos/moai/skills"
MIRA_TITLES = ROOT / "mira/moai_tools.py"
MIRA_SYSTEM_PAGE = ROOT / "mira/pages/system.py"
ARABIC = re.compile("[؀-ۿ]")


def declared():
    spec = importlib.util.spec_from_file_location("moai_tool_schemas_for_mira_names", SCHEMAS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def literal_dict(path: Path, name: str) -> dict:
    """A module-level `NAME = {...}` read as data, without running the module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else \
            [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.relative_to(ROOT)} has no literal {name}")


class MiraNamesWhatMoosDeclares(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = declared()
        cls.tools = sorted(t["function"]["name"] for t in cls.module.ALL_TOOLS)
        cls.skills = sorted(cls.module.SKILLS)

    def test_every_tool_has_a_title_in_both_languages(self):
        arabic = literal_dict(MIRA_TITLES, "TITLES_AR")
        english = literal_dict(MIRA_TITLES, "TITLES_EN")
        self.assertGreaterEqual(len(self.tools), 50, "the schema list did not load")
        for name in self.tools:
            self.assertIn(name, arabic, f"{name}: Mira would show the identifier in Arabic")
            self.assertIn(name, english, f"{name}: Mira would show the identifier in English")
            self.assertTrue(arabic[name].strip() and english[name].strip(), name)
            self.assertIsNone(ARABIC.search(english[name]), f"{name}: Arabic in the English title")
            self.assertTrue(ARABIC.search(arabic[name]) or arabic[name].startswith("Mo "),
                            f"{name}: the Arabic title is not Arabic")

    def test_every_playbook_has_words_on_the_system_page(self):
        strings = literal_dict(MIRA_SYSTEM_PAGE, "STRINGS")
        shipped = sorted(p.stem for p in SKILLS_DIR.glob("*.md"))
        self.assertEqual(shipped, self.skills, "the shipped playbooks and SKILLS disagree")
        for skill in self.skills:
            key = "sy_sk_" + skill
            self.assertIn(key, strings, f"{skill}: the System page would show the raw id")
            arabic, english = strings[key]
            self.assertTrue(ARABIC.search(arabic), f"{key}: no Arabic words")
            self.assertTrue(english.strip() and not ARABIC.search(english), f"{key}: no English words")

    def test_miras_own_check_reads_the_playbooks_from_what_her_build_stage_has(self):
        """The image build copies the schema FILE into Mira's test stage and not the playbook
        folder, so a check that lists the folder passes there on nothing. Her own suite must take
        the playbooks from SKILLS in that file, which the stage does have."""
        for containerfile in ("Containerfile", "Containerfile.arm"):
            text = (ROOT / containerfile).read_text(encoding="utf-8")
            start = text.index(" AS mira-build")
            stage = text[start:text.index("\nFROM ", start)]
            self.assertIn("system_files/usr/lib/moai/moai_tool_schemas.py", stage,
                          f"{containerfile}: Mira's stage no longer receives the schema file")
        suite = (ROOT / "mira/test_page_system.py").read_text(encoding="utf-8")
        self.assertIn("shipped |= set(schemas.SKILLS)", suite,
                      "Mira's system-page suite lists only the playbook folder again")


if __name__ == "__main__":
    unittest.main(verbosity=1)
