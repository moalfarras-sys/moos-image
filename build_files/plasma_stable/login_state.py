"""Conform one empty RPM-created greeter directory to its native tmpfiles rule.

The6.8.1 RPM declares01770 while its runtime creator declares0750. A systemd
upgrade normally applies the latter globally; an already-upgraded canary does
not run that trigger again. Keep the generic transaction metadata gate strict.
"""
from pathlib import Path
import stat
import subprocess

from finalize_image_state import owned_path

RELATIVE='var/lib/plasmalogin'
AUTHORITY='usr/lib/tmpfiles.d/plasmalogin.conf'
REVIEWED_NVR='6.8.1-1.fc44'
RECORD={'mode':0o750,'user':'plasmalogin','group':'plasmalogin','kind':'directory',
        'authorities':[{'authority':AUTHORITY,'rule':['d','/'+RELATIVE,'0750','plasmalogin','plasmalogin']}]}


def reconcile(transaction):
    root=transaction.root
    if transaction.finished:raise RuntimeError('greeter state transaction already finished')
    if root==Path('/') and (not Path('/run/.containerenv').exists() or Path('/run/ostree-booted').exists()):
        raise RuntimeError('greeter directory normalization requires an unbooted image')
    if transaction.records.get(RELATIVE)!=RECORD:
        raise RuntimeError('greeter runtime record drifted')
    package=subprocess.check_output(['rpm','-q','--qf','%{VERSION}-%{RELEASE}','plasma-login-manager'],text=True).strip()
    if package!=REVIEWED_NVR:raise RuntimeError('unreviewed greeter directory package')
    path=owned_path(root,RELATIVE)
    if not path.exists():return False
    mode=stat.S_IMODE(path.lstat().st_mode)
    if mode not in (0o750,0o1770):raise RuntimeError('unreviewed greeter directory mode')
    uid,gid=transaction.ids(RECORD)
    transaction.require(path,'directory',mode,uid,gid)
    if any(path.iterdir()):raise RuntimeError('populated greeter directory must be retained')
    transaction.authority(RECORD)
    authority=owned_path(root,AUTHORITY)
    rules=[line.split() for line in authority.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    scoped=[rule for rule in rules if len(rule)>1 and (rule[1]=='/'+RELATIVE or rule[1].startswith('/'+RELATIVE+'/'))]
    if scoped!=[RECORD['authorities'][0]['rule'],['Z','/'+RELATIVE,'-','plasmalogin','plasmalogin']]:
        raise RuntimeError('greeter directory creator scope drifted')
    if mode==0o750:return False
    rows=[line.split() for line in subprocess.check_output(['rpm','-q','--dump','plasma-login-manager'],text=True).splitlines() if line.split() and line.split()[0]=='/'+RELATIVE]
    if (len(rows)!=1 or len(rows[0])<7 or rows[0][1]!='0' or rows[0][4]!='041770'
            or rows[0][5:7]!=['plasmalogin','plasmalogin']):
        raise RuntimeError('greeter directory has no exact native RPM metadata')
    before=authority.read_bytes()
    path.chmod(0o750)
    transaction.require(path,'directory',0o750,uid,gid)
    if any(path.iterdir()) or authority.read_bytes()!=before:
        raise RuntimeError('greeter directory inputs changed during normalization')
    print('Native greeter directory: empty RPM01770 conforms to retained runtime0750 creator')
    return True
