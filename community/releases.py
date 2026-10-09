"""Accept only the currently promoted official digest and its OS-key signature."""
import json
from pathlib import Path
import re
import subprocess

REGISTRY = 'ghcr.io/moalfarras-sys'
EDITIONS = {'moos', 'moos-nvidia', 'moos-cloud', 'moos-arm'}


def verify_promoted(edition, version, digest, *, key='/etc/pki/containers/moos.pub', run=None):
    if (edition not in EDITIONS or not re.fullmatch(r'44\.\d{8}\.\d+', version)
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', digest) or not Path(key).is_file()):
        return False
    run = run or subprocess.run
    repository = f'{REGISTRY}/{edition}'
    def command(args):
        return run(args, capture_output=True, text=True, check=True, timeout=30).stdout
    def current():
        data = json.loads(command(['skopeo', 'inspect', f'docker://{repository}:latest']))
        return data['Digest'], data['Labels']['org.opencontainers.image.version']
    try:
        if current() != (digest, version):
            return False
        # Identical verification contract to the MoOS signed-image workflows;
        # no ignored transparency check or candidate/tag trust shortcut.
        payload = json.loads(command(['cosign', 'verify', '--key', key, '--output', 'json',
                                      repository+'@'+digest]))
        if not isinstance(payload, list) or not any(
            isinstance(item, dict) and item.get('critical', {}).get('image', {}).get(
                'docker-manifest-digest') == digest for item in payload):
            return False
        # Promotion may change while the signature is being checked.
        return current() == (digest, version)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError, AttributeError):
        return False
