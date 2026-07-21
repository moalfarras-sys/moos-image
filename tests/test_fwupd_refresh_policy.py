#!/usr/bin/env python3
"""Gate the fwupd-refresh polkit fix so it cannot silently regress or over-grant.

fwupd-refresh.service runs `fwupdmgr refresh` as the DynamicUser fwupd-refresh
with no session; polkit then judges the LVFS metadata action
org.freedesktop.fwupd.refresh-remote (allow_any=auth_admin) with no agent and
the timer dies "Failed to obtain auth". The fix is a scoped polkit rule that
grants ONLY metadata refresh to ONLY that user.

Two ways this fix could rot, and this gate bites on both:
  1. Someone deletes/edits the rule and fwupd-refresh starts failing again.
  2. Someone widens the rule to grant a firmware-flashing action to a
     session-less user — turning a cosmetic fix into a privilege hole.

Per AGENTS.md, the assertions read the CODE with comments stripped, so a gate
cannot be satisfied by the prose in the rule's own header comment.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]

RULE = "system_files/usr/share/polkit-1/rules.d/60-moos-fwupd-refresh.rules"
DROPIN = (
    "system_files/usr/lib/systemd/system/"
    "fwupd-refresh.service.d/10-moos-log-the-error.conf"
)

# The ONLY two fwupd actions this rule is allowed to grant. refresh-remote is the
# action `fwupdmgr refresh` needs; it implies get-remotes. Anything else that can
# flash, downgrade, modify or unlock firmware/devices must keep its auth_admin
# default, so a session-less user can never reach it.
ALLOWED_ACTIONS = {
    "org.freedesktop.fwupd.refresh-remote",
    "org.freedesktop.fwupd.get-remotes",
}

errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def strip_slash_comments(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


def strip_hash_comments(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


rule_path = ROOT / RULE
require(rule_path.is_file(), f"missing polkit rule: {RULE}")

if rule_path.is_file():
    rule = strip_slash_comments(rule_path.read_text(encoding="utf-8"))

    # It actually fixes the bug: grants metadata refresh to the fwupd-refresh user.
    require(
        "org.freedesktop.fwupd.refresh-remote" in rule,
        "rule no longer grants org.freedesktop.fwupd.refresh-remote — "
        "fwupd-refresh.service will fail 'Failed to obtain auth' again",
    )
    require(
        "polkit.Result.YES" in rule,
        "rule no longer returns polkit.Result.YES — it grants nothing",
    )

    # It is SCOPED to the fwupd-refresh user, not a blanket allow.
    require(
        "subject.user" in rule and '"fwupd-refresh"' in rule,
        "rule is not scoped to subject.user == \"fwupd-refresh\" — refusing a "
        "broader grant",
    )

    # It grants NOTHING beyond the two metadata actions. Any other fwupd action
    # id appearing in the code is an over-grant and fails the gate.
    granted = set(re.findall(r"org\.freedesktop\.fwupd\.[a-z0-9-]+", rule))
    extra = granted - ALLOWED_ACTIONS
    require(
        not extra,
        "rule references fwupd actions beyond metadata refresh "
        f"(possible privilege over-grant): {sorted(extra)}",
    )
    require(
        granted,  # non-empty
        "rule references no fwupd action at all",
    )

dropin_path = ROOT / DROPIN
require(dropin_path.is_file(), f"missing drop-in: {DROPIN}")
if dropin_path.is_file():
    dropin = strip_hash_comments(dropin_path.read_text(encoding="utf-8"))
    # Keep the failure readable: if the fix ever regresses, the error must reach
    # the journal instead of being swallowed by upstream's StandardError=null.
    require(
        "StandardError=journal" in dropin,
        "drop-in no longer forces StandardError=journal — a future fwupd-refresh "
        "failure would be silent again",
    )

if errors:
    print("fwupd-refresh policy gate FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("fwupd-refresh policy gate passed (scoped metadata refresh, no over-grant)")
