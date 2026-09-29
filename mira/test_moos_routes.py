"""Mira's moos:// allowlist: strict, whole-URL, and every route it allows is one moos-open declares.

A route Mira may open but moos-open has no case for lands in the router's default arm ("unknown
MoOS action"): a button that does nothing (AGENTS.md, "A button is only as real as its route").

    /var/home/moos/.local/share/mira/venv/bin/python -m unittest test_moos_routes -v
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import moos_routes  # noqa: E402

HERE = Path(__file__).resolve().parent
ROUTER = HERE.parent / 'system_files/usr/bin/moos-open'
PID = '0123456789abcdef0123'          # the id moos_routes.EXAMPLES uses

# At least one real URL per allowlist pattern (moos_routes.EXAMPLES); test_every_pattern_has_a_sample
# keeps that list complete.
SAMPLES = moos_routes.EXAMPLES

REFUSED = [
    None, 7, '', 'moos://', 'https://example.com',
    'moos://app/moplayer',                              # moos-open has no such arm
    'moos://app/store/', 'moos://app/store\n', ' moos://app/store', 'moos://app/storex',
    'moos://privacy/stop-sharing/now', 'moos://privacy/stop-sharingx', 'moos://privacy/stop/rdp',
    'moos://dev/code/' + PID[:-1],                      # 19 digits
    'moos://dev/code/' + PID + '0',                     # 21 digits
    'moos://dev/code/' + PID.upper(),
    'moos://dev/code/' + PID + '/',
    'moos://dev/code/' + PID + '?x=1',
    'moos://dev/code/../../etc',
    'moos://dev/code/%2E%2E%2Fetc%2Fpasswd0000',
    'moos://dev/bash/' + PID,
    'moos://dev/' + PID,
    'moos://dev/codex/' + PID + '\n',
    'moos://settings/', 'moos://settings/Update', 'moos://settings/a/b',
    'moos://apps/install-file/file%3A%2F%2F%2F', 'moos://apps/install-file/https%3A%2F%2Fx',
    'moos://do/update', 'moos://ai/ask/hello',
]


def declared_routes(text):
    """moos-open's case labels ('app/store', 'apps/install-file/*'…), never the bare `*` default arm."""
    labels = set()
    for match in re.finditer(r'^\s{4}([a-z0-9/*|-]+)\)', text, re.MULTILINE):
        labels.update(label.strip() for label in match.group(1).split('|') if label.strip() != '*')
    return labels


def covered(path, labels):
    return path in labels or any(label.endswith('*') and path.startswith(label[:-1]) for label in labels)


class Allowlist(unittest.TestCase):
    def test_samples_are_allowed(self):
        for url in SAMPLES:
            self.assertTrue(moos_routes.allowed(url), url)

    def test_near_misses_are_refused(self):
        for url in REFUSED:
            self.assertFalse(moos_routes.allowed(url), repr(url))

    def test_every_pattern_has_a_sample(self):
        for pattern in moos_routes._ALLOWED:
            self.assertTrue(any(re.fullmatch(pattern, url) for url in SAMPLES),
                            f'{pattern} has no sample here, so nothing proves moos-open routes it')

    def test_the_workbench_project_route_takes_only_a_registered_id_shape(self):
        for agent in ('code', 'codex', 'claude', 'opencode'):
            self.assertTrue(moos_routes.allowed(f'moos://dev/{agent}/{PID}'))
            self.assertFalse(moos_routes.allowed(f'moos://dev/{agent}/{PID[:10]}'))
            self.assertFalse(moos_routes.allowed(f'moos://dev/{agent}/{"g" * 20}'))

    def test_open_route_refuses_before_any_process_starts(self):
        with mock.patch('subprocess.Popen') as popen:
            self.assertEqual(moos_routes.open_route('moos://app/moplayer'),
                             {'status': 'error', 'error': 'route_not_allowed'})
            self.assertEqual(moos_routes.open_route('moos://dev/code/' + PID + ';rm'),
                             {'status': 'error', 'error': 'route_not_allowed'})
        popen.assert_not_called()

    def test_open_route_hands_the_exact_url_to_moos_open(self):
        with mock.patch('subprocess.Popen') as popen:
            self.assertEqual(moos_routes.open_route('moos://privacy/stop-sharing'), {'status': 'ok'})
        self.assertEqual(popen.call_args.args[0], ['moos-open', 'moos://privacy/stop-sharing'])
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        with mock.patch('subprocess.Popen', side_effect=FileNotFoundError('moos-open')):
            self.assertEqual(moos_routes.open_route('moos://app/store'),
                             {'status': 'error', 'error': 'FileNotFoundError'})

    def test_file_route_stays_inside_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            inside = home / 'Downloads' / 'My Tool.AppImage'
            inside.parent.mkdir()
            inside.write_bytes(b'\x7fELF')
            with mock.patch.object(Path, 'home', return_value=home):
                route = moos_routes.file_route('install-file', str(inside))
                self.assertTrue(moos_routes.allowed(route), route)
                self.assertTrue(route.startswith('moos://apps/install-file/file%3A%2F%2F%2F'))
                with self.assertRaises(ValueError):
                    moos_routes.file_route('install-file', '/etc/passwd')
                with self.assertRaises(ValueError):
                    moos_routes.file_route('install-rpm', str(home / 'missing.rpm'))


@unittest.skipUnless(ROUTER.is_file(), 'moos-open is not in this tree (the image build stage copies only Mira)')
class RouterAgrees(unittest.TestCase):
    def setUp(self):
        self.labels = declared_routes(ROUTER.read_text(encoding='utf-8'))

    def test_the_default_arm_is_not_a_route(self):
        self.assertNotIn('*', self.labels)
        self.assertGreater(len(self.labels), 20, 'the case statement of moos-open was not read')
        self.assertFalse(covered('app/moplayer', self.labels), 'this check can fail')

    def test_every_allowed_route_has_a_case_in_moos_open(self):
        for url in SAMPLES:
            path = url[len('moos://'):]
            self.assertTrue(covered(path, self.labels),
                            f'Mira may open {url}, but moos-open has no case for it: that button does nothing')

    def test_every_settings_page_mira_names_has_a_case(self):
        pages = set()
        for source in [HERE / 'moos_routes.py', HERE / 'controller.py', *sorted((HERE / 'pages').glob('*.py'))]:
            if source.is_file():
                pages.update(re.findall(r"moos://settings/([a-z0-9][a-z0-9-]*[a-z0-9])['\"]",
                                        source.read_text(encoding='utf-8')))
        self.assertTrue(pages, 'no settings page was found in Mira; this check read nothing')
        for page in sorted(pages):
            self.assertTrue(covered('settings/' + page, self.labels), f'settings/{page} has no case in moos-open')


if __name__ == '__main__':
    unittest.main(verbosity=2)
