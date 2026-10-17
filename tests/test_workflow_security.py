#!/usr/bin/env python3
"""Real workflow checks plus isolated broken-source negative controls."""
import importlib.util
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workflow_security', ROOT / 'build_files/verify_workflow_security.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
CHECKOUT = re.search(r'actions/checkout@[0-9a-f]{40}',
                     (ROOT / '.github/workflows/repo-gates.yml').read_text()).group()


class WorkflowSecurity(unittest.TestCase):
    def test_maintained_workflows(self):
        self.assertGreater(gate.verify(ROOT), 0)

    def broken(self, filename, before, after, message):
        with tempfile.TemporaryDirectory(prefix='moos-workflow-security-') as directory:
            root = Path(directory)
            shutil.copytree(ROOT / '.github', root / '.github')
            path = root / '.github/workflows' / filename
            source = path.read_text()
            self.assertIn(before, source)
            path.write_text(source.replace(before, after, 1))
            with self.assertRaisesRegex(ValueError, message):
                gate.verify(root)

    def test_moving_tag_is_rejected(self):
        self.broken('repo-gates.yml',
                    CHECKOUT,
                    'actions/checkout@v5', 'mutable action')

    def test_unknown_complete_sha_is_rejected(self):
        self.broken('repo-gates.yml',
                    CHECKOUT,
                    'actions/checkout@'+'0'*40, 'absent from reviewed pins')

    def test_persisted_checkout_token_is_rejected(self):
        self.broken('repo-gates.yml', 'persist-credentials: false',
                    'persist-credentials: true', 'must not persist credentials')

    def test_public_comment_cannot_remove_owner_boundary(self):
        self.broken('claude.yml', '${{ github.actor == github.repository_owner }}',
                    '${{ true }}', 'exact owner boundary')

    def test_public_comment_cannot_bypass_owner_with_or_true(self):
        self.broken('claude.yml', '${{ github.actor == github.repository_owner }}',
                    '${{ github.actor == github.repository_owner || true }}', 'exact owner boundary')

    def test_fork_head_cannot_enter_advisory_secret_job(self):
        self.broken('claude-code-review.yml',
                    ' && github.event.pull_request.head.repo.full_name == github.repository',
                    '', 'exact owner boundary')

    def test_privileged_pr_event_is_rejected(self):
        self.broken('repo-gates.yml', '  pull_request:', '  pull_request_target:',
                    'privileged PR trigger')

    def test_broad_write_permissions_are_rejected(self):
        self.broken('repo-gates.yml', 'permissions:\n  contents: read',
                    'permissions: write-all', 'broad write permissions')


if __name__ == '__main__':
    unittest.main()
