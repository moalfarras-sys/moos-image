#!/usr/bin/env python3
""""Set up Android" must pass its OTA channels, because nothing supplies them here.

MEASURED ON THE STATION, 2026-09-20: `moai-do setup-waydroid` had never worked. Not
"was flaky" — had never, once, completed, from the day it shipped. Running it printed:

    ERROR: You must provide 'System OTA' and 'Vendor OTA' URLs.

`waydroid init` builds its download URL as

    <system_channel>/<rom_type>/waydroid_<arch>/<system_type>.json

and when `-c`/`-v` are absent it falls back to a channels config read by
`tools.config.load_channels()`. MoOS ships no such file and neither does Fedora's
waydroid package, so both channels resolved empty and initialisation stopped before
it downloaded a byte.

Why no gate caught it: every check that existed read the SOURCE. `moai-do`'s action
list was complete, the route existed, `moos-open` dispatched it, the confirmation
appeared — each half was correct and the whole thing was dead. It took running it on
a real machine, which is what plan row A1 is for.

So this gate holds the one property the source can express: the init call passes both
channels explicitly and does not depend on a file that is not there. The URLs
themselves were verified reachable before being written down —
`…/system/lineage/waydroid_x86_64/VANILLA.json` and
`…/vendor/waydroid_x86_64/MAINLINE.json` both answered HTTP 200 — but this test does
NOT reach the network: a gate that needs the internet fails for reasons that have
nothing to do with the tree, which is the same lesson `scripts/npm-audit-gate.sh`
exists for.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOAI_DO = ROOT / "system_files/usr/bin/moai-do"


def setup_action() -> str:
    """The body of do_setup_waydroid, where the init call lives."""
    source = MOAI_DO.read_text(encoding="utf-8")
    start = source.index("do_setup_waydroid()")
    # The next top-level function definition ends it.
    nxt = re.search(r"\n[a-z_]+\(\) \{", source[start + 10:])
    return source[start:start + 10 + (nxt.start() if nxt else len(source))]


class AndroidSetupPassesItsChannels(unittest.TestCase):
    def setUp(self):
        self.body = setup_action()
        self.source = MOAI_DO.read_text(encoding="utf-8")

    def init_call(self) -> str | None:
        """The whole `run_priv waydroid init` command, continuation lines included.

        Line logic rather than a regex on purpose: the command is written across
        several backslash-continued lines, and a pattern that consumes to end of
        line eats the backslash it then needs to see. A comment that merely
        mentions the command cannot match, because the line must START with it.
        """
        lines = self.body.splitlines()
        for index, line in enumerate(lines):
            if not line.strip().startswith("run_priv waydroid init"):
                continue
            call = [line]
            while call[-1].rstrip().endswith("\\") and index + len(call) < len(lines):
                call.append(lines[index + len(call)])
            return "\n".join(call)
        return None

    def test_the_init_call_passes_both_channels(self):
        """Without these, waydroid stops before downloading anything."""
        call = self.init_call()
        self.assertIsNotNone(
            call, "do_setup_waydroid no longer calls run_priv waydroid init")
        for flag, what in (("-c", "system"), ("-v", "vendor")):
            self.assertIn(
                f'{flag} "', call,
                f"`waydroid init` does not pass the {what} OTA channel ({flag}). "
                "MoOS ships no channels config for it to fall back on, so it will fail "
                "with \"You must provide 'System OTA' and 'Vendor OTA' URLs\" — which is "
                "exactly how this action shipped dead.")

    def test_the_channels_are_real_https_urls_with_a_default(self):
        for name in ("WAYDROID_SYSTEM_CHANNEL", "WAYDROID_VENDOR_CHANNEL"):
            match = re.search(rf'{name}="\$\{{{name}:-([^}}"]+)\}}"', self.source)
            self.assertIsNotNone(
                match, f"{name} must have a shipped default, not rely on the environment")
            url = match.group(1)
            self.assertTrue(url.startswith("https://"),
                            f"{name} must be https, got {url!r}")
            self.assertNotIn(" ", url)

    def test_the_action_still_asks_before_a_gigabyte_of_download(self):
        """The fix must not have quietly removed the consent along the way."""
        self.assertIn("confirm || return 0", self.body,
                      "setup-waydroid must still confirm: it downloads about a gigabyte "
                      "and starts a container")

    def test_the_action_still_escalates_through_the_one_privileged_path(self):
        self.assertIn("run_priv waydroid init", self.body,
                      "initialisation must go through run_priv (polkit), never a bare "
                      "sudo or a direct call")


if __name__ == "__main__":
    unittest.main(verbosity=2)
