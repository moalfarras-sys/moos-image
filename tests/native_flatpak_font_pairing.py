#!/usr/bin/env python3
"""Opt-in named Arabic pairing and personal-order controls in four runtimes.

Actual source-owned be3→successor upgrade with a retained private cache. This
tests native matching, not rendered shaping, keyboard or application lifecycle.
"""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('font_policy', ROOT / 'system_files/usr/lib/moos/moos_flatpak_fonts.py')
policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
APPS = ('ai.opencode.opencode', 'org.gnome.Snapshot', 'org.kde.krecorder', 'com.google.Chrome')
QUERIES = ['Meyar Sans', 'Meyar Mono', 'Meyar Arabic', 'Meyar Mono Arabic',
           'Meyar Sans:charset=0627', 'Meyar Mono:charset=0627',
           'Meyar Sans:charset=0651', 'Meyar Mono:charset=0651',
           'Meyar Sans:charset=067e', 'Meyar Mono:charset=067e',
           'Meyar Sans:charset=06cc', 'Meyar Mono:charset=06cc',
           'Meyar Sans:charset=0627:weight=200', 'Meyar Mono:charset=0627:weight=200',
           'Meyar Sans:lang=ar', 'Meyar Mono:lang=ar',
           'DejaVu Sans', 'DejaVu Sans Mono', 'DejaVu Sans:charset=0627', 'DejaVu Sans Mono:charset=0627',
           'Inter', 'Inter:charset=0041', 'Inter:charset=0627',
           'sans-serif', 'sans-serif:charset=0627', 'monospace', 'monospace:charset=0627',
           'DejaVu Sans,Meyar Sans:charset=0627', 'Meyar Sans,DejaVu Sans:charset=0627',
           'DejaVu Sans Mono,Meyar Mono:charset=0627', 'Meyar Mono,DejaVu Sans Mono:charset=0627',
           'Inter,Meyar Sans:charset=0041', 'Inter,Meyar Sans:charset=0627']
QUERIES += [f'{family}:charset={point}' for family in ('Meyar Sans', 'Meyar Mono')
            for point in ('0041', '4e2d', '0915', '03a9', '0416', '0259', '1ea1', '1f642')]
PERSONAL = b'''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <match target="pattern"><test name="family" compare="eq"><string>Meyar Sans</string></test><edit name="family" mode="assign_replace" binding="strong"><string>DejaVu Sans</string></edit></match>
</fontconfig>
'''
assert len(QUERIES) == len(set(QUERIES)) == 49
record = {'schema': 1, 'dateUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'sourceSHA': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'moduleSHA256': hashlib.sha256(Path(policy.__file__).read_bytes()).hexdigest(),
          'queries': QUERIES, 'rows': [], 'scope': 'Private native Fontconfig matching only; no real app configuration, permission or GUI changed.'}
destination = ROOT / ('test-results/flatpak-font-delivery-20261101/native-named-successor-' + secrets.token_hex(6) + '.json')
destination.parent.mkdir(parents=True, exist_ok=True)


def snapshot(path):
    if not path.exists(): return None
    return [(str(p.relative_to(path)), p.lstat().st_mode, p.lstat().st_uid, p.lstat().st_mtime_ns,
             os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else '')
            for p in [path] + sorted(path.rglob('*'))]


try:
    booted = policy.signed_generation(json.loads(policy.output(['/usr/bin/rpm-ostree', 'status', '--json'])))
    for app in APPS:
        apphome = Path.home() / '.var/app' / app
        parent = apphome / 'cache'
        if parent.resolve() != parent or not parent.is_dir(): raise ValueError('Existing canonical app cache required')
        scratch = Path(tempfile.mkdtemp(prefix='moos-native-font-pairing-v2-', dir=parent))
        home = scratch / 'private-home'; home.mkdir(mode=0o700)
        config = home / '.var/app' / app / 'config'; cache = scratch / 'retained-cache'; cache.mkdir()
        before = snapshot(apphome / 'config/fontconfig')
        row = {'app': app, 'scratch': str(scratch), 'calls': []}; record['rows'].append(row)
        runtime = policy.output(['flatpak', 'info', '--show-runtime', app])
        commit = policy.output(['flatpak', 'info', '--show-commit', 'runtime/' + runtime])
        row['runtime'] = runtime; row['runtime_commit'] = commit
        legacy = policy._render_fragment(booted, [(runtime, commit)], 1)
        policy.install(home, app, legacy)
        def matches(queries=QUERIES):
            # The shell is fixed and every pattern is a quoted positional arg;
            # no request is interpolated as shell code or evaluated.
            shell = 'for request do printf "%s\\t" "$request"; fc-match -f "%{family}|%{file}|%{spacing}\\n" "$request" || exit; done'
            argv = ['flatpak', 'run', '--command=env', app, '-u', 'FONTCONFIG_FILE', '-u', 'FONTCONFIG_PATH',
                    'XDG_CONFIG_HOME=' + str(config), 'XDG_CACHE_HOME=' + str(cache), 'LANG=C.UTF-8', 'LANGUAGE=C',
                    'sh', '-c', shell, 'moos-named-font-proof', *queries]
            p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            row['calls'].append({'argv': argv, 'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
            if p.returncode: raise RuntimeError(p.stderr)
            values = dict(line.split('\t', 1) for line in p.stdout.splitlines())
            assert list(values) == list(queries)
            return values
        old = matches(); row['be3'] = old
        assert policy.refresh([app], home=home) == [app]
        fixed = matches(); warm = matches(); row['successor'] = fixed; row['warm'] = warm
        assert fixed == warm
        changed = []
        for request in QUERIES:
            old_family_file = old[request].split('|')[:2]
            fixed_family_file = fixed[request].split('|')[:2]
            if old_family_file != fixed_family_file: changed.append(request)
            paired = ('Meyar Arabic' if request.startswith('Meyar Sans:charset=06') else
                      'Meyar Mono Arabic' if request.startswith('Meyar Mono:charset=06') else
                      'Meyar Arabic' if request == 'Inter,Meyar Sans:charset=0627' else None)
            if paired:
                assert fixed_family_file[0] == paired, (request, fixed[request])
                assert fixed_family_file[1].startswith('/run/host/fonts/meyar/')
            else:
                assert old_family_file == fixed_family_file, (request, old[request], fixed[request])
            if fixed_family_file[0] in ('Meyar Mono', 'Meyar Mono Arabic'):
                assert fixed[request].split('|')[2] == '100'
        assert 'Meyar Sans:charset=0627' in changed
        row['changed_family_file_queries'] = changed
        path = config / 'fontconfig/conf.d' / policy.FILE
        exact = path.read_bytes()
        personal = config / 'fontconfig/fonts.conf'; personal.write_bytes(PERSONAL)
        row['personal_override'] = matches(['Meyar Sans:charset=0627'])
        assert row['personal_override']['Meyar Sans:charset=0627'].startswith('DejaVu Sans|')
        assert policy.refresh([app], home=home) == []
        assert personal.read_bytes() == PERSONAL and path.read_bytes() == exact
        row['personal_config_preserved'] = True
        row['actual_config_unchanged'] = snapshot(apphome / 'config/fontconfig') == before
        assert row['actual_config_unchanged']
    record['pass'] = True
finally:
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'proof': str(destination), 'pass': record.get('pass', False)}, ensure_ascii=False))
