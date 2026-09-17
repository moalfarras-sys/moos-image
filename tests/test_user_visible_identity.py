#!/usr/bin/env python3
"""Gate: text MoOS itself shows a person may not name another operating system or desktop.

WHY THIS EXISTS

The three image firewalls (verify_identity.py, verify_image_experience.py,
verify_no_foreign_identity.py) defend files, logos and os-release, and they sweep for one family
of words: the base distribution's. Nothing swept for the DESKTOP's name, and nothing read the
strings MoOS's own programs print. An audit on 2026-09-17 found, all shipping, all green:

  * Mo AI's Apps panel warned that a COSMIC app "may crash on MoOS (KDE)" — the one string in
    the tree that equates MoOS with another desktop — and described six apps as "KDE-native";
  * Mo AI's SYSTEM PROMPT told the model it runs on "a KDE Plasma 6 desktop", so the assistant
    would say so on request. The prompt's identity rule forbade naming another distribution and
    was silent about the desktop;
  * Mo Store's Sources page showed a card titled "Discover · System engine" for "Plasma
    add-ons", although the image gate exists so that no surface shows a second store's name;
  * a GUI error dialog reached from MoOS Settings said "Plasma must be running";
  * MoPlayer's own store page advertised "the Plasma media applet";
  * `systemctl --user` listed "Watch Plasma automatic theme transitions".

The rule (docs/DEVELOPMENT_PLAN.md, "Identity lock"): in a MoOS-OWNED surface the user reads
MoOS names. Upstream application names, licence text, identifiers and diagnostics stay intact —
so this gate reads only what is displayed and leaves every identifier alone:

  1. string literals in first-party QML (apps, MoOS plasmoids, look-and-feel, wallpapers),
     after comments are stripped, skipping literals that are identifiers (no whitespace, ASCII:
     `org.kde.kirigami`, `kcm_kscreen`, icon names, D-Bus names, URLs);
  2. bilingual "عربي | English" messages and `fail`/`die` texts in shipped scripts;
  3. `Description=` of MoOS-owned systemd units (system and user);
  4. AppStream text of org.moos.* metainfo;
  5. display keys of org.moos.* desktop entries.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYS = ROOT / "system_files"

FOREIGN = re.compile(
    r"fedora|kinoite|silverblue|red\s*hat|redhat|\brhel\b|\bublue\b|universal\s+blue|bazzite|"
    r"\bkde\b|\bplasma\b|\bbreeze\b|\bkwin\b|\bubuntu\b|\bdebian\b|\bgnome\b",
    re.IGNORECASE)

# Upstream PRODUCT names a person installs or recognises by that name. Each entry is a phrase that
# is removed before the sweep, so "KDE Connect" stays legal and "KDE-native" does not.
UPSTREAM_NAMES = (
    "KDE Connect",
)
# The plan leaves DIAGNOSTICS intact: a tool an engineer runs to find out which component is
# wrong has to name that component ("KWin is not using OpenGL"). These tools print to a terminal
# for the owner or an agent and are exempt from the terminal-message rule ONLY — a bilingual
# message or a dialog/notification in them is still swept, because that reaches a person's screen.
DIAGNOSTIC_TOOLS = {
    "moos-selfcheck", "moos-theme", "moos-bar-apply", "moos-cloud-desktop", "moos-visual-tier",
    "moos-health", "mokernel", "moos-hardware", "moos-wait-drm",
}
ARABIC = re.compile(r"[؀-ۿ]")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_./:@+\-%#=&?,\[\]{}()*$|\\^~<>!;'`\"]*$")


def cleaned(text: str) -> str:
    """Remove what is an identifier even inside prose: `code spans` and reverse-DNS app ids."""
    # Ids first: a prompt is built from concatenated literals, so a `code span` can open in one
    # literal and close in the next, and pairing backticks inside one literal would be wrong.
    text = re.sub(r"\b(?:org|io|com|net|dev|app)\.[A-Za-z0-9_.\-]+", "", text)
    text = re.sub(r"`[^`]*`", "", text)
    for name in UPSTREAM_NAMES:
        text = re.sub(re.escape(name), "", text, flags=re.IGNORECASE)
    return text


def hit(text: str) -> str | None:
    match = FOREIGN.search(cleaned(text))
    return match.group(0) if match else None


def qml_literals(source: str):
    source = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.DOTALL)
    source = re.sub(r"(?m)//[^\n]*$", "", source)
    for number, line in enumerate(source.splitlines(), 1):
        if re.match(r"\s*(import|pragma)\b", line):
            continue
        for literal in re.findall(r'"((?:\\.|[^"\\\n])*)"', line):
            yield number, literal


def is_prose(literal: str) -> bool:
    """A displayed string has a space or a non-ASCII letter; an identifier has neither."""
    if not literal.strip():
        return False
    if ARABIC.search(literal) or " " in literal.strip():
        return True
    return not IDENTIFIER.match(literal)


def sweep_qml(errors: list[str]) -> int:
    trees = [SYS / "usr/share/moos/apps"]
    trees += sorted((SYS / "usr/share/plasma/plasmoids").glob("org.moos.*"))
    trees += sorted((SYS / "usr/share/plasma/look-and-feel").glob("org.moos.*"))
    trees += sorted((SYS / "usr/share/plasma/wallpapers").glob("org.moos.*"))
    count = 0
    for tree in trees:
        for path in sorted(tree.rglob("*.qml")):
            count += 1
            rel = path.relative_to(ROOT).as_posix()
            for number, literal in qml_literals(path.read_text(encoding="utf-8")):
                word = hit(literal) if is_prose(literal) else (
                    literal if FOREIGN.fullmatch(literal.strip()) else None)
                if word:
                    errors.append(f"{rel}:{number}: displayed text names `{word}`: "
                                  f"\"{literal[:90]}\"")
            # A name can also arrive as DATA. `uname -r` continues with the packager's build tag
            # ("7.2.5-200.fc44.x86_64"), and two MoOS panels printed it whole — one of them into
            # the context the model quotes from. No literal names anything, so the sweep above
            # cannot see it: a kernel release is shown through a helper that keeps the number.
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("//", 1)[0]
                if re.search(r"\.kernel\b(?!\s*\))", code) and not re.search(r"kernel(Number|Label)\(", code):
                    errors.append(f"{rel}:{number}: shows the raw kernel release, which carries the "
                                  f"packager's build tag — pass it through kernelNumber()/kernelLabel()")
    return count


def sweep_scripts(errors: list[str]) -> int:
    roots = [SYS / "usr/bin", SYS / "usr/libexec", SYS / "usr/lib/moai", SYS / "usr/lib/moos"]
    # Command position only: the WORD "confirm" inside a message is not a call to confirm().
    at_command = r"(?:^|[;&|(]|\bif|\bthen|\belse|\bdo|!)\s*"
    on_screen = re.compile(at_command + r"(?:kdialog|notify-send|notify|confirm|zenity)\s")
    terminal = re.compile(at_command + r"(?:fail|die|bad)\s")
    count = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if not text.startswith("#!") and path.suffix != ".py":
                continue
            count += 1
            rel = path.relative_to(ROOT).as_posix()
            # A message may span lines inside one quoted argument (English line, Arabic line).
            if path.name not in DIAGNOSTIC_TOOLS:
                for match in re.finditer(r"(?m)^[^#\n]*\b(?:fail|die)\s+'([^']*\n[^']*)'", text):
                    if hit(match.group(1)):
                        number = text.count("\n", 0, match.start(1)) + 1
                        errors.append(f"{rel}:{number}: a message shown to the person names "
                                      f"`{hit(match.group(1))}`: "
                                      f"\"{match.group(1).splitlines()[0][:90]}\"")
            for number, line in enumerate(text.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for literal in re.findall(r'"((?:\\.|[^"\\\n])*)"|\'((?:[^\'\n])*)\'', line):
                    value = literal[0] or literal[1]
                    bilingual = " | " in value and ARABIC.search(value)
                    spoken = " " in value.strip() and (
                        on_screen.search(line)
                        or (terminal.search(line) and path.name not in DIAGNOSTIC_TOOLS))
                    if (bilingual or spoken) and hit(value):
                        errors.append(f"{rel}:{number}: a message shown to the person names "
                                      f"`{hit(value)}`: \"{value[:90]}\"")
    return count


def sweep_units(errors: list[str]) -> int:
    count = 0
    for scope in ("system", "user"):
        for path in sorted((SYS / "usr/lib/systemd" / scope).glob("*")):
            if not path.is_file() or not re.match(r"(moos|moai|mo)[-_.]", path.name):
                continue
            count += 1
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.startswith("Description=") and hit(line):
                    errors.append(f"{path.relative_to(ROOT).as_posix()}:{number}: unit "
                                  f"description names `{hit(line)}`: {line}")
    return count


def sweep_metainfo(errors: list[str]) -> int:
    count = 0
    for path in sorted((SYS / "usr/share/metainfo").glob("org.moos.*.xml")):
        count += 1
        tree = ET.parse(path)
        for element in tree.iter():
            if element.tag in {"name", "summary", "p", "li", "keyword", "caption"} and element.text:
                if hit(element.text):
                    errors.append(f"{path.relative_to(ROOT).as_posix()}: <{element.tag}> names "
                                  f"`{hit(element.text)}`: \"{element.text.strip()[:90]}\"")
    return count


def sweep_desktop_entries(errors: list[str]) -> int:
    count = 0
    keys = re.compile(r"^(Name|GenericName|Comment|Keywords)(\[[^\]]+\])?=(.*)$")
    for path in sorted((SYS / "usr/share/applications").glob("org.moos.*.desktop")):
        count += 1
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = keys.match(line)
            if match and hit(match.group(3)):
                errors.append(f"{path.relative_to(ROOT).as_posix()}:{number}: `{match.group(1)}` "
                              f"names `{hit(match.group(3))}`: {line[:100]}")
    return count


def main() -> int:
    errors: list[str] = []
    counts = (sweep_qml(errors), sweep_scripts(errors), sweep_units(errors),
              sweep_metainfo(errors), sweep_desktop_entries(errors))
    if min(counts) == 0:
        print(f"GATE FAIL: a sweep found no files at all {counts} — a moved directory would turn "
              "this gate into a no-op; move its paths with the tree.")
        return 1
    if errors:
        print("GATE FAIL: tests/test_user_visible_identity.py — MoOS-owned text names another "
              "operating system or desktop:")
        for error in errors:
            print(f" - {error}")
        print(" Say what it IS in MoOS terms (the MoOS desktop, the built-in player, the system "
              "update engine). An upstream PRODUCT name a person installs by that name belongs in "
              "UPSTREAM_NAMES, with the reason.")
        return 1
    print("user-visible identity gate passed ({} QML files, {} scripts, {} units, {} metainfo, "
          "{} desktop entries)".format(*counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
