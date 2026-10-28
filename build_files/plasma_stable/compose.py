#!/usr/bin/python3
"""Compose the reviewed stable Plasma stack in an unbooted x86 image only.

The native ARM base continues using its qualified native packages; the x86-only
publisher repository is never added to an ARM image. No installed-host layering.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


KEY_SHA256='b6ce6671a21c947928b08595514d09991975b2f300a8bb6e661fe34cfc54aa29'
FINGERPRINT='96BDF4E8710B8F9FFB11D83DDB51F4CB6C33BDBB'
REPO='copr:copr.fedorainfracloud.org:group_kdesig:kde-final'
EXPECTED={name:'6.8.2-1.fc44' for name in ('plasma-workspace','plasma-desktop',
          'kwin','libplasma','kscreenlocker','plasma-login-manager')}

def run(*args):
    return subprocess.check_output(list(args),text=True).strip()


def sync_packages():
    # The current vendor base can make one transaction rotate DNF's 1MiB
    # log. Keep only build-command logs private, as the beta composer does;
    # do not admit rotated logs into the generic mutable-state contract.
    with tempfile.TemporaryDirectory(prefix='moos-stable-dnf-',dir='/tmp') as logs:
        options=['dnf5','--setopt=logdir='+logs]
        subprocess.run([*options,'-y','distro-sync','--refresh','--best',
                        '--setopt=install_weak_deps=False','--exclude=kernel*'],check=True)
        actual={name:run('rpm','-q','--qf','%{VERSION}-%{RELEASE}',name) for name in EXPECTED}
        if actual!=EXPECTED:
            raise RuntimeError('stable desktop package inputs drifted: '+repr(actual))
        subprocess.run([*options,'clean','all'],check=True)
    return actual

def compose(root=Path('/')):
    if root!=Path('/') or not Path('/run/.containerenv').exists() or Path('/run/ostree-booted').exists():
        raise RuntimeError('stable Plasma composition requires an unbooted image build container')
    if run('rpm','--eval','%{_arch}')!='x86_64':
        raise RuntimeError('the reviewed stable repository contains x86_64 packages only')
    key=Path(__file__).with_name('kde-final-pubkey.gpg').read_bytes()
    if hashlib.sha256(key).hexdigest()!=KEY_SHA256:
        raise RuntimeError('publisher signing key bytes differ from the reviewed key')
    current=run('rpm','-q','--qf','%{VERSION}', 'plasma-workspace')
    if current not in ('6.7.5','6.7.91','6.8.0','6.8.1','6.8.2'):
        raise RuntimeError('unreviewed Plasma base version: '+current)
    dest=Path('/usr/share/moos/keys/kde-final-pubkey.gpg');dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(key);dest.chmod(0o644)
    run('rpm','--import',str(dest))
    repo=Path('/etc/yum.repos.d/moos-plasma-stable.repo')
    repo.write_text(f'[{REPO}]\nname=MoOS reviewed stable desktop source\n'
                    'baseurl=https://download.copr.fedorainfracloud.org/results/@kdesig/kde-final/fedora-44-$basearch/\n'
                    'enabled=1\ngpgcheck=1\nsslverify=1\n'
                    f'gpgkey=file://{dest}\nskip_if_unavailable=0\n')
    # Preserve the base kernel and its matching driver input. A solver conflict
    # fails the build; do not erase desktop/authentication or input components.
    from runtime_state import Transaction
    from finalize_canary_base import finalize as finalize_canary_base
    transaction = Transaction()
    actual=sync_packages()
    Path('/usr/share/moos/plasma-stable.json').write_text(json.dumps({
        'schema':1,'architecture':'x86_64','packages':actual,'signing_key_sha256':KEY_SHA256,
        'signing_key_fingerprint':FINGERPRINT,'source':REPO},indent=2)+'\n')
    # An already-upgraded canary has no systemd trigger to reconcile this
    # RPM's01770 empty directory with its native0750 runtime creator.
    from login_state import reconcile as reconcile_login_state
    reconcile_login_state(transaction)
    # A systemd upgrade runs machine-id-setup and global tmpfiles even during
    # an image compose. Restore the pristine input before any SDK/final stage
    # can inherit those runtime identities and service scaffolds.
    finalize_canary_base(Path('/'))
    transaction.finalize()

if __name__=='__main__': compose()
