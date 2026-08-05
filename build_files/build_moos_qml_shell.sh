#!/usr/bin/env bash
# =============================================================================
# build_moos_qml_shell.sh — compile MoOS's one self-built C++ binary, in its own
# Containerfile stage so the toolchain never enters the shipped image.
# =============================================================================
# moos-qml-shell is the ONLY binary MoOS compiles itself: the QML host that gives
# every pure-QML app a real Wayland app_id (see the long comment in
# build_files/moos-qml-shell.cpp). It used to be compiled inside build.sh — the
# compiler and Qt/KF headers were installed, used, and removed in the same RUN —
# but that removal never held: qt6-qtdeclarative-devel (installed later for its
# qml-qt6 runner) requires qt6-qtbase-devel, which requires qt6-rpm-macros, which
# requires gcc-c++. So the compiler came back as a dependency and shipped to
# every user. See section (e0) of build.sh for the whole story.
#
# The fix, per this script: compile in a throwaway stage. The Containerfile's
# qml-shell-build stage installs the toolchain, runs this script, and the final
# image receives ONLY the single stripped binary via COPY --from. gcc-c++ then
# never enters the image at all — the (e0) sweep and gate in build.sh become the
# firewall that proves it, not the thing that does the work.
#
# This script runs inside that stage under `set -euo pipefail`, with $1 pointing
# at the source file (bind-mounted via the ctx stage) and $2 being the output
# path. It expects the build-only packages (gcc-c++, qt6-qtbase-devel,
# qt6-qtdeclarative-devel, kf6-kdbusaddons-devel, kf6-kwindowsystem-devel) to
# already be installed — the Containerfile's RUN does that before calling this.
set -euo pipefail

_src="${1:-/ctx/moos-qml-shell.cpp}"
_out="${2:-/out/moos-qml-shell}"

# moos-qml-shell now carries a Q_OBJECT (InstallerBridge — the installer's secure
# recipe channel), so it must be moc'd: the .cpp ends with #include
# "moos-qml-shell.moc", which moc generates next to the source. Locate moc across
# the paths Fedora's qt6-qtbase-devel installs it under.
_moc="$(command -v moc-qt6 2>/dev/null || true)"
[ -z "$_moc" ] && [ -x /usr/lib64/qt6/libexec/moc ] && _moc=/usr/lib64/qt6/libexec/moc
[ -z "$_moc" ] && _moc="$(command -v moc 2>/dev/null || true)"
[ -n "$_moc" ] || { echo "FATAL: Qt6 moc not found — cannot build moos-qml-shell."; exit 1; }
# Write the generated meta-object to writable /tmp (the source lives on a
# read-only bind mount) and let g++ find it via -I/tmp.
"$_moc" "$_src" -o /tmp/moos-qml-shell.moc

# HARDENING. This is the ONE binary MoOS compiles itself, and it was the only ELF in
# the image built without any of it: no PIE (so no ASLR for the executable's own text),
# no stack canary, no FORTIFY, and lazy binding with a writable PLT — while every Fedora
# package around it carries the lot. It parses no untrusted input, which is why this is
# hardening and not an incident, but "the distro hardens everything except the file we
# wrote" is not a defensible line in an OS that lists security as a target.
# -fPIE/-pie replaces the old -fPIC (which alone produces a position-independent OBJECT,
# not a position-independent EXECUTABLE — the distinction is exactly what was missing).
# -fstack-protector-ALL, not Fedora's usual -strong, and the reason is verifiability:
# this source is pure Qt (QString/QGuiApplication, no local char arrays, no
# address-taken locals), so -strong correctly decides there is nothing here worth
# instrumenting and emits no canary at all — measured: the gate below went red on a
# binary compiled WITH -strong, while the same flags on a source holding one
# std::string produced the symbol. A protection that leaves no trace cannot be
# gated, and an ungated flag is one edit away from silently disappearing. -all
# instruments every frame, which costs a launcher that runs once per app launch
# nothing measurable and makes the property something the build can PROVE.
mkdir -p "$(dirname "$_out")"
g++ -std=c++17 -O2 -I/tmp "$_src" -o "$_out" \
    -fstack-protector-all -D_FORTIFY_SOURCE=3 -fPIE -pie \
    -Wl,-z,relro,-z,now -Wall -Wextra \
    -I/usr/include/KF6/KDBusAddons -I/usr/include/KF6/KWindowSystem \
    -lKF6DBusAddons -lKF6WindowSystem \
    $(pkg-config --cflags --libs Qt6Gui Qt6Qml Qt6Core Qt6DBus)

# Prove the hardening on the UNSTRIPPED binary, then strip. Order matters and it cost
# a build to learn: the canary is observable through the `__stack_chk_fail` symbol, and
# `strip` can take the only reference to it with the symbol table — so a gate placed
# after `strip` reports "no canary" on a binary that is fully instrumented. Verify
# first, shrink second. (The other two properties are structural and survive either
# way; they are checked here too so all three read from one unstripped object.)
_elf_h="$(readelf -hW "$_out")"
_elf_d="$(readelf -dW "$_out")"
grep -qE 'Type:[[:space:]]+DYN' <<<"${_elf_h}" \
    || { echo "GATE FAIL: moos-qml-shell is not a PIE — its own text has no ASLR"; exit 1; }
grep -q 'BIND_NOW' <<<"${_elf_d}" \
    || { echo "GATE FAIL: moos-qml-shell has a writable PLT (no -z now / full RELRO)"; exit 1; }
# NOT `readelf -sW … | grep -q …`. This file runs under `set -o pipefail`, and that
# combination is a false-negative machine: `grep -q` exits the instant it matches, the
# producer still has hundreds of symbols to write, it dies of SIGPIPE (141), and
# pipefail hands the PIPELINE that 141 — so a symbol that IS present reports as absent.
# It cost three builds here: the canary gate failed while `readelf -sW … | grep -i stack`
# in the very same shell printed `UND __stack_chk_fail@GLIBC_2.4`. The two gates above
# survive only because a file header and a dynamic section are small enough that readelf
# finishes before grep leaves. Capture first, match second — no pipe, no race.
_shell_syms="$(readelf -sW "$_out")"
case "$_shell_syms" in
    *__stack_chk_fail*) ;;
    *)
        echo "GATE FAIL: moos-qml-shell has no stack canary (-fstack-protector-all lost)"
        echo "--- diagnostics ---"
        echo "file:    $(stat -c '%s bytes, mode %a' "$_out" 2>&1)"
        echo "gcc:     $(g++ --version 2>&1 | head -1)"
        echo "stack syms:"; printf '%s\n' "$_shell_syms" | grep -i stack | head -5 || true
        exit 1
        ;;
esac
unset _shell_syms
echo "=== moos-qml-shell: PIE + full RELRO + stack canary verified before strip ==="

strip "$_out"
chmod 0755 "$_out"
