#!/usr/bin/env python3
"""Finite read-only Linux memory sampling for an owner-requested investigation.

Run as the desktop user. Output contains process names/PIDs and memory counters,
never process arguments, environment, credentials or file contents. This is an
observation tool, not a pass/fail stability gate. Keep output local by default.
"""
import argparse
import datetime
import json
import time
from pathlib import Path


def snapshot():
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        name, value = line.split(':', 1)
        if name in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
            mem[name + '_KiB'] = int(value.split()[0])
    processes = []
    for directory in Path('/proc').iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            fields = {}
            for line in (directory / 'status').read_text().splitlines():
                name, value = line.split(':', 1)
                if name in {'Name', 'VmRSS', 'VmSwap', 'VmHWM'}:
                    fields[name] = value.strip()
            rss = int(fields.get('VmRSS', '0 kB').split()[0])
            processes.append({'pid': int(directory.name), 'name': fields.get('Name', ''),
                              'rss_KiB': rss,
                              'swap_KiB': int(fields.get('VmSwap', '0 kB').split()[0]),
                              'peak_rss_KiB': int(fields.get('VmHWM', '0 kB').split()[0])})
        except (OSError, ValueError):
            continue  # A process can exit between directory listing and read.
    vmstat = dict(line.split() for line in Path('/proc/vmstat').read_text().splitlines())
    return {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'memory': mem, 'oom_kills_since_boot': int(vmstat.get('oom_kill', 0)),
            'largest_processes': sorted(processes, key=lambda p: p['rss_KiB'], reverse=True)[:30]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=1)
    parser.add_argument('--interval', type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.samples <= 120 or not 5 <= args.interval <= 300:
        parser.error('samples must be 1..120; interval must be 5..300 seconds')
    for i in range(args.samples):
        print(json.dumps(snapshot(), ensure_ascii=True), flush=True)
        if i + 1 < args.samples:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
