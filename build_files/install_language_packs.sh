#!/usr/bin/env bash
# Build-only transaction guard: RPM's raw Arabic IGNORE directive aborts its
# converter before the normal MoOS dictionary pass can sanitize a private copy.
set -euo pipefail
if [ ! -e /run/.containerenv ] && [ ! -e /.dockerenv ]; then
    echo 'FATAL: language-pack transaction helper is container-only' >&2
    exit 1
fi
convert=/usr/lib64/qt6/libexec/qwebengine_convert_dict
if [ ! -x "$convert" ]; then
    dnf5 -y install langpacks-ar langpacks-en
    exit 0
fi
work=$(mktemp -d /tmp/moos-dictionary-transaction.XXXXXX)
cp -a "$convert" "$work/original"
cleanup() {
    cp -a "$work/original" "$convert"
    cmp "$work/original" "$convert"
    rm -rf -- "$work"
}
trap cleanup EXIT
# This wrapper exists only during the transaction, never in the shipped image.
cat > "$convert" <<WRAPPER
#!/usr/bin/env bash
set -euo pipefail
export QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1
src=\$1
out=\$2
aff=\${src%.dic}.aff
if [ -f "\$aff" ] && grep -q '^IGNORE' "\$aff"; then
    tmp=\$(mktemp -d)
    trap 'rm -rf -- "\$tmp"' EXIT
    name=\$(basename "\$src" .dic)
    grep -v '^IGNORE' "\$aff" > "\$tmp/\$name.aff"
    cp -L "\$src" "\$tmp/\$name.dic"
    "$work/original" "\$tmp/\$name.dic" "\$out"
else
    "$work/original" "\$src" "\$out"
fi
WRAPPER
chmod 0755 "$convert"
sha256sum "$convert" > "$work/wrapper.sha256"
dnf5 -y install langpacks-ar langpacks-en
sha256sum --check "$work/wrapper.sha256"
# cleanup restores exact vendor bytes, mode and mtime even if DNF fails.
