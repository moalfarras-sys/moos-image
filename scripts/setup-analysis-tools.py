#!/usr/bin/env python3
"""Optional user-space REA/Ghidra profile; reuses the existing MoOS SDK.

--check is read-only. Installation needs the two official versioned archives;
no host RPM, kernel, account, provider or MCP configuration is changed.
"""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile

INPUTS=Path(__file__).resolve().parent/'workstation/analysis-tools'
LEASE='.analysis-tools-profile.lock'


def digest(path,algorithm='sha256'):
    h=hashlib.new(algorithm)
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def child(root,relative):
    parts=Path(relative)
    if parts.is_absolute() or '..' in parts.parts:raise RuntimeError('unsafe archive path')
    result=root/parts
    for parent in (result,*result.parents):
        if parent==root.parent:break
        if parent.is_symlink():raise RuntimeError('archive path is a link')
    return result


def verify_ghidra(archive,target,manifest,extract=False):
    if archive.stat().st_size!=manifest['bytes'] or digest(archive)!=manifest['sha256']:
        raise RuntimeError('official Ghidra archive digest/size differs')
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            parts=Path(entry.filename).parts
            if not parts or parts[0]!=manifest['directory']:raise RuntimeError('unexpected Ghidra root')
            if len(parts)==1:continue
            mode=entry.external_attr>>16
            if stat.S_ISLNK(mode):raise RuntimeError('Ghidra archive link refused')
            path=child(target,str(Path(*parts[1:])))
            if entry.is_dir():
                if extract:path.mkdir(parents=True,exist_ok=True)
                continue
            if extract:
                path.parent.mkdir(parents=True,exist_ok=True)
                with zipped.open(entry) as source,path.open('xb') as output:shutil.copyfileobj(source,output)
                path.chmod((mode&0o777) or 0o644)
            else:
                if not path.is_file() or path.is_symlink():raise RuntimeError('installed Ghidra file missing/type drift')
                h=hashlib.sha256()
                with zipped.open(entry) as source:
                    for block in iter(lambda:source.read(1024*1024),b''):h.update(block)
                if digest(path)!=h.hexdigest():raise RuntimeError('installed Ghidra bytes drifted: '+str(path.relative_to(target)))


def verify_rea_archive(archive,target,manifest):
    require_rea_integrity(archive,manifest)
    with tarfile.open(archive,'r:gz') as tar:
        for entry in tar:
            if entry.isdir():continue
            if not entry.isfile() or not entry.name.startswith('package/'):
                raise RuntimeError('REA archive type/root refused')
            path=child(target,entry.name.removeprefix('package/'))
            h=hashlib.sha256();source=tar.extractfile(entry)
            with source:
                for block in iter(lambda:source.read(1024*1024),b''):h.update(block)
            if not path.is_file() or path.is_symlink() or digest(path)!=h.hexdigest():
                raise RuntimeError('installed REA bytes drifted: '+str(path.relative_to(target)))


def require_rea_integrity(archive,manifest):
    expected=manifest['integrity'].removeprefix('sha512-')
    actual=base64.b64encode(bytes.fromhex(digest(archive,'sha512'))).decode()
    if actual!=expected:raise RuntimeError('official REA archive integrity differs')


def normalized_lock(data):
    data=json.loads(json.dumps(data));data['name']='moos-analysis-rea';data['version']='1.0.0'
    root=data['packages'][''];dependencies=root.get('dependencies',{})
    if set(dependencies)!= {'rea-agents'}:raise RuntimeError('unexpected REA root dependencies')
    dependency=dependencies['rea-agents']
    if dependency!='6.7.0' and not (dependency.startswith('file:') and dependency.endswith('/rea-agents-6.7.0.tgz')):
        raise RuntimeError('unexpected REA root dependency source')
    source=data['packages']['node_modules/rea-agents']['resolved']
    if source!='https://registry.npmjs.org/rea-agents/-/rea-agents-6.7.0.tgz' and not (source.startswith('file:') and source.endswith('/rea-agents-6.7.0.tgz')):
        raise RuntimeError('unexpected REA archive source')
    root.update({'name':data['name'],'version':data['version'],'dependencies':{'rea-agents':'6.7.0'}})
    data['packages']['node_modules/rea-agents']['resolved']='https://registry.npmjs.org/rea-agents/-/rea-agents-6.7.0.tgz'
    return data


def reviewed_lock(manifest):
    data=(INPUTS/'package-lock.json').read_bytes()
    if hashlib.sha256(data).hexdigest()!=manifest['package_lock_sha256']:
        raise RuntimeError('reviewed lock digest differs')
    return json.loads(data)


def rea_generation(manifest):
    version=manifest['rea']['version']; lock=manifest['package_lock_sha256']
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}',version) or not re.fullmatch(r'[0-9a-f]{64}',lock):
        raise RuntimeError('invalid REA generation identity')
    return 'rea-'+version+'-sha256-'+lock


def generation_record(manifest):
    return (json.dumps({'schema':1,'generation':rea_generation(manifest),
                       'package_lock_sha256':manifest['package_lock_sha256'],
                       'rea':manifest['rea']},sort_keys=True)+'\n').encode()


def check_generation_receipt(target,manifest):
    info=target.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:
        raise RuntimeError('REA generation type/owner/mode refused')
    marker=target/'.moos-rea-generation.json'
    if not marker.exists():raise RuntimeError('unknown REA generation; preserve existing directory')
    info=owned_file(marker,'REA generation receipt')
    if stat.S_IMODE(info.st_mode)!=0o600:raise RuntimeError('REA generation receipt mode differs')
    if marker.read_bytes()!=generation_record(manifest):raise RuntimeError('REA generation receipt differs')


def owned_file(path,description):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1:
        raise RuntimeError(description+' type/owner/link refused')
    return info


@contextmanager
def profile_lease(base,install=False,timeout=10):
    """Serialize publication and readback; a read-only check creates nothing."""
    if install:base.mkdir(parents=True,exist_ok=True)
    directory=os.open(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    fd=None
    try:
        info=os.fstat(directory)
        if info.st_uid!=os.getuid() or info.st_mode&0o022:
            raise RuntimeError('profile directory owner/mode refused')
        flags=(os.O_RDWR|os.O_CREAT) if install else os.O_RDONLY
        fd=os.open(LEASE,flags|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,0o600,dir_fd=directory)
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size!=0):
            raise RuntimeError('profile lease type/owner/mode refused')
        deadline=time.monotonic()+timeout
        while True:
            try:
                fcntl.flock(fd,(fcntl.LOCK_EX if install else fcntl.LOCK_SH)|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise RuntimeError('profile busy; nothing was published or checked')
                time.sleep(min(0.05,max(0,deadline-time.monotonic())))
        current=os.stat(LEASE,dir_fd=directory,follow_symlinks=False)
        if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino):
            raise RuntimeError('profile lease changed while waiting')
        yield
    finally:
        if fd is not None:os.close(fd)
        os.close(directory)


def check_rea(target,manifest):
    package=target/'node_modules/rea-agents/package.json'
    if not package.is_file() or json.loads(package.read_text())['version']!=manifest['rea']['version']:
        raise RuntimeError('REA version missing/drifted')
    expected=reviewed_lock(manifest)
    if normalized_lock(json.loads((target/'package-lock.json').read_text()))!=expected:
        raise RuntimeError('REA transitive lock differs')
    for name,record in expected['packages'].items():
        if not name:continue
        path=target/name/'package.json'
        if not path.exists() and record.get('optional'):continue
        if not path.is_file() or json.loads(path.read_text())['version']!=record['version']:
            raise RuntimeError('REA dependency version differs: '+name)


def ensure_rea(target,archive,manifest,node):
    if target.name!=rea_generation(manifest):raise RuntimeError('REA generation path differs')
    reviewed_lock(manifest)
    require_rea_integrity(archive,manifest['rea'])
    if target.is_symlink():raise RuntimeError('tool installation link refused')
    marker=target/'.moos-rea-generation.json'
    if target.exists():check_generation_receipt(target,manifest)
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='.moos-rea-',dir=target.parent) as temporary:
            staged=Path(temporary)/'rea';staged.mkdir()
            for name in ('package.json','package-lock.json'):shutil.copyfile(INPUTS/name,staged/name)
            env=dict(os.environ,PATH=str(node.parent)+':/usr/local/bin:/usr/bin')
            subprocess.run([str(node.parent/'npm'),'ci','--ignore-scripts','--no-audit','--no-fund','--registry=https://registry.npmjs.org'],cwd=staged,env=env,check=True)
            check_rea(staged,manifest);verify_rea_archive(archive,staged/'node_modules/rea-agents',manifest['rea'])
            receipt=staged/marker.name;receipt.write_bytes(generation_record(manifest));receipt.chmod(0o600)
            os.rename(staged,target)
    check_rea(target,manifest);verify_rea_archive(archive,target/'node_modules/rea-agents',manifest['rea'])


def ensure_ghidra(target,archive,manifest):
    if target.is_symlink():raise RuntimeError('tool installation link refused')
    if target.exists():verify_ghidra(archive,target,manifest)
    else:
        with tempfile.TemporaryDirectory(prefix='.moos-ghidra-',dir=target.parent) as temporary:
            staged=Path(temporary)/manifest['directory'];staged.mkdir()
            verify_ghidra(archive,staged,manifest,extract=True);os.rename(staged,target)


def check_replacement(path,data,replace=False):
    if path.is_symlink():raise RuntimeError('managed launcher link refused')
    if path.exists():
        if not path.is_file():raise RuntimeError('managed launcher is not a file')
        owned_file(path,'managed launcher')
        if path.read_bytes()==data:return
        if not replace:raise RuntimeError('existing launcher differs; use --replace-launchers to preserve a backup and replace')
        backup=path.with_name(path.name+'.before-analysis-'+digest(path)[:16])
        if os.path.lexists(backup):
            if (backup.is_symlink() or not backup.is_file()
                    or backup.read_bytes()!=path.read_bytes()):
                raise RuntimeError('launcher backup collision')
            owned_file(backup,'launcher backup')
            if stat.S_IMODE(backup.stat().st_mode)!=0o600:raise RuntimeError('launcher backup mode differs')


def replace_file(path,data,mode,replace=False):
    check_replacement(path,data,replace)
    if path.exists():
        if path.read_bytes()==data:
            if stat.S_IMODE(path.stat().st_mode)==mode:return False
            path.chmod(mode);return True
        backup=path.with_name(path.name+'.before-analysis-'+digest(path)[:16])
        if not os.path.lexists(backup):
            with backup.open('xb') as out:out.write(path.read_bytes())
            backup.chmod(0o600)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.moos-analysis-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(temporary,mode);os.replace(temporary,path)
    finally:
        if os.path.lexists(temporary):os.unlink(temporary)
    return True


def launchers(home,manifest):
    result={home/'.local/bin'/name:((INPUTS/name).read_bytes(),0o755) for name in ('moos-rea','moos-ghidra')}
    path=home/'.local/bin/moos-rea';template=result[path][0]
    if template.count(b'@REA_GENERATION@')!=1:raise RuntimeError('REA launcher generation placeholder differs')
    result[path]=(template.replace(b'@REA_GENERATION@',rea_generation(manifest).encode()),0o755)
    def quote(value):return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
    icon=home/'.local/share/moos-dev-platform'/manifest['ghidra']['directory']/'docs/GhidraClass/AdvancedDevelopment/Images/GhidraLogo64.png'
    desktop='''[Desktop Entry]
Type=Application
Name=Ghidra
GenericName=Software Analysis
GenericName[ar]=تحليل البرامج
Comment=Local native software analysis with the MoOS development SDK
Comment[ar]=تحليل محلي للبرامج باستخدام بيئة تطوير MoOS
Exec=/usr/bin/moai-open --app %s
Icon=%s
Terminal=false
Categories=Development;Debugger;
StartupNotify=true
StartupWMClass=ghidra-Ghidra
'''%(quote(home/'.local/bin/moos-ghidra'),str(icon))
    result[home/'.local/share/applications/org.moos.ghidra.desktop']=(desktop.encode(),0o644)
    return result


def profile_record(manifest):
    return {'schema':2,'manifest_sha256':digest(INPUTS/'manifest.json'),
            'rea_generation':rea_generation(manifest),'package_lock_sha256':manifest['package_lock_sha256'],
            'rea':manifest['rea'],'ghidra':manifest['ghidra'],
            'archive_payloads_verified':True,'rea_lock_verified':True,'sdk':manifest['sdk_container'],
            'scope':'archive/package and launcher qualification; physical GUI, MCP clients and provider logins are separate'}


def check_profile(home,manifest):
    base=home/'.local/share/moos-dev-platform';rea=base/rea_generation(manifest)
    check_generation_receipt(rea,manifest)
    check_rea(rea,manifest)
    properties=(base/manifest['ghidra']['directory']/'Ghidra/application.properties').read_text()
    if 'application.version='+manifest['ghidra']['version'] not in properties.splitlines():raise RuntimeError('Ghidra version differs')
    for path,(data,mode) in launchers(home,manifest).items():
        owned_file(path,'managed launcher')
        if path.read_bytes()!=data or stat.S_IMODE(path.stat().st_mode)!=mode:raise RuntimeError('launcher bytes/mode differ: '+path.name)
    receipt=base/'analysis-tools-profile.json';owned_file(receipt,'profile receipt')
    if json.loads(receipt.read_text())!=profile_record(manifest):raise RuntimeError('profile receipt missing/drifted')


def run_profile(home,manifest,args):
    base=home/'.local/share/moos-dev-platform';rea=base/rea_generation(manifest)
    ghidra=base/manifest['ghidra']['directory']
    node=base/('node-v'+manifest['node']+'-linux-x64')/'bin/node'
    with profile_lease(base,args.install):
        reviewed_lock(manifest)
        if subprocess.check_output([str(node),'--version'],text=True).strip()!='v'+manifest['node']:raise RuntimeError('shared Node version differs')
        subprocess.run(['/usr/bin/podman','container','exists',manifest['sdk_container']],check=True)
        if args.install:
            expected=launchers(home,manifest);receipt=base/'analysis-tools-profile.json'
            record=(json.dumps(profile_record(manifest),indent=2)+'\n').encode()
            # Refuse every known collision, including recovery, before installing.
            for path,(data,mode) in expected.items():check_replacement(path,data,args.replace_launchers)
            check_replacement(receipt,record,True)
            if os.path.lexists(rea):check_generation_receipt(rea,manifest)
            require_rea_integrity(args.rea_tarball,manifest['rea'])
            if args.ghidra_archive.stat().st_size!=manifest['ghidra']['bytes'] or digest(args.ghidra_archive)!=manifest['ghidra']['sha256']:
                raise RuntimeError('official Ghidra archive digest/size differs')
            ensure_ghidra(ghidra,args.ghidra_archive,manifest['ghidra'])
            ensure_rea(rea,args.rea_tarball,manifest,node)
            subprocess.run(['/usr/bin/toolbox','run','--container',manifest['sdk_container'],manifest['java_home']+'/bin/java','-version'],check=True)
            reviewed_lock(manifest)
            for path,(data,mode) in expected.items():replace_file(path,data,mode,args.replace_launchers)
            replace_file(receipt,record,0o600,replace=True)
        check_profile(home,manifest)


def main():
    if Path('/.flatpak-info').exists():
        os.execv('/usr/bin/flatpak-spawn',['flatpak-spawn','--host','/usr/bin/python3',str(Path(__file__).resolve()),*__import__('sys').argv[1:]])
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group();action.add_argument('--check',action='store_true');action.add_argument('--install',action='store_true')
    parser.add_argument('--ghidra-archive',type=Path);parser.add_argument('--rea-tarball',type=Path)
    parser.add_argument('--replace-launchers',action='store_true')
    args=parser.parse_args()
    if os.getuid()==0 or platform.machine()!='x86_64':raise RuntimeError('profile requires the x86_64 owner account, not root')
    manifest=json.loads((INPUTS/'manifest.json').read_text())
    if args.install:
        if not args.ghidra_archive or not args.rea_tarball:parser.error('--install needs both official archives; URLs and digests are in the profile manifest')
    run_profile(Path.home(),manifest,args)
    print(json.dumps({'rea':manifest['rea']['version'],'rea_generation':rea_generation(manifest),'ghidra':manifest['ghidra']['version'],'node':manifest['node'],'sdk':manifest['sdk_container'],'profile_receipt':True,'launchers_exact':True,'mcp_registration_changed':False,'scope':'read-only installed profile check; not a new functional or GUI acceptance test'},indent=2))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,RuntimeError,subprocess.SubprocessError) as error:
        raise SystemExit('MoOS analysis profile: '+str(error))
