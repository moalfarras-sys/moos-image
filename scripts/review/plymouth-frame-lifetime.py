#!/usr/bin/env python3
"""Reproduce P0.7 in a disposable native SDK container, without booting/flashing.

Requires gcc, libasan, rpm2cpio, cpio, patch and the exact vendor Plymouth libs.
Input: reviewed source RPM; output: native ASan evidence and a proposed patch.
This deliberately does not install or package a repaired boot component.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tarfile

NVR = '24.004.60-24.fc44'
SRPM_SHA = 'e45ef414519b4c9d441b086fbb6b3456df523d61890c9cc3876c069f0eaf57a4'
SOURCE_SHA = '534300245b54b301638bb474deeda7fd1e98c2e295b2155c8af9d6f664d42a9c'
RELATIVE = Path('src/libply-splash-core/ply-boot-splash.c')
REPRO = '''#include SPLASH_SOURCE
static void finish(ply_event_loop_t *loop) { ply_event_loop_exit(loop, 0); }
int main(void) {
    static const ply_boot_splash_plugin_interface_t plugin = {0};
    ply_event_loop_t *loop = ply_event_loop_new();
    ply_boot_splash_t *splash = calloc(1, sizeof(*splash));
    splash->loop = loop;
    splash->plugin_interface = &plugin;
    splash->is_shown = true;
    ply_event_loop_watch_for_timeout(loop, 0.000001,
        (ply_event_loop_timeout_handler_t) on_new_frame, splash);
    ply_event_loop_watch_for_timeout(loop, 0.002,
        (ply_event_loop_timeout_handler_t) finish, loop);
    ply_boot_splash_free(splash);
    int result = ply_event_loop_run(loop);
    ply_event_loop_free(loop);
    return result;
}
'''


def run(args, *, cwd=None, env=None):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=60)


def require(result):
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--srpm', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not Path('/run/.containerenv').exists():
        parser.error('run inside a disposable native Podman SDK container')
    for tool in ('gcc', 'rpm', 'rpm2cpio', 'cpio', 'patch'):
        if shutil.which(tool) is None:
            parser.error('container is missing required tool: ' + tool)
    if digest(args.srpm) != SRPM_SHA:
        parser.error('source RPM differs from the reviewed vendor input')
    nvr = require(run(['rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}',
                       'plymouth-core-libs']))
    if nvr != NVR:
        parser.error('native Plymouth libraries differ from the reviewed source RPM')
    # Even a malformed compiler/runtime failure must not leave host coredumps.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    vendor = output / 'srpm'
    vendor.mkdir()
    cpio = subprocess.run(['rpm2cpio', str(args.srpm.resolve())],
                          capture_output=True, check=True, timeout=60).stdout
    subprocess.run(['cpio', '-idm', '--no-absolute-filenames', '--no-preserve-owner'],
                   input=cpio, cwd=vendor, capture_output=True, check=True, timeout=60)
    with tarfile.open(vendor / 'plymouth-24.004.60.tar.bz2') as archive:
        archive.extractall(output / 'source', filter='data')
    roots = list((output / 'source').iterdir())
    if len(roots) != 1:
        raise RuntimeError('unexpected source archive layout')
    source = roots[0]
    patches = re.findall(r'^Patch:\s*(\S+)', (vendor / 'plymouth.spec').read_text(), re.M)
    if len(patches) != 23:
        raise RuntimeError('unexpected vendor patch set')
    for patch in patches:
        require(run(['patch', '-p1', '--batch', '--forward', '-i', str(vendor / patch)],
                    cwd=source))
    if digest(source / RELATIVE) != SOURCE_SHA:
        raise RuntimeError('patched vendor splash source differs from reviewed bytes')
    fixed = output / 'fixed'
    shutil.copytree(source, fixed)
    original = (source / RELATIVE).read_text()
    modified = original.replace(
        'static void ply_boot_splash_update_progress (ply_boot_splash_t *splash);',
        'static void on_new_frame (ply_boot_splash_t *splash);\n'
        'static void ply_boot_splash_update_progress (ply_boot_splash_t *splash);', 1)
    modified = modified.replace(
        '        if (splash->loop != NULL) {\n'
        '                if (splash->plugin_interface->on_boot_progress != NULL) {',
        '        splash->is_shown = false;\n'
        '        if (splash->loop != NULL) {\n'
        '                ply_event_loop_stop_watching_for_timeout (splash->loop,\n'
        '                                                          (ply_event_loop_timeout_handler_t) on_new_frame,\n'
        '                                                          splash);\n'
        '                if (splash->plugin_interface->on_boot_progress != NULL) {', 1)
    (fixed / RELATIVE).write_text(modified)
    (output / 'proposed-frame-lifetime.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True), modified.splitlines(True),
        fromfile='a/' + str(RELATIVE), tofile='b/' + str(RELATIVE))))
    (output / 'repro.c').write_text(REPRO)
    results = []
    for name, tree, repeats in [('vendor', source, 3), ('fixed', fixed, 20)]:
        executable = output / ('repro-' + name)
        compile_result = run([
            'gcc', '-g', '-O1', '-fsanitize=address', '-fno-omit-frame-pointer',
            '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
            '-DSPLASH_SOURCE="' + str(tree / RELATIVE) + '"',
            '-I' + str(tree / 'src/libply'), '-I' + str(tree / 'src/libply-splash-core'),
            str(output / 'repro.c'), '-o', str(executable), '-Wl,--no-as-needed',
            '-l:libply-splash-core.so.5', '-l:libply.so.5', '-ldl', '-lm'])
        (output / (name + '-compile.log')).write_text(compile_result.stdout + compile_result.stderr)
        require(compile_result)
        env = dict(os.environ, ASAN_OPTIONS=
                   'abort_on_error=0:disable_coredump=1:detect_leaks=0:exitcode=71')
        for index in range(repeats):
            result = run([str(executable)], env=env)
            (output / f'{name}-{index}.log').write_text(result.stdout + result.stderr)
            uaf = 'heap-use-after-free' in result.stderr and 'on_new_frame' in result.stderr
            accepted = result.returncode == (71 if name == 'vendor' else 0)
            accepted = accepted and (uaf if name == 'vendor' else not uaf)
            results.append({'source': name, 'trial': index, 'exit': result.returncode,
                            'frame_use_after_free': uaf, 'expected': accepted})
    evidence = {'source_rpm_sha256': SRPM_SHA, 'native_libraries': nvr,
                'vendor_patches': len(patches), 'trials': results,
                'passed': all(item['expected'] for item in results),
                'scope': 'native frame/free regression only; no package install or boot proof'}
    (output / 'proof.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({key: value for key, value in evidence.items() if key != 'trials'}))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
