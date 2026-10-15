#!/usr/bin/env python3
"""Mo Store must report progress in the owner's language, not the backend's.

Observed on the live system: an entirely Arabic Mo Store showed the English
toast "Rebuilding the unified app index" next to its own Arabic cancel button.
The cause was structural, not a missed string -- every job message moos-storectl
emits was English prose, and main.qml went further and *branched on that prose*
to decide install state, so translating the backend would have silently broken
install detection.

The contract this gates: the backend emits a stable `message_key`, the UI owns
the words. Failures are the deliberate exception -- they carry no key so their
real diagnostic text reaches the user verbatim.
"""

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CTL = ROOT / "system_files/usr/bin/moos-storectl"
QML = ROOT / "system_files/usr/share/moos/apps/store/main.qml"
# main.qml owns jobPhrases; the views beside it (the job shelf among them) are read with it, so
# no file of the Store can branch on backend prose.
QML_FILES = sorted((p for p in QML.parent.rglob("*") if p.is_file() and p.suffix in (".qml", ".js")),
                   key=lambda p: (p != QML, p.relative_to(QML.parent).as_posix()))

ctl = CTL.read_text(encoding="utf-8")
qml = "\n".join(path.read_text(encoding="utf-8") for path in QML_FILES)

# Strip full-line comments so no assertion below can be satisfied by prose that
# merely talks about the contract.
ctl_code = "\n".join(l for l in ctl.splitlines() if not l.lstrip().startswith("#"))
qml_code = "\n".join(l for l in qml.splitlines() if not l.lstrip().startswith("//"))

# ---------------------------------------------------------------- backend keys
assert "message_key" in ctl_code, "moos-storectl no longer emits message keys"
for api in ('("message_key", message_key),',):
    assert ctl_code.count(api) == 2, \
        "both Job.update and Job.update_item must persist message_key"

emitted = set(re.findall(r'message_key="([a-z_]+)"', ctl_code))
# Terminal success lines carry their key as finish_from_items' second argument,
# not as message_key=. Miss that form and a typo there goes unnoticed.
emitted |= set(re.findall(r'finish_from_items\([^)]*,\s*"([a-z_]+)"\)', ctl_code))
# A document built as a literal (the busy refusal) spells the key as a dict entry.
emitted |= set(re.findall(r'"message_key":\s*"([a-z_]+)"', ctl_code))
assert emitted, "no message keys are emitted at all"
# Every key must be one the patterns above can see whole: a digit or a capital in a key would
# make it invisible to this gate, and the UI phrase beside it would look like an orphan.
spelled = re.findall(r'message_key="([^"]*)"', ctl_code)
spelled += re.findall(r'"message_key":\s*"([^"]*)"', ctl_code)
unseen = sorted({key for key in spelled if not re.fullmatch(r"[a-z_]+", key)})
assert not unseen, f"message keys this gate cannot hold to a phrase: {unseen}"

# ------------------------------------- a publisher's own package: every refusal has words
# usr/lib/moos/moos_vendor_rpm.py refuses with stable codes; moos-storectl turns each one into a
# key through ONE table, VENDOR_FAILURE_KEYS, and keeps the same refusal in English in
# VENDOR_FAILURE_WORDS for its diagnostic message. The table must name exactly the module's
# ERROR_CODES: a code it misses would reach an Arabic session as English prose, and a code the
# module no longer raises is a phrase nothing can show. Its keys count as emitted below, so the
# phrase check runs both ways for them too.
VENDOR = ROOT / "system_files/usr/lib/moos/moos_vendor_rpm.py"


def module_constant(tree: ast.Module, name: str):
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            value = node.value
            if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "frozenset":
                value = value.args[0]
            return ast.literal_eval(value)
    raise AssertionError(f"{name} is not defined as a literal")


ctl_tree = ast.parse(ctl)
vendor_keys = module_constant(ctl_tree, "VENDOR_FAILURE_KEYS")
vendor_words = module_constant(ctl_tree, "VENDOR_FAILURE_WORDS")
vendor_codes = set(module_constant(ast.parse(VENDOR.read_text(encoding="utf-8")), "ERROR_CODES"))
unmapped = sorted(vendor_codes - set(vendor_keys))
assert not unmapped, f"moos_vendor_rpm codes moos-storectl has no key for: {unmapped}"
unknown = sorted(set(vendor_keys) - vendor_codes)
assert not unknown, f"VENDOR_FAILURE_KEYS maps codes the module never raises: {unknown}"
assert all(re.fullmatch(r"[a-z_]+", key) for key in vendor_keys.values()), \
    "a vendor failure key this gate cannot hold to a phrase"
assert set(vendor_words) == set(vendor_keys.values()), (
    "every vendor failure key needs its English diagnostic words, and only those keys: "
    f"{sorted(set(vendor_words) ^ set(vendor_keys.values()))}")
assert "VENDOR_FAILURE_KEYS.get(code)" in ctl_code, \
    "moos-storectl must turn a vendor refusal into its key through the table"
emitted |= set(vendor_keys.values())

# ------------------------------------------------------------------- UI phrases
block = re.search(r"readonly property var jobPhrases: \(\{(.*?)\n    \}\)", qml_code, re.S)
assert block, "main.qml lost the jobPhrases map"
phrases = dict(
    (m.group(1), (m.group(2), m.group(3)))
    for m in re.finditer(r'"([a-z_]+)":\s*\["([^"]+)",\s*"([^"]+)"\]', block.group(1))
)
assert phrases, "jobPhrases parsed empty"

missing = sorted(emitted - set(phrases))
assert not missing, (
    "moos-storectl emits keys the UI cannot render, so these fall back to "
    f"English prose in an Arabic session: {missing}")

orphans = sorted(set(phrases) - emitted)
assert not orphans, (
    "the UI carries phrases nothing emits, which usually means a key was "
    f"renamed on one side only: {orphans}")

for key, (arabic, english) in sorted(phrases.items()):
    assert arabic != english, f"{key} is not actually translated"
    assert re.search(r"[؀-ۿ]", arabic), \
        f"{key} has no Arabic text in its Arabic slot"

# ------------------------------------------------- no branching on backend prose
for prose in (
    '"Already installed system-wide"',
    '"Already installed for this user"',
    '"not installed"',
):
    hits = [
        line for line in qml_code.splitlines()
        if prose in line and ("===" in line or "indexOf" in line)
    ]
    assert not hits, (
        "main.qml compares backend prose to decide state; translating the "
        f"backend would silently break it: {hits}")

assert "function jobItemIs(" in qml_code and "function jobText(" in qml_code, \
    "the key-based accessors must exist"

# ------------------------------------------------- failures stay diagnostic
assert ctl_code.count("message_key=None") >= 3, (
    "every failure path must clear message_key; a job document keeps fields it "
    "was given, so a stale key would render a finished step's progress line "
    "over a real error")
assert 'document.message_key = ""' in qml_code, (
    "the UI's stale-job rewrite must clear the key for the same reason")

print(f"Mo Store job language gate passed ({len(emitted)} keys, {len(phrases)} phrases)")
