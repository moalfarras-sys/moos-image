"""One exact native runtime tree; no server, test, operator or private data ships."""
from pathlib import Path
import shutil
import sys

RUNTIME = ('__init__.py', 'client.py', 'transport.py', 'outbox.py', 'main.qml')


def stage(source, output):
    source, output = Path(source), Path(output)
    for name in RUNTIME:
        file = source/name
        if not file.is_file() or file.is_symlink():
            raise ValueError('native runtime missing: '+name)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('an empty staging destination is required')
    for name in RUNTIME:
        shutil.copyfile(source/name, output/name)
        (output/name).chmod(0o644)
    output.chmod(0o755)
    print('MoOS participation native runtime staged: '+str(len(RUNTIME))+' files')


if __name__=='__main__':
    stage(*sys.argv[1:])
