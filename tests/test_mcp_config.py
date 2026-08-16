#!/usr/bin/env python3
"""Gate: the shared agent contract stays honest — no leaked keys, no silent hollowing.

Two files in this repo decide what an automated agent can reach: `.mcp.json` (which
MCP servers exist) and `.claude/settings.json` (which of them are pre-approved, and
which shell commands run without asking). Both are COMMITTED, because the point is
that any agent cloning this repo starts with the same tools and the same limits.

Committed means three things can go wrong quietly, and this gate is here for all three:

  1. A KEY GETS PASTED IN. Someone debugs an image-gen failure by dropping the real
     GEMINI_API_KEY into `.mcp.json` "just to test", and it is public the moment it is
     pushed. Every credential in these files must be `${VAR}` expansion, never a value.

  2. A SERVER IS ADDED AND NOT APPROVED. `.mcp.json` alone is not enough — a server
     missing from `enabledMcpjsonServers` sits at "Pending approval" forever, and a
     server missing from `permissions.allow` prompts on every single call. Both are
     invisible to whoever added it (their own machine already approved it locally) and
     land on the next agent as a tool that appears broken.

  3. THE GUARD RAILS GET HOLLOWED OUT. The deny list is the reason this repo can hand
     an agent broad permissions at all: it is what stands between an automated session
     and a force-push over `main`, or an `rpm-ostree` on the maintainer's daily driver.
     Deleting an entry to make one command work is a one-line diff nobody would notice
     in review. The load-bearing entries are pinned here by exact string.

See docs/MCP.md. Run standalone: `python3 tests/test_mcp_config.py`.
"""

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MCP_JSON = ROOT / ".mcp.json"
SETTINGS = ROOT / ".claude" / "settings.json"

# Deny rules that may never leave the shared contract. Each one guards something this
# project has already documented as unrecoverable-by-a-test: a rewritten history on the
# branch CI publishes from, or a mutation of the live deployment on the machine the
# maintainer is reading this on.
REQUIRED_DENY = [
    "Bash(git push --force:*)",
    "Bash(git push -f:*)",
    "Bash(flatpak-spawn --host sudo -n rpm-ostree:*)",
    "Bash(flatpak-spawn --host sudo -n bootc:*)",
    "Read(./cosign.key)",
]

# Shapes of real credentials. A value matching one of these is a live key, not a
# placeholder — no amount of "it is only a test key" makes it safe to commit.
SECRET_SHAPES = [
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "Google/Gemini API key"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), "OpenAI-style secret key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained PAT"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), "Slack token"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
]

# Field names whose value is a credential by definition. Anything here must be an
# unexpanded ${VAR} reference or empty — never a literal.
CREDENTIAL_HINT = re.compile(r"(?i)(key|token|secret|password|passwd|credential|authorization)")

errors: list[str] = []


def load(path: Path) -> dict:
    if not path.is_file():
        errors.append(f"{path.relative_to(ROOT)} is missing — every agent needs it (docs/MCP.md)")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)} is not valid JSON: {exc}")
        return {}


def walk(node, path: str, visit) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            walk(value, f"{path}.{key}", visit)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk(value, f"{path}[{index}]", visit)
    else:
        visit(path, node)


def check_no_secrets(name: str, data: dict) -> None:
    def visit(path: str, value) -> None:
        if not isinstance(value, str):
            return
        for pattern, label in SECRET_SHAPES:
            if pattern.search(value):
                errors.append(f"{name} at {path} contains what looks like a {label}")
                return
        leaf = path.rsplit(".", 1)[-1]
        if CREDENTIAL_HINT.search(leaf) and value and "${" not in value:
            errors.append(
                f"{name} at {path} sets a credential field to a literal value; "
                f"use ${{VAR}} expansion instead"
            )

    walk(data, name, visit)


mcp = load(MCP_JSON)
settings = load(SETTINGS)

check_no_secrets(".mcp.json", mcp)
check_no_secrets(".claude/settings.json", settings)

servers = mcp.get("mcpServers")
if not isinstance(servers, dict) or not servers:
    errors.append(".mcp.json has no mcpServers object")
    servers = {}

for name, spec in sorted(servers.items()):
    if not isinstance(spec, dict):
        errors.append(f".mcp.json server {name!r} is not an object")
        continue
    transport = spec.get("type", "stdio")
    if transport == "stdio":
        if not spec.get("command"):
            errors.append(f".mcp.json server {name!r} is stdio but has no command")
    elif transport in ("http", "sse"):
        if not spec.get("url"):
            errors.append(f".mcp.json server {name!r} is {transport} but has no url")
    else:
        errors.append(f".mcp.json server {name!r} has unknown transport {transport!r}")

permissions = settings.get("permissions", {}) if isinstance(settings, dict) else {}
allow = permissions.get("allow", []) or []
deny = permissions.get("deny", []) or []
enabled = settings.get("enabledMcpjsonServers", []) or [] if isinstance(settings, dict) else []

if settings:
    for name in sorted(servers):
        if name not in enabled:
            errors.append(
                f"server {name!r} is in .mcp.json but not in enabledMcpjsonServers — "
                f"it will sit at 'Pending approval' for every agent"
            )
        if not any(rule in (f"mcp__{name}", f"mcp__{name}__*") for rule in allow):
            errors.append(
                f"server {name!r} has no 'mcp__{name}' rule in permissions.allow — "
                f"every one of its tool calls will prompt"
            )

    for name in sorted(set(enabled) - set(servers)):
        errors.append(f"enabledMcpjsonServers lists {name!r}, which no longer exists in .mcp.json")

    for rule in REQUIRED_DENY:
        if rule not in deny:
            errors.append(
                f"permissions.deny is missing the required guard {rule!r} — "
                f"this is what makes the broad allow list safe (docs/MCP.md)"
            )

if errors:
    print("MCP config gate FAILED:")
    for error in errors:
        print(f"  - {error}")
    print(
        "\nThese two files are the contract every agent working on MoOS inherits."
        "\nSecrets belong in .claude/settings.local.json, which is gitignored."
        "\nSee docs/MCP.md."
    )
    sys.exit(1)

print(
    f"MCP config gate passed ({len(servers)} servers approved, "
    f"{len(REQUIRED_DENY)} guard rails intact, no literal credentials)"
)
