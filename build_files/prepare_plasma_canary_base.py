#!/usr/bin/python3
"""Compose the experimental KDE base within one pristine image transaction.

No installed identity is reset. The shared transaction verifies an unbooted,
empty input before any package command and preflights its own generated state.
The next-version assertion and full MoOS gates remain separate and mandatory.
"""
from pathlib import Path
import subprocess
import tempfile

from runtime_state import Transaction
from finalize_canary_base import finalize as finalize_canary
from finalize_root_home import finalize as finalize_root_home


def dnf(logdir,*arguments):
    subprocess.run(['dnf5','--setopt=logdir='+logdir,*arguments],check=True)


def compose():
    transaction=Transaction()
    arch=subprocess.check_output(['rpm','--eval','%{_arch}'],text=True).strip()
    if arch!='x86_64':raise RuntimeError('experimental KDE base requires x86_64')
    # Several DNF calls can rotate a 1MiB log into /var/log/dnf5.log.1. Keep
    # only these build-command logs in a private temporary directory instead
    # of widening the shared runtime/identity gate to accept arbitrary logs.
    # Native command stdout/stderr remains in the retained compose log.
    with tempfile.TemporaryDirectory(prefix='moos-canary-dnf-',dir='/tmp') as logs:
        dnf(logs,'-y','copr','enable','@kdesig/kde-beta')
        optional=subprocess.run(['rpm','-q','kcm-fcitx5'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if optional.returncode not in (0,1):raise RuntimeError('optional input-module query failed')
        if optional.returncode==0:
            dnf(logs,'-y','remove','--no-autoremove','kcm-fcitx5')
        # Keep the exact stock boot kernel just as stable composition does.
        # Without exclusion, distro-sync reinstalls the same-NVR untrimmed
        # kernel RPM, runs dracut and leaves an unrelated rpm-state/kernel.
        dnf(logs,'-y','distro-sync','--refresh','--allowerasing','--best','--exclude=kernel*')
        dnf(logs,'clean','all')
    finalize_canary(Path('/'))
    finalize_root_home(Path('/'))
    transaction.finalize()
    print('Experimental KDE base: pristine transaction complete; next-version and full image gates still required')


if __name__=='__main__':compose()
