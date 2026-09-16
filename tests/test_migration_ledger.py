#!/usr/bin/env python3
"""Gate: P1.1 — session migrations are versioned, idempotent and transaction-safe.

WHY THIS EXISTS

moos-ui-migrate carries every repair MoOS applies to an account that predates a change:
NumLock, the OpenClaw idle mask, the keyboard shadow, KWallet, the GStreamer registry and the
theme caches. They run at every login, on accounts in unknown states, and they are interrupted
by whatever ends a session — a logout, a crash, an OOM kill. Three properties have to hold, and
a marker file alone establishes only the second:

  * VERSIONED — every migration carries its own revision in its id, so a bumped revision
    re-runs exactly the accounts that need it and no others.
  * IDEMPOTENT — running twice is indistinguishable from running once; the second login must
    not re-apply a repair the owner has since deliberately undone.
  * TRANSACTION-SAFE — an interrupted migration leaves the ORIGINAL state, never half of the
    new one. This is the property that was missing: disabling KWallet takes two keys and
    kwriteconfig6 edits in place, so an interruption between the two calls left an account with
    Enabled=false and First Use untouched — a half-disabled wallet that still prompts at login.

It also asserts the ledger. The per-migration .log files are prose for a human already reading
one failure; nothing could answer "which migrations ran on this account, at which revision, and
did any fail?" — the question a support bundle or an upgrade check asks.

SAFETY NOTE FOR WHOEVER RUNS THIS ON A REAL DESKTOP

The wallet migration calls bare `systemctl --user mask --now` and `pkill kwalletd6`. Pointed at
a temporary XDG root its marker is absent, so it WILL try to mask and kill the real session's
services. Every case here shadows systemctl, pkill and the kconfig tools with fakes earlier on
PATH, and asserts afterwards that the fakes — not the real tools — were the ones called.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "system_files/usr/bin/moos-ui-migrate"

# A fake kwriteconfig6/kreadconfig6 pair over a trivial "group.key=value" store. The real tools
# are KDE binaries that CI does not have, and the script skips itself entirely when they are
# missing — which would make this gate pass by doing nothing.
FAKE_KWRITE = r"""#!/usr/bin/bash
file=""; group=""; key=""; value=""
while [ $# -gt 0 ]; do
  case "$1" in
    --file) file="$2"; shift 2 ;;
    --group) group="$2"; shift 2 ;;
    --key) key="$2"; shift 2 ;;
    *) value="$1"; shift ;;
  esac
done
printf '%s\n' "kwriteconfig6 $group/$key" >>"$MOOS_TEST_CALLS"
# Simulate an interruption at a chosen key: the process dies before writing.
if [ "$MOOS_TEST_FAIL_KEY" = "$key" ]; then exit 1; fi
printf '%s.%s=%s\n' "$group" "$key" "$value" >>"$file"
"""

FAKE_KREAD = r"""#!/usr/bin/bash
file=""; group=""; key=""; default=""
while [ $# -gt 0 ]; do
  case "$1" in
    --file) file="$2"; shift 2 ;;
    --group) group="$2"; shift 2 ;;
    --key) key="$2"; shift 2 ;;
    --default) default="$2"; shift 2 ;;
    *) shift ;;
  esac
done
value="$(grep -E "^${group}\.${key}=" "$file" 2>/dev/null | tail -1 | cut -d= -f2-)"
printf '%s\n' "${value:-$default}"
"""

# Anything that would touch the real session is replaced by a recorder.
FAKE_RECORDER = r"""#!/usr/bin/bash
printf '%s %s\n' "$(basename "$0")" "$*" >>"$MOOS_TEST_CALLS"
exit 0
"""


class Account:
    """A throwaway account root with its own XDG dirs and a shadowed PATH."""

    def __init__(self, stack: unittest.TestCase, *, kwalletrc: str | None = None,
                 fail_key: str = "") -> None:
        self.root = Path(stack.enterContext(tempfile.TemporaryDirectory(prefix="moos-migration-")))
        self.home = self.root / "home"
        self.config = self.root / "config"
        self.state = self.root / "state"
        self.cache = self.root / "cache"
        self.bin = self.root / "bin"
        for directory in (self.home, self.config, self.state, self.cache, self.bin):
            directory.mkdir(parents=True, exist_ok=True)
        self.calls = self.root / "calls.txt"
        self.calls.write_text("", encoding="utf-8")

        for name, body in (("kwriteconfig6", FAKE_KWRITE), ("kreadconfig6", FAKE_KREAD),
                           ("systemctl", FAKE_RECORDER), ("pkill", FAKE_RECORDER),
                           ("kbuildsycoca6", FAKE_RECORDER), ("gdbus", FAKE_RECORDER)):
            path = self.bin / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)

        self.kwalletrc = self.config / "kwalletrc"
        if kwalletrc is not None:
            self.kwalletrc.write_text(kwalletrc, encoding="utf-8")

        self.env = os.environ | {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_STATE_HOME": str(self.state),
            "XDG_DATA_HOME": str(self.root / "data"),
            "XDG_CACHE_HOME": str(self.cache),
            "PATH": f"{self.bin}:{os.environ.get('PATH', '')}",
            "MOOS_TEST_CALLS": str(self.calls),
            "MOOS_TEST_FAIL_KEY": fail_key,
            "MOOS_SYSTEMD_USER_DIR": str(self.root / "no-units"),
        }

    def run(self) -> int:
        return subprocess.run([str(MIGRATE)], env=self.env, capture_output=True,
                              text=True, timeout=60).returncode

    @property
    def ledger(self) -> list[list[str]]:
        path = self.state / "moos/migrations/ledger.tsv"
        if not path.is_file():
            return []
        return [line.split("\t") for line in
                path.read_text(encoding="utf-8").splitlines() if line]

    def wallet_keys(self) -> dict[str, str]:
        if not self.kwalletrc.is_file():
            return {}
        pairs = {}
        for line in self.kwalletrc.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                name, _, value = line.partition("=")
                pairs[name] = value
        return pairs

    def stray_temp_files(self) -> list[str]:
        return sorted(p.name for p in self.config.glob("*.moos-*"))

    def recorded(self) -> str:
        return self.calls.read_text(encoding="utf-8")


class MigrationLedger(unittest.TestCase):
    def test_a_clean_account_applies_the_wallet_migration_and_records_it(self):
        account = Account(self)
        self.assertEqual(account.run(), 0)
        keys = account.wallet_keys()
        self.assertEqual(keys.get("Wallet.Enabled"), "false")
        self.assertEqual(keys.get("Wallet.First Use"), "false",
                         "both keys or neither — one key is a wallet that still prompts")
        self.assertTrue((account.state / "moos/wallet-disabled-v2.done").exists())
        applied = [row for row in account.ledger
                   if row[1] == "wallet-disabled-v2" and row[3] == "applied"]
        self.assertEqual(len(applied), 1, f"ledger: {account.ledger}")

    def test_running_twice_changes_nothing_and_does_not_re_apply(self):
        account = Account(self)
        account.run()
        first_state = account.kwalletrc.read_text(encoding="utf-8")
        first_ledger = account.ledger
        account.run()
        self.assertEqual(account.kwalletrc.read_text(encoding="utf-8"), first_state,
                         "a second login must not rewrite an already-migrated account")
        self.assertEqual(account.ledger, first_ledger,
                         "a no-op run must not append to the ledger")

    def test_an_interrupted_migration_leaves_the_original_file_untouched(self):
        """The property that was missing: half of a two-key change must never land."""
        original = "Wallet.Enabled=true\nWallet.Other=keep-me\n"
        account = Account(self, kwalletrc=original, fail_key="First Use")
        self.assertEqual(account.run(), 0)
        self.assertEqual(account.kwalletrc.read_text(encoding="utf-8"), original,
                         "an interrupted wallet migration must leave the ORIGINAL config")
        self.assertFalse((account.state / "moos/wallet-disabled-v2.done").exists(),
                         "a failed migration must not stamp its marker; it retries next login")
        failed = [row for row in account.ledger
                  if row[1] == "wallet-disabled-v2" and row[3] == "failed"]
        self.assertEqual(len(failed), 1, f"ledger: {account.ledger}")
        self.assertEqual(account.stray_temp_files(), [],
                         "a failed transaction must not leave its staging file behind")

    def test_the_account_converges_on_the_login_after_an_interruption(self):
        account = Account(self, kwalletrc="Wallet.Enabled=true\n", fail_key="First Use")
        account.run()
        account.env["MOOS_TEST_FAIL_KEY"] = ""      # the next login is not interrupted
        self.assertEqual(account.run(), 0)
        keys = account.wallet_keys()
        self.assertEqual(keys.get("Wallet.Enabled"), "false")
        self.assertEqual(keys.get("Wallet.First Use"), "false")
        self.assertTrue((account.state / "moos/wallet-disabled-v2.done").exists())

    def test_a_clean_account_and_an_upgraded_account_reach_the_same_owned_state(self):
        clean = Account(self)
        upgraded = Account(self, kwalletrc="Wallet.Enabled=true\nWallet.First Use=true\n")
        clean.run()
        upgraded.run()
        self.assertEqual(clean.wallet_keys().get("Wallet.Enabled"),
                         upgraded.wallet_keys().get("Wallet.Enabled"))
        self.assertEqual(clean.wallet_keys().get("Wallet.First Use"),
                         upgraded.wallet_keys().get("Wallet.First Use"))
        clean_markers = sorted(p.name for p in (clean.state / "moos").glob("*.done"))
        upgraded_markers = sorted(p.name for p in (upgraded.state / "moos").glob("*.done"))
        self.assertEqual(clean_markers, upgraded_markers,
                         "an upgraded account must end up owning exactly what a fresh one does")

    def test_the_ledger_is_parseable_and_its_outcomes_are_a_closed_set(self):
        account = Account(self)
        account.run()
        self.assertTrue(account.ledger, "a migrating account must leave a record")
        for row in account.ledger:
            self.assertEqual(len(row), 4, f"expected 4 tab-separated fields, got {row}")
            timestamp, identifier, revision, outcome = row
            self.assertRegex(timestamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertTrue(identifier and identifier[0].isalpha(), row)
            self.assertTrue(revision.isdigit(), f"a migration must carry its revision: {row}")
            self.assertIn(outcome, {"applied", "skipped", "preserved", "failed"}, row)

    def test_every_migration_id_carries_a_revision(self):
        """Versioned means the id itself pins the revision, so a bump re-runs the right accounts."""
        source = MIGRATE.read_text(encoding="utf-8")
        import re
        markers = set(re.findall(r'state_dir/([a-z0-9-]+)\.done"', source))
        markers.discard("gst-registry-${deployment}")
        self.assertTrue(markers, "expected marker names to inspect")
        for marker in markers:
            self.assertRegex(marker, r"-v?\d+$",
                             f"marker {marker!r} has no revision; a bump could not re-run it")

    def test_the_real_session_is_never_touched_by_this_gate(self):
        account = Account(self)
        account.run()
        recorded = account.recorded()
        self.assertIn("systemctl", recorded,
                      "the fake must be the one called — if not, the real systemctl was")
        self.assertNotIn("/usr/bin/systemctl", recorded)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(MigrationLedger))
    sys.exit(0 if result.wasSuccessful() else 1)
