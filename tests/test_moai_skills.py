#!/usr/bin/env python3
"""Gate: every Mo AI skill is true about this system — each step is a tool that exists.

WHY THIS EXISTS

Mo AI's brain is whatever free cloud model answers today. It knows a great deal about computers
in general and nothing about this one: that sound here is three user services, that `/` always
reads 100% full because it is a read-only image, that an update is staged and the previous
version is kept, that there IS a repair for sound and there is NOT one for an arbitrary service.
Left to guess, such a model recommends terminal commands for a different kind of system, or
presses the one repair it has heard of.

A skill is a playbook the image ships (usr/share/moos/moai/skills/<id>.md): what to look at
first, which repair exists, when to stop and say so. The model finds them with `list_skills` and
reads one with `read_skill` — two read-only tools of the same closed-grammar, redacting reader as
every other inspection. A skill grants nothing: each step is one of the existing tools, under
that tool's own confirmation rule.

A playbook that names a tool that does not exist, an argument the tool does not take, or a value
outside its enum is worse than no playbook: the model follows it faithfully into an error, or
learns to ignore playbooks. So this gate reads every skill the way the model will:

  * the shipped files and the `read_skill` enum are the same set, in both directions;
  * every `tool` call written in a skill is a real tool, every `key=value` after it is a real
    parameter with a value its schema accepts, every skill it points to exists, every unit name
    has the shape the reader enforces;
  * a skill never hands the model a shell command, never names another system (the identity
    contract reaches the model's mouth too), and says "asks first" when it uses a tool that does;
  * the REAL reader lists them all, returns each one unredacted and untruncated, and refuses
    anything that is not an id — including a link planted in the skills directory.
"""

from __future__ import annotations

import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "system_files/usr/share/moos/moai/skills"
INSPECT = ROOT / "system_files/usr/bin/moos-inspect"
SUPPORT = ROOT / "system_files/usr/libexec/moos-support-bundle"
MOAI = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
SCHEMAS = runpy.run_path(str(ROOT / "system_files/usr/lib/moai/moai_tool_schemas.py"))
TOOLS = {tool["function"]["name"]: tool["function"] for tool in SCHEMAS["ALL_TOOLS"]}
FOREIGN = runpy.run_path(str(ROOT / "tests/test_user_visible_identity.py"))["FOREIGN"]

FIELDS = ("id", "title_en", "title_ar", "use_when")
CALL = re.compile(r"`([a-z]+(?:_[a-z]+)+)`((?:\s+[a-z_]+=(?:`[^`]*`|<[^>]+>|[A-Za-z0-9]+))*)")
ARGUMENT = re.compile(r"([a-z_]+)=(?:`([^`]*)`|(<[^>]+>)|([A-Za-z0-9]+))")
UNIT = re.compile(SCHEMAS["_UNIT_PARAM"]["pattern"])
# A playbook gives the model TOOLS. A command line in it is an instruction to bypass them.
COMMANDS = re.compile(r"\b(sudo|pkexec|systemctl|journalctl|rpm-ostree|bootc|dnf|yum|apt(?:-get)?|pacman|"
                      r"flatpak\s+(?:install|remove|uninstall|update)|chmod|chown|rm\s+-|curl|wget)\b")


def parse(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: no front matter"
    head, body = text[4:].split("\n---\n", 1)
    meta = dict((key.strip(), value.strip()) for key, _, value in
                (line.partition(":") for line in head.splitlines()))
    return meta, body.strip()


SKILLS = {path.stem: parse(path) for path in sorted(SKILLS_DIR.glob("*.md"))}


class ShippedSet(unittest.TestCase):
    def test_the_enum_and_the_files_are_the_same_set(self) -> None:
        self.assertGreaterEqual(len(SKILLS), 10)
        self.assertEqual(sorted(SKILLS), sorted(SCHEMAS["SKILLS"]),
                         "a shipped skill the model cannot ask for, or an enum value with no file")
        self.assertEqual(TOOLS["read_skill"]["parameters"]["properties"]["name"]["enum"],
                         list(SCHEMAS["SKILLS"]))
        for name in ("list_skills", "read_skill"):
            self.assertEqual(SCHEMAS["TOOL_META"][name]["category"], SCHEMAS["READ_ONLY"])
            self.assertEqual(SCHEMAS["TOOL_META"][name]["executor"], "moos-inspect")
            self.assertFalse(SCHEMAS["needs_confirmation"](name, {"name": "no-sound"}))

    def test_front_matter_is_complete_and_bilingual(self) -> None:
        for skill, (meta, body) in SKILLS.items():
            with self.subTest(skill=skill):
                self.assertEqual(sorted(meta), sorted(FIELDS))
                self.assertEqual(meta["id"], skill, "the id is the file name; the reader lists by it")
                self.assertRegex(meta["title_ar"], r"[؀-ۿ]")
                self.assertNotRegex(meta["title_en"], r"[؀-ۿ]")
                self.assertGreaterEqual(len(meta["use_when"]), 40, "say WHEN, in a full sentence")
                self.assertIn("## Steps", body)
                self.assertRegex(body, r"(?m)^## (Look first|Know this first)")
                # One tool result is bounded at 12 KB; a playbook must arrive whole.
                self.assertLess(len(body.encode("utf-8")), 6000)


class EveryStepIsReal(unittest.TestCase):
    def test_every_tool_call_matches_the_schema(self) -> None:
        referenced: set[str] = set()
        for skill, (_meta, body) in SKILLS.items():
            for name, arguments in CALL.findall(body):
                with self.subTest(skill=skill, tool=name):
                    self.assertIn(name, TOOLS, f"{skill} tells the model to use `{name}`, which does not exist")
                    referenced.add(name)
                    properties = TOOLS[name]["parameters"].get("properties", {})
                    for key, quoted, placeholder, bare in ARGUMENT.findall(arguments):
                        self.assertIn(key, properties, f"`{name}` takes no `{key}`")
                        if placeholder:
                            continue
                        value, spec = quoted or bare, properties[key]
                        if "enum" in spec:
                            self.assertIn(value, spec["enum"], f"`{name}` {key}={value}")
                        if "pattern" in spec:
                            self.assertRegex(value, spec["pattern"], f"`{name}` {key}={value}")
                        if spec["type"] == "boolean":
                            self.assertIn(value, ("true", "false"))
                        if spec["type"] == "integer":
                            self.assertTrue(spec["minimum"] <= int(value) <= spec["maximum"])
        # The playbooks exist to make the inspection tools and the fixed repairs USED.
        for essential in ("read_journal", "unit_status", "list_failed_units", "disk_status", "os_state",
                          "fix_audio", "net_doctor", "optimize_system", "system_update", "system_rollback"):
            self.assertIn(essential, referenced, f"no skill ever reaches for `{essential}`")

    def test_anything_shaped_like_a_tool_is_one(self) -> None:
        for skill, (_meta, body) in SKILLS.items():
            for token in re.findall(r"`([^`\n]+)`", body):
                with self.subTest(skill=skill, token=token):
                    if re.fullmatch(r"[a-z]+(?:_[a-z]+)+", token):
                        self.assertIn(token, TOOLS, f"`{token}` reads like a tool and is not one")
                    if re.search(r"\.(service|timer|socket|target)$", token):
                        self.assertRegex(token, UNIT)

    def test_every_skill_it_points_to_exists(self) -> None:
        for skill, (_meta, body) in SKILLS.items():
            for target in re.findall(r"skill `([^`]+)`", body):
                self.assertIn(target, SKILLS, f"{skill} sends the model to a skill that is not shipped")
                self.assertNotEqual(target, skill, f"{skill} points at itself")

    def test_a_skill_gives_tools_never_command_lines(self) -> None:
        for skill, (meta, body) in SKILLS.items():
            with self.subTest(skill=skill):
                hit = COMMANDS.search(body)
                self.assertIsNone(hit, f"{skill} hands the model a command: {hit.group(0) if hit else ''}")
                foreign = FOREIGN.search(body + " " + " ".join(meta.values()))
                self.assertIsNone(foreign, f"{skill} names another system: {foreign.group(0) if foreign else ''}")

    def test_a_repair_that_asks_is_described_as_asking(self) -> None:
        confirm = set(SCHEMAS["CONFIRM_NAMES"])
        for skill, (_meta, body) in SKILLS.items():
            used = {name for name, _ in CALL.findall(body)} & confirm
            if used:
                self.assertRegex(body, r"asks (first|for confirmation|the person|them)",
                                 f"{skill} uses {sorted(used)} and never says the person is asked")


@unittest.skipUnless(sys.platform.startswith("linux"), "runs the real reader")
class TheRealReader(unittest.TestCase):
    def inspect(self, *argv: str, script: Path = INSPECT) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(script), *argv], capture_output=True, text=True,
                              encoding="utf-8", timeout=60, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8",
                                                                  "HOME": tempfile.gettempdir()})

    def test_it_lists_every_skill_with_when_to_use_it(self) -> None:
        done = self.inspect("skills")
        self.assertEqual(done.returncode, 0, done.stderr)
        for skill, (meta, _body) in SKILLS.items():
            self.assertIn(f"{skill} — {meta['use_when']}", done.stdout)
        self.assertNotIn("[redacted]", done.stdout)

    def test_each_skill_arrives_whole_and_unchanged(self) -> None:
        for skill, (meta, body) in SKILLS.items():
            with self.subTest(skill=skill):
                done = self.inspect("skill", skill)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stdout, f"## skill {skill}: {meta['title_en']}\n{body}\n",
                                 "the redactor or the size bound changed a playbook on its way to the model")

    def test_only_an_id_is_accepted(self) -> None:
        for bad in ("../no-sound", "/etc/passwd", "no-sound.md", "NO-SOUND", "no sound", "nope", "", "--all"):
            with self.subTest(name=bad):
                done = self.inspect("skill", bad)
                self.assertEqual(done.returncode, 2, f"{bad!r}: {done.stdout[:80]}")
                self.assertEqual(done.stdout, "")

    def test_a_link_planted_among_the_skills_is_not_a_skill(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw) / "usr"
            (tree / "bin").mkdir(parents=True)
            (tree / "libexec").mkdir()
            skills = tree / "share/moos/moai/skills"
            shutil.copytree(SKILLS_DIR, skills)
            shutil.copy(INSPECT, tree / "bin/moos-inspect")
            shutil.copy(SUPPORT, tree / "libexec/moos-support-bundle")
            secret = Path(raw) / "secret.md"
            secret.write_text("---\nid: planted\ntitle_en: x\ntitle_ar: x\nuse_when: never, this is a planted file\n---\nTOP SECRET\n")
            (skills / "planted.md").symlink_to(secret)
            listed = self.inspect("skills", script=tree / "bin/moos-inspect")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn("no-sound", listed.stdout)
            self.assertNotIn("planted", listed.stdout)
            read = self.inspect("skill", "planted", script=tree / "bin/moos-inspect")
            self.assertEqual(read.returncode, 2)
            self.assertNotIn("TOP SECRET", read.stdout + read.stderr)


@unittest.skipUnless(sys.platform.startswith("linux"), "runs the real reader")
class TheImageGate(unittest.TestCase):
    def test_the_image_gates_own_check_passes_on_this_tree_and_can_fail(self) -> None:
        """The image build runs skills_are_readable(""); run the SAME code here first (plan P0.9)."""
        import ast

        gate = (ROOT / "build_files/verify_image_experience.py").read_text(encoding="utf-8")
        function = next(node for node in ast.parse(gate).body
                        if isinstance(node, ast.FunctionDef) and node.name == "skills_are_readable")
        scope: dict = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "verify_image_experience.py", "exec"), scope)
        self.assertEqual(scope["skills_are_readable"](str(ROOT / "system_files")), [])
        self.assertIn('skills_are_readable("")', gate, "the image build no longer calls the check")

        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw)
            for part in ("usr/bin", "usr/libexec", "usr/lib/moai"):
                (tree / part).mkdir(parents=True)
            shutil.copy(INSPECT, tree / "usr/bin/moos-inspect")
            shutil.copy(SUPPORT, tree / "usr/libexec/moos-support-bundle")
            shutil.copy(ROOT / "system_files/usr/lib/moai/moai_tool_schemas.py", tree / "usr/lib/moai")
            shutil.copytree(SKILLS_DIR, tree / "usr/share/moos/moai/skills")
            (tree / "usr/share/moos/moai/skills/no-sound.md").unlink()
            problems = scope["skills_are_readable"](str(tree))
        self.assertTrue(any("no-sound" in problem for problem in problems),
                        f"a skill missing from the image went unnoticed: {problems}")


class TheModelIsTold(unittest.TestCase):
    def test_the_system_prompt_sends_the_model_to_the_skills(self) -> None:
        prompt = MOAI.read_text(encoding="utf-8")
        for needle in ("SKILLS:", "list_skills", "read_skill", "A skill gives you no new powers"):
            self.assertIn(needle, prompt)

    def test_every_chip_on_the_home_screen_leads_to_a_shipped_skill(self) -> None:
        qml = MOAI.read_text(encoding="utf-8")
        block = qml[qml.index("readonly property var skillChips: ["):]
        block = block[:block.index("\n    ]")]
        chips = re.findall(r'\{ skill: "([^"]+)", icon: "([^"]+)", ar: "([^"]+)", en: "([^"]+)",\s*'
                           r'send: root\.local\("([^"]+)", "([^"]+)"\) \}', block)
        self.assertGreaterEqual(len(chips), 6, "the home screen lost its skill chips (or their shape changed)")
        self.assertEqual(len(chips), block.count("{ skill:"), "a chip this gate cannot read")
        icons = ROOT / "system_files/usr/share/icons/hicolor/scalable/actions"
        for skill, icon, ar, en, send_ar, send_en in chips:
            with self.subTest(chip=en):
                self.assertIn(skill, SKILLS, f"the chip “{en}” promises help no playbook backs")
                self.assertTrue((icons / f"{icon}.svg").is_file(), f"{icon} is not a shipped MoOS glyph")
                self.assertRegex(ar, r"[؀-ۿ]")
                self.assertRegex(send_ar, r"[؀-ۿ]")
                # A chip speaks as the person would; ids and tool names are the model's business.
                for text in (ar, en, send_ar, send_en):
                    self.assertNotIn(skill, text)
                    self.assertNotRegex(text, r"[a-z]+_[a-z]+")
        self.assertEqual(len({chip[0] for chip in chips}), len(chips), "two chips for one skill")


if __name__ == "__main__":
    unittest.main(verbosity=2)
