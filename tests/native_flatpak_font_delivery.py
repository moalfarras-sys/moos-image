#!/usr/bin/env python3
"""Opt-in native Flatpak Fontconfig proof; never changes actual app settings.

Run with an existing app whose sandbox includes its own cache (no new grants):
  python3 tests/native_flatpak_font_delivery.py ai.opencode.opencode
Private evidence is retained in that app's cache for the review/reproducer.
This tests native discovery/cache mechanics, not an application's painted text.
"""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flatpak_fonts', ROOT / 'system_files/usr/lib/moos/moos_flatpak_fonts.py')
policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
app_id = sys.argv[1]
if app_id != 'ai.opencode.opencode':
    raise SystemExit('This old/fixed harness targets the measured OpenCode freedesktop26.08 failure only')
app_home = Path.home() / '.var/app' / app_id
scratch_parent = app_home / 'cache'
if scratch_parent.resolve() != scratch_parent or not scratch_parent.is_dir():
    raise SystemExit('Existing canonical app cache required')
scratch = Path(tempfile.mkdtemp(prefix='moos-host-font-delivery-', dir=scratch_parent))
result = {'schema': 1, 'dateUTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'app': app_id, 'scratch': str(scratch), 'calls': [], 'claims': 'Native Fontconfig discovery/cache only; no GUI, app configuration, permission or running process changed.'}
result['source_files'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (ROOT / 'system_files/usr/lib/moos/moos_flatpak_fonts.py', Path(__file__).resolve())}


def fingerprint(path):
    if not path.exists(): return None
    rows = []
    for child in sorted([path] + list(path.rglob('*'))):
        info = child.lstat()
        row = [str(child.relative_to(path)), info.st_mode, info.st_uid, info.st_size, info.st_mtime_ns]
        if child.is_symlink(): row.append(os.readlink(child))
        elif child.is_file(): row.append(hashlib.sha256(child.read_bytes()).hexdigest())
        rows.append(row)
    return rows


actual_config = app_home / 'config/fontconfig'
before = fingerprint(actual_config)


def call(argv):
    started = time.monotonic()
    p = subprocess.run(argv, text=True, capture_output=True, timeout=45)
    result['calls'].append({'argv': argv, 'exit': p.returncode, 'stdout': p.stdout,
                            'stderr': p.stderr, 'seconds': time.monotonic() - started})
    if p.returncode: raise RuntimeError(p.stderr or str(argv))
    return p.stdout.strip()


def native(config, cache, *command):
    config.mkdir(parents=True, exist_ok=True); cache.mkdir(parents=True, exist_ok=True)
    # env runs after sandbox entry. Flatpak --env alone can be reset by an app's
    # wrapper; no application wrapper or GUI executable is involved here.
    return call(['flatpak', 'run', '--command=env', app_id, '-u', 'FONTCONFIG_FILE', '-u', 'FONTCONFIG_PATH',
                 'XDG_CONFIG_HOME=' + str(config), 'XDG_CACHE_HOME=' + str(cache), *command])


try:
    old_config, old_cache = scratch / 'old/config', scratch / 'old/cache'
    native(old_config, old_cache, 'fc-cache', '-V')
    version_call = result['calls'][-1]
    result['fontconfig_version'] = (version_call['stdout'] + version_call['stderr']).strip()
    assert result['fontconfig_version'] == 'fontconfig version 2.18.3', result['fontconfig_version']
    result['runtime'] = call(['flatpak', 'info', '--show-runtime', app_id])
    assert result['runtime'] == 'org.freedesktop.Platform/x86_64/26.08', result['runtime']
    result['booted_signed_checksum'] = policy.signed_generation(json.loads(policy.output(['/usr/bin/rpm-ostree', 'status', '--json'])))
    families = ['Meyar Sans', 'Meyar Arabic', 'Meyar Mono', 'Meyar Mono Arabic']
    controls = ['DejaVu Sans', 'sans-serif', 'monospace', 'Meyar Sans:charset=0627']
    old = {f: native(old_config, old_cache, 'fc-match', '-f', '%{family}|%{file}', f) for f in families + controls}
    old_cjk = native(old_config, old_cache, 'fc-list', ':charset=4e2d', '-f', '%{file}\n').splitlines()
    private_home = scratch / 'private-home'; private_home.mkdir(mode=0o700)
    timings = []
    for _ in range(3):
        queries = []
        def measured_query(argv):
            query_started = time.monotonic()
            text = policy.output(argv)
            queries.append({'argv': argv, 'seconds': time.monotonic() - query_started, 'output_bytes': len(text.encode())})
            return text
        started = time.monotonic()
        changed = policy.refresh(home=private_home, query=measured_query)
        timings.append({'seconds': time.monotonic() - started, 'changed': changed, 'queries': queries})
    config = private_home / '.var/app' / app_id / 'config'
    cache = scratch / 'fixed/cache'
    fixed = {f: native(config, cache, 'fc-match', '-f', '%{family}|%{file}', f) for f in families + controls}
    warm = {f: native(config, cache, 'fc-match', '-f', '%{family}|%{file}', f) for f in families}
    fixed_cjk = native(config, cache, 'fc-list', ':charset=4e2d', '-f', '%{file}\n').splitlines()
    result.update(old=old, fixed=fixed, warm=warm, old_cjk_faces=len(old_cjk), fixed_cjk_faces=len(fixed_cjk),
                  refresh_timings=timings, actual_fragment=str(config / 'fontconfig/conf.d' / policy.FILE))
    for f in families:
        assert not old[f].startswith(f + '|'), ('original refusal missing', f, old[f])
        assert fixed[f].startswith(f + '|/run/host/fonts/meyar/'), (f, fixed[f])
        assert warm[f] == fixed[f]
    for f in controls: assert old[f] == fixed[f], (f, old[f], fixed[f])
    assert len(fixed_cjk) > len(old_cjk)

    # Native immutable-directory mechanism: one private tree, zero directory
    # mtimes and the same cache home. Keep an old cache plausible while adding
    # another font, reproduce stale discovery, then change only the generation.
    # The target is a private tree here; the preceding exact production fragment
    # already proves the real /run/host/fonts route in this same native library.
    tree = scratch / 'zero-mtime-font-tree'; tree.mkdir()
    fonts = ROOT / 'system_files/usr/share/fonts/meyar'
    shutil.copyfile(fonts / 'MeyarSans[wght].ttf', tree / 'first.ttf')
    os.utime(tree, (0, 0))
    mechanism_config = scratch / 'mechanism/config'
    mechanism_cache = scratch / 'mechanism/cache'
    mechanism_conf = mechanism_config / 'fontconfig/fonts.conf'
    mechanism_conf.parent.mkdir(parents=True)
    runtimes = [('org.freedesktop.Platform/x86_64/26.08', 'c' * 64)]
    def mechanism_generation(letter):
        generated = policy.runtime_fragment(letter * 64, runtimes).decode()
        # Reuse the generated salt and remap semantics on the private stand-in.
        # A fixture-only reject excludes immutable host/runtime faces so the
        # zero-mtime old/new distinction cannot pass through another directory.
        generated = generated.replace('/run/host/fonts', str(tree))
        generated = generated.replace('</fontconfig>', '<selectfont><rejectfont><glob>/run/host/fonts</glob><glob>/usr/share/fonts</glob></rejectfont></selectfont></fontconfig>')
        mechanism_conf.write_text(generated)
    mechanism_generation('a')
    a = native(mechanism_config, mechanism_cache, 'fc-list', '-f', '%{family}|%{file}\n')
    shutil.copyfile(fonts / 'MeyarArabic[wght].ttf', tree / 'second.ttf'); os.utime(tree, (0, 0))
    stale = native(mechanism_config, mechanism_cache, 'fc-list', '-f', '%{family}|%{file}\n')
    mechanism_generation('b')
    b = native(mechanism_config, mechanism_cache, 'fc-list', '-f', '%{family}|%{file}\n')
    # Retire only the exact fixture-owned added file, then emulate A rollback.
    (tree / 'second.ttf').unlink(); os.utime(tree, (0, 0))
    predecessor = native(mechanism_config, mechanism_cache, 'fc-list', '-f', '%{family}|%{file}\n')
    mechanism_generation('a')
    rollback = native(mechanism_config, mechanism_cache, 'fc-list', '-f', '%{family}|%{file}\n')
    result['zero_mtime_generation'] = {'A': a, 'same_salt_after_add': stale, 'B': b,
                                      'predecessor_A_tree_B_salt': predecessor, 'rollback_A': rollback}
    result['generation_cache_files'] = fingerprint(mechanism_cache / 'fontconfig')
    assert 'Meyar Sans|' in a and 'Meyar Arabic|' not in a, a
    assert stale == a, ('static salt old refusal did not reproduce', a, stale)
    assert 'Meyar Arabic|' in b, b
    assert predecessor == b, ('uninstrumented predecessor stale-cache refusal missing', predecessor, b)
    assert rollback == a, (rollback, a)
    result['actual_config_unchanged'] = fingerprint(actual_config) == before
    assert result['actual_config_unchanged']
    result['pass'] = True
finally:
    result['actual_config_before'] = before
    result['actual_config_after'] = fingerprint(actual_config)
    (scratch / 'proof.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'proof': str(scratch / 'proof.json'), 'pass': result.get('pass', False)}, ensure_ascii=False))
