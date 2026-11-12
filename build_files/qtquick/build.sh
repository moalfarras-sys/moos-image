#!/usr/bin/bash
# Original vendor source/spec and flags; never an in-place workstation repair.
set -euo pipefail
qt_task=/work/qtquick-rpmbuild
qt_source=/src/build_files/qtquick
case "${1:-}" in
prepare)
    mkdir -p "$qt_task/SOURCES" "$qt_task/SPECS" /work/qtquick-proof
    qt_base="$(rpm -q --qf '%{VERSION}-%{RELEASE}' qt6-qtdeclarative)"
    python3 "$qt_source/rpms.py" source "$qt_base" > /work/qtquick-source.json
    qt_url="$(python3 -c 'import json; print(json.load(open("/work/qtquick-source.json"))["source_url"])')"
    curl --fail --location --retry 3 --connect-timeout 30 "$qt_url" -o /work/qtquick.src.rpm
    python3 - <<'PY'
import hashlib,json
from pathlib import Path
data=json.loads(Path('/work/qtquick-source.json').read_text())
if hashlib.sha256(Path('/work/qtquick.src.rpm').read_bytes()).hexdigest()!=data['source_sha256']:
    raise SystemExit('Qt signed source digest mismatch')
PY
    LC_ALL=C rpmkeys --checksig --verbose /work/qtquick.src.rpm > /work/qtquick-source-signature.txt
    grep -F '36f612dcf27f7d1a48a835e4dbfcf71c6d9f90a6: OK' /work/qtquick-source-signature.txt
    rpm2cpio /work/qtquick.src.rpm > /work/qtquick-source.cpio
    (cd "$qt_task/SOURCES" && cpio -idm --quiet --no-absolute-filenames --no-preserve-owner < /work/qtquick-source.cpio)
    echo '215b7b70517e380123eabc6b92243f3c47b6f016a91d126057dbe53551c6b430  /work/qtquick-rpmbuild/SOURCES/qtdeclarative-everywhere-src-6.11.2.tar.xz' | sha256sum --check
    cp "$qt_source/itemview-lifetime.patch" "$qt_task/SOURCES/moos-itemview-lifetime.patch"
    python3 "$qt_source/rpms.py" prepare-spec "$qt_task/SOURCES/qt6-qtdeclarative.spec" "$qt_task/SPECS/qt6-qtdeclarative.spec"
    dnf5 -y --setopt=install_weak_deps=False builddep "$qt_task/SPECS/qt6-qtdeclarative.spec"
    test "$(rpm -q --qf '%{VERSION}-%{RELEASE}' qt6-qtdeclarative)" = "$qt_base"
    test "$(rpm -q --qf '%{VERSION}' qt6-qtbase)" = 6.11.2
    # Compile the real QQuickView owner once; no authentication or compositor.
    # Qt's own build dependencies omit QtQuick headers from the prior runtime.
    # A reused SDK can hide this missing native old-control dependency.
    python3 "$qt_source/rpms.py" sdk "$qt_base"
    g++ -std=c++17 -O2 "$qt_source/native-proof.cpp" -o /work/qtquick-proof/teardown-probe \
        $(pkg-config --cflags --libs Qt6Quick)
    python3 "$qt_source/native-proof.py" --probe /work/qtquick-proof/teardown-probe \
        --qml "$qt_source/teardown.qml" --quick /usr/lib64/libQt6Quick.so.6.11.2 \
        --expect crash --receipt /work/qtquick-proof/vendor-old.json
    ;;
compile)
    rpmbuild -bb --define "_topdir $qt_task" --define '_buildhost moos-build' \
        --define '_smp_mflags -j4' "$qt_task/SPECS/qt6-qtdeclarative.spec"
    python3 "$qt_source/rpms.py" collect "$qt_task/RPMS" /out/qtquick /work/qtquick-proof/teardown-probe
    ;;
*) echo 'usage: build.sh prepare | compile' >&2; exit 2 ;;
esac
