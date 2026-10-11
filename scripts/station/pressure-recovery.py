#!/usr/bin/env python3
"""Native oomd proof confined to a new private user slice, capped at 256 MiB.

Never pressures the whole machine or changes an existing unit. The negative
control keeps the same bounded allocator alive with monitoring disabled; the
positive control enables monitoring for only that private slice. Read back the
daemon's monitored path, preserve a separate sentinel, and reject kernel OOM.
This proves the mechanism, not weak-hardware frame latency or global recovery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def command(args, *, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=12)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result


def ctl(*args, check=True):
    return command(['systemctl', '--user', *args], check=check)


def properties(unit):
    result = ctl('show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result',
                 '-p', 'ExecMainCode', '-p', 'ExecMainStatus', '-p', 'ControlGroup')
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def events(path):
    return {key: int(value) for key, value in (line.split() for line in
            (path / 'memory.events').read_text().splitlines())}


ALLOCATOR = '''import time, tempfile, os
from pathlib import Path
# oomd requires reclaim activity as well as PSI. Anonymous pages with swap
# disabled can stall without anything reclaimable (measured on ARM). Give
# this private actor its own small, unlinked disk-backed cache to reclaim.
cache = tempfile.TemporaryFile(prefix="moos-pressure-control-", dir=Path.home()/".cache")
chunk = bytes(range(256)) * (64 * 1024)
cache.write(chunk)
cache.flush()
os.fdatasync(cache.fileno())
del chunk
until = time.monotonic() + 90
while time.monotonic() < until:
    # A single allocation creates only a short pressure burst on fast hosts:
    # subsequent writes to its resident pages need no reclaim. Keep charging
    # and releasing the SAME bounded allocation throughout the proof.
    data = []
    # Interleave cache faults with small charges. A single 128 MiB calloc
    # stalled at 80–100 MiB on ARM before it could renew the reclaim activity.
    for _ in range(16):
        data.append(bytearray(8 * 1024 * 1024))
        cache.seek(0)
        cached = cache.read(16 * 1024 * 1024)
        del cached
    del data
    time.sleep(0.02)
'''


def run(output: Path):
    if output.exists() or output.is_symlink():
        raise RuntimeError('refuse to overwrite earlier pressure evidence')
    if os.geteuid() == 0 or Path('/.flatpak-info').exists():
        raise RuntimeError('run as the real native desktop user, never root or the editor sandbox')
    available = next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    if available < 1024 * 1024:
        raise RuntimeError('less than 1 GiB available; refuse even this bounded fixture')
    if command(['systemctl', 'is-active', '--quiet', 'systemd-oomd'], check=False).returncode:
        raise RuntimeError('oomd is not active')
    suffix = uuid.uuid4().hex[:12]
    base = 'moos-owner-pressure-' + suffix
    parent, sentinel = base + '.slice', base + '-sentinel.service'
    actors = []
    record = dict(start_utc=datetime.now(timezone.utc).isoformat(), uid=os.geteuid(),
                  maximum_bytes=256 * 1024**2, slice=parent, scope='private native cgroup only')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        command(['systemd-run', '--user', '--unit=' + sentinel, '--slice=' + parent,
                 '--property=RuntimeMaxSec=180', '--property=ManagedOOMPreference=omit',
                 '/usr/bin/sleep', '170'])
        ctl('set-property', '--runtime', parent, 'MemoryHigh=64M', 'MemoryMax=256M',
            'MemorySwapMax=0', 'CPUWeight=1', 'ManagedOOMMemoryPressure=auto')
        group = properties(parent)['ControlGroup']
        if not group.startswith(f'/user.slice/user-{os.geteuid()}.slice/user@{os.geteuid()}.service/'):
            raise RuntimeError('fixture is outside the native user namespace')
        group_path = Path('/sys/fs/cgroup' + group)
        record['cgroup'] = group
        for label, monitor, seconds in (('negative', 'auto', 30), ('positive', 'kill', 65)):
            ctl('set-property', '--runtime', parent, 'ManagedOOMMemoryPressure=' + monitor,
                'ManagedOOMMemoryPressureLimit=1%')
            actor = base + '-' + label + '.service'
            actors.append(actor)
            snapshot = events(group_path)
            pressure_before = (group_path / 'memory.pressure').read_text()
            monitored = command(['oomctl', '--no-pager']).stdout
            if monitor == 'kill' and f'Path: {group}' not in monitored:
                # Allow the daemon one short asynchronous registration interval.
                time.sleep(1)
                monitored = command(['oomctl', '--no-pager']).stdout
            if monitor == 'kill' and f'Path: {group}' not in monitored:
                raise RuntimeError('private group never reached oomd monitoring')
            command(['systemd-run', '--user', '--unit=' + actor, '--slice=' + parent,
                     '--property=RuntimeMaxSec=95', '--property=Nice=19',
                     '/usr/bin/python3', '-u', '-c', ALLOCATOR])
            started = time.monotonic()
            while time.monotonic() - started < seconds:
                state = properties(actor)
                if state['ActiveState'] not in ('active', 'activating'):
                    break
                time.sleep(1)
            current = events(group_path)
            state = properties(actor)
            record[label] = dict(elapsed_seconds=round(time.monotonic()-started, 2),
                                 actor=state, sentinel=properties(sentinel),
                                 memory_events_before=snapshot, memory_events_after=current,
                                 pressure_before=pressure_before,
                                 pressure_after=(group_path / 'memory.pressure').read_text(),
                                 reclaim_stat=(group_path / 'memory.stat').read_text(),
                                 private_group_monitored=f'Path: {group}' in monitored)
            if current['oom_kill'] != snapshot['oom_kill'] or current['max'] != snapshot['max']:
                raise RuntimeError('kernel OOM or hard-limit hit; this is not an oomd recovery proof')
            if current['high'] <= snapshot['high']:
                raise RuntimeError('fixture generated no reclaim pressure')
            if properties(sentinel)['ActiveState'] != 'active':
                raise RuntimeError('protected sentinel did not survive')
            if label == 'negative' and state['ActiveState'] != 'active':
                raise RuntimeError('unmonitored control died')
            if label == 'positive' and (state['Result'] != 'oom-kill'
                                       or state['ExecMainCode'] != '2' or state['ExecMainStatus'] != '9'):
                raise RuntimeError('monitored allocator was not killed by the user-space guard')
            ctl('stop', actor, check=False)
            ctl('reset-failed', actor, check=False)
        record['passed'] = True
    except Exception as exc:
        record.update(passed=False, error=str(exc))
    finally:
        ctl('stop', *actors, sentinel, parent, check=False)
        ctl('reset-failed', *actors, sentinel, parent, check=False)
        ctl('revert', parent, check=False)
        record['cleanup'] = {name: properties(name)['ActiveState'] for name in (*actors, sentinel, parent)}
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(json.dumps(record, indent=2) + '\n')
    if not record.get('passed') or any(value != 'inactive' for value in record['cleanup'].values()):
        raise RuntimeError(record.get('error', 'fixture cleanup failed'))
    print('PASS: bounded native negative/positive pressure controls; sentinel survives; kernel OOM=0')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', required=True, type=Path)
    run(parser.parse_args().output)
