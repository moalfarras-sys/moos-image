#!/usr/bin/env python3
"""The Updater's trust badge must report the booted origin, never assert it.

Found on the live system: the badge read "SIGNED IMAGE · ATOMIC" as a hardcoded
constant while `ostree admin status` showed the running deployment's origin was
`ostree-unverified-registry`. This is the only place the desktop tells the owner
whether the system they are running is the one MoOS signed, so a badge that
claims it without looking is worse than no badge at all.

The two functions are exec'd in isolation rather than imported, because
moos-update pulls in Gtk at module scope and a gate must not need a display.
"""

import ast
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
UPDATER = ROOT / "system_files/usr/bin/moos-update"

source = UPDATER.read_text(encoding="utf-8")
tree = ast.parse(source)

wanted = {"booted_origin", "trust_badge"}
found = {
    node.name: node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in wanted
}
assert set(found) == wanted, f"moos-update lost {sorted(wanted - set(found))}"

# The badge must not be built from a literal in the widget code.
widget = source[source.index("trust_label, trust_warns"):]
widget = widget[:widget.index("hero.append(trust)")]
assert "SIGNED IMAGE" not in widget, (
    "the trust badge is hardcoded again; it must come from trust_badge(), "
    "which reads the booted deployment's real origin")
assert "trust_badge()" in widget, "the badge must be derived from trust_badge()"

namespace = {"os": __import__("os"),
             "local_text": lambda arabic, english: english}
exec(compile(ast.Module(body=[found["booted_origin"], found["trust_badge"]],
                        type_ignores=[]), str(UPDATER), "exec"), namespace)
booted_origin = namespace["booted_origin"]
trust_badge = namespace["trust_badge"]


def fixture(directory, reference):
    """A deployment tree shaped like the real one: cmdline -> symlink -> origin."""
    root = pathlib.Path(directory)
    deploy = root / "ostree/deploy/default/deploy"
    deploy.mkdir(parents=True)
    target = deploy / "abc123.0"
    target.mkdir()
    if reference is not None:
        (deploy / "abc123.0.origin").write_text(
            "[origin]\ncontainer-image-reference=" + reference + "\n",
            encoding="utf-8")
    boot = root / "ostree/boot.0/default/deadbeef"
    boot.mkdir(parents=True)
    (boot / "0").symlink_to(target)
    cmdline = root / "cmdline"
    cmdline.write_text(
        f"BOOT_IMAGE=(hd0,gpt2)/boot/vmlinuz ostree={boot / '0'} rw quiet\n",
        encoding="utf-8")
    return str(cmdline)


cases = [
    ("ostree-image-signed:docker://ghcr.io/x/moos-arm@sha256:" + "a" * 64,
     "SIGNED IMAGE", False),
    ("ostree-unverified-registry:ghcr.io/x/moos-arm@sha256:" + "b" * 64,
     "UNVERIFIED ORIGIN", True),
    ("ostree-unverified-image:docker://ghcr.io/x/moos-arm:latest",
     "UNVERIFIED ORIGIN", True),
    (None, "UNKNOWN ORIGIN", True),
]

for reference, expected, expected_warning in cases:
    with tempfile.TemporaryDirectory(prefix="moos-trust-badge-") as directory:
        cmdline = fixture(directory, reference)
        label, warns = trust_badge(cmdline)
        assert expected in label, f"{reference!r} produced {label!r}"
        assert warns is expected_warning, \
            f"{reference!r} warning state was {warns}, expected {expected_warning}"
        if reference is not None:
            assert booted_origin(cmdline) == reference

# A missing or unreadable cmdline must read as unknown, never as trusted.
label, warns = trust_badge("/nonexistent/cmdline")
assert "UNKNOWN ORIGIN" in label and warns is True, \
    "an unreadable cmdline must never be reported as a signed system"

# The warning state needs a visible style, not just different words.
UI2 = ROOT / "system_files/usr/lib/moos/moos_ui2.py"
style = UI2.read_text(encoding="utf-8")
assert ".ui2-badge.ui2-badge-warning" in style and "@ui2_warning" in style, \
    "an unverified origin must be visually distinct, not only differently worded"
assert "ui2-badge-warning" in source, "moos-update never applies the warning class"

print("Updater trust badge gate passed (4 origin states)")
