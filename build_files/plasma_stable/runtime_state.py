#!/usr/bin/python3
"""Restore a pristine image after the native systemd RPM transaction.

This is a build transaction, never a general machine-id reset or /var cleaner.
The pristine input is verified before dnf; all cleanup is preflighted afterwards.
Only reviewed empty native scaffolds, derived package caches/catalog and a newly
created systemd identity/seed can retire. The general final image gate is separate.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

from finalize_canary_base import mount_points, refuse_mounted_tree, refuse_tmpfiles_overrides, mapped_local_override_folder
from finalize_image_state import owned_path, reject_unsafe_cleanup_entries


class Transaction:
    def __init__(self, root=Path('/'), records=None):
        self.root = root.resolve()
        if self.root == Path('/') and (not Path('/run/.containerenv').exists()
                                      or Path('/run/ostree-booted').exists()):
            raise RuntimeError('runtime normalization requires an unbooted build container')
        self.mounts = mount_points()
        refuse_mounted_tree(self.root, self.root / "var", self.mounts)
        refuse_mounted_tree(self.root, self.root / "etc/machine-id", self.mounts)
        self.owner = self.root.stat()
        self.records = records if records is not None else json.loads(
            Path(__file__).with_name('runtime-rules.json').read_text())['records']
        self.identity = owned_path(self.root, 'etc/machine-id')
        self.require(self.identity, 'file', 0o644, self.owner.st_uid, self.owner.st_gid)
        if self.identity.stat().st_size:
            raise RuntimeError('transaction input machine-id must be empty')
        var = owned_path(self.root, 'var')
        self.require(var, 'directory', 0o755, self.owner.st_uid, self.owner.st_gid)
        entries = list(var.iterdir())
        if [p.name for p in entries] != ['tmp']:
            raise RuntimeError('transaction input /var must contain only empty tmp')
        self.require(var/'tmp', 'directory', 0o1777, self.owner.st_uid, self.owner.st_gid)
        if any((var/'tmp').iterdir()):
            raise RuntimeError('transaction input /var/tmp must be empty')
        self.finished = False

    @staticmethod
    def require(path, kind, mode, uid, gid):
        info = path.lstat()
        kinds = {'file': stat.S_ISREG, 'directory': stat.S_ISDIR, 'link': stat.S_ISLNK}
        if (not kinds[kind](info.st_mode) or stat.S_IMODE(info.st_mode) != mode
                or info.st_uid != uid or info.st_gid != gid or path.is_mount()
                or (kind == 'file' and info.st_nlink != 1)):
            raise RuntimeError('unsafe transaction metadata: '+str(path))

    def ids(self, record):
        def lookup(file, name, field):
            if name == 'root':return self.owner.st_uid if file == 'passwd' else self.owner.st_gid
            matches = set()
            # Atomic images retain vendor service identities in /usr/lib;
            # /etc contains the mutable account additions. Refuse conflicts.
            for prefix in ('etc/', 'usr/lib/'):
                path = owned_path(self.root, prefix+file)
                if not path.exists():continue
                info = path.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_size > 1024*1024
                        or info.st_uid != self.owner.st_uid or info.st_gid != self.owner.st_gid
                        or stat.S_IMODE(info.st_mode) & 0o022 or path.is_mount()):
                    raise RuntimeError('unsafe native account authority')
                for line in path.read_text().splitlines():
                    a=line.split(':')
                    if a[0] == name:matches.add(int(a[field]))
            if len(matches) != 1:raise RuntimeError('ambiguous native owner: '+name)
            return matches.pop()
        return lookup('passwd', record['user'], 2), lookup('group', record['group'], 2)

    def authority(self, record):
        for authority in record.get('authorities', []):
            refuse_tmpfiles_overrides(self.root, authority['authority'], self.mounts)
            path = owned_path(self.root, authority['authority'])
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_size > 64*1024 or path.is_mount()
                    or info.st_uid != self.owner.st_uid or info.st_gid != self.owner.st_gid
                    or stat.S_IMODE(info.st_mode) & 0o022):
                raise RuntimeError('unsafe runtime tmpfiles authority')
            rules = [line.split() for line in path.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith('#')]
            scoped = [r for r in rules if len(r)>1 and r[1] == authority['rule'][1]
                      and r[0].rstrip('!+-~^$=') in ('d','D','L','f','v','q','Q')]
            if scoped != [authority['rule']]:
                raise RuntimeError('runtime tmpfiles authority drifted: '+str(path))

    def ssh_migration_authority(self):
        # The native14->16 upgrade runs POSTIN even in an OSTree build and
        # touches this empty completion marker. This is not permission to
        # retire a key, an installed machine's state, or an unknown creator.
        package = 'openssh-server'
        command = ['rpm', '--root', str(self.root), '-q']
        expected = 'openssh-server 10.2p1-16.fc44 x86_64 openssh-10.2p1-16.fc44.src.rpm'
        actual = subprocess.check_output([*command, '--qf',
            '%{NAME} %{VERSION}-%{RELEASE} %{ARCH} %{SOURCERPM}', package], text=True)
        if actual != expected:
            raise RuntimeError('unreviewed SSH migration package')
        postin = subprocess.check_output([*command, '--qf', '%{POSTIN}', package])
        if hashlib.sha256(postin).hexdigest() != '8b779b4969ab318b9400284739e8c2eb37fafcc2170fdf1923cede900fdde2fa':
            raise RuntimeError('SSH migration POSTIN authority drifted')
        rows = subprocess.check_output([*command, '--dump', package], text=True).splitlines()
        authorities = {
            'usr/libexec/openssh/ssh-host-keys-migration.sh':
                (0o744, '423ed19b93c41154c490f15f2989294e67ee31582d60e08f311602cea4abaf82'),
            'usr/lib/systemd/system/ssh-host-keys-migration.service':
                (0o644, '679dcbee8d88ff85b4ed05766aa561ea538830bd706182e65a80d911f4060cec'),
        }
        for relative, (mode, digest) in authorities.items():
            path = owned_path(self.root, relative)
            refuse_mounted_tree(self.root, path, self.mounts)
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != mode
                    or info.st_uid != self.owner.st_uid or info.st_gid != self.owner.st_gid
                    or info.st_size > 64*1024 or path.is_mount()):
                raise RuntimeError('unsafe SSH migration authority')
            # Read-only package inputs may legitimately have base hardlinks;
            # the runtime retirement target still requires exactly one link.
            matches = [row.split() for row in rows if row.split()[0] == '/'+relative]
            if (hashlib.sha256(path.read_bytes()).hexdigest() != digest
                    or len(matches) != 1 or matches[0][3] != digest):
                raise RuntimeError('SSH migration authority payload drifted')
        for prefix in ('etc/systemd/system', 'run/systemd/system', 'usr/local/lib/systemd/system'):
            prefix = mapped_local_override_folder(self.root, prefix, self.mounts)
            for suffix in ('ssh-host-keys-migration.service', 'ssh-host-keys-migration.service.d'):
                path = self.root / prefix / suffix
                refuse_mounted_tree(self.root, path, self.mounts)
                owned_path(self.root, prefix)
                if os.path.lexists(path):
                    raise RuntimeError('SSH migration unit override')
        keys = owned_path(self.root, 'etc/ssh')
        refuse_mounted_tree(self.root, keys, self.mounts)
        self.require(keys, 'directory', 0o755, self.owner.st_uid, self.owner.st_gid)
        if any(keys.glob('ssh_host_*')):
            raise RuntimeError('SSH host key state must be preserved')

    def catalog_matches(self, path):
        # Rebuild from the actual immutable native catalogue inputs. Never bless
        # arbitrary nonempty data merely because its filename looks generated.
        refuse_mounted_tree(self.root, self.root / 'usr/lib/systemd/catalog', self.mounts)
        source = owned_path(self.root, 'usr/lib/systemd/catalog')
        with tempfile.TemporaryDirectory(prefix='moos-catalog-', dir='/tmp') as temp:
            target = Path(temp)/'usr/lib/systemd/catalog';target.mkdir(parents=True)
            for entry in source.iterdir():
                info = entry.lstat()
                if (not stat.S_ISREG(info.st_mode) or entry.is_mount()
                        or info.st_uid != self.owner.st_uid or info.st_gid != self.owner.st_gid
                        or stat.S_IMODE(info.st_mode) & 0o022 or info.st_size > 4*1024*1024):
                    raise RuntimeError('unsafe native catalogue input')
                shutil.copyfile(entry, target/entry.name)
            subprocess.run(['journalctl', '--root='+temp, '--update-catalog'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            rebuilt = Path(temp)/'var/lib/systemd/catalog/database'
            return hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(rebuilt.read_bytes()).digest()

    def finalize(self):
        if self.finished:raise RuntimeError('transaction already finalized')
        self.mounts = mount_points()
        refuse_mounted_tree(self.root, self.root / 'var', self.mounts)
        refuse_mounted_tree(self.root, self.root / 'etc/machine-id', self.mounts)
        self.require(self.identity, 'file', 0o644, self.owner.st_uid, self.owner.st_gid)
        if self.identity.stat().st_size not in (0,33):
            raise RuntimeError('unexpected transaction-generated machine-id')
        identity = self.identity.read_bytes()
        if identity and (len(identity) != 33 or identity[-1:] != b'\n'
                         or any(c not in b'0123456789abcdef' for c in identity[:-1])
                         or identity[:-1] == b'0'*32):
            raise RuntimeError('unexpected transaction-generated machine-id')
        # Cache/log cleanup already belongs to the image build contract. Refuse
        # escaping links, mounts and special nodes before touching any tree.
        derived = ('var/cache', 'var/lib/dnf/repos')
        for relative in derived:reject_unsafe_cleanup_entries(self.root, relative)
        pending=[]
        def walk(path):
            for child in path.iterdir():
                rel=str(child.relative_to(self.root))
                if rel == 'var/tmp':
                    self.require(child,'directory',0o1777,self.owner.st_uid,self.owner.st_gid)
                    if any(child.iterdir()):raise RuntimeError('unexpected transaction tmp payload')
                    continue
                if any(rel == prefix or rel.startswith(prefix+'/') for prefix in derived):
                    continue
                if rel == 'var/log/dnf5.log':
                    self.require(child,'file',0o644,self.owner.st_uid,self.owner.st_gid)
                    pending.append(child);continue
                record=self.records.get(rel)
                if record is None:raise RuntimeError('unexpected transaction state: '+rel)
                # The final component may be an exact reviewed runtime alias;
                # every parent is still checked without following a link.
                owned_path(self.root,str(child.parent.relative_to(self.root)))
                self.require(child,record['kind'],record['mode'],*self.ids(record))
                self.authority(record)
                if rel == 'var/lib/.ssh-host-keys-migration':
                    if record.get('rpm_postin_authority') != 'openssh-server-10.2p1-16.fc44.x86_64':
                        raise RuntimeError('unreviewed SSH migration authority role')
                    if child.stat().st_size:
                        raise RuntimeError('nonempty SSH migration marker')
                    self.ssh_migration_authority()
                if record['kind']=='link':
                    if os.readlink(child)!=record['target']:
                        raise RuntimeError('runtime alias drifted: '+rel)
                elif record['kind']=='directory':walk(child)
                elif rel == 'var/lib/systemd/random-seed':
                    if not identity or child.stat().st_size != 32:
                        raise RuntimeError('unexpected transaction random seed')
                elif rel == 'var/lib/systemd/catalog/database':
                    if child.stat().st_size > 16*1024*1024 or not self.catalog_matches(child):
                        raise RuntimeError('native catalogue mismatch')
                elif child.stat().st_size:
                    raise RuntimeError('nonempty transaction scaffold: '+rel)
                pending.append(child)
        walk(owned_path(self.root,'var'))
        # All policies, identities and state have passed. Restore only the empty
        # identity observed in this same transaction; no persisted reset receipt.
        for relative in derived:
            path=owned_path(self.root,relative)
            if path.exists():
                for child in path.iterdir():
                    if child.is_dir():shutil.rmtree(child)
                    else:child.unlink()
                if relative != 'var/cache':path.rmdir()
                else:pending.append(path)
        for path in sorted(pending,key=lambda p:len(p.parts),reverse=True):
            if path.is_symlink():path.unlink()
            elif path.is_dir():path.rmdir()
            else:path.unlink()
        with self.identity.open('r+b') as file:file.truncate(0)
        self.finished=True
        print('Native RPM transaction: pristine empty identity restored; reviewed runtime scaffolds retired; authorities preserved')
