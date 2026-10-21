#!/usr/bin/python3
"""Normalize the pristine native ARM base before SDK/runtime package stages.

The published bootc image has three extra empty scaffolds. Verify their exact
metadata, empty identity and native var/run authority before retiring them;
then use the same in-memory pristine package transaction as x86. No installed
host identity or arbitrary persistent data may enter this operation.
"""
import json
import hashlib
import os
from pathlib import Path
import stat
import subprocess

from finalize_image_state import owned_path
from finalize_canary_base import finalize as finalize_canary
from finalize_root_home import finalize as finalize_root_home
from runtime_state import Transaction

RPMSTATE_AUTHORITY='usr/lib/tmpfiles.d/bootc-base-rpmstate.conf'
REVIEWED_RPMSTATE_SHA256='2dd8ea0e27ce15f7182dc9d358dbeead11880dec0fd7aefc9511ede98aa96680'
# These generated native NSS inputs arrive root:root0664 in the published
# pristine base. Make only these exact known bodies root-writable before the
# shared account reader consumes them. Names/IDs/content remain unchanged.
GENERATED_ACCOUNTS={
    'usr/lib/passwd':(2161,'5cc5d8b1c2b1b992396f9086a449373070664fc155b93a7855b9747b189ad2ae'),
    'usr/lib/group':(828,'dd95420d94abe0a69e9ace9df1acc368256e4323e9266aa6e4af73ae5dfbb6dc'),
}


def account_permission_plan(root):
    owner=root.stat();pending=[]
    for relative,(size,digest) in GENERATED_ACCOUNTS.items():
        path=owned_path(root,relative)
        if not path.exists():continue
        info=path.lstat();mode=stat.S_IMODE(info.st_mode)
        if (not stat.S_ISREG(info.st_mode) or mode not in (0o644,0o664)
                or info.st_uid!=owner.st_uid or info.st_gid!=owner.st_gid
                or path.is_mount() or info.st_size>1024*1024):
            raise RuntimeError('unsafe ARM native account input')
        if mode==0o664:
            if info.st_size!=size or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('unreviewed writable ARM account input')
            pending.append((path,digest))
    return pending


def canonicalize_account_permissions(pending):
    for path,digest in pending:
        path.chmod(0o644)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise RuntimeError('ARM account content changed during permission normalization')
    if pending:print('ARM native account inputs: exact bytes retained; write permission restricted to root')


class ArmTransaction(Transaction):
    def authority(self,record):
        for entry in record.get('authorities',[]):
            path=owned_path(self.root,entry['authority']);info=path.lstat()
            if entry['authority']==RPMSTATE_AUTHORITY and stat.S_IMODE(info.st_mode)&0o020:
                # The published bootc base generates this one root:root0664
                # authority. Preserve it, accepting only its fully reviewed
                # bytes/metadata/rule; every other writable input still refuses.
                if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o664
                        or info.st_uid!=self.owner.st_uid or info.st_gid!=self.owner.st_gid
                        or info.st_size!=100 or path.is_mount()
                        or entry['rule']!=['d','/var/lib/rpm-state','0755','-','-','-']
                        or hashlib.sha256(path.read_bytes()).hexdigest()!=REVIEWED_RPMSTATE_SHA256):
                    raise RuntimeError('unreviewed ARM rpm-state authority')
            else:
                super().authority({'authorities':[entry]})


def require_container(root):
    if root == Path('/') and (not Path('/run/.containerenv').exists()
                             or Path('/run/ostree-booted').exists()):
        raise RuntimeError('ARM base preparation requires an unbooted build container')


def canonicalize_input(root):
    root=root.resolve();require_container(root);owner=root.stat()
    identity=owned_path(root,'etc/machine-id')
    Transaction.require(identity,'file',0o644,owner.st_uid,owner.st_gid)
    if identity.stat().st_size:raise RuntimeError('ARM base input identity must be empty')
    alias=root/'root'
    if (not alias.is_symlink() or os.readlink(alias)!='var/roothome'
            or alias.lstat().st_uid!=owner.st_uid or alias.lstat().st_gid!=owner.st_gid):
        raise RuntimeError('ARM root-home alias is not canonical')
    accounts=account_permission_plan(root)
    var=owned_path(root,'var');Transaction.require(var,'directory',0o755,owner.st_uid,owner.st_gid)
    tmp=owned_path(root,'var/tmp');Transaction.require(tmp,'directory',0o1777,owner.st_uid,owner.st_gid)
    if any(tmp.iterdir()):raise RuntimeError('ARM base tmp contains unexpected data')
    entries={p.name for p in var.iterdir()}
    if entries=={'tmp'}:
        canonicalize_account_permissions(accounts)
        return
    if entries!={'tmp','lib','run'}:raise RuntimeError('unexpected ARM base input state')
    library=owned_path(root,'var/lib');state=owned_path(root,'var/lib/rpm-state')
    for path in (library,state):Transaction.require(path,'directory',0o775,owner.st_uid,owner.st_gid)
    if {p.name for p in library.iterdir()}!={'rpm-state'} or any(state.iterdir()):
        raise RuntimeError('ARM base package scaffold contains unexpected data')
    run=var/'run';Transaction.require(run,'link',0o777,owner.st_uid,owner.st_gid)
    if os.readlink(run)!='../run':raise RuntimeError('ARM base run alias drifted')
    authority=owned_path(root,'usr/lib/tmpfiles.d/var.conf');info=authority.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_size>64*1024 or authority.is_mount()
            or info.st_uid!=owner.st_uid or info.st_gid!=owner.st_gid
            or stat.S_IMODE(info.st_mode)&0o022):
        raise RuntimeError('unsafe ARM base run authority')
    rules=[line.split() for line in authority.read_text().splitlines()
           if line.strip() and not line.lstrip().startswith('#')]
    rules=[rule for rule in rules if len(rule)>1 and rule[1]=='/var/run']
    if rules!=[['L','/var/run','-','-','-','-','../run']]:
        raise RuntimeError('ARM base run authority drifted')
    # Every initial scaffold/identity/authority was checked before any deletion.
    canonicalize_account_permissions(accounts)
    run.unlink();state.rmdir();library.rmdir()
    print('ARM pristine input: exact native empty package scaffolds and run alias retired')


def main():
    root=Path('/');require_container(root)
    arch=subprocess.check_output(['rpm','--eval','%{_arch}'],text=True).strip()
    if arch!='aarch64':raise RuntimeError('ARM base preparation requires native ARM package architecture')
    canonicalize_input(root)
    records=json.loads(Path(__file__).with_name('arm-runtime-rules.json').read_text())['records']
    transaction=ArmTransaction(root,records)
    subprocess.run(['dnf5','-y','upgrade','--refresh','--best',
                    '--setopt=install_weak_deps=False','--exclude=kernel*','systemd'],check=True)
    subprocess.run(['dnf5','clean','all'],check=True)
    finalize_canary(root)
    finalize_root_home(root)
    transaction.finalize()
    print('ARM native base package transaction complete; full image and boot gates remain required')


if __name__=='__main__':main()
