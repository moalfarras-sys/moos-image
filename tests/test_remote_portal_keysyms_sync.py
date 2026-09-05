#!/usr/bin/env python3
"""Gate the explicit ordering contract for a portal ``keysyms`` batch.

Most typing stays fire-and-forget so portal latency cannot block the input queue.  The Unicode paste
fallback is different: its synthetic sequence is one transaction and must not be overtaken by a
later event.  It marks that batch ``sync:true``; layout-changing batches remain synchronous too.
"""

import ast
import sys
import unittest
from pathlib import Path

from test_remote_portal_layout_refresh import LayoutRefreshTests


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def main() -> int:
    source = HELPER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(HELPER))
    handle = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "handle"),
        None,
    )
    if handle is None:
        print("GATE FAIL: portal helper has no input handler.")
        return 1

    code = ast.unparse(handle)
    errors: list[str] = []
    if "bool(m.get('sync')) or any(('layout' in e for e in events))" not in code:
        errors.append("keysyms does not make sync:true OR a layout change select ordered delivery")
    if "send = notify_sync if ordered else notify" not in code:
        errors.append("the ordered decision does not select notify_sync")

    if errors:
        print("GATE FAIL: an explicitly synchronous keysyms batch can be overtaken.\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: keysyms sync:true and layout changes use ordered portal delivery.")
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(LayoutRefreshTests))
    if not result.wasSuccessful():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
