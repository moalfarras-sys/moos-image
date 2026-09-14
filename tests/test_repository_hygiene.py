#!/usr/bin/env python3
"""Keep the repository's current-document and artwork boundary executable."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RETIRED = (
    "MOOS_ROADMAP.md",
    "MO_AI_ARCHITECTURE.md",
    "artwork/MOOS_HORIZON_BAR_DESIGN.md",
    "artwork/UTM-INSTALLER-README.txt",
    "artwork/generated",
    "artwork/moos-ui",
    "docs/MOOS_COMPLETION_PLAN.md",
    "docs/MOOS_DESIGN_PLAN.md",
    "docs/MOOS_SYSTEM_DEVELOPMENT_PLAN.md",
    "docs/MOOS_UNIFIED_PLATFORM.md",
    "docs/MOOS_VISUAL_ROADMAP.md",
    "docs/MOOS_X86_SYSTEM_PLAN.md",
    "docs/MO_PC_REMOTE_ARCHITECTURE.md",
    "docs/REMOTE_V40_CLOUD_DESKTOP.md",
    "docs/evidence",
    "moremote/docs/ROOT_CAUSE_INPUT.md",
)


class RepositoryHygiene(unittest.TestCase):
    def test_retired_documents_and_artwork_do_not_return(self) -> None:
        for relative in RETIRED:
            self.assertFalse((ROOT / relative).exists(), f"retired path returned: {relative}")

    def test_current_state_stays_a_state_file_not_a_session_diary(self) -> None:
        lines = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(len(lines), 200, "PROJECT_STATE.md must remain concise")

    def test_markdown_relative_links_resolve(self) -> None:
        missing = []
        for document in ROOT.rglob("*.md"):
            if any(part in {".git", "build", "node_modules"} for part in document.parts):
                continue
            text = document.read_text(encoding="utf-8", errors="replace")
            for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
                target = raw.strip().strip("<>").split("#", 1)[0]
                if not target or target.startswith(("/", "http://", "https://", "mailto:", "app://")):
                    continue
                if not (document.parent / target).exists():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [], "broken Markdown links:\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main(verbosity=2)
