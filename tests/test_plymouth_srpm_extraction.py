"""Run the build script's extraction with a padded archive and failing tools."""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build_files/build_plymouth_fix.sh'


def entry(name, data=b'', mode=0o100644):
    name = name.encode() + b'\0'
    fields = [1, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(name), 0]
    header = b'070701' + ''.join('%08x' % value for value in fields).encode()
    return header + name + b'\0' * (-(len(header) + len(name)) % 4) + data + b'\0' * (-len(data) % 4)


class Extraction(unittest.TestCase):
    def run_extract(self, producer='ok', consumer='ok'):
        with tempfile.TemporaryDirectory(prefix='moos-srpm-extract-') as raw:
            root = Path(raw)
            work = root / 'work'; tools = root / 'bin'
            work.mkdir(); tools.mkdir()
            top = work / 'rpmbuild'; sources = top / 'SOURCES'
            sources.mkdir(parents=True)
            expected = {'plymouth.spec': b'private fixture spec\n', 'vendor.patch': b'x' * 90000}
            payload = b''.join(entry(name, data) for name, data in expected.items()) + entry('TRAILER!!!', mode=0)
            payload += b'\0' * (-len(payload) % 512)
            (root / 'payload').write_bytes(payload)
            real_cpio = shutil.which('cpio')
            self.assertIsNotNone(real_cpio, 'cpio is required for the real extraction gate')
            rpm = tools / 'rpm2cpio'
            rpm.write_text('''#!/usr/bin/env python3
import fcntl,os,signal,stat,sys,time
from pathlib import Path
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
if os.environ['PRODUCER'] == 'fail':
    os.write(1,b'partial'); sys.exit(7)
pipe = stat.S_ISFIFO(os.fstat(1).st_mode)
if pipe: fcntl.fcntl(1,fcntl.F_SETPIPE_SZ,4096)
data = Path(os.environ['PAYLOAD']).read_bytes() if os.environ['PRODUCER'] == 'ok' else b'not a cpio archive'
def emit(value):
    while value: value = value[os.write(1,value):]
emit(data)
if pipe: time.sleep(.05)  # let the consumer finish at the archive trailer
emit(b'\\0' * 8836)
''')
            rpm.chmod(0o700)
            cpio = tools / 'cpio'
            cpio.write_text('''#!/usr/bin/env python3
import os,sys
from pathlib import Path
Path(os.environ['CONSUMER_MARKER']).touch()
if os.environ['CONSUMER'] == 'fail': sys.exit(9)
os.execv(os.environ['REAL_CPIO'], [os.environ['REAL_CPIO']] + sys.argv[1:])
''')
            cpio.chmod(0o700)
            text = Path(os.environ.get('MOOS_PLYMOUTH_EXTRACTION_SOURCE', SOURCE)).read_text()
            start = re.search(r'^.*\| sha256sum --check\n', text, re.M).end()
            end = text.index('\ncp "${_top}/SOURCES/plymouth.spec"', start)
            section = text[start:end].replace('/work/', str(work) + '/')
            script = 'set -euo pipefail\n_top=' + shlex.quote(str(top)) + '\n' + section
            env = dict(os.environ, PATH=str(tools) + ':' + os.environ.get('PATH', '/usr/bin:/bin'),
                       PRODUCER=producer, CONSUMER=consumer, REAL_CPIO=real_cpio,
                       CONSUMER_MARKER=str(root/'consumer-started'), PAYLOAD=str(root/'payload'))
            done = subprocess.run(['bash', '-c', script], env=env, capture_output=True, timeout=10)
            files = {p.name:p.read_bytes() for p in sources.iterdir() if p.is_file()}
            return done.returncode, files, expected, (root/'consumer-started').exists(), (work/'plymouth-source.cpio').exists()

    def test_padding_after_the_trailer_does_not_kill_the_producer(self):
        code, files, expected, called, archive = self.run_extract()
        self.assertEqual(code, 0, 'archive trailer closed a live producer pipe')
        self.assertEqual(files, expected)
        self.assertTrue(called)
        self.assertFalse(archive, 'completed private scratch was not removed')

    def test_failed_producer_never_runs_the_consumer(self):
        code, _, _, called, _ = self.run_extract(producer='fail')
        self.assertEqual(code, 7)
        self.assertFalse(called)

    def test_corrupt_archive_is_rejected(self):
        code, _, _, called, archive = self.run_extract(producer='corrupt')
        self.assertNotEqual(code, 0)
        self.assertTrue(called)
        self.assertTrue(archive, 'failed extraction diagnostics were discarded')

    def test_consumer_failure_is_not_suppressed(self):
        code, _, _, called, _ = self.run_extract(consumer='fail')
        self.assertEqual(code, 9)
        self.assertTrue(called)


if __name__ == '__main__':
    unittest.main(verbosity=2)
