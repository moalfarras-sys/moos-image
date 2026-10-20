#!/usr/bin/python3
"""Publish bounded enrollment availability; never authenticate or read templates."""
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import tempfile
import time

TARGET = Path('/run/moos-login/fingerprint-users.json')


def query(arguments, deadline, run=subprocess.run, clock=time.monotonic):
    remaining = deadline - clock()
    if remaining <= 0:
        raise TimeoutError('enrollment availability budget exhausted')
    result = run(['/usr/bin/busctl', '--system', '--json=short', 'call',
                  'net.reactivated.Fprint', *arguments], check=True,
                 capture_output=True, text=True, timeout=min(2, remaining))
    data = json.loads(result.stdout)
    expected = 'ao' if arguments[2] == 'GetDevices' else 'as'
    if len(result.stdout) > 16384 or not isinstance(data, dict) or data.get('type') != expected:
        raise ValueError('invalid availability response')
    values = data.get('data')
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], list):
        raise ValueError('invalid availability array')
    if len(values[0]) > 32 or any(not isinstance(value, str) for value in values[0]):
        raise ValueError('invalid availability entries')
    return values[0]


def enrolled_users(users, *, run=subprocess.run, clock=time.monotonic):
    deadline = clock() + 4
    devices = query(['/net/reactivated/Fprint/Manager', 'net.reactivated.Fprint.Manager',
                     'GetDevices'], deadline, run, clock)
    found = []
    for username in users[:32]:
        for device in devices[:4]:
            if not device.startswith('/net/reactivated/Fprint/Device/'):
                raise ValueError('invalid reader path')
            try:
                fingers = query([device, 'net.reactivated.Fprint.Device',
                                 'ListEnrolledFingers', 's', username], deadline, run, clock)
            except subprocess.CalledProcessError:
                # No enrollment/permission for one account must not hide another
                # account's positively confirmed enrollment.
                continue
            if fingers:
                found.append(username)
                break
    return found


def publish(target, record):
    directory = target.parent
    directory.mkdir(mode=0o755, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('availability directory is not root controlled')
    fd, temporary = tempfile.mkstemp(prefix='.fingerprint-', dir=directory)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Availability collection must run as the display-manager administrator')
    record = {'schema': 1, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'users': []}
    try:
        subprocess.run(['/usr/libexec/moos-configure-fingerprint-login', '--check'],
                       capture_output=True, text=True, check=True, timeout=2)
        users = [user.pw_name for user in pwd.getpwall()
                 if 1000 <= user.pw_uid <= 60513 and not user.pw_shell.endswith(('/nologin', '/false'))]
        record['users'] = enrolled_users(users)
    except Exception as error:
        # Missing reader, enrollment or reviewed policy keeps the stock password UI.
        # This optional metadata is never a condition for boot or authentication.
        record['unavailable'] = type(error).__name__
        print('MoOS: automatic fingerprint unavailable:', type(error).__name__, flush=True)
    publish(TARGET, record)
    print('MoOS: fingerprint availability refreshed for', len(record['users']), 'local accounts', flush=True)


if __name__ == '__main__':
    main()
