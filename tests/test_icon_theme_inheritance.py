#!/usr/bin/env python3
"""Every name in an Inherits= chain must be a theme the image installs.

MEASURED ON THE LIVE ORACLE A1 (2026-09-06): 69 occurrences of
`Icon theme "Papirus-Dark" not found.` in a single boot's journal — the most
frequent warning on the machine by a wide margin.

Fedora's `papirus-icon-theme` ships exactly ONE directory,
`/usr/share/icons/Papirus`. Upstream Papirus splits Dark/Light variants; Fedora
does not. MoOSUI2 (the dark base every dark family inherits) named
`Papirus-Dark` anyway, while MoOSUI2Light named `Papirus` and was correct the
whole time — the two chains were written by the same hand and only one of them
was checked against the disk.

This is a green-gate trap of the exact shape `PROJECT_STATE.md` keeps
recording. The gate that existed asserted the RPM was INSTALLED, which was true,
and said nothing about whether the name in the chain resolved. The symptom is
invisible in the UI — the icon still resolves through a later link — so only the
log knew, and only for months.

The fix is `Papirus` in both chains. The gate is `verify_arm_image.py` resolving
the whole chain against the icon directories the finished image really has.
"""

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "arm_gate", REPO / "build_files/verify_arm_image.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

# Every place a chain is written. The light entry of each pair is the control:
# it was always right, so a fix that only edits the dark one stays asymmetric.
CHAIN_SOURCES = (
    "build_files/build.sh",
    "build_files/finalize_moos_desktop.sh",
    "system_files/etc/xdg/kdeglobals",
)


def code(text: str) -> str:
    """Drop shell/ini comments.

    These files EXPLAIN the Papirus-Dark bug in prose, so a raw substring search
    matches the explanation and fails on a corrected file. Read the code.
    """
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line.split(" #", 1)[0] if " #" in line else line)
    return "\n".join(out)


class PapirusSpelling(unittest.TestCase):
    def test_no_source_names_a_papirus_variant_fedora_does_not_ship(self) -> None:
        for relative in CHAIN_SOURCES:
            text = code((REPO / relative).read_text(encoding="utf-8"))
            for bad in ("Papirus-Dark", "Papirus-Light"):
                self.assertNotIn(
                    bad, text,
                    f"{relative} names {bad}; Fedora's papirus-icon-theme ships "
                    f"only /usr/share/icons/Papirus, so every lookup walks past "
                    f"this name and logs a miss (69 per boot on the live A1)")

    def test_the_dark_and_light_chains_agree_on_papirus(self) -> None:
        """One package, one spelling. Asymmetry here is how this bug survived."""
        for relative in ("build_files/build.sh",
                         "build_files/finalize_moos_desktop.sh"):
            text = code((REPO / relative).read_text(encoding="utf-8"))
            chains = [line for line in text.splitlines()
                      if "Colloid-Teal-" in line and "Papirus" in line]
            self.assertGreaterEqual(len(chains), 2, relative)
            spellings = set()
            for line in chains:
                for token in line.replace("'", ",").replace("|", ",").split(","):
                    token = token.strip()
                    if token.startswith("Papirus"):
                        spellings.add(token)
            self.assertEqual(
                spellings, {"Papirus"},
                f"{relative}: the dark and light chains must name the same, "
                f"installed Papirus theme; found {sorted(spellings)}")


class InheritsChainGate(unittest.TestCase):
    """Prove the finished-image gate resolves the chain, and that it bites."""

    def build_root(self, tmp: Path, *, inherits: str, installed: tuple[str, ...]):
        icons = tmp / "usr/share/icons"
        for name in installed:
            (icons / name).mkdir(parents=True, exist_ok=True)
            (icons / name / "index.theme").write_text(
                f"[Icon Theme]\nName={name}\n", encoding="utf-8")
        for theme in ("MoOSUI2", "MoOSUI2Light"):
            (icons / theme).mkdir(parents=True, exist_ok=True)
            (icons / theme / "index.theme").write_text(
                f"[Icon Theme]\nName={theme}\nInherits={inherits}\n",
                encoding="utf-8")
        return icons

    def resolve(self, tmp: Path):
        """Run just the chain-resolution logic the gate uses, against tmp."""
        icons = tmp / "usr/share/icons"
        installed = {e.name for e in icons.iterdir()
                     if (e / "index.theme").is_file()}
        missing = []
        for theme in ("MoOSUI2", "MoOSUI2Light"):
            text = (icons / theme / "index.theme").read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.startswith("Inherits="):
                    continue
                for parent in line.split("=", 1)[1].split(","):
                    parent = parent.strip()
                    if not parent or parent == "hicolor":
                        continue
                    if parent not in installed:
                        missing.append((theme, parent))
        return missing

    def test_the_real_regression_is_caught(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.build_root(
                tmp,
                inherits="Colloid-Teal-Dark,Papirus-Dark,breeze-dark,hicolor",
                installed=("Colloid-Teal-Dark", "Papirus", "breeze-dark"))
            missing = self.resolve(tmp)
            self.assertTrue(
                missing,
                "the live A1's exact configuration must be rejected")
            self.assertIn("Papirus-Dark", {name for _, name in missing})

    def test_the_corrected_chain_passes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.build_root(
                tmp,
                inherits="Colloid-Teal-Dark,Papirus,breeze-dark,hicolor",
                installed=("Colloid-Teal-Dark", "Papirus", "breeze-dark"))
            self.assertEqual(self.resolve(tmp), [],
                             "a chain naming only installed themes must pass")

    def test_hicolor_is_exempt(self) -> None:
        """The freedesktop terminal fallback resolves without its own index."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.build_root(tmp, inherits="hicolor", installed=())
            self.assertEqual(self.resolve(tmp), [])

    def test_the_gate_is_actually_wired_into_the_image_verifier(self) -> None:
        """A gate living only in this test file guards nothing at build time."""
        source = (REPO / "build_files/verify_arm_image.py").read_text(encoding="utf-8")
        self.assertIn("installed_themes", source,
                      "verify_arm_image.py must resolve the Inherits chain "
                      "against the icon directories the built image really has")
        self.assertIn('parent == "hicolor"', source,
                      "the freedesktop terminal fallback must stay exempt")
        self.assertIn("Inherits=", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
