#!/usr/bin/env python3
"""Opt-in actual four-runtime scan-metadata regression; private state only.

Retains the same cache across be3 cold/warm, rule-without-rekey refusal and
source successor cold/warm. No app GUI, owner config, permission or cache purge.
"""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('font_policy', ROOT / 'system_files/usr/lib/moos/moos_flatpak_fonts.py')
policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
FAMILIES = ('Meyar Mono', 'Meyar Mono Arabic')
REQUESTS = [f + style for f in FAMILIES for style in ('', ':weight=bold')]
REQUESTS += ['DejaVu Sans', 'monospace']
APPS = ('ai.opencode.opencode', 'org.gnome.Snapshot', 'org.kde.krecorder', 'com.google.Chrome')
record = {'schema': 1, 'dateUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'sourceSHA': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'moduleSHA256': hashlib.sha256(Path(policy.__file__).read_bytes()).hexdigest(),
          'scope': 'Native Fontconfig in four installed runtimes, isolated appcache fixtures; no actual application painting or settings change.',
          'rows': []}
destination = ROOT / 'test-results/flatpak-font-delivery-20261101/native-scan-successor.json'
destination.parent.mkdir(parents=True, exist_ok=True)


def snapshot(path):
    if not path.exists(): return None
    return [(str(p.relative_to(path)), p.lstat().st_mode, p.lstat().st_uid,
             p.lstat().st_mtime_ns, os.readlink(p) if p.is_symlink() else
             hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else '')
            for p in [path] + sorted(path.rglob('*'))]


try:
    booted = policy.signed_generation(json.loads(policy.output(['/usr/bin/rpm-ostree', 'status', '--json'])))
    for app in APPS:
        apphome = Path.home() / '.var/app' / app
        parent = apphome / 'cache'
        if parent.resolve() != parent or not parent.is_dir():
            raise ValueError('Existing canonical app cache required: ' + app)
        scratch = Path(tempfile.mkdtemp(prefix='moos-native-font-scan-v2-', dir=parent))
        home = scratch / 'private-home'; home.mkdir(mode=0o700)
        before = snapshot(apphome / 'config/fontconfig')
        row = {'app': app, 'scratch': str(scratch), 'calls': []}
        record['rows'].append(row)
        def native(config, cache, *command):
            config.mkdir(parents=True, exist_ok=True); cache.mkdir(parents=True, exist_ok=True)
            argv = ['flatpak', 'run', '--command=env', app, '-u', 'FONTCONFIG_FILE', '-u', 'FONTCONFIG_PATH',
                    'XDG_CONFIG_HOME=' + str(config), 'XDG_CACHE_HOME=' + str(cache), *command]
            p = subprocess.run(argv, capture_output=True, text=True, timeout=45)
            row['calls'].append({'argv': argv, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
            if p.returncode: raise RuntimeError(p.stderr)
            return p.stdout.strip()
        def measure(config, cache):
            matches = {r: native(config, cache, 'fc-match', '-f', '%{family}|%{style}|%{spacing}|%{file}', r)
                       for r in REQUESTS}
            fonts = native(config, cache, 'fc-list', '-f', '%{family}|%{style}|%{spacing}|%{file}\n')
            instances = sorted(s for s in fonts.splitlines() if '/run/host/fonts/meyar/MeyarMono' in s)
            return {'matches': matches, 'instances': instances}
        oldconfig, oldcache = scratch / 'original-config', scratch / 'original-cache'
        native(oldconfig, oldcache, 'fc-cache', '-V')
        version_call = row['calls'][-1]
        row['fontconfig_version'] = (version_call['stdout'] + version_call['stderr']).strip()
        row['runtime'] = policy.output(['flatpak', 'info', '--show-runtime', app])
        row['runtime_commit'] = policy.output(['flatpak', 'info', '--show-commit', 'runtime/' + row['runtime']])
        row['original'] = measure(oldconfig, oldcache)
        legacy = policy._render_fragment(booted, [(row['runtime'], row['runtime_commit'])], 1)
        policy.install(home, app, legacy)
        config = home / '.var/app' / app / 'config'
        cache = scratch / 'retained-cache'
        path = config / 'fontconfig/conf.d' / policy.FILE
        row['be3_cold'] = measure(config, cache)
        row['be3_warm'] = measure(config, cache)
        assert row['be3_cold'] == row['be3_warm']
        assert len(row['be3_cold']['instances']) >= 2
        assert all(s.split('|')[2] == '90' for s in row['be3_cold']['instances'])
        # Keep be3's cache and salt while adding only its missing native rules.
        # This intentionally edited fixture is NOT admitted by the policy owner.
        mutant = legacy.replace(b'</fontconfig>', policy.SCAN_RULES + b'</fontconfig>')
        assert not policy.owned(mutant)
        path.write_bytes(mutant)
        row['rules_without_rekey'] = measure(config, cache)
        assert row['rules_without_rekey'] == row['be3_warm']
        path.write_bytes(legacy)  # restore exact fixture-owned bytes for managed upgrade
        row['changed'] = policy.refresh([app], home=home)
        assert row['changed'] == [app]
        row['successor_cold'] = measure(config, cache)
        row['successor_warm'] = measure(config, cache)
        assert row['successor_cold'] == row['successor_warm']
        fixed = row['successor_cold']
        assert len(fixed['instances']) == len(row['be3_cold']['instances'])
        assert all(s.split('|')[2] == '100' for s in fixed['instances'])
        for request in REQUESTS[:4]:
            assert fixed['matches'][request].split('|')[0] == request.split(':')[0]
            assert fixed['matches'][request].split('|')[2] == '100'
        for request in REQUESTS[4:]:
            assert fixed['matches'][request] == row['original']['matches'][request]
        if app in ('org.kde.krecorder', 'com.google.Chrome'):
            # Preserve contrary healthy-runtime evidence: discovery itself
            # already worked and be3 regressed only the native grid metadata.
            for family in FAMILIES:
                assert row['original']['matches'][family].split('|')[0] == family
                assert row['original']['matches'][family].split('|')[2] == '100'
        recoveries = list((config / 'fontconfig/conf.d/.moos-host-font-cache-recovery').iterdir())
        assert len(recoveries) == 1 and recoveries[0].read_bytes() == legacy
        row['recovery_exact'] = True
        row['actual_config_unchanged'] = snapshot(apphome / 'config/fontconfig') == before
        assert row['actual_config_unchanged']
    record['pass'] = True
finally:
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'proof': str(destination), 'pass': record.get('pass', False)}, ensure_ascii=False))
