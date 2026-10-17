#!/usr/bin/env python3
"""Baloo must start after the desktop publishes its graphical environment."""
import configparser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DROPIN = ROOT / 'system_files/usr/lib/systemd/user/kde-baloo.service.d/30-moos-session-ordering.conf'


class BalooStartup(unittest.TestCase):
    def test_indexer_waits_for_core_not_its_own_parent(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read(DROPIN)
        after = config.get('Unit', 'After').split()
        self.assertIn('plasma-core.target', after)
        # kde-baloo is Before=plasma-workspace.target; waiting for that same
        # parent would create an ordering cycle and discard a startup job.
        self.assertNotIn('plasma-workspace.target', after)
        self.assertNotIn('graphical-session.target', after)

    def test_vendor_index_and_idle_integration_remain_owned_upstream(self):
        text = DROPIN.read_text()
        for override in ('ExecStart=', 'Environment=', 'Restart=', 'WantedBy=', 'Requires='):
            self.assertNotIn(override, text)
        self.assertTrue((ROOT / 'system_files/usr/lib/systemd/user/kde-baloo.service.d/20-moos-regexp-stability.conf').is_file())


if __name__ == '__main__':
    unittest.main()
