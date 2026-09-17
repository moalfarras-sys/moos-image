#!/usr/bin/env python3
"""Gate: the image gate's comment stripper must not delete shell code, and the settings-route
parser must see the router this tree ships — before the merge, not after it.

WHY THIS EXISTS

`build_files/verify_image_experience.py` runs only inside the x86 image build, and `build.yml`
does not run on pull requests. So whatever that gate parses is parsed for the first time on
`main`, after the merge, by a build that takes the better part of an hour.

On 2026-09-17 that cost a red `main` for all three x86 editions. The gate reads `moos-open`
through `source(router, "#")`, and `source()` removed `/* … */` spans from every file it was
given — correct for QML and JavaScript, wrong for bash, where those two characters are a `case`
glob (`ai/ask/*)`) or a parameter expansion (`${path#*/}`). It had been deleting two harmless
lines for weeks. Then wave W5 added

    privacy_id="${privacy_act#*/}"

and that `*/` closed a span opened 235 lines earlier by a COMMENT — "There is deliberately no
settings/kcm/* wildcard". Everything between them disappeared from the gate's view: 24 of the
28 `settings/*` routes. The build printed

    the settings route parser found almost nothing — moos-open's shape changed and this gate
    stopped guarding anything (got 4)

about a router that was correct. Every pull-request check had been green.

This test runs the gate's OWN `source()` and its OWN route pattern (both lifted out of the gate
file with `ast`, so they cannot drift from it) against the `moos-open` in this checkout. It
fails on a pull request in seconds, in `Repo gates`, where the image gate cannot run.

It also pins the two behaviours the stripper exists for, so the fix cannot trade one blindness
for another: `#` prose must never satisfy a shell assertion, and `/* … */` prose must never
satisfy a QML one.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "build_files/verify_image_experience.py"
ROUTER = ROOT / "system_files/usr/bin/moos-open"


def legacy_source(raw: str, prefix: str = "//") -> str:
    """The stripper as it shipped until 2026-09-17: block comments removed for EVERY language.

    Kept only to prove the fixture below really reproduces the defect. A fixture that the broken
    implementation also passes would guard nothing.
    """
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)
    return "\n".join(l for l in raw.splitlines() if not l.lstrip().startswith(prefix))


# The shape that blinded the gate, reduced to what matters: prose containing "/*", real routes,
# then a parameter expansion containing "*/".
SHELL_FIXTURE = """\
case "$cat/$tgt" in
    # There is deliberately no settings/kcm/* wildcard: URL text never becomes argv.
    settings/display)   gui systemsettings kcm_kscreen ;;
    settings/sound)     gui systemsettings kcm_pulseaudio ;;
    settings/about)     gui kinfocenter kcm_about-distro ;;
    # settings/ghost)   gui systemsettings kcm_ghost ;;
    privacy/stop/*)
        privacy_id="${privacy_act#*/}" ;;
esac
"""

QML_FIXTURE = """\
Item {
    /* Qt.openUrlExternally("moos://store/install") was removed on purpose:
       a web page must never trigger an installation. */
    // Qt.openUrlExternally("moos://also/removed")
    Button { onClicked: Qt.openUrlExternally("moos://store/open") }
}
"""


def lift_from_gate() -> tuple[object, str, int]:
    """Return the gate's real source() function, its settings-route pattern and its floor."""
    tree = ast.parse(GATE.read_text(encoding="utf-8"), filename=str(GATE))

    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "source"), None)
    if fn is None:
        raise LookupError("verify_image_experience.py no longer defines source()")
    namespace: dict[str, object] = {"re": re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(GATE), "exec"), namespace)

    pattern = None
    floor = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "_kcm_routes" for t in node.targets)
                and isinstance(node.value, ast.Call) and node.value.args):
            pattern = ast.literal_eval(node.value.args[0])
        if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Call)
                and getattr(node.left.func, "id", "") == "len"
                and node.left.args and getattr(node.left.args[0], "id", "") == "_kcm_routes"
                and len(node.ops) == 1 and isinstance(node.ops[0], ast.GtE)):
            floor = ast.literal_eval(node.comparators[0])
    if not isinstance(pattern, str) or not isinstance(floor, int):
        raise LookupError("verify_image_experience.py no longer parses settings routes into "
                          "_kcm_routes with a `len(_kcm_routes) >= N` floor")
    return namespace["source"], pattern, floor


def main() -> int:
    errors: list[str] = []
    for path in (GATE, ROUTER):
        if not path.is_file():
            print(f"GATE FAIL: {path.relative_to(ROOT)} is missing.")
            return 1

    try:
        source, pattern, floor = lift_from_gate()
    except LookupError as exc:
        print(f"GATE FAIL: {exc} — this test lifts them from the gate so the two cannot drift; "
              "update it together with the gate.")
        return 1

    # 1. The fixture must reproduce the defect, or the rest of this file proves nothing.
    seen_by_legacy = re.findall(pattern, legacy_source(SHELL_FIXTURE, "#"))
    if len(seen_by_legacy) >= 3:
        errors.append("the shell fixture no longer reproduces the 2026-09-17 defect: the legacy "
                      "stripper still sees every route in it, so this test cannot go red.")

    # 2. The gate's stripper must keep shell code between a `/*` and a later `*/`.
    seen = [route for route, _host, _kcm in re.findall(pattern, source(SHELL_FIXTURE, "#"))]
    if seen != ["display", "sound", "about"]:
        errors.append("source(…, '#') lost or invented shell routes — expected "
                      f"['display', 'sound', 'about'], got {seen}. `/* … */` is not a comment in "
                      "bash; it is a case glob or a parameter expansion.")
    if "privacy_act#*/" not in source(SHELL_FIXTURE, "#"):
        errors.append("source(…, '#') deleted the `${privacy_act#*/}` expansion itself.")

    # 3. …while `#` prose still cannot satisfy an assertion (the reason the stripper exists).
    if "ghost" in source(SHELL_FIXTURE, "#") or "wildcard" in source(SHELL_FIXTURE, "#"):
        errors.append("source(…, '#') kept a `#` comment line — a commented-out route or the "
                      "prose explaining one could satisfy the gate again.")

    # 4. …and the `//` languages keep BOTH of their comment forms stripped.
    qml = source(QML_FIXTURE)
    if "store/install" in qml or "also/removed" in qml:
        errors.append("source() kept a QML comment — documentation of a removed call could "
                      "satisfy a gate after the real call is gone.")
    if "moos://store/open" not in qml:
        errors.append("source() deleted live QML code while stripping comments.")

    # 5. The router THIS tree ships, through the gate's own eyes. This is the assertion the
    #    image build makes on `main`; here it fails on the pull request instead.
    router_raw = ROUTER.read_text(encoding="utf-8")
    routes_raw = re.findall(pattern, "\n".join(
        l for l in router_raw.splitlines() if not l.lstrip().startswith("#")))
    routes_seen = re.findall(pattern, source(router_raw, "#"))
    if len(routes_seen) < floor:
        errors.append(f"the image gate would find {len(routes_seen)} settings routes in "
                      f"moos-open and needs {floor}: every x86 edition would fail on `main` with "
                      "\"the settings route parser found almost nothing\". If moos-open's route "
                      "lines changed shape, move the gate's pattern with them.")
    if len(routes_seen) != len(routes_raw):
        hidden = sorted({r for r, _h, _k in routes_raw} - {r for r, _h, _k in routes_seen})
        errors.append(f"the image gate's stripper hides {len(routes_raw) - len(routes_seen)} "
                      f"settings route(s) that moos-open really declares: {hidden}. A hidden route "
                      "is an unverified Command Center tile.")

    if errors:
        print("GATE FAIL: tests/test_image_gate_source_parser.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"image-gate source parser gate passed ({len(routes_seen)} settings routes visible to "
          f"the image gate, floor {floor}; shell and QML comment rules hold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
