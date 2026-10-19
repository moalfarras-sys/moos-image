#!/usr/bin/env python3
"""Finite native proof of the shipped hardware adapter's periodic service lifecycle.

Uses owned transient USER timers and a private marker writer only. It never runs
moos-hardware-adapt, installs a unit, changes hardware, or touches owner units.
The source interval is accelerated to 500ms; this proves recurrence semantics,
not a day-long hardware qualification. Run after the source says RemainAfterExit=no.
"""
import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*argv, check=True):
    return subprocess.run(argv, capture_output=True, text=True, check=check, timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    service = root / 'system_files/usr/lib/systemd/system/moos-hardware-adapt.service'
    timer = service.with_suffix('.timer')
    service_config = configparser.ConfigParser(interpolation=None)
    service_config.read(service)
    timer_config = configparser.ConfigParser(interpolation=None)
    timer_config.read(timer)
    source_remain = service_config['Service'].get('RemainAfterExit', '').lower()
    assert source_remain in ('no', 'false', '0'), 'source must release its completed oneshot'
    assert service_config['Service'].get('Type') == 'oneshot'
    assert timer_config['Timer'].get('Unit') == service.name
    assert timer_config['Timer'].get('OnUnitActiveSec'), 'source must declare recurring activation'
    runtime = root / 'tests/verify_arm_runtime.sh'
    predicate = re.search(r'^hwadapt_completed\(\) \{\n.*?^\}', runtime.read_text(), re.MULTILINE | re.DOTALL)
    assert predicate, 'runtime completion predicate must be present'

    def completed(snapshot):
        return command('bash', '-c', predicate.group(0) + '\nhwadapt_completed "$1"',
                       'hardware-completion', snapshot, check=False).returncode == 0

    def snapshot(unit):
        return command('systemctl', '--user', 'show', unit + '.service',
                       '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result',
                       '-p', 'ExecMainStatus', '-p', 'ExecMainExitTimestampMonotonic',
                       '-p', 'ConditionResult').stdout

    revision = command('git', '-C', str(root), 'rev-parse', 'HEAD', check=False)
    receipt = {
        'utc': datetime.now(timezone.utc).isoformat(),
        'source_root': str(root), 'source_revision': revision.stdout.strip() if revision.returncode == 0 else None,
        'source_service_sha256': sha(service), 'source_timer_sha256': sha(timer),
        'probe_sha256': sha(Path(__file__)), 'runtime_gate_sha256': sha(runtime),
        'source_interval': timer_config['Timer']['OnUnitActiveSec'],
        'scope': 'private transient user units; marker writer replaces real ExecStart; 1s initial/500ms recurring',
        'cases': {},
    }
    receipt['result'] = 'FAIL'
    try:
        with tempfile.TemporaryDirectory(prefix='moos-hardware-timer-proof-') as raw:
            for label, remain in (('old_negative', 'yes'), ('source_positive', source_remain)):
                unit = 'moos-hw-private-' + uuid.uuid4().hex
                marker = Path(raw) / label
                record = {'unit': unit, 'RemainAfterExit': remain}
                receipt['cases'][label] = record
                try:
                    command('systemd-run', '--user', '--unit=' + unit,
                            '--on-active=1s', '--on-unit-active=500ms', '--timer-property=AccuracySec=1ms',
                            '--property=Type=' + service_config['Service']['Type'],
                            '--property=RemainAfterExit=' + remain, '--property=TimeoutStartSec=2s',
                            '/usr/bin/python3', '-c',
                            'import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); '
                            'f=p.open("a"); f.write(str(time.monotonic())+"\\n"); f.close()', str(marker))
                    before = snapshot(unit)
                    record['before_snapshot'] = dict(line.split('=', 1) for line in before.splitlines() if '=' in line)
                    record['before_accepted'] = completed(before)
                    assert not record['before_accepted'] and not marker.exists(), record
                    time.sleep(3)
                    after = snapshot(unit)
                    # A periodic timer can be sampled during its next start. Require an
                    # actual completed generation within one bounded interval, not a
                    # snapshot that accidentally lands between two invocations.
                    completion_deadline = time.monotonic() + 1
                    retries = 0
                    while label == 'source_positive' and not completed(after) and time.monotonic() < completion_deadline:
                        time.sleep(0.025)
                        after = snapshot(unit)
                        retries += 1
                    record['completion_retries'] = retries
                    record['snapshot'] = dict(line.split('=', 1) for line in after.splitlines() if '=' in line)
                    record['after_accepted'] = completed(after)
                    assert record['after_accepted'] is (label == 'source_positive'), record
                    record['firings'] = len(marker.read_text().splitlines()) if marker.exists() else 0
                    assert record['firings'] == 1 if label == 'old_negative' else record['firings'] >= 2, record
                    assert record['snapshot']['Result'] == 'success', record
                    assert record['snapshot']['ConditionResult'] == 'yes', record
                    assert record['snapshot']['ExecMainStatus'] == '0', record
                    assert int(record['snapshot']['ExecMainExitTimestampMonotonic']) > 0, record
                finally:
                    stopped = command('systemctl', '--user', 'stop', unit + '.timer', unit + '.service', check=False)
                    reset = command('systemctl', '--user', 'reset-failed', unit + '.timer', unit + '.service', check=False)
                    record['cleanup_stop_exit'] = stopped.returncode
                    record['cleanup_reset_exit'] = reset.returncode
                    # A disappeared transient unit is also cleaned. No owned unit may remain active.
                    active = command('systemctl', '--user', 'is-active', unit + '.timer', unit + '.service', check=False)
                    record['cleanup_states'] = active.stdout.splitlines()
                    assert not any(state in ('active', 'activating', 'deactivating') for state in record['cleanup_states']), record
        receipt['result'] = 'PASS'
    finally:
        receipt['completed_utc'] = datetime.now(timezone.utc).isoformat()
        args.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
