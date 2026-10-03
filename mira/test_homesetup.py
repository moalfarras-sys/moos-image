"""The home hub on this computer: the quadlet Mira writes, the stages the page shows, and the first-run
setup's requests — with no real systemd, Podman or Home Assistant (the real first run was proven
against a throwaway Home Assistant 2026.9.4 on 2026-10-03; see the commit).
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import homesetup


class Quadlet(unittest.TestCase):
    def setUp(self):
        root = Path(tempfile.mkdtemp())
        self.quadlet = root / 'containers' / 'systemd' / 'mira-homeassistant.container'
        self.data = root / 'share' / 'config'
        patches = [mock.patch.object(homesetup, 'QUADLET', self.quadlet),
                   mock.patch.object(homesetup, 'DATA', self.data),
                   mock.patch.object(homesetup, '_zone', return_value='Europe/Berlin'),
                   mock.patch.object(homesetup, '_systemctl')]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        homesetup._systemctl.return_value = mock.Mock(returncode=0, stdout='', stderr='')

    def test_writes_a_pinned_host_network_quadlet_and_starts_without_blocking(self):
        result = homesetup.install()
        text = self.quadlet.read_text()
        self.assertTrue(result['written'])
        self.assertIn('@sha256:', text, 'the image is pinned by digest')
        self.assertIn('Network=host', text)
        self.assertIn(f'Volume={self.data}:/config:Z', text)
        self.assertIn('Environment=TZ=Europe/Berlin', text)
        self.assertTrue(self.data.is_dir())
        calls = [c.args for c in homesetup._systemctl.call_args_list]
        self.assertEqual(calls, [('daemon-reload',), ('start', '--no-block', homesetup.UNIT)])

    def test_never_rewrites_the_owners_own_hub(self):
        self.quadlet.parent.mkdir(parents=True)
        self.quadlet.write_text('[Container]\nImage=his/own:latest\n')
        result = homesetup.install()
        self.assertFalse(result['written'])
        self.assertEqual(self.quadlet.read_text(), '[Container]\nImage=his/own:latest\n')

    def test_a_failing_systemd_is_said(self):
        homesetup._systemctl.return_value = mock.Mock(returncode=1, stdout='', stderr='Unit not found')
        with self.assertRaises(homesetup.SetupError):
            homesetup.install()

    def test_stages(self):
        cases = [({'reachable': False}, False, 'inactive', False, 'none'),
                 ({'reachable': False}, False, 'activating', True, 'starting'),
                 ({'reachable': True, 'needs_onboarding': True}, False, 'active', True, 'onboarding'),
                 ({'reachable': True, 'needs_onboarding': False}, False, 'active', True, 'token'),
                 ({'reachable': True, 'needs_onboarding': False}, True, 'active', True, 'linked')]
        for probe, linked, unit, quadlet, stage in cases:
            with self.subTest(stage=stage), \
                    mock.patch('homehub.probe', return_value=probe), \
                    mock.patch('homehub.load', return_value=object() if linked else None), \
                    mock.patch.object(homesetup, '_unit_state', return_value=unit):
                if quadlet:
                    self.quadlet.parent.mkdir(parents=True, exist_ok=True)
                    self.quadlet.write_text('x')
                elif self.quadlet.exists():
                    self.quadlet.unlink()
                self.assertEqual(homesetup.status()['stage'], stage)


class FirstRun(unittest.TestCase):
    def test_account_token_and_link_in_order_and_nothing_of_the_password_kept(self):
        posts = []

        def post(url, body, *, token=None, form=False, timeout=30.0):
            posts.append((url.rsplit('/', 2)[-2:], dict(body), token, form))
            if url.endswith('/api/onboarding/users'):
                return {'auth_code': 'code-1'}
            if url.endswith('/auth/token'):
                return {'access_token': 'short-lived'}
            if url.endswith('/integration'):
                raise homesetup.SetupError('Home Assistant answered 403: step done')
            return {}

        session = mock.MagicMock()
        session.__enter__.return_value.command.return_value = 'L' * 180
        config = Path(tempfile.mkdtemp()) / 'home.json'
        hub = mock.Mock()
        with mock.patch.object(homesetup, '_post', side_effect=post), \
                mock.patch('homehub.Session', return_value=session) as opened, \
                mock.patch('homehub.load', return_value=hub):
            result = homesetup.onboard('Mohammed', 'Mohammed', 'secret-pass-1', config_path=config)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(posts[0][1]['username'], 'mohammed', 'user names are lower case')
        self.assertEqual(posts[1][1], {'grant_type': 'authorization_code', 'code': 'code-1',
                                       'client_id': homesetup.CLIENT_ID})
        self.assertTrue(posts[1][3], 'the token exchange is a form post')
        self.assertEqual([p[0][-1] for p in posts[2:]], ['core_config', 'analytics', 'integration'])
        self.assertTrue(all(p[2] == 'short-lived' for p in posts[2:]))
        opened.assert_called_once_with(homesetup.URL, 'short-lived', 15.0)
        command = session.__enter__.return_value.command.call_args.args[0]
        self.assertEqual(command['type'], 'auth/long_lived_access_token')
        saved = config.read_text()
        self.assertIn('L' * 180, saved)
        self.assertNotIn('secret-pass-1', saved)
        hub.states.assert_called_once_with()

    def test_refuses_a_weak_password_before_asking_anyone(self):
        with mock.patch.object(homesetup, '_post') as post:
            with self.assertRaises(homesetup.SetupError):
                homesetup.onboard('Mo', 'mo', 'short')
        post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
