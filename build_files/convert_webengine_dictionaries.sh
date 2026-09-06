#!/usr/bin/env bash
# convert_webengine_dictionaries.sh — build Qt WebEngine's spell-check
# dictionaries, for EVERY edition.
#
# WHY THIS IS A SHARED SCRIPT. hunspell dictionaries are not readable by
# QtWebEngine; it needs them converted to its own .bdic format. The
# qt6-qtwebengine RPM runs that converter from a scriptlet and the converter
# SIGTRAPs, and the scriptlet swallows it — so the directory ships empty or
# half-populated and spell-check silently does not exist.
#
# x86 has done this correctly for months. ARM never got the block, and the
# result was measured on the live Oracle A1 on 2026-09-06: 24 en_*.bdic and
# ZERO ar_*.bdic, with six qwebengine_convert_dict coredumps in coredumpctl,
# every one of them an Arabic locale. An Arabic-speaking owner's own machine
# had no Arabic spell-check, on an OS whose skill file calls Arabic first-class,
# while AGENTS.md described this as a build-enforced contract.
#
# The cause of that divergence was a copied block, so this is a script both
# builds call rather than a block each build keeps its own copy of.
#
# Usage: convert_webengine_dictionaries.sh [output_dir]
set -euo pipefail

out="${1:-/usr/share/qt6/qtwebengine_dictionaries}"
convert=/usr/lib64/qt6/libexec/qwebengine_convert_dict

if [ ! -x "$convert" ]; then
    echo "convert_webengine_dictionaries: ${convert} is absent; nothing to do"
    exit 0
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$out"

# The SIGTRAPs below are expected and their cores carry zero signal, but the
# HOST's systemd-coredump still collects ~26 of them from every rootless local
# build — a crash burst that reads like a real incident in `coredumpctl list`
# (it derailed one live audit already, and the ARM ones were how this very bug
# was found). A zero core limit keeps known build-container crashes out of the
# host journal; the gate below still asserts the converted output, which is the
# only truth that matters.
ulimit -c 0 2>/dev/null || true

built=0
for dic in /usr/share/hunspell/*.dic; do
    [ -e "$dic" ] || continue
    name="$(basename "$dic" .dic)"
    aff="/usr/share/hunspell/${name}.aff"
    src="$dic"

    # Chromium's converter aborts on the hunspell IGNORE command ("We don't
    # support the IGNORE command yet", aff_reader.cc) — and EVERY Arabic
    # dictionary uses it, to ignore tashkeel. Read off the live A1:
    #   /usr/share/hunspell/ar_SD.aff:  IGNORE ًٌٍَُِّْـٰ
    # That single unsupported directive is the whole reason a bilingual OS
    # shipped with no Arabic spell-check.
    #
    # Convert from a copy with IGNORE removed. The honest cost: diacritics are
    # no longer ignored, so a FULLY VOCALISED Arabic word can be flagged as
    # misspelled. Ordinary undiacritised Arabic — nearly all of it — checks
    # correctly. A dictionary that is right about the common case beats no
    # dictionary at all.
    if [ -f "$aff" ] && grep -q "^IGNORE" "$aff" 2>/dev/null; then
        grep -v "^IGNORE" "$aff" > "${work}/${name}.aff"
        cp -L "$dic" "${work}/${name}.dic"
        src="${work}/${name}.dic"
    fi

    if QTWEBENGINE_DISABLE_SANDBOX=1 QT_QPA_PLATFORM=offscreen \
        "$convert" "$src" "${out}/${name}.bdic" >/dev/null 2>&1; then
        built=$((built + 1))
    fi
done
echo "OK: built ${built} Qt WebEngine spell-check dictionaries in ${out}."

# Arabic and English are the two languages this OS promises. Shipping the
# directory empty — or, as ARM did, English-only — is the silent regression this
# whole script exists to stop, so assert on BOTH.
ls "${out}"/en_US.bdic >/dev/null 2>&1 \
    || { echo "FATAL: no English spell-check dictionary was produced."; exit 1; }
ls "${out}"/ar_*.bdic >/dev/null 2>&1 \
    || { echo "FATAL: no Arabic spell-check dictionary was produced."; exit 1; }
